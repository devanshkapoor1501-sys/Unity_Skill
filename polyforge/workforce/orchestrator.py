"""Minimal sequential coordinator; no provider SDK or arbitrary code execution."""

import threading
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from polyforge.capabilities.dispatch import execute
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.runner.locks import FileLock
from polyforge.runner.state import atomic_json
from polyforge.workforce.ledger import JobLedger
from polyforge.workforce.models import resume_plan
from polyforge.workforce.permissions import authorize, execution_profile
from polyforge.workforce.router import plan_task
from polyforge.workforce.workers import require_approval, seal_candidate


def execute_leased(
    ledger: JobLedger,
    job: str,
    lease: dict[str, Any],
    identifier: str,
    inputs: dict[str, Any],
    seed: int,
    *,
    job_ticket: dict[str, Any] | None = None,
    resources: dict[str, Any] | None = None,
) -> Result:
    from polyforge.unity.bridge import configuration
    from polyforge.workforce.discovery import (
        admit_resources,
        check_resource_floors,
        resource_usage,
    )

    config = configuration(ledger.policy)
    budget = 600  # Compatibility default for callers predating optional job metadata.
    if job_ticket is not None:
        validate_schema(job_ticket, "job_ticket.schema.json")
        if job_ticket["job_id"] != job or job_ticket["capability_id"] != identifier:
            raise InputError("Job ticket does not identify the requested operation")
        if (
            "context" in job_ticket
            and canonical_digest(job_ticket["context"]) != job_ticket["context_digest"]
        ):
            raise InputError("Job context digest differs from its frozen metadata")
        authorize(ledger.policy, job_ticket["role_id"], "tool", identifier)
        budget = job_ticket["budget_seconds"]
    ticket_resources = (job_ticket or {}).get("context", {}).get("resources")
    if resources is not None and ticket_resources is not None and resources != ticket_resources:
        raise InputError("Job resources differ from its frozen task request")
    requirements = dict(ticket_resources if ticket_resources is not None else resources or {})
    admission = admit_resources(ledger.policy, requirements)
    native_ceiling = (
        config.unity_timeout_seconds if "unity" in identifier else config.blender_timeout_seconds
    )
    budget = min(budget, native_ceiling)
    deadline = time.monotonic() + budget
    cancel = threading.Event()
    finished = threading.Event()
    expired = threading.Event()
    resource_failed = threading.Event()

    def check_running() -> None:
        try:
            check_resource_floors(resource_usage(ledger.policy), requirements)
        except (OSError, ValueError):
            resource_failed.set()
            cancel.set()
            return
        state = load_json(ledger.policy.path(ledger._state(job)))
        if state["state"] != "RUNNING":
            cancel.set()

    def monitor() -> None:
        last = time.monotonic()
        while not finished.wait(0.25):
            try:
                if time.monotonic() >= deadline:
                    expired.set()
                    cancel.set()
                    return
                check_running()
                if cancel.is_set():
                    return
                if time.monotonic() - last > 10:
                    ledger.heartbeat(job, lease)
                    last = time.monotonic()
            except (OSError, ValueError):
                cancel.set()
                return

    watcher = threading.Thread(target=monitor, daemon=True)
    watcher.start()
    try:
        from polyforge.workforce.operations import operation_context

        context = operation_context(ledger.policy.root, ledger.task_id, job, seed, cancel)
        context = replace(
            context,
            timeout_seconds=budget,
            max_output_bytes=config.max_output_bytes,
            retry_limit=config.retry_limit,
        )
        atomic_json(
            ledger.policy,
            ".polyforge/operations/" + str(context.operation_id) + ".intent.json",
            {
                "task_id": ledger.task_id,
                "job_id": job,
                "capability_id": identifier,
                "input_digest": canonical_digest(inputs),
                "seed": seed,
                "context_digest": job_ticket.get("context_digest") if job_ticket else None,
                "budget_seconds": budget,
                "resources": requirements,
                "resource_admission": admission,
            },
        )
        result = execute(identifier, inputs, context)
        try:
            check_running()
        except (OSError, ValueError):
            cancel.set()
        if resource_failed.is_set():
            return failure(
                ErrorKind.POLICY_DENIED,
                "PF-WORKFORCE-RESOURCE",
                "Required RAM/disk/CPU availability was exhausted or became unknown",
            )
        if expired.is_set() or time.monotonic() >= deadline:
            return failure(
                ErrorKind.PRODUCER_FAILURE, "PF-WORKFORCE-DEADLINE", "Job budget expired"
            )
        if cancel.is_set():
            if result.status != "PASS":
                return result
            return failure(ErrorKind.INTERRUPTED, "PF-WORKFORCE-CANCELLED", "Job was cancelled")
        return result
    finally:
        finished.set()
        watcher.join(1)


def run_task(
    workspace: Path, request: dict[str, Any], *, dry_run: bool = False, mode: str = "sequential"
) -> Result:
    plan = plan_task(request, workspace=workspace)
    profile = execution_profile(mode)
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.workforce.discovery import admit_resources

    admission = admit_resources(WorkspacePolicy(workspace), request.get("resources", {}))
    profile["resource_admission"] = admission
    ledger = JobLedger(workspace, plan["task_id"])
    if dry_run or not plan["jobs"]:
        return Result(
            input_digest=plan["input_digest"], data={"plan": plan, **profile, "dry_run": dry_run}
        )
    if mode == "single":
        ledger = JobLedger(workspace, plan["task_id"] + "_single")
    policy = ledger.policy
    relative = ledger.relative
    with FileLock(policy, relative + "/plan.lock", wait_seconds=5):
        frozen = policy.path(relative + "/plan.json")
        if frozen.is_file():
            plan = resume_plan(load_json(frozen), plan)
        else:
            atomic_json(policy, frozen, plan)
    asset = request["input"].get(
        "asset_id", request["input"].get("spec", {}).get("asset_id", "game_project")
    )
    if request["capability_id"] == "asset.package.build.v1":
        # The inner specialist transaction owns the canonical asset lease; the outer workflow
        # owns its admission ticket, avoiding a self-conflict while preserving both fences.
        asset = "wf_" + canonical_digest(asset)[:40]
    candidate: dict[str, Any] = {}
    review: dict[str, Any] = {}
    lineage = []
    for job in plan["jobs"]:
        if "context" in job and job["context"]["task_digest"] != plan["input_digest"]:
            raise InputError("Job metadata belongs to a different frozen task")
        job_id = job["job_id"]
        prior = ledger.completed(job_id)
        lease = ledger.claim(job_id, asset)
        if prior is not None:
            value = prior
            if job_id in {"job_1", "job_3"}:
                from polyforge.workforce.operations import operation_context, recover

                identifier = (
                    request["capability_id"] if job_id == "job_1" else "animation.robot.unity.v1"
                )
                inputs = (
                    request["input"]
                    if job_id == "job_1"
                    else {
                        "schema_version": "1.0.0",
                        "candidate_file": relative + "/handoff.json",
                        "review_file": relative + "/review.json",
                        "production_file": relative + "/production.json",
                    }
                )
                if (
                    recover(
                        identifier,
                        inputs,
                        operation_context(
                            workspace, ledger.task_id, job_id, request.get("seed", 42), None
                        ),
                    )
                    is None
                ):
                    raise InputError("Committed job lacks a current native operation receipt")
        else:
            started = time.monotonic()
            if lease is None:
                raise InputError("Job committed concurrently; resume to read its durable result")
            if job_id == "job_0":
                value = {
                    "original_request": request,
                    "brief_digest": canonical_digest(request["brief"]),
                }
            elif job_id == "job_1":
                authorize(policy, job["role_id"], "tool", request["capability_id"])
                checkpoint = policy.path(relative + "/production.json")
                if checkpoint.is_file():
                    value = load_json(checkpoint)
                    from polyforge.workforce.workers import check_candidate

                    check_candidate(policy, value["candidate"])
                else:
                    result = execute_leased(
                        ledger,
                        job_id,
                        lease,
                        request["capability_id"],
                        request["input"],
                        request.get("seed", 42),
                        job_ticket=job,
                        resources=request.get("resources", {}),
                    )
                    if result.status != "PASS":
                        ledger.cancel(job_id)
                        return result
                    value = {
                        "result": result.to_dict(),
                        "candidate": seal_candidate(
                            policy, result, canonical_digest(request["brief"])
                        ),
                    }
                    atomic_json(policy, checkpoint, value)
            elif job_id == "job_2":
                authorize(policy, job["role_id"], "tool", "artifact.candidate.inspect.v1")
                atomic_json(policy, relative + "/handoff.json", candidate)
                inspected = execute_leased(
                    ledger,
                    job_id,
                    lease,
                    "artifact.candidate.inspect.v1",
                    {
                        "schema_version": "1.0.0",
                        "candidate_file": relative + "/handoff.json",
                        "task_file": relative + "/plan.json",
                    },
                    request.get("seed", 42),
                    job_ticket=job,
                    resources=request.get("resources", {}),
                )
                if inspected.status != "PASS":
                    ledger.cancel(job_id)
                    return inspected
                value = inspected.data
                atomic_json(policy, relative + "/review.json", value["review"])
                atomic_json(policy, relative + "/board.json", value["board"])
            else:
                require_approval(policy, candidate, review)
                authorize(policy, job["role_id"], "tool", "animation.robot.unity.v1")
                integrated = execute_leased(
                    ledger,
                    job_id,
                    lease,
                    "animation.robot.unity.v1",
                    {
                        "schema_version": "1.0.0",
                        "candidate_file": relative + "/handoff.json",
                        "review_file": relative + "/review.json",
                        "production_file": relative + "/production.json",
                    },
                    request.get("seed", 42),
                    job_ticket=job,
                    resources=request.get("resources", {}),
                )
                value = {"result": integrated.to_dict()}
                if value["result"]["status"] != "PASS":
                    ledger.cancel(job_id)
                    return Result(
                        **{k: v for k, v in value["result"].items() if k != "operation_status"}
                    )
            if time.monotonic() - started >= job["budget_seconds"]:
                ledger.cancel(job_id)
                return failure(
                    ErrorKind.PRODUCER_FAILURE, "PF-WORKFORCE-DEADLINE", "Job budget expired"
                )
            ledger.commit(job_id, lease, value)
        if job_id == "job_1":
            candidate = value["candidate"]
        elif job_id == "job_2":
            review = value["review"]
        lineage.append(
            {
                "job_id": job_id,
                "role_id": job["role_id"],
                "stage": job["stage"],
                "state": "VERIFIED"
                if job_id == "job_3"
                else value.get("board", {}).get("promotion", "APPROVED")
                if job_id == "job_2"
                else "PRODUCED",
                "result_digest": canonical_digest(value),
                **profile,
            }
        )
        atomic_json(policy, relative + "/lineage.json", lineage)
    atomic_json(policy, relative + "/handoff.json", candidate)
    atomic_json(policy, relative + "/review.json", review)
    require_approval(policy, candidate, review)
    return Result(
        run_id=ledger.task_id,
        input_digest=plan["input_digest"],
        evaluated_test_status="PASS",
        data={
            "plan": plan,
            "candidate": candidate,
            "review": review,
            "lineage": lineage,
            **profile,
        },
        evidence_paths=[
            relative + "/lineage.json",
            relative + "/handoff.json",
            relative + "/review.json",
        ],
    )
