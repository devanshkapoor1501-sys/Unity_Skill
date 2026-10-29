"""Forensic execution uses existing native transactions and durable attempt ownership."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any

from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, load_json
from polyforge.repairs.diagnostics import finish_attempt, plan_repair, reserve_attempt
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


def _finish(policy: WorkspacePolicy, run: str, intent: dict[str, Any], result: Result) -> Result:
    result = replace(result, run_id=run)
    path = "runs/" + run + "/result.json"
    atomic_json(policy, path, result.to_dict())
    finish_attempt(
        policy,
        intent["attempt"],
        status="PASS"
        if result.status == "PASS"
        else "BLOCKED"
        if result.status == "BLOCKED"
        else "FAIL",
        evidence_paths=[path, *result.evidence_paths],
    )
    return result


def apply_forensic(workspace: Path, proposal: dict[str, Any]) -> Result:
    policy = WorkspacePolicy(workspace)
    issue = proposal.get("diagnosis")
    if not isinstance(issue, dict) or proposal != plan_repair(policy, issue):
        raise InputError("Forensic proposal was changed or is stale")
    attempt = reserve_attempt(policy, issue, proposal)
    run = "forensic-" + attempt["token"]
    intent = {"proposal": proposal, "attempt": attempt, "transaction_id": None}
    atomic_json(policy, "runs/" + run + "/intent.json", intent)
    path = "runs/" + run + "/native-plan.json"
    atomic_json(policy, path, proposal["native_plan"])
    from polyforge.unity.repairs import repair_apply

    try:
        result = repair_apply(workspace, path, forensic_run=run)
    except (InputError, OSError) as exc:
        # A transaction, if begun, is resumed through recovery rather than replayed.
        live = load_json(policy.path("runs/" + run + "/intent.json"))
        if live["transaction_id"] is not None:
            raise
        result = failure(ErrorKind.CONTRACT_FAILURE, "PF-FORENSIC-APPLY", str(exc))
    return _finish(policy, run, intent, result)


def resume_forensic(policy: WorkspacePolicy, run: str) -> Result:
    intent = load_json(policy.path("runs/" + run + "/intent.json"))
    if (
        set(intent) != {"proposal", "attempt", "transaction_id"}
        or run != "forensic-" + intent["attempt"]["token"]
    ):
        raise InputError("Forensic resume identity differs from durable ownership")
    saved = policy.path("runs/" + run + "/result.json")
    if saved.is_file():
        value = load_json(saved)
        result = Result(**{k: v for k, v in value.items() if k != "operation_status"})
        # Close a crash boundary between durable result and attempt completion.
        history = load_json(policy.path(".polyforge/forensic-attempts.json"))
        attempt = next(
            (
                a
                for a in history.get(intent["attempt"]["symptom_signature"], [])
                if a["token"] == intent["attempt"]["token"]
            ),
            None,
        )
        if attempt == intent["attempt"]:
            return _finish(policy, run, intent, result)
        if result.run_id != run or attempt is None or attempt["status"] == "RESERVED":
            raise InputError("Forensic result lacks its completed attempt receipt")
        hashes = attempt.get("evidence_hashes", {})
        if set(hashes) != set(attempt["evidence_paths"]) or any(
            hashlib.sha256(policy.path(name).read_bytes()).hexdigest() != digest
            for name, digest in hashes.items()
        ):
            raise InputError("Completed forensic evidence changed after recording")
        if result.rollback_id is not None:
            from polyforge.unity.transactions import ManagedTransaction, inventory

            tx = ManagedTransaction(policy, result.rollback_id)
            journal = tx.read()
            if journal.get("forensic_run") != run:
                raise InputError("Completed forensic transaction ownership changed")
            if (
                journal["status"] == "COMMITTED"
                and inventory(policy, journal.get("dependencies", []))
                != journal["committed_inventory"]
            ):
                raise InputError("Committed forensic project changed afterward")
            if journal["status"] == "ROLLED_BACK" and not tx.verify_restored():
                raise InputError("Recovered forensic project changed afterward")
        return result
    tx_id = intent["transaction_id"]
    if tx_id is None:
        return _finish(
            policy,
            run,
            intent,
            failure(
                ErrorKind.POLICY_DENIED,
                "PF-FORENSIC-NO-TRANSACTION",
                "Interrupted before mutation; reserved proposal is not automatically replayed",
            ),
        )
    from polyforge.unity.recovery import resume_run
    from polyforge.unity.transactions import ManagedTransaction

    tx = ManagedTransaction(policy, tx_id)
    journal = tx.read()
    if journal.get("forensic_run") != run:
        raise InputError("Forensic transaction ownership mismatch")
    if journal["status"] == "COMMITTED":
        result = Result(
            rollback_id=tx_id,
            data={"repair_status": "COMMITTED"},
            evidence_paths=[tx.relative + "/journal.json"],
        )
    else:
        recovered = resume_run(policy.root, tx_id)
        result = (
            recovered
            if recovered.status != "PASS"
            else replace(
                failure(
                    ErrorKind.CONTRACT_FAILURE,
                    "PF-FORENSIC-RECOVERED",
                    "Interrupted repair restored its baseline; no repair replayed",
                ),
                rollback_id=tx_id,
                evidence_paths=recovered.evidence_paths,
            )
        )
    return _finish(policy, run, intent, result)
