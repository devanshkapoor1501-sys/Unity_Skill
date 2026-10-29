"""Real captured native fault, independently rescored for forensic routing."""

import hashlib
import json
from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.repairs.diagnostics import diagnose_evidence, plan_repair
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.evidence import reconcile_report


def native_fixture(tmp_path, monkeypatch):
    from polyforge.unity import repairs

    p = WorkspacePolicy(tmp_path)
    request = load_json(Path("tests/fixtures/phase9/native-request.json"))
    raw = load_json(Path("tests/fixtures/phase9/native-fault.json"))
    report = reconcile_report(request, raw)
    issues = [
        {**row, "issue_id": "ISSUE-" + canonical_digest(row)[:12]} for row in report["issues"]
    ]
    atomic_json(p, "runs/native/bindings.json", raw)
    atomic_json(
        p,
        ".polyforge/unity-issues.json",
        {"input_digest": request["input_digest"], "evidence_dir": "runs/native", "issues": issues},
    )
    row = next(i for i in issues if i["category"] == "scale" and i["asset_id"] == "robot_a")
    value = {
        "schema_version": "1.0.0",
        "input_digest": request["input_digest"],
        "producer_id": "unity_integration",
        "tool": {"name": "unity", "version": "6000.6.3f1"},
        "structured": {"status": "FAIL", "code": "PF-FBX-AXES"},
        "log": json.dumps({**row, "repair_supported": True}, sort_keys=True),
        "affected_ids": ["robot_a"],
        "artifacts": [
            {
                "id": "native_bindings",
                "path": "runs/native/bindings.json",
                "sha256": hashlib.sha256(
                    p.path("runs/native/bindings.json").read_bytes()
                ).hexdigest(),
            }
        ],
    }
    monkeypatch.setattr(repairs, "current_request", lambda _: request)
    return p, value


def test_actual_native_scale_fault_selects_exact_symptom_and_registered_action(
    tmp_path, monkeypatch
):
    p, value = native_fixture(tmp_path, monkeypatch)
    plan = plan_repair(p, diagnose_evidence(value))
    assert plan["status"] == "PROPOSED"
    assert plan["action"] == "rebuild_native_binding"
    assert plan["native_plan"]["category"] == "scale"
    assert plan["native_plan"]["asset_id"] == "robot_a"


@pytest.mark.parametrize(
    "change", ["invalid_log", "wrong_symptom", "wrong_source", "wrong_manifest", "stale_registry"]
)
def test_misleading_native_symptom_cannot_authorize_another_repair(tmp_path, monkeypatch, change):
    p, value = native_fixture(tmp_path, monkeypatch)
    if change == "invalid_log":
        value["log"] = "NullReferenceException"
    elif change == "wrong_symptom":
        claimed = json.loads(value["log"])
        claimed["actual"] = [999, 999, 999]
        value["log"] = json.dumps(claimed)
    elif change == "wrong_source":
        value["artifacts"][0]["path"] = "runs/other/bindings.json"
        p.mkdir("runs/other")
        p.path("runs/other/bindings.json").write_bytes(
            p.path("runs/native/bindings.json").read_bytes()
        )
    elif change == "wrong_manifest":
        value["input_digest"] = "b" * 64
    else:
        record = load_json(p.path(".polyforge/unity-issues.json"))
        record["issues"] = []
        atomic_json(p, ".polyforge/unity-issues.json", record)
    issue = diagnose_evidence(value)
    if change in {"wrong_manifest", "stale_registry"}:
        with pytest.raises(InputError):
            plan_repair(p, issue)
    else:
        assert plan_repair(p, issue)["status"] == "BLOCKED"
