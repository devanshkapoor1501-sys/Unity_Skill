"""Evidence-based native-binding repair; no arbitrary patches or source execution."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.contracts.manifest import load_manifest
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.locks import FileLock
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bootstrap import check_project_idle
from polyforge.unity.bridge import configuration, launch, unity_tool
from polyforge.unity.evidence import reconcile_report
from polyforge.unity.transactions import ManagedTransaction

CATEGORIES = {"scale", "axis", "pivot", "material", "socket", "component", "binding", "collider"}


def verify_source_hashes(policy: WorkspacePolicy, request: dict[str, Any]) -> None:
    for asset in request["assets"]:
        path = policy.path("UnityProject/" + asset["fbx_path"])
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        if actual != asset["sha256"]:
            raise InputError(
                f"Source identity mismatch for {asset['id']}: expected "
                f"{asset['sha256']}, observed {actual}; rebuild S3/S4",
                kind=ErrorKind.CONTRACT_FAILURE,
                code="PF-UNITY-SOURCE-IDENTITY",
            )


def symptom(issue: dict[str, Any]) -> str:
    return canonical_digest(
        {key: issue[key] for key in ("category", "asset_id", "expected", "actual")}
    )


def resolve_plan(policy: WorkspacePolicy, plan: dict[str, Any], request: dict[str, Any]) -> str:
    validate_plan(plan, request)
    evidence = load_json(policy.path(".polyforge/unity-issues.json"))
    match = next((i for i in evidence["issues"] if i["issue_id"] == plan["issue_id"]), None)
    if (
        evidence["input_digest"] != request["input_digest"]
        or match is None
        or match["category"] != plan["category"]
        or match["asset_id"] != plan["asset_id"]
    ):
        raise InputError("Repair plan does not match recorded diagnostic evidence")
    return canonical_digest({"input_digest": request["input_digest"], "symptom": symptom(match)})


def scoped_verification(baseline: dict[str, Any], after: dict[str, Any], asset_id: str) -> bool:
    allowed = Counter(symptom(i) for i in baseline["issues"] if i["asset_id"] != asset_id)
    actual = Counter(symptom(i) for i in after["issues"])
    return not any(i["asset_id"] == asset_id for i in after["issues"]) and actual <= allowed


def equivalent_bindings(before: Any, after: Any) -> bool:
    """Static restore equivalence: 0.1mm / 1ppm for numbers, exact identities."""
    if type(before) in {int, float} and type(after) in {int, float}:
        return math.isclose(before, after, abs_tol=0.0001, rel_tol=1e-6)
    if isinstance(before, dict):
        return (
            isinstance(after, dict)
            and before.keys() == after.keys()
            and all(equivalent_bindings(v, after[k]) for k, v in before.items())
        )
    if isinstance(before, list):
        return (
            isinstance(after, list)
            and len(before) == len(after)
            and all(equivalent_bindings(a, b) for a, b in zip(before, after, strict=True))
        )
    return bool(before == after)


def current_request(policy: WorkspacePolicy) -> dict[str, Any]:
    check_project_idle(policy)
    if not policy.path("UnityProject/.polyforge-project.json").is_file():
        raise InputError("A managed S4 project is required")
    request: dict[str, Any] = load_json(policy.path(".polyforge/unity-request.json"))
    if request["input_digest"] != load_manifest(policy.path("game_manifest.json")).input_digest:
        raise InputError("Manifest/source identity changed; rebuild S4 before reconciliation")
    verify_source_hashes(policy, request)
    return request


def reconcile_workspace(workspace: Path) -> Result:
    policy = WorkspacePolicy(workspace)
    request = current_request(policy)
    config = configuration(policy)
    executable = unity_tool(config)
    run_id = "reconcile-" + uuid4().hex[:16]
    relative = "runs/" + run_id
    with FileLock(policy, ".polyforge/locks/unity-project.lock"):
        request_path = atomic_json(policy, relative + "/request.json", request)
        path = policy.path(relative + "/bindings.json")
        launch(
            policy,
            executable,
            config,
            relative + "/observe",
            "reconcile",
            request=request_path,
            output=path,
            allow_contract_failure=True,
        )
        report = reconcile_report(request, load_json(path))
        for issue in report["issues"]:
            issue["issue_id"] = "ISSUE-" + canonical_digest(issue)[:12]
        atomic_json(policy, relative + "/reconcile.json", report)
        atomic_json(
            policy,
            ".polyforge/unity-issues.json",
            {
                "input_digest": request["input_digest"],
                "evidence_dir": relative,
                "issues": report["issues"],
            },
        )
    return Result(
        status=report["status"],
        exit_code=0 if report["status"] == "PASS" else 6,
        error_code=None if report["status"] == "PASS" else "PF-UNITY-RECONCILE",
        run_id=run_id,
        input_digest=request["input_digest"],
        data=report,
        evidence_paths=[relative + "/bindings.json", relative + "/reconcile.json"],
    )


def diagnose(workspace: Path, evidence_dir: str) -> Result:
    policy = WorkspacePolicy(workspace)
    request = current_request(policy)
    directory = policy.path(evidence_dir)
    if directory.parent != policy.path("runs"):
        raise InputError("Diagnosis requires one managed run evidence directory")
    raw = load_json(policy.path(directory / "bindings.json"))
    report = reconcile_report(request, raw)
    issues = [
        {
            **issue,
            "issue_id": "ISSUE-" + canonical_digest(issue)[:12],
            "repair_supported": issue["category"] in CATEGORIES,
        }
        for issue in report["issues"]
    ]
    return Result(
        input_digest=request["input_digest"],
        data={
            "diagnosis_status": report["status"],
            "issues": issues,
            "evidence_dir": directory.relative_to(policy.root).as_posix(),
        },
    )


def validate_plan(plan: dict[str, Any], request: dict[str, Any]) -> None:
    fields = {"schema_version", "input_digest", "issue_id", "category", "asset_id", "operation"}
    if (
        not isinstance(plan, dict)
        or set(plan) != fields
        or any(not isinstance(v, str) for v in plan.values())
        or plan["schema_version"] != "1.0.0"
        or plan["input_digest"] != request["input_digest"]
        or plan["category"] not in CATEGORIES
        or plan["asset_id"] not in {a["id"] for a in request["assets"]}
        or plan["operation"] != "rebuild_native_binding"
        or not isinstance(plan["issue_id"], str)
        or not re.fullmatch(r"ISSUE-[a-zA-Z0-9]+", plan["issue_id"])
    ):
        raise InputError("Repair plan is stale, unbounded or outside native-binding scope")


def repair_plan(workspace: Path, issue_id: str) -> Result:
    policy = WorkspacePolicy(workspace)
    request = current_request(policy)
    evidence = load_json(policy.path(".polyforge/unity-issues.json"))
    if evidence["input_digest"] != request["input_digest"]:
        raise InputError("Diagnosis belongs to a different manifest")
    issue = next((i for i in evidence["issues"] if i["issue_id"] == issue_id), None)
    if issue is None:
        raise InputError("Unknown issue ID; reconcile the managed project first")
    plan = {
        "schema_version": "1.0.0",
        "input_digest": request["input_digest"],
        "issue_id": issue_id,
        "category": issue["category"],
        "asset_id": issue["asset_id"],
        "operation": "rebuild_native_binding",
    }
    validate_plan(plan, request)
    identifier = issue["asset_id"]
    return Result(
        input_digest=request["input_digest"],
        data={
            "dry_run": True,
            "plan": plan,
            "patch_preview": {
                "operation": "Restore native bindings from frozen source; rebuild dependent scenes",
                "asset_id": identifier,
                "geometry_generation": "NOT_RUN",
                "managed_prefix": "UnityProject/Assets/PolyForgeGenerated",
            },
            "verification": "native reconciliation; automatic rollback on failed verification",
            "cross_application_recovery": "NOT_RUN; Phase 9",
        },
    )


def repair_apply(workspace: Path, plan_path: str) -> Result:
    policy = WorkspacePolicy(workspace)
    request = current_request(policy)
    plan = load_json(policy.path(plan_path))
    key = resolve_plan(policy, plan, request)
    config = configuration(policy)
    executable = unity_tool(config)
    tx_id = "tx-" + uuid4().hex[:16]
    relative = f"transactions/{tx_id}"
    with FileLock(policy, ".polyforge/locks/unity-project.lock"):
        attempts_path = policy.path(".polyforge/repair-attempts.json")
        attempts = load_json(attempts_path) if attempts_path.is_file() else {}
        if attempts.get(key, 0) >= 2:
            return failure(
                ErrorKind.RETRY_EXHAUSTED,
                "PF-REPAIR-ATTEMPTS",
                "Two proposals already attempted for this symptom",
            )
        before = policy.path(".polyforge/unity-request.json")
        baseline_path = policy.path(f"runs/repair-baseline-{tx_id}/bindings.json")
        launch(
            policy,
            executable,
            config,
            f"runs/repair-baseline-{tx_id}",
            "reconcile",
            request=before,
            output=baseline_path,
            allow_contract_failure=True,
        )
        baseline_raw = load_json(baseline_path)
        baseline = reconcile_report(request, baseline_raw)
        if not any(
            i["asset_id"] == plan["asset_id"] and i["category"] == plan["category"]
            for i in baseline["issues"]
        ):
            raise InputError("Issue is no longer present; reconcile and replan")
        tx = ManagedTransaction.create(policy, tx_id)
        tx.record("BASELINE", observed=baseline_raw, reconciliation=baseline)
        attempts[key] = attempts.get(key, 0) + 1
        atomic_json(policy, attempts_path, attempts)
        affected = copy.deepcopy(request)
        affected["rebuild_asset_ids"] = [plan["asset_id"]]
        apply_request = atomic_json(policy, relative + "/request.json", affected)
        tx.record("APPLY", plan=plan)
        try:
            output = policy.path(relative + "/after.json")
            launch(
                policy,
                executable,
                config,
                relative + "/apply",
                "build",
                request=apply_request,
                output=output,
                allow_contract_failure=True,
            )
            report = reconcile_report(request, load_json(output))
            if not scoped_verification(baseline, report, plan["asset_id"]):
                raise InputError(json.dumps(report["issues"]), kind=ErrorKind.CONTRACT_FAILURE)
            tx.record("COMMITTED", verification=report)
            return Result(
                rollback_id=tx_id,
                data={
                    "repair_status": "COMMITTED",
                    "plan": plan,
                    "remaining_issues": report["issues"],
                },
                evidence_paths=[relative + "/journal.json", relative + "/after.json"],
            )
        except (InputError, OSError, KeyboardInterrupt) as exc:
            try:
                tx.restore()
                if not tx.verify_restored():
                    raise InputError("Restored bytes do not match snapshot")
                restored = policy.path(relative + "/restored.json")
                launch(
                    policy,
                    executable,
                    config,
                    relative + "/restore",
                    "restore",
                    request=before,
                    output=restored,
                    allow_contract_failure=True,
                )
                restored_raw = load_json(restored)
                check = reconcile_report(request, restored_raw)
                if not equivalent_bindings(baseline_raw, restored_raw):
                    raise InputError("Restored native bindings differ from the observed baseline")
                tx.record("ROLLED_BACK", verification=check)
                return replace(
                    failure(
                        ErrorKind.INTERRUPTED
                        if isinstance(exc, KeyboardInterrupt)
                        else ErrorKind.CONTRACT_FAILURE,
                        "PF-REPAIR-ROLLED-BACK",
                        str(exc),
                    ),
                    rollback_id=tx_id,
                    evidence_paths=[relative + "/journal.json"],
                )
            except (InputError, OSError):
                tx.record("ROLLBACK_FAILED", failure=str(exc))
                return replace(
                    failure(
                        ErrorKind.CONTRACT_FAILURE,
                        "PF-ROLLBACK-FAILED",
                        "Native restore could not be verified; project requires manual recovery",
                    ),
                    rollback_id=tx_id,
                    evidence_paths=[relative + "/journal.json"],
                )
