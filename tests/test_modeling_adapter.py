"""Advanced modeling uses the existing bounded capability entry point."""

import threading

import pytest

from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.validation import InputError


def request():
    return {
        "schema_version": "1.0.0",
        "asset_id": "practice_part",
        "parameters": {"size_m": [2, 1, 3]},
    }


def test_modeling_preview_is_a_compiled_plan_without_any_writes(tmp_path):
    from polyforge.blender.modeling_adapter import execute_modeling

    result = execute_modeling("room_kit", request(), RunContext(tmp_path, dry_run=True))
    assert result.status == "PASS"
    assert result.data["execution_status"] == "NOT_RUN"
    assert result.data["plan"]["workflow"] == "room_kit"
    assert list(tmp_path.iterdir()) == []


def test_bad_modeling_request_does_not_create_outputs(tmp_path):
    from polyforge.blender.modeling_adapter import execute_modeling

    value = request()
    value["parameters"]["size_m"] = [True, 1, 3]
    with pytest.raises(InputError):
        execute_modeling("room_kit", value, RunContext(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_cancelled_modeling_does_not_create_outputs(tmp_path):
    from polyforge.blender.modeling_adapter import execute_modeling

    cancelled = threading.Event()
    cancelled.set()
    result = execute_modeling("room_kit", request(), RunContext(tmp_path, cancel=cancelled))
    assert result.status == "FAIL" and result.exit_code == 9
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("kind", ["room_kit", "vehicle", "mechanical_prop", "organic"])
def test_registered_modeling_capabilities_preview_through_dispatch(kind, tmp_path):
    from polyforge.blender.modeling import MODELING_CAPABILITIES
    from polyforge.capabilities.dispatch import execute
    from polyforge.capabilities.registry import lookup

    identifier = MODELING_CAPABILITIES[kind]
    assert lookup(identifier)["input_schema"] == "contracts/modeling_request.schema.json"
    result = execute(identifier, request(), RunContext(tmp_path, dry_run=True))
    assert result.data["plan"]["workflow"] == kind
    assert result.data["execution_status"] == "NOT_RUN"
    assert list(tmp_path.iterdir()) == []


def test_empty_inventory_cannot_recover_as_a_completed_modeling_run(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    from polyforge.blender import modeling_adapter as adapter
    from polyforge.blender.modeling import compile_modeling
    from polyforge.contracts.validation import canonical_digest
    from polyforge.runner.state import atomic_json
    from polyforge.security.paths import WorkspacePolicy

    policy = WorkspacePolicy(tmp_path)
    monkeypatch.setattr(adapter, "discover_tool", lambda *_: Path(sys.executable))
    monkeypatch.setattr(adapter, "_sha", lambda *_, **__: "a" * 64)
    plan = compile_modeling("room_kit", request())
    fingerprints = dict.fromkeys(("modeling_worker", "modeling_inspector", "executable"), "a" * 64)
    identity = canonical_digest({"plan": plan, "toolchain": fingerprints})
    empty = {"artifacts": []}
    atomic_json(policy, "runs/model-empty/artifacts.json", empty)
    atomic_json(
        policy,
        "runs/model-empty/result.json",
        {"identity": identity, "inventory_digest": canonical_digest(empty)},
    )
    with pytest.raises(InputError, match="inventory is incomplete"):
        adapter.execute_modeling("room_kit", request(), RunContext(tmp_path, run_id="empty"))


def test_existing_unfinished_run_is_preserved(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    from polyforge.blender import modeling_adapter as adapter

    monkeypatch.setattr(adapter, "discover_tool", lambda *_: Path(sys.executable))
    root = tmp_path / "runs/model-interrupted"
    root.mkdir(parents=True)
    log = root / "partial.log"
    log.write_text("interrupted original run")
    with pytest.raises(InputError, match="without a completion receipt"):
        adapter.execute_modeling("room_kit", request(), RunContext(tmp_path, run_id="interrupted"))
    assert list(root.iterdir()) == [log]
