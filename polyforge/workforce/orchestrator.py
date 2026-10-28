"""Minimal sequential coordinator; no provider SDK or arbitrary code execution."""

import threading
import time
from pathlib import Path
from typing import Any

from polyforge.capabilities.dispatch import execute
from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import Result
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.state import atomic_json
from polyforge.workforce.ledger import JobLedger
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
) -> Result:
    cancel = threading.Event()
    finished = threading.Event()

    def monitor() -> None:
        last = time.monotonic()
        while not finished.wait(0.05):
            try:
                state = load_json(ledger.policy.path(ledger._state(job)))
                if state["state"] != "RUNNING":
                    cancel.set()
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
        atomic_json(
            ledger.policy,
            ".polyforge/operations/" + str(context.operation_id) + ".intent.json",
            {
                "task_id": ledger.task_id,
                "job_id": job,
                "capability_id": identifier,
                "input_digest": canonical_digest(inputs),
                "seed": seed,
            },
        )
        return execute(identifier, inputs, context)
    finally:
        finished.set()
        watcher.join(1)


def run_task(
    workspace: Path, request: dict[str, Any], *, dry_run: bool = False, mode: str = "sequential"
) -> Result:
    plan = plan_task(request, workspace=workspace)
    profile = execution_profile(mode)
    ledger = JobLedger(workspace, plan["task_id"])
    if dry_run or not plan["jobs"]:
        return Result(
            input_digest=plan["input_digest"], data={"plan": plan, **profile, "dry_run": dry_run}
        )
    if mode == "single":
        ledger = JobLedger(workspace, plan["task_id"] + "_single")
    policy = ledger.policy
    relative = ledger.relative
    atomic_json(policy, relative + "/plan.json", plan)
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
                inspected = execute(
                    "artifact.candidate.inspect.v1",
                    {
                        "schema_version": "1.0.0",
                        "candidate_file": relative + "/handoff.json",
                        "task_file": relative + "/plan.json",
                    },
                    RunContext(workspace),
                )
                value = inspected.data
                atomic_json(policy, relative + "/review.json", value["review"])
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
                )
                value = {"result": integrated.to_dict()}
                if value["result"]["status"] != "PASS":
                    ledger.cancel(job_id)
                    return Result(
                        **{k: v for k, v in value["result"].items() if k != "operation_status"}
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
                else "APPROVED"
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
