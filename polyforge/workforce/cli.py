"""Workforce commands share canonical task validation and bounded dispatch."""

import argparse
from pathlib import Path

from polyforge.contracts.results import Result
from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy, workspace_input
from polyforge.workforce.discovery import discover
from polyforge.workforce.ledger import JobLedger
from polyforge.workforce.orchestrator import run_task
from polyforge.workforce.permissions import ROLES, execution_profile
from polyforge.workforce.router import plan_task
from polyforge.workforce.workers import inspect_candidate


def dispatch(args: argparse.Namespace) -> Result:
    policy = WorkspacePolicy(Path(args.workspace))
    operation = args.spec.path[-1]
    if operation == "roles":
        return Result(
            data={"roles": ROLES, **execution_profile("sequential"), "discovery": discover(policy)}
        )
    if operation == "plan":
        request = load_json(policy.path("task.json"))
        brief = workspace_input(policy.root, Path(args.brief)).read_text("utf-8")
        if brief != request["brief"]:
            raise InputError("task.json brief must exactly match the original brief file")
        plan = plan_task(request, workspace=policy.root)
        if not args.dry_run:
            atomic_json(policy, "workforce/" + plan["task_id"] + "/plan.json", plan)
        return Result(
            input_digest=plan["input_digest"],
            data={"plan": plan, "discovery": discover(policy), "dry_run": args.dry_run},
        )
    if operation == "run":
        plan = load_json(workspace_input(policy.root, Path(args.plan)))
        if plan_task(plan["original_request"], workspace=policy.root) != plan:
            raise InputError("Plan changed or belongs to another engine contract")
        return run_task(policy.root, plan["original_request"], dry_run=args.dry_run, mode=args.mode)
    if operation in {"status", "cancel"}:
        ledger = JobLedger(policy.root, args.run_id)
        if operation == "cancel":
            ledger.cancel(args.job_id)
            return Result(data={"job_id": args.job_id, "state": "CANCELLED"})
        directory = policy.path(ledger.relative + "/jobs")
        if not directory.is_dir():
            raise InputError("Unknown workforce run")
        return Result(
            data={"jobs": {p.stem: load_json(p) for p in sorted(directory.glob("*.json"))}}
        )
    matches = [
        p
        for p in policy.path("workforce").glob("*/handoff.json")
        if load_json(p)["artifact_id"] == args.artifact_id
    ]
    if len(matches) != 1:
        raise InputError("Expected exactly one immutable candidate handoff")
    plan = load_json(policy.path(matches[0].parent / "plan.json"))
    return Result(
        data={"review": inspect_candidate(policy, load_json(matches[0]), plan["original_request"])}
    )
