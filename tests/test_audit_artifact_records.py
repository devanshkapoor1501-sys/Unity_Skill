"""Section6.3 records bind ownership and bytes without inflating validation claims."""

import hashlib
import json

import pytest

from polyforge.contracts.validation import InputError
from polyforge.security.paths import WorkspacePolicy


def test_registration_records_real_bytes_and_explicit_ownership(tmp_path):
    from polyforge.runner.artifacts import complete_records

    folder = tmp_path / "runs/native/asset"
    folder.mkdir(parents=True)
    (folder / "source.blend").write_bytes(b"native source")
    (tmp_path / "game_manifest.json").write_text(
        json.dumps({"project": {"id": "arena_demo"}}), encoding="utf-8"
    )
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    records = complete_records(
        WorkspacePolicy(tmp_path),
        "native",
        "S2",
        [{"relative_path": "runs/native/asset/source.blend"}],
        input_digest="a" * 64,
    )
    row = records[0]
    assert row["project_id"] == "arena_demo" and row["run_id"] == "native"
    assert row["stage"] == "S2" and row["kind"] == "blend"
    assert row["artifact_id"] == "native:runs/native/asset/source.blend"
    assert row["sha256"] == hashlib.sha256(b"native source").hexdigest()
    assert row["bytes"] == 13 and row["upstream_input_hashes"] == ["a" * 64]
    assert row["resolved_location"] == str((folder / "source.blend").resolve())
    assert row["timestamp"] and row["validation_status"] == "HASH_VERIFIED"
    assert {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


@pytest.mark.parametrize("damage", ["hash", "size", "escape", "missing", "stage", "run"])
def test_registration_rejects_forged_or_escaping_entries_without_writes(tmp_path, damage):
    from polyforge.runner.artifacts import complete_records

    (tmp_path / "output.json").write_text("{}", encoding="utf-8")
    item = {"relative_path": "output.json"}
    if damage == "hash":
        item["sha256"] = "0" * 64
    elif damage == "size":
        item["bytes"] = 99
    elif damage in {"escape", "missing"}:
        item["relative_path"] = "../secret" if damage == "escape" else "missing"
    before = list(tmp_path.iterdir())
    with pytest.raises(InputError):
        complete_records(
            WorkspacePolicy(tmp_path),
            "../run" if damage == "run" else "run",
            "PASS" if damage == "stage" else "S3",
            [item],
        )
    assert list(tmp_path.iterdir()) == before


def test_registration_preserves_validation_evidence_without_inventing_project_identity(tmp_path):
    from polyforge.runner.artifacts import complete_records

    path = tmp_path / "evidence"
    path.write_bytes(b"measured")
    row = {
        "artifact_id": "observation",
        "relative_path": "evidence",
        "upstream_input_digest": "b" * 64,
        "validation_status": "PASS",
        "validator": "independent.fixture.v1",
        "kind": "telemetry",
    }
    result = complete_records(WorkspacePolicy(tmp_path), "fixture", "S5", [row])[0]
    assert result["project_id"].startswith("workspace_")
    assert result["validator"] == "independent.fixture.v1"
    assert result["validation_status"] == "PASS" and result["kind"] == "telemetry"
    assert result["upstream_input_hashes"] == ["b" * 64]
    with pytest.raises(InputError):
        complete_records(WorkspacePolicy(tmp_path), "fixture", "S5", [row, row])
    for invalid in [None, [{}], ["unsafe"]]:
        with pytest.raises(InputError):
            complete_records(WorkspacePolicy(tmp_path), "fixture", "S5", invalid)


def test_planning_inventory_binds_project_stage_and_lock_bytes(tmp_path):
    from test_phase2_contracts import arena

    from polyforge.compiler.commands import manifest_command

    arena(tmp_path)
    result = manifest_command(tmp_path / "game_manifest.json", "plan")
    assert result.status == "PASS"
    state = json.loads((tmp_path / ".polyforge/planning-state.json").read_text("utf-8"))
    lock = next(row for row in state["artifacts"] if row["relative_path"] == "polyforge.lock.json")
    assert lock["project_id"] == "arena_demo" and lock["stage"] == "S1"
    assert lock["run_id"].startswith("planning_") and lock["timestamp"]
    assert lock["upstream_input_hashes"] == [result.input_digest]


@pytest.mark.parametrize(
    "existing,checkpoint", [(False, "commit"), (True, "commit"), (True, "lock")]
)
def test_interrupted_planning_publication_retains_exact_lock_ownership(
    tmp_path, monkeypatch, existing, checkpoint
):
    import importlib

    from test_phase2_contracts import arena

    from polyforge.compiler import commands

    arena(tmp_path)
    monkeypatch.setattr(
        importlib.import_module("polyforge.doctor"), "discover_tool", lambda *a: None
    )
    manifest = tmp_path / "game_manifest.json"
    if existing:
        commands.manifest_command(manifest, "plan")
        value = json.loads(manifest.read_text("utf-8"))
        value["project"]["seed"] = 43
        manifest.write_text(json.dumps(value), encoding="utf-8")
    original = commands.atomic_json

    def interrupt(policy, relative, value):
        if (
            checkpoint == "commit"
            and str(relative) == ".polyforge/planning-state.json"
            and value.get("status") == "COMMITTED"
        ) or (checkpoint == "lock" and str(relative) == "polyforge.lock.json"):
            raise OSError("injected publication interruption")
        return original(policy, relative, value)

    monkeypatch.setattr(commands, "atomic_json", interrupt)
    with pytest.raises(OSError, match="injected publication"):
        commands.manifest_command(manifest, "plan")
    monkeypatch.setattr(commands, "atomic_json", original)
    assert commands.manifest_command(manifest, "plan").status == "PASS"


def test_repeated_interruption_preserves_current_lock_when_new_plan_changes(tmp_path, monkeypatch):
    import importlib

    from test_phase2_contracts import arena

    from polyforge.compiler import commands

    arena(tmp_path)
    monkeypatch.setattr(
        importlib.import_module("polyforge.doctor"), "discover_tool", lambda *a: None
    )
    manifest = tmp_path / "game_manifest.json"
    original = commands.atomic_json
    checkpoint = ["commit"]

    def interrupt(policy, relative, value):
        if (
            checkpoint[0] == "commit"
            and str(relative) == ".polyforge/planning-state.json"
            and value.get("status") == "COMMITTED"
        ) or (checkpoint[0] == "lock" and str(relative) == "polyforge.lock.json"):
            raise OSError("injected interruption")
        return original(policy, relative, value)

    monkeypatch.setattr(commands, "atomic_json", interrupt)
    with pytest.raises(OSError):
        commands.manifest_command(manifest, "plan")
    value = json.loads(manifest.read_text("utf-8"))
    value["project"]["seed"] = 43
    manifest.write_text(json.dumps(value), encoding="utf-8")
    checkpoint[0] = "lock"
    with pytest.raises(OSError):
        commands.manifest_command(manifest, "plan")
    monkeypatch.setattr(commands, "atomic_json", original)
    assert commands.manifest_command(manifest, "plan").status == "PASS"
