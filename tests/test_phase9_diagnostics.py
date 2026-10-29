"""Cross-tool diagnosis must be falsifiable, bounded and evidence-backed."""

import copy
import hashlib

import pytest

from polyforge.contracts.validation import InputError
from polyforge.security.paths import WorkspacePolicy

FAULTS = [
    ("PF-GUID-MISMATCH", "GUID", "rebuild_native_binding"),
    ("PF-FBX-AXES", "FBX_AXES", "rebuild_export"),
    ("PF-GEOMETRY-DEGENERATE", "GEOMETRY", "regenerate_geometry"),
    ("PF-UNITY-API", "UNITY_API", None),
    ("PF-COMPONENT-MISSING", "MISSING_COMPONENT", "rebuild_native_binding"),
    ("PF-SPRITE-CURVE", "SPRITE_CURVE", "rebuild_sprite"),
    ("PF-ANIMATION-SLOT", "ANIMATION_SLOT", "rebuild_motion"),
    ("PF-WORKER-TIMEOUT", "WORKER_TIMEOUT", "retry_registered_worker"),
    ("PF-MATERIAL-SWAPPED", "GUID", "rebuild_native_binding"),
    ("PF-CLIP-MISLEADING", "ANIMATION_SLOT", "rebuild_motion"),
    ("PF-MECHANIC-MISSING", "MISSING_COMPONENT", "rebuild_native_binding"),
    ("PF-TEST-FAKE-PASS", None, None),
]


def evidence(code="PF-GUID-MISMATCH"):
    return {
        "schema_version": "1.0.0",
        "input_digest": "a" * 64,
        "producer_id": "unity_integration",
        "tool": {"name": "unity", "version": "6000.6.3f1"},
        "structured": {"status": "FAIL", "code": code},
        "log": "Observed native evidence, not an inferred successful repair.",
        "affected_ids": ["robot_a"],
        "artifacts": [
            {
                "id": "native_observation",
                "path": "runs/source/observation.json",
                "sha256": hashlib.sha256(b"observed").hexdigest(),
            }
        ],
    }


@pytest.mark.parametrize("code,playbook,action", FAULTS)
def test_twelve_defects_select_evidence_driven_playbook_without_claiming_repair(
    code, playbook, action
):
    from polyforge.repairs.diagnostics import diagnose_evidence

    diagnosis = diagnose_evidence(evidence(code))
    assert diagnosis["playbook"] == playbook
    assert diagnosis["recommended_action"] == action
    assert diagnosis["repair_status"] == "NOT_RUN"
    assert diagnosis["evidence_graph"]["edges"]
    assert diagnosis["producer_id"] == "unity_integration"
    assert diagnosis["evaluated_test_status"] == "NOT_RUN"


def test_structured_success_wins_over_stale_error_log_and_unknown_null_ref_is_ambiguous():
    from polyforge.repairs.diagnostics import diagnose_evidence

    value = evidence()
    value["structured"] = {"status": "PASS", "code": None}
    value["log"] = "error CS0117: old prior-run error"
    assert diagnose_evidence(value)["diagnosis_status"] == "PASS"
    value["structured"] = {"status": "FAIL", "code": "UNKNOWN"}
    value["log"] = "NullReferenceException in Update"
    diagnosis = diagnose_evidence(value)
    assert diagnosis["recommended_action"] is None
    assert diagnosis["diagnosis_status"] == "REVIEW"
    assert len(diagnosis["hypotheses"]) > 1


@pytest.mark.parametrize(
    "text,detail",
    [
        ("error CS0117: Foo has no definition", "API_MISMATCH"),
        ("UnityEditor namespace is unavailable in runtime assembly", "ASSEMBLY_CONTEXT"),
        ("operator bpy.ops requires OBJECT mode", "MODE_CONTEXT"),
        ("com.unity.inputsystem package not found", "PACKAGE_ABSENCE"),
        ("domain reload invalidated object reference", "DOMAIN_RELOAD"),
    ],
)
def test_novel_code_failures_remain_proposals_with_distinct_context(text, detail):
    from polyforge.repairs.diagnostics import diagnose_evidence

    value = evidence("UNKNOWN")
    value["log"] = text
    result = diagnose_evidence(value)
    assert result["context_failure"] == detail
    assert result["recommended_action"] is None
    assert result["repair_status"] == "NOT_RUN"


def test_minimal_proposal_verifies_actual_evidence_and_denies_substitution(tmp_path):
    from polyforge.repairs.diagnostics import diagnose_evidence, plan_repair

    p = WorkspacePolicy(tmp_path)
    p.mkdir("runs/source")
    p.path("runs/source/observation.json").write_bytes(b"observed")
    issue = diagnose_evidence(evidence())
    plan = plan_repair(p, issue)
    assert plan["action"] == "rebuild_native_binding"
    assert plan["dry_run"] is True
    assert plan["verification_plan"] and plan["rollback_required"]
    changed = copy.deepcopy(issue)
    changed["recommended_action"] = "shell.exec"
    with pytest.raises(InputError):
        plan_repair(p, changed)
    p.path("runs/source/observation.json").write_bytes(b"substituted")
    with pytest.raises(InputError):
        plan_repair(p, issue)


def test_missing_version_unsafe_reference_and_invalid_status_fail_closed(tmp_path):
    from polyforge.repairs.diagnostics import diagnose_evidence

    for field, replacement in [
        ("affected_ids", []),
        ("input_digest", "invalid"),
        ("tool", {"name": "unity", "version": ""}),
    ]:
        value = evidence()
        value[field] = replacement
        with pytest.raises(InputError):
            diagnose_evidence(value)
    value = evidence()
    value["artifacts"][0]["path"] = "../private/secret"
    with pytest.raises(InputError):
        diagnose_evidence(value)
    value = evidence()
    value["structured"]["status"] = "APPROVED"
    with pytest.raises(InputError):
        diagnose_evidence(value)
    assert list(tmp_path.iterdir()) == []


def test_attempt_limit_is_durable_and_same_failed_proposal_escalates(tmp_path, monkeypatch):
    from polyforge.repairs.diagnostics import (
        diagnose_evidence,
        finish_attempt,
        plan_repair,
        reserve_attempt,
    )

    p = WorkspacePolicy(tmp_path)
    p.mkdir("runs/source")
    p.path("runs/source/observation.json").write_bytes(b"observed")
    from polyforge.repairs import diagnostics

    monkeypatch.setattr(
        diagnostics, "_native_plan", lambda *_: {"operation": "rebuild_native_binding"}
    )
    issue = diagnose_evidence(evidence())
    plan = plan_repair(p, issue)
    attempt = reserve_attempt(p, issue, plan)
    finish_attempt(p, attempt, status="FAIL", evidence_paths=["runs/source/observation.json"])
    with pytest.raises(InputError, match="identical|Escalat"):
        reserve_attempt(WorkspacePolicy(tmp_path), issue, plan)


@pytest.mark.parametrize(
    "change",
    [
        {"tool": {"name": [], "version": "1.0"}},
        {"structured": {"status": [], "code": "UNKNOWN"}},
        {"producer_id": []},
        {"affected_ids": [True]},
    ],
)
def test_malformed_evidence_is_a_contract_error_not_an_unhandled_exception(change):
    from polyforge.repairs.diagnostics import diagnose_evidence

    with pytest.raises(InputError):
        diagnose_evidence({**evidence(), **change})


def test_forensic_cli_is_pure_and_unknown_repairs_stay_blocked(tmp_path):
    from polyforge.cli import build_parser, dispatch
    from polyforge.runner.state import atomic_json

    p = WorkspacePolicy(tmp_path)
    atomic_json(p, "failure.json", evidence("PF-UNITY-API"))
    args = [
        "repair",
        "inspect",
        "--workspace",
        str(tmp_path),
        "--evidence",
        "failure.json",
        "--json",
    ]
    result = dispatch(build_parser().parse_args(args))
    assert result.data["diagnosis"]["playbook"] == "UNITY_API"
    assert result.data["diagnosis"]["recommended_action"] is None
    assert not p.path(".polyforge").exists()


@pytest.mark.parametrize("status", ["BLOCKED", "NOT_RUN"])
def test_blocked_or_unexecuted_result_cannot_be_reclassified_as_an_executed_repairable_failure(
    status,
):
    from polyforge.repairs.diagnostics import diagnose_evidence

    value = evidence("PF-COMPONENT-MISSING")
    value["structured"]["status"] = status
    value["log"] = "error CS0117 from an older attempt"
    result = diagnose_evidence(value)
    assert result["diagnosis_status"] == status
    assert result["recommended_action"] is None
    assert not result["hypotheses"]
