"""The second game style is a reusable worker capability, with approval boundaries."""

import json

import pytest
from test_phase11_platformer import source_fixture

from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.validation import InputError
from polyforge.security.paths import WorkspacePolicy


def task(inputs):
    return {
        "schema_version": "1.0.0",
        "brief": "Build a 2D checkpoint platformer with grounded jumping and a hazard.",
        "task_class": "BUILD_GAME",
        "domain_tags": ["unity", "2d", "gameplay"],
        "feature_ids": ["grounded_jump", "checkpoint_respawn", "hazard_damage", "goal_contact"],
        "capability_id": "unity.game.platformer.v1",
        "input": inputs,
        "seed": 42,
    }


def test_platformer_capability_is_registered_after_native_qualification():
    from polyforge.capabilities.registry import lookup

    descriptor = lookup("unity.game.platformer.v1")
    assert descriptor["input_schema"] == "contracts/platformer.schema.json"
    assert descriptor["trust_requirement"] == "TRUSTED_LOCAL"
    assert "unity==6000.6.3f1" in descriptor["requires"]


def test_capability_dry_run_uses_same_compiler_and_preserves_files(tmp_path):
    from polyforge.capabilities.dispatch import execute

    inputs = source_fixture(tmp_path)
    before = {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }
    result = execute("unity.game.platformer.v1", inputs, RunContext(tmp_path, dry_run=True))
    assert result.status == "PASS"
    assert result.data["game_contract"]["scene_id"] == inputs["scene_id"]
    assert result.data["execution_status"] == "NOT_RUN"
    assert before == {
        p.relative_to(tmp_path).as_posix(): p.read_bytes()
        for p in tmp_path.rglob("*")
        if p.is_file()
    }


def test_worker_plan_freezes_imported_sprite_inputs_without_arena_substitution(tmp_path):
    from polyforge.workforce.router import plan_task

    inputs = source_fixture(tmp_path)
    request = task(inputs)
    plan = plan_task(request, workspace=tmp_path)
    assert plan["original_request"] == request
    assert [job["role_id"] for job in plan["jobs"]] == [
        "intent_analyst",
        "unity_integration",
        "gameplay_qa_inspector",
    ]
    assert plan["stages"] == ["S0", "S1", "S4", "S5"]
    assert [job["stage"] for job in plan["jobs"]] == ["S1", "S4", "S5"]
    assert plan["jobs"][1]["capability_id"] == "unity.game.platformer.v1"
    assert "game_manifest.json" not in plan["workspace_inputs"]
    assert (
        "UnityProject/Assets/PolyForgeGenerated/Game/PlayableArena.unity"
        not in plan["workspace_inputs"]
    )
    assert inputs["sprite_receipt"] in plan["workspace_inputs"]
    (tmp_path / "UnityProject/Assets/PolyForgeGenerated/Sprites/Sprite.controller").write_bytes(
        b"changed"
    )
    assert plan_task(request, workspace=tmp_path)["task_id"] != plan["task_id"]


def test_platformer_worker_tools_keep_production_and_inspection_separate(tmp_path):
    from polyforge.workforce.permissions import authorize

    policy = WorkspacePolicy(tmp_path)
    assert authorize(policy, "unity_integration", "tool", "unity.game.platformer.v1")
    for role in ("asset_inspector", "asset_producer", "intent_analyst"):
        with pytest.raises(InputError):
            authorize(policy, role, "tool", "unity.game.platformer.v1")


def test_platformer_transaction_snapshots_its_latest_marker(tmp_path):
    from polyforge.unity.transactions import ManagedTransaction

    marker = tmp_path / ".polyforge/platformer-latest.json"
    marker.parent.mkdir()
    original = {"input_digest": "a" * 64, "request": "runs/old/game-input.json"}
    marker.write_text(json.dumps(original))
    tx = ManagedTransaction.create(WorkspacePolicy(tmp_path), "platformer-marker")
    marker.write_text(json.dumps({"request": "runs/new/game-input.json"}))
    tx.restore()
    assert json.loads(marker.read_text()) == original


def test_platformer_knowledge_route_preserves_2d_domain_and_does_not_substitute_3d(tmp_path):
    from polyforge.knowledge.router import route_reference

    policy = WorkspacePolicy(tmp_path)
    request = {
        "schema_version": "1.0.0",
        "output": "GAME",
        "query": "Build a 2D checkpoint platformer",
    }
    routed = route_reference(policy, request)
    assert routed["capability_ids"] == ["unity.game.platformer.v1"]
    assert routed["status"] in {"REVIEW", "BLOCKED"}
    assert (
        route_reference(policy, {**request, "query": "Build a 3D checkpoint platformer"})[
            "capability_ids"
        ]
        == []
    )


def test_platformer_cli_nonobject_is_a_structured_input_error(tmp_path, capsys):
    from polyforge.cli import main

    (tmp_path / "request.json").write_text("[]")
    assert (
        main(
            [
                "platformer",
                "build",
                "--workspace",
                str(tmp_path),
                "--input",
                "request.json",
                "--json",
            ]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["status"] == "FAIL"


@pytest.mark.parametrize("inputs", [[], None, True, 42, "request"])
def test_capability_nonobject_is_rejected_before_writes(tmp_path, inputs):
    from polyforge.capabilities.dispatch import execute

    with pytest.raises(InputError):
        execute("unity.game.platformer.v1", inputs, RunContext(tmp_path, dry_run=True))
    assert not list(tmp_path.iterdir())


def test_operation_receipt_fingerprints_editable_platformer_build(tmp_path):
    from polyforge.contracts.results import Result
    from polyforge.workforce.operations import complete, operation_context, recover

    inputs = source_fixture(tmp_path)
    build = "platformer-build-" + "a" * 16
    folder = tmp_path / "runs" / build
    folder.mkdir()
    archive = folder / "native-output.zip"
    archive.write_bytes(b"editable native build")
    check = "platformer-check-" + "b" * 16
    (tmp_path / "runs" / check).mkdir()
    result = Result(run_id=check, data={"build_run_id": build})
    context = operation_context(tmp_path, "task", "build", 42, None)
    complete("unity.game.platformer.v1", inputs, context, result)
    assert recover("unity.game.platformer.v1", inputs, context) == result
    archive.write_bytes(b"changed source delivery")
    with pytest.raises(InputError, match="output changed"):
        recover("unity.game.platformer.v1", inputs, context)


@pytest.mark.parametrize("missing", [None, "archive", "bindings", "delivery", "standalone"])
def test_inspector_requires_sealed_editable_delivery_and_requested_standalone(
    tmp_path, monkeypatch, missing
):
    from test_phase11_platformer import native_boundary

    from polyforge.contracts.validation import canonical_digest
    from polyforge.unity import evidence
    from polyforge.workforce.workers import inspect_candidate, seal_candidate

    # Only the native process/XML/oracle boundaries are simulated here.
    # Actual native qualification is a separate reported gate.
    module, _ = native_boundary(monkeypatch, tmp_path)
    from polyforge.scenarios.platformer_oracle import (
        CORE_SCENARIOS,
        INPUT_SCENARIOS,
        MUTANT_SCENARIOS,
    )

    boundary_launch = module.launch

    def launch(*args, **kwargs):
        boundary_launch(*args, **kwargs)
        if args[4] == "platformer":
            folder = tmp_path / "UnityProject/Assets/PolyForgeGenerated/Platformer"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "SpritePlatformer.unity").write_text("unit native-scene boundary")
            (folder / "SpritePlatformer.unity.meta").write_text("guid: " + "1" * 32)
        if args[4] == "tests":
            telemetry = kwargs["telemetry_directory"]
            telemetry.mkdir(parents=True, exist_ok=True)
            for identifier in (*CORE_SCENARIOS, *INPUT_SCENARIOS, *MUTANT_SCENARIOS):
                (telemetry / (identifier + ".json")).write_text("{}")

    monkeypatch.setattr(module, "launch", launch)
    inputs = source_fixture(tmp_path)
    result = module.build_platformer(tmp_path, inputs)
    candidate = seal_candidate(
        WorkspacePolicy(tmp_path), result, canonical_digest(task(inputs)["brief"])
    )
    monkeypatch.setattr(evidence, "verify_test_xml", lambda *args: {})
    request = task(inputs)
    if missing in {"archive", "bindings", "delivery"}:
        suffix = {
            "archive": "/native-output.zip",
            "bindings": "/bindings.json",
            "delivery": "/delivery.json",
        }[missing]
        candidate["files"] = [row for row in candidate["files"] if not row["path"].endswith(suffix)]
        candidate["candidate_digest"] = canonical_digest(
            {k: v for k, v in candidate.items() if k != "candidate_digest"}
        )
    elif missing == "standalone":
        import hashlib

        delivery = tmp_path / "runs" / result.run_id / "delivery.json"
        value = json.loads(delivery.read_text())
        value["standalone_requested"] = True
        delivery.write_text(json.dumps(value))
        for row in candidate["files"]:
            if row["path"].endswith("/delivery.json"):
                row["sha256"] = hashlib.sha256(delivery.read_bytes()).hexdigest()
        candidate["candidate_digest"] = canonical_digest(
            {k: v for k, v in candidate.items() if k != "candidate_digest"}
        )
    if missing is None:
        assert (
            inspect_candidate(WorkspacePolicy(tmp_path), candidate, request, technical_only=True)[
                "verdict"
            ]
            == "APPROVED"
        )
        from polyforge.review.board import review_candidate

        board = review_candidate(WorkspacePolicy(tmp_path), candidate, request)
        assert board["promotion"] == "REVIEW"
        assert board["acceptance"]["game_status"] == "PARTIAL"
    else:
        with pytest.raises(InputError):
            inspect_candidate(WorkspacePolicy(tmp_path), candidate, request, technical_only=True)


@pytest.mark.parametrize(
    "fault", [None, "scene", "guid", "atlas", "duplicate", "prefab", "controller", "clip"]
)
def test_editable_archive_is_bound_to_scene_and_imported_sprite(tmp_path, fault):
    import hashlib
    import zipfile

    from polyforge.workforce import workers

    archive = tmp_path / "native-output.zip"
    scene = "Assets/PolyForgeGenerated/Platformer/SpritePlatformer.unity"
    prefab = "Assets/PolyForgeGenerated/Sprites/Robot2D.prefab"
    files = {
        scene: b"editable scene",
        scene + ".meta": b"guid: " + b"1" * 32,
        prefab: b"prefab",
        prefab + ".meta": b"guid: " + b"2" * 32,
        "Assets/PolyForgeGenerated/Sprites/atlas.png": b"atlas",
        "Assets/PolyForgeGenerated/Sprites/Sprite.controller": b"approved controller",
        "Assets/PolyForgeGenerated/Sprites/Walk.anim": b"approved clip",
    }
    game = {
        "scene_path": scene,
        "sprite_prefab": prefab,
        "sprite_prefab_guid": "2" * 32,
        "atlas_sha256": hashlib.sha256(b"atlas").hexdigest(),
        "source_hashes": {
            "UnityProject/" + name: hashlib.sha256(value).hexdigest()
            for name, value in files.items()
            if name != scene and name != scene + ".meta"
        },
    }
    if fault == "scene":
        del files[scene]
    elif fault == "guid":
        files[prefab + ".meta"] = b"guid: " + b"3" * 32
    elif fault == "atlas":
        files["Assets/PolyForgeGenerated/Sprites/atlas.png"] = b"wrong sprite source"
    elif fault in {"prefab", "controller", "clip"}:
        name = {
            "prefab": prefab,
            "controller": "Assets/PolyForgeGenerated/Sprites/Sprite.controller",
            "clip": "Assets/PolyForgeGenerated/Sprites/Walk.anim",
        }[fault]
        files[name] = b""
    with zipfile.ZipFile(archive, "w") as output:
        for name, data in files.items():
            output.writestr(name, data)
        if fault == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                output.writestr(scene, b"second ambiguous scene")
    verify = getattr(workers, "verify_platformer_archive", None)
    assert callable(verify), "Editable archive verification is missing"
    if fault is None:
        verify(archive, game, "1" * 32)
    else:
        with pytest.raises(InputError):
            verify(archive, game, "1" * 32)
