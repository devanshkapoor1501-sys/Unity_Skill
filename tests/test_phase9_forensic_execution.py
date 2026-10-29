"""Forensic entry points consume durable budgets and resume recovery, never replay."""

import pytest
from test_phase9_diagnostics import evidence

from polyforge.contracts.results import ErrorKind, failure
from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


def test_unregistered_cross_tool_routes_are_explicitly_blocked(tmp_path):
    from polyforge.repairs.diagnostics import diagnose_evidence, plan_repair, reserve_attempt

    p = WorkspacePolicy(tmp_path)
    p.mkdir("runs/source")
    p.path("runs/source/observation.json").write_bytes(b"observed")
    for code in (
        "PF-GEOMETRY-DEGENERATE",
        "PF-SPRITE-CURVE",
        "PF-ANIMATION-SLOT",
        "PF-WORKER-TIMEOUT",
    ):
        issue = diagnose_evidence(evidence(code))
        plan = plan_repair(p, issue)
        assert plan["status"] == "BLOCKED"
        assert plan["original_specialist"]
        with pytest.raises(InputError):
            reserve_attempt(p, issue, plan)
    assert not p.path(".polyforge").exists()


def test_apply_failure_reserves_once_and_resume_never_replays_worker(tmp_path, monkeypatch):
    from polyforge.repairs import diagnostics, execution
    from polyforge.unity import recovery, repairs

    p = WorkspacePolicy(tmp_path)
    p.mkdir("runs/source")
    p.path("runs/source/observation.json").write_bytes(b"observed")
    native = {
        "schema_version": "1.0.0",
        "input_digest": "a" * 64,
        "issue_id": "ISSUE-native",
        "category": "component",
        "asset_id": "robot_a",
        "operation": "rebuild_native_binding",
    }
    monkeypatch.setattr(diagnostics, "_native_plan", lambda *_: native)
    issue = diagnostics.diagnose_evidence(evidence("PF-COMPONENT-MISSING"))
    plan = diagnostics.plan_repair(p, issue)
    atomic_json(p, "proposal.json", plan)
    calls = []

    def fail(workspace, path, *, forensic_run=None):
        calls.append(path)
        return failure(ErrorKind.CONTRACT_FAILURE, "PF-INJECTED", "Observed failure")

    monkeypatch.setattr(repairs, "repair_apply", fail)
    result = execution.apply_forensic(tmp_path, plan)
    assert result.status == "FAIL" and len(calls) == 1
    history = load_json(p.path(".polyforge/forensic-attempts.json"))
    assert history[issue["symptom_signature"]][0]["status"] == "FAIL"
    resumed = recovery.resume_run(tmp_path, result.run_id)
    assert resumed == result and len(calls) == 1
    with pytest.raises(InputError, match="Escalate"):
        execution.apply_forensic(tmp_path, plan)


def test_crashed_forensic_reservation_without_transaction_is_blocked_not_replayed(
    tmp_path, monkeypatch
):
    from polyforge.repairs import diagnostics
    from polyforge.unity import recovery

    p = WorkspacePolicy(tmp_path)
    p.mkdir("runs/source")
    p.path("runs/source/observation.json").write_bytes(b"observed")
    monkeypatch.setattr(
        diagnostics, "_native_plan", lambda *_: {"operation": "rebuild_native_binding"}
    )
    issue = diagnostics.diagnose_evidence(evidence())
    plan = diagnostics.plan_repair(p, issue)
    attempt = diagnostics.reserve_attempt(p, issue, plan)
    run = "forensic-" + attempt["token"]
    atomic_json(
        p,
        "runs/" + run + "/intent.json",
        {"proposal": plan, "attempt": attempt, "transaction_id": None},
    )
    result = recovery.resume_run(tmp_path, run)
    assert result.status == "BLOCKED"
    assert (
        load_json(p.path(".polyforge/forensic-attempts.json"))[issue["symptom_signature"]][0][
            "status"
        ]
        == "BLOCKED"
    )
