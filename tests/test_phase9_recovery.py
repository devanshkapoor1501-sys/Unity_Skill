"""File restoration is only a step toward application-aware rollback proof."""

import hashlib
import json

import pytest

from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.transactions import ManagedTransaction


def source_fixture(tmp_path):
    p = WorkspacePolicy(tmp_path)
    p.mkdir("runs/source/asset")
    path = "runs/source/asset/source.blend"
    p.path(path).write_bytes(b"registered editable Blender source")
    atomic_json(
        p,
        "runs/source/artifacts.json",
        {
            "artifacts": [
                {
                    "relative_path": path,
                    "sha256": hashlib.sha256(p.path(path).read_bytes()).hexdigest(),
                }
            ]
        },
    )
    p.mkdir("UnityProject/Assets/PolyForgeGenerated")
    p.path("UnityProject/Assets/PolyForgeGenerated/robot.prefab").write_bytes(
        b"native prefab bytes"
    )
    return p, path


def test_registered_blender_source_and_game_state_are_in_transaction_closure(tmp_path):
    p, path = source_fixture(tmp_path)
    atomic_json(p, ".polyforge/game-latest.json", {"request": "runs/game/input.json"})
    tx = ManagedTransaction.create(p, "cross_tool", dependencies=[path])
    journal = load_json(p.path(tx.relative + "/journal.json"))
    assert journal["status"] == "PREPARED"
    p.path(path).write_bytes(b"damaged source")
    atomic_json(p, ".polyforge/game-latest.json", {"request": "wrong"})
    tx.restore()
    assert tx.verify_restored()
    assert p.path(path).read_bytes() == b"registered editable Blender source"
    assert load_json(p.path(".polyforge/game-latest.json"))["request"] == "runs/game/input.json"
    assert load_json(p.path(tx.relative + "/journal.json"))["status"] == "ROLLING_BACK"


@pytest.mark.parametrize(
    "dependency",
    [
        "private.blend",
        "runs/unregistered/asset/source.blend",
        "../outside.blend",
        "UnityProject/Assets/User/scene.unity",
    ],
)
def test_snapshot_cannot_expand_write_scope_through_unregistered_dependencies(tmp_path, dependency):
    p, path = source_fixture(tmp_path)
    with pytest.raises(InputError):
        ManagedTransaction.create(p, "unsafe", dependencies=[dependency])
    assert not p.path("transactions/unsafe").exists()


def test_snapshot_validation_happens_before_any_restore_write(tmp_path):
    p, path = source_fixture(tmp_path)
    tx = ManagedTransaction.create(p, "tampered", dependencies=[path])
    p.path(path).write_bytes(b"current bytes must stay on failed preflight")
    p.path(tx.relative + "/snapshot/" + path).write_bytes(b"corrupt snapshot")
    with pytest.raises(InputError, match="hash|digest"):
        tx.restore()
    assert p.path(path).read_bytes() == b"current bytes must stay on failed preflight"


def test_tampered_original_inventory_and_transaction_identity_are_rejected(tmp_path):
    p, path = source_fixture(tmp_path)
    tx = ManagedTransaction.create(p, "identity", dependencies=[path])
    journal_path = p.path(tx.relative + "/journal.json")
    original = load_json(journal_path)
    for change in ["identity", "inventory"]:
        value = json.loads(json.dumps(original))
        if change == "identity":
            value["transaction_id"] = "another_transaction"
        else:
            value["original"] = {}
        atomic_json(p, journal_path, value)
        with pytest.raises(InputError):
            tx.restore()
    assert p.path(path).read_bytes() == b"registered editable Blender source"


@pytest.mark.parametrize(
    "damage",
    [
        "dependency_type",
        "duplicate",
        "hash",
        "canonical_path",
        "scope_digest",
        "missing_registry",
        "registry_hash",
        "registry_shape",
        "orphan",
        "registry_member",
        "proof_scope",
        "proof_hash",
    ],
)
def test_every_saved_scope_and_proof_is_checked_before_restoration(tmp_path, damage):
    p, source = source_fixture(tmp_path)
    tx = ManagedTransaction.create(p, "corrupt_closure", dependencies=[source])
    tx.record("BASELINE", prestate=native_state())
    journal_path = tx.relative + "/journal.json"
    value = load_json(p.path(journal_path))
    # Structural validation must also protect legacy journals without digest fields.
    value.pop("snapshot_digest")
    value.pop("scope_digest")
    registry = "runs/source/artifacts.json"
    if damage == "dependency_type":
        value["dependencies"] = "runs/source"
    elif damage == "duplicate":
        value["dependencies"].append(source)
    elif damage == "hash":
        value["original"][source] = "invalid"
    elif damage == "canonical_path":
        key = "UnityProject/Assets/PolyForgeGenerated/robot.prefab"
        value["original"]["./" + key] = value["original"].pop(key)
    elif damage == "scope_digest":
        value["scope_digest"] = "0" * 64
    elif damage == "missing_registry":
        value["dependencies"].remove(registry)
        value["original"].pop(registry)
    elif damage == "registry_hash":
        p.path(tx.relative + "/snapshot/" + registry).write_bytes(b"substituted provenance")
    elif damage in {"registry_shape", "registry_member"}:
        target = tx.relative + "/snapshot/" + registry
        atomic_json(
            p, target, {"artifacts": None} if damage == "registry_shape" else {"artifacts": []}
        )
        value["original"][registry] = hashlib.sha256(p.path(target).read_bytes()).hexdigest()
    elif damage == "orphan":
        value["dependencies"].remove(source)
        value["original"].pop(source)
    elif damage == "proof_scope":
        value["prestate"]["evidence_path"] = (
            "transactions/another/evidence/prestate-" + "0" * 64 + ".json"
        )
    else:
        p.path(value["prestate"]["evidence_path"]).write_bytes(b"changed proof")
    atomic_json(p, journal_path, value)
    managed = p.path("UnityProject/Assets/PolyForgeGenerated/robot.prefab")
    managed.write_bytes(b"live bytes must survive invalid snapshot")
    p.path("user.txt").write_bytes(b"unmanaged user bytes")
    with pytest.raises(InputError):
        tx.restore()
    assert managed.read_bytes() == b"live bytes must survive invalid snapshot"
    assert p.path("user.txt").read_bytes() == b"unmanaged user bytes"


def test_different_workspace_roots_use_one_physical_project_lock(tmp_path):
    from polyforge.runner.locks import unity_project_lock

    p, path = source_fixture(tmp_path)
    nested = p.mkdir("nested")
    project = p.mkdir("nested/UnityProject")
    with unity_project_lock(p, project):
        with pytest.raises(InputError):
            with unity_project_lock(WorkspacePolicy(nested), project):
                pass


def test_project_lock_does_not_create_an_unbootstrapped_project(tmp_path):
    from polyforge.runner.locks import unity_project_lock

    p = WorkspacePolicy(tmp_path)
    with unity_project_lock(p, p.path("UnityProject")):
        assert not p.path("UnityProject").exists()


def native_state():
    return {
        "bindings": {
            "scene_guids": ["a" * 32],
            "scene_object_count": 3,
            "objects": [{"id": "robot", "guid": "b" * 32}],
        },
        "regressions": {"arena": {"status": "PASS", "scenarios": {"player_moves": "PASS"}}},
        "profile_inputs": {},
        "proof_scope": "NATIVE_REIMPORT_AND_REGRESSION",
    }


def test_byte_restore_requires_native_proof_and_failed_proof_quarantines(tmp_path, monkeypatch):
    from polyforge.unity import recovery

    p, path = source_fixture(tmp_path)
    monkeypatch.setattr(recovery, "observe_state", lambda *a, **k: native_state())
    tx = recovery.prepare_transaction(p, "proof", dependencies=[path])
    p.path(path).write_bytes(b"corruption")
    changed = native_state()
    changed["bindings"]["objects"][0]["guid"] = "c" * 32
    monkeypatch.setattr(recovery, "observe_state", lambda *a, **k: changed)
    result = recovery.repair_rollback(tmp_path, "proof")
    assert result.error_code == "PF-ROLLBACK-FAILED"
    assert p.path(path).read_bytes() == b"registered editable Blender source"
    assert load_json(p.path(tx.relative + "/journal.json"))["status"] == "ROLLBACK_FAILED"
    assert p.path("UnityProject/.polyforge/repair-quarantine.json").is_file()
    from polyforge.runner.locks import unity_project_lock

    with pytest.raises(InputError, match="quarantin"):
        with unity_project_lock(p, p.path("UnityProject")):
            pass


def test_resume_after_crash_repeats_reimport_and_scenario_proof(tmp_path, monkeypatch):
    from polyforge.unity import recovery

    p, path = source_fixture(tmp_path)
    monkeypatch.setattr(recovery, "observe_state", lambda *a, **k: native_state())
    tx = recovery.prepare_transaction(p, "interrupted", dependencies=[path])
    p.path(path).write_bytes(b"corruption")
    tx.restore()  # Simulated kill boundary: bytes restored, no reimport/evaluation.
    assert tx.read()["status"] == "ROLLING_BACK"
    calls = []

    def observe(*args, **kwargs):
        calls.append(kwargs.get("restore"))
        return native_state()

    monkeypatch.setattr(recovery, "observe_state", observe)
    result = recovery.resume_run(tmp_path, "interrupted")
    assert result.status == "PASS"
    assert calls == [True]
    assert tx.read()["status"] == "ROLLED_BACK"
    assert result.evaluated_test_status == "PASS"


def test_resume_preserves_failed_native_attempt_logs(tmp_path, monkeypatch):
    from polyforge.unity import recovery

    p, source = source_fixture(tmp_path)
    monkeypatch.setattr(recovery, "observe_state", lambda *a, **k: native_state())
    tx = recovery.prepare_transaction(p, "keep_negative", dependencies=[source])
    paths = []

    def observe(policy, relative, **kwargs):
        paths.append(relative)
        atomic_json(
            policy,
            relative + "/native/process.json",
            {"reason": "timeout" if len(paths) == 1 else "exit"},
        )
        if len(paths) == 1:
            raise InputError("Injected timeout")
        return native_state()

    monkeypatch.setattr(recovery, "observe_state", observe)
    assert recovery.repair_rollback(tmp_path, tx.identifier).status == "FAIL"
    assert recovery.resume_run(tmp_path, tx.identifier).status == "PASS"
    assert paths[0] != paths[1]
    assert load_json(p.path(paths[0] + "/native/process.json"))["reason"] == "timeout"


def test_failed_scenario_blocks_rollback_even_when_native_bindings_match(tmp_path, monkeypatch):
    from polyforge.unity import recovery

    p, path = source_fixture(tmp_path)
    monkeypatch.setattr(recovery, "observe_state", lambda *a, **k: native_state())
    tx = recovery.prepare_transaction(p, "scenario", dependencies=[path])
    wrong = native_state()
    wrong["regressions"]["arena"]["scenarios"]["player_moves"] = "FAIL"
    monkeypatch.setattr(recovery, "observe_state", lambda *a, **k: wrong)
    assert recovery.repair_rollback(tmp_path, tx.identifier).error_code == "PF-ROLLBACK-FAILED"


def test_unknown_resume_never_creates_or_executes_anything(tmp_path):
    from polyforge.unity.recovery import resume_run

    with pytest.raises(InputError):
        resume_run(tmp_path, "unrecorded")
    assert list(tmp_path.iterdir()) == []


def test_recovery_observer_is_a_fixed_registered_unity_method(tmp_path, monkeypatch):
    from polyforge.config import Config
    from polyforge.runner.processes import ProcessOutcome
    from polyforge.unity import bridge

    p = WorkspacePolicy(tmp_path)
    calls = []

    def run(argv, *args, **kwargs):
        calls.append(argv)
        return ProcessOutcome(0, "exit", None, "UNIT_FIXTURE", 0, "", "", False)

    monkeypatch.setattr(bridge, "run_process", run)
    bridge.launch(
        p,
        tmp_path / "Unity.exe",
        Config(),
        "runs/probe",
        "recovery",
        output=p.path("runs/probe/identity.json"),
    )
    assert "PolyForge.Editor.RecoveryProbe.ObserveBatch" in calls[0]


def test_quarantine_is_checked_when_lock_is_acquired_not_only_when_created(tmp_path):
    from polyforge.runner.locks import unity_project_lock

    p, path = source_fixture(tmp_path)
    guard = unity_project_lock(p, p.path("UnityProject"))
    atomic_json(p, "UnityProject/.polyforge/repair-quarantine.json", {"status": "ROLLBACK_FAILED"})
    with pytest.raises(InputError, match="quarantin"):
        with guard:
            pass


def test_source_closure_follows_consumers_back_to_registered_producer(tmp_path):
    from polyforge.unity.recovery import source_dependencies

    p, source = source_fixture(tmp_path)
    fbx = "runs/source/asset/asset.fbx"
    p.path(fbx).write_bytes(b"registered exported model")
    p.path("UnityProject/Assets/PolyForgeGenerated/robot.fbx").write_bytes(p.path(fbx).read_bytes())
    records = [
        {"relative_path": n, "sha256": hashlib.sha256(p.path(n).read_bytes()).hexdigest()}
        for n in (source, fbx)
    ]
    atomic_json(p, "runs/source/artifacts.json", {"artifacts": records})
    # A later consumer may seal the producer's files by reference without owning them.
    atomic_json(p, "runs/later_consumer/artifacts.json", {"artifacts": records})
    assert set(source_dependencies(p)) == {source, fbx}


def test_native_input_archive_survives_changed_original_and_duplicate_consumer_runs(tmp_path):
    from polyforge.unity.recovery import _profile_inputs

    p, source = source_fixture(tmp_path)
    p.mkdir("UnityProject/Assets/PolyForgeGenerated/Sprites")
    p.path("UnityProject/Assets/PolyForgeGenerated/Sprites/SpriteArena.unity").write_bytes(b"scene")
    p.path("UnityProject/Assets/PolyForgeGenerated/Sprites/atlas.png").write_bytes(
        b"imported atlas"
    )
    job = {"atlas_sha256": hashlib.sha256(b"imported atlas").hexdigest(), "fps": 6}
    atomic_json(p, "runs/sprite-unity-first/input.json", job)
    profiles = _profile_inputs(p)
    archived = profiles["sprite"]["path"]
    assert archived.startswith(".polyforge/native-inputs/sprite/")
    tx = ManagedTransaction.create(p, "archive_inputs", dependencies=[source])
    assert archived in tx.read()["original"]
    atomic_json(p, "runs/sprite-unity-second/input.json", job)
    atomic_json(p, "runs/sprite-unity-first/input.json", {"fps": 999})
    p.path(archived).write_bytes(b"corrupted archived job")
    tx.restore()
    assert _profile_inputs(p, profiles) == profiles
    assert load_json(p.path(archived)) == job


def test_large_native_proof_is_immutable_external_evidence_not_an_unreadable_journal(tmp_path):
    p, path = source_fixture(tmp_path)
    tx = ManagedTransaction.create(p, "large_native", dependencies=[path])
    proof = {"native_references": ["asset reference " + str(i) + "x" * 100 for i in range(10000)]}
    tx.record("BASELINE", prestate=proof)
    metadata = p.path(tx.relative + "/journal.json")
    assert metadata.stat().st_size < 10000
    assert tx.read()["prestate"] == proof
    saved = load_json(metadata)["prestate"]["evidence_path"]
    p.path(saved).write_bytes(b"tampered native proof")
    with pytest.raises(InputError, match="hash|digest"):
        tx.read()


def test_invalid_prepare_dependencies_are_rejected_before_native_observation(tmp_path, monkeypatch):
    from polyforge.unity import recovery

    p, path = source_fixture(tmp_path)
    before = set(tmp_path.rglob("*"))
    monkeypatch.setattr(
        recovery,
        "observe_state",
        lambda *a, **k: pytest.fail("invalid input reached a native worker"),
    )
    with pytest.raises(InputError):
        recovery.prepare_transaction(p, "invalid_preflight", dependencies=["../private.blend"])
    assert set(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("mode", ["sequential", "single"])
def test_workforce_resume_preserves_original_ledger_identity_and_mode(tmp_path, monkeypatch, mode):
    from test_workforce import request

    from polyforge.contracts.results import Result
    from polyforge.unity.recovery import resume_run
    from polyforge.workforce import orchestrator
    from polyforge.workforce.router import plan_task

    p = WorkspacePolicy(tmp_path)
    saved = plan_task(request(), workspace=tmp_path)
    run_id = saved["task_id"] + ("_single" if mode == "single" else "")
    atomic_json(p, "workforce/" + run_id + "/plan.json", saved)
    calls = []

    def run(*args, **kwargs):
        calls.append(kwargs.get("mode", "sequential"))
        return Result()

    monkeypatch.setattr(orchestrator, "run_task", run)
    assert resume_run(tmp_path, run_id).status == "PASS"
    assert calls == [mode]
    atomic_json(p, "workforce/renamed_run/plan.json", saved)
    with pytest.raises(InputError):
        resume_run(tmp_path, "renamed_run")


def test_completed_recovery_resume_cannot_overwrite_later_workspace_changes(tmp_path, monkeypatch):
    from polyforge.unity import recovery

    p, path = source_fixture(tmp_path)
    monkeypatch.setattr(recovery, "observe_state", lambda *a, **k: native_state())
    tx = recovery.prepare_transaction(p, "completed", dependencies=[path])
    assert recovery.repair_rollback(tmp_path, tx.identifier).status == "PASS"
    p.path(path).write_bytes(b"later intentional source revision")
    with pytest.raises(InputError):
        recovery.resume_run(tmp_path, tx.identifier)
    assert p.path(path).read_bytes() == b"later intentional source revision"


def test_recovery_cannot_clear_another_transaction_quarantine(tmp_path, monkeypatch):
    from polyforge.unity import recovery

    p, path = source_fixture(tmp_path)
    monkeypatch.setattr(recovery, "observe_state", lambda *a, **k: native_state())
    tx = recovery.prepare_transaction(p, "one", dependencies=[path])
    marker = "UnityProject/.polyforge/repair-quarantine.json"
    atomic_json(p, marker, {"transaction_id": "another", "status": "ROLLBACK_FAILED"})
    with pytest.raises(InputError):
        recovery.repair_rollback(tmp_path, tx.identifier)
    assert load_json(p.path(marker))["transaction_id"] == "another"


@pytest.mark.parametrize("target", ["UserProject/keep.txt", "UserProject"])
@pytest.mark.parametrize("legacy", [False, True])
def test_corrupt_dependency_closure_cannot_delete_unrelated_user_data(tmp_path, target, legacy):
    p, source = source_fixture(tmp_path)
    p.mkdir("UserProject")
    user_file = p.path("UserProject/keep.txt")
    user_file.write_bytes(b"untouched user project")
    tx = ManagedTransaction.create(p, "closure_corrupt", dependencies=[source])
    p.path(source).write_bytes(b"current source must also remain unchanged on rejection")
    path = p.path(tx.relative + "/journal.json")
    journal = load_json(path)
    if legacy:
        journal.pop("scope_digest", None)
    journal["dependencies"].append(target)
    atomic_json(p, path, journal)
    with pytest.raises(InputError):
        tx.restore()
    assert user_file.read_bytes() == b"untouched user project"
    assert p.path(source).read_bytes() == b"current source must also remain unchanged on rejection"


@pytest.mark.parametrize("blocked", ["contention", "quarantine"])
def test_arena_boundary_cannot_be_written_before_project_lock_and_quarantine_preflight(
    tmp_path, monkeypatch, blocked
):
    from contextlib import nullcontext

    from polyforge.contracts.manifest import load_manifest
    from polyforge.contracts.results import Result
    from polyforge.runner.locks import unity_project_lock
    from polyforge.unity import bridge, game
    from polyforge.workspace import init_workspace

    root = tmp_path / "arena"
    init_workspace(root, "simple_arena")
    p = WorkspacePolicy(root)
    model = load_manifest(p.path("game_manifest.json"))
    target = p.path("UnityProject/Assets/PolyForgeGenerated/Game/Models/arena_boundary.fbx")
    p.mkdir(target.parent)
    target.write_bytes(b"original managed boundary")
    folder = p.mkdir("runs/wall_export/asset")
    (folder / "asset.fbx").write_bytes(b"new generated boundary")
    atomic_json(
        p,
        "runs/static/request.json",
        {"assets": [{"id": "ground_a", "materials": [{"id": "grey"}]}]},
    )

    def parent(*args, **kwargs):
        if blocked == "quarantine":
            atomic_json(
                p,
                "UnityProject/.polyforge/repair-quarantine.json",
                {"transaction_id": "other", "status": "ROLLBACK_FAILED"},
            )
        return Result(run_id="static")

    monkeypatch.setattr(bridge, "build_unity", parent)
    monkeypatch.setattr(game, "unity_tool", lambda config: p.path("Unity.exe"))
    monkeypatch.setattr(game, "reusable_export", lambda *a: folder)
    with (
        unity_project_lock(p, p.path("UnityProject")) if blocked == "contention" else nullcontext()
    ):
        result = game.build_game(model, model.recipes)
    assert result.status == "BLOCKED"
    assert target.read_bytes() == b"original managed boundary"
