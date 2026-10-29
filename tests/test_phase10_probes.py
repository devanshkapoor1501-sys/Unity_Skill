"""Only fixed engine probes can establish version/API evidence."""

import hashlib
import sys
from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


def test_unknown_probe_and_dry_run_write_nothing(tmp_path, monkeypatch):
    from polyforge.knowledge import probes

    monkeypatch.setattr(probes, "discover_tool", lambda *a: Path(sys.executable))
    with pytest.raises(InputError):
        probes.probe_tool(tmp_path, "shell")
    result = probes.probe_tool(tmp_path, "blender", dry_run=True)
    assert result.data["execution_status"] == "NOT_RUN"
    assert result.data["probe_id"] == "blender.mesh-context.v1"
    assert not list(tmp_path.iterdir())


def test_missing_probe_tool_is_blocked_without_writes(tmp_path, monkeypatch):
    from polyforge.knowledge import probes

    monkeypatch.setattr(probes, "discover_tool", lambda *a: None)
    result = probes.probe_tool(tmp_path, "unity")
    assert result.status == "BLOCKED" and result.exit_code == 3
    assert not list(tmp_path.iterdir())
    dry = probes.probe_tool(tmp_path, "unity", dry_run=True)
    assert dry.status == "PASS" and dry.data["execution_status"] == "NOT_RUN"
    assert dry.data["availability"] == "UNAVAILABLE"
    assert not list(tmp_path.iterdir())


def test_success_requires_actual_typed_native_probe_not_a_pass_label(tmp_path):
    from polyforge.knowledge.probes import validate_observation

    valid = {
        "schema_version": "1.0.0",
        "probe_id": "blender.mesh-context.v1",
        "tool_version": "5.2.2",
        "checks": {
            "valid_mesh_unchanged": True,
            "degenerate_mesh_repaired": True,
            "context_poll_without_active_object": False,
            "context_poll_with_active_object": True,
        },
        "artifacts": [],
    }
    assert validate_observation("blender", valid)["knowledge_state"] == "VERSION_PROBED"
    for change in [
        {"checks": {}},
        {"tool_version": "6.0.0"},
        {"probe_id": "caller.claimed"},
        {"checks": {**valid["checks"], "degenerate_mesh_repaired": False}},
    ]:
        with pytest.raises(InputError):
            validate_observation("blender", {**valid, **change})


def test_probe_receipts_bind_binary_script_result_and_no_ui_or_delegation_claim(tmp_path):
    from polyforge.knowledge.probes import read_probe

    p = WorkspacePolicy(tmp_path)
    assert read_probe(p, "blender") is None
    atomic_json(
        p,
        ".polyforge/knowledge-blender.json",
        {"status": "PASS", "knowledge_state": "VERIFIED_IN_WORKFLOW"},
    )
    with pytest.raises(InputError):
        read_probe(p, "blender")


def test_cli_route_and_catalog_are_pure_and_unknown_stays_review(tmp_path):
    from polyforge.cli import build_parser, dispatch

    p = WorkspacePolicy(tmp_path)
    atomic_json(
        p,
        "request.json",
        {
            "schema_version": "1.0.0",
            "query": "Explain Timeline versus Animator",
            "output": "EXPLAIN",
        },
    )
    before = p.path("request.json").read_bytes()
    parser = build_parser()
    result = dispatch(
        parser.parse_args(
            ["knowledge", "route", "--workspace", str(tmp_path), "--request", "request.json"]
        )
    )
    assert result.status == "PASS"
    assert result.data["reference_route"]["capability_ids"] == []
    assert dispatch(parser.parse_args(["knowledge", "list"])).data["knowledge_cards"]
    assert p.path("request.json").read_bytes() == before and len(list(tmp_path.iterdir())) == 1


def successful_probe(tmp_path, monkeypatch, tool="blender"):
    from polyforge.knowledge import probes
    from polyforge.runner.processes import ProcessOutcome

    p = WorkspacePolicy(tmp_path)
    monkeypatch.setattr(probes, "discover_tool", lambda *a: Path(sys.executable))

    def run(argv, policy, relative, limits):
        output = argv[-1]
        atomic_json(
            policy,
            output,
            {
                "schema_version": "1.0.0",
                "probe_id": probes.PINS[tool][1],
                "tool_version": probes.PINS[tool][0],
                "checks": probes.CHECKS[tool],
                "artifacts": [],
            },
        )
        return ProcessOutcome(0, "exit", 123, "UNIT_FIXTURE", 0, "", "", False)

    monkeypatch.setattr(probes, "run_process", run)
    result = probes.probe_tool(tmp_path, tool)
    return p, result


@pytest.mark.parametrize("tool", ["blender", "unity"])
def test_current_fixed_receipt_is_version_probed_but_does_not_promote_workflow(
    tmp_path, monkeypatch, tool
):
    from polyforge.knowledge.probes import read_probe
    from polyforge.knowledge.router import route_reference

    p, result = successful_probe(tmp_path, monkeypatch, tool)
    assert result.status == "PASS"
    observed = read_probe(p, tool)
    assert observed["knowledge_state"] == "VERSION_PROBED"
    assert observed["execution_support_promoted"] is False
    query = {
        "schema_version": "1.0.0",
        "query": "Make a crate" if tool == "blender" else "Import supplied sprites",
        "output": "ASSET" if tool == "blender" else "SPRITE",
    }
    routed = route_reference(p, query)
    assert routed["required_probes"][0]["status"] == "VERSION_PROBED"
    assert all(c["knowledge_state"] == "REFERENCE_ONLY" for c in routed["cards"])


def test_fixed_probe_cannot_promote_unrelated_reference_knowledge(tmp_path, monkeypatch):
    from polyforge.knowledge.router import route_reference

    p, result = successful_probe(tmp_path, monkeypatch, "unity")
    repair = route_reference(
        p,
        {
            "schema_version": "1.0.0",
            "query": "Repair an unknown compiler failure",
            "output": "REPAIR",
        },
    )
    assert repair["cards"][0]["api_probe_id"] == "none"
    assert repair["cards"][0]["knowledge_state"] == "REFERENCE_ONLY"
    known = route_reference(
        p,
        {
            "schema_version": "1.0.0",
            "query": "Inspect TypeCache Unity Editor API",
            "output": "INSPECT",
            "domain": "unity",
        },
    )
    assert (
        next(c for c in known["cards"] if c["knowledge_id"] == "unity.editor")["knowledge_state"]
        == "VERSION_PROBED"
    )
    assert all(
        c["knowledge_state"] == "REFERENCE_ONLY"
        for c in known["cards"]
        if c["api_probe_id"] == "none"
    )


@pytest.mark.parametrize(
    "damage", ["binary", "source", "observation", "process", "path", "argv", "exit"]
)
def test_changed_probe_inputs_or_outputs_cannot_reuse_a_receipt(tmp_path, monkeypatch, damage):
    from polyforge.knowledge import probes

    p, result = successful_probe(tmp_path, monkeypatch)
    marker = ".polyforge/knowledge-blender.json"
    receipt = load_json(p.path(marker))
    if damage == "binary":
        receipt["binary_sha256"] = "0" * 64
    elif damage in {"source", "observation", "process"}:
        p.path(receipt[damage + "_path"]).write_bytes(b"substituted")
    elif damage == "path":
        receipt["observation_path"] = "../secret.json"
    else:
        process = load_json(p.path(receipt["process_path"]))
        if damage == "argv":
            process["argv"] = ["arbitrary", "script"]
        else:
            process["returncode"] = 1
        atomic_json(p, receipt["process_path"], process)
        receipt["process_sha256"] = hashlib.sha256(
            p.path(receipt["process_path"]).read_bytes()
        ).hexdigest()
    atomic_json(p, marker, receipt)
    with pytest.raises(InputError):
        probes.read_probe(p, "blender")


def test_worker_failure_does_not_publish_success_receipt(tmp_path, monkeypatch):
    from polyforge.knowledge import probes
    from polyforge.runner.processes import ProcessOutcome

    monkeypatch.setattr(probes, "discover_tool", lambda *a: Path(sys.executable))
    monkeypatch.setattr(
        probes,
        "run_process",
        lambda *a: ProcessOutcome(1, "timeout", 123, "UNIT_FIXTURE", 1, "", "", False),
    )
    result = probes.probe_tool(tmp_path, "blender")
    assert result.status == "FAIL" and result.data["knowledge_state"] == "UNAVAILABLE"
    assert not (tmp_path / ".polyforge/knowledge-blender.json").exists()
