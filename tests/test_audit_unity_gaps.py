"""Regression checks for the original supplied-texture/collider/obstacle duties."""

import copy
import hashlib
import json
import struct
import zlib

import pytest

from polyforge.contracts.validation import InputError
from polyforge.unity.evidence import reconcile_report


def complete_native():
    from test_phase5_contracts import native_contract_fixture

    request, report = native_contract_fixture()
    request["scene_bounds_m"] = [20, 5, 20]
    request["assets"][0]["collider"] = "box"
    request["actors"] = [{"id": "enemy", "asset_id": "robot", "spawn_xyz": [3, 0, 2]}]
    report["objects"][0].update(
        collider="box",
        colliders=[
            dict(
                kind="BoxCollider",
                path="",
                enabled=True,
                is_trigger=False,
                center_m=[0, 1, 0],
                size_m=[1, 2, 3],
            )
        ],
    )
    report.update(camera_count=2, light_count=2, scene_instances=[])
    for scene in ("Arena", "Training"):
        for identifier, position in (("asset:robot", [0, 0, 0]), ("actor:enemy", [3, 0, 2])):
            report["scene_instances"].append(
                dict(
                    scene=scene,
                    id=identifier,
                    asset_id="robot",
                    prefab_guid="b" * 32,
                    source_guid="a" * 32,
                    position_m=position,
                    scale=[1, 1, 1],
                    rotation_xyzw=[0, 0, 0, 1],
                )
            )
    return request, report


@pytest.mark.parametrize(
    "field,value",
    [
        ("collider", "none"),
        ("colliders", []),
    ],
)
def test_collider_intent_is_independently_checked(field, value):
    request, report = complete_native()
    assert reconcile_report(request, report)["status"] == "PASS"
    report["objects"][0][field] = value
    assert reconcile_report(request, report)["status"] == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("enabled", False),
        ("is_trigger", True),
        ("kind", "CapsuleCollider"),
        ("center_m", [0, 0, 0]),
        ("size_m", [1, 2, 30]),
        ("path", "wrong/child"),
    ],
)
def test_collider_geometry_and_state_cannot_hide_behind_worker_pass(field, value):
    request, report = complete_native()
    report["objects"][0]["colliders"][0][field] = value
    assert reconcile_report(request, report)["status"] == "FAIL"


def test_capsule_direction_and_mesh_filter_references_are_checked():
    request, report = complete_native()
    asset, actual = request["assets"][0], report["objects"][0]
    asset["collider"] = actual["collider"] = "capsule"
    actual["colliders"][0].update(kind="CapsuleCollider", size_m=[3, 3, 3], direction=1)
    assert reconcile_report(request, report)["status"] == "PASS"
    actual["colliders"][0]["direction"] = 0
    assert reconcile_report(request, report)["status"] == "FAIL"
    asset["collider"] = actual["collider"] = "mesh"
    node = next(n for n in actual["nodes"] if n["kind"] == "module")
    node.update(mesh_guid="a" * 32, mesh_local_id=300)
    actual["colliders"] = [
        dict(
            kind="MeshCollider",
            path=node["path"],
            enabled=True,
            is_trigger=False,
            mesh_guid="a" * 32,
            mesh_local_id=300,
            convex=False,
        )
    ]
    assert reconcile_report(request, report)["status"] == "PASS"
    actual["colliders"][0]["mesh_local_id"] = 301
    assert reconcile_report(request, report)["status"] == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("scene_instances", []),
        ("camera_count", 0),
        ("light_count", 0),
    ],
)
def test_scene_observables_are_required(field, value):
    request, report = complete_native()
    report[field] = value
    assert reconcile_report(request, report)["status"] == "FAIL"
    del report[field]
    assert reconcile_report(request, report)["status"] == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("scene", "Unknown"),
        ("id", "actor:other"),
        ("asset_id", "other"),
        ("prefab_guid", "c" * 32),
        ("source_guid", "b" * 32),
        ("position_m", [1, 0, 0]),
        ("scale", [1, 2, 1]),
        ("rotation_xyzw", [0, 1, 0, 0]),
    ],
)
def test_scene_identity_pose_and_prefab_source_are_independent(field, value):
    request, report = complete_native()
    report["scene_instances"][0][field] = value
    assert reconcile_report(request, report)["status"] == "FAIL"


def png():
    def chunk(kind, payload):
        return (
            struct.pack(">I", len(payload))
            + kind
            + payload
            + struct.pack(">I", zlib.crc32(kind + payload))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x80\x80\xff\xff" * 2) * 2))
        + chunk(b"IEND", b"")
    )


def texture_model(tmp_path):
    from polyforge.contracts.manifest import load_manifest
    from polyforge.workspace import init_workspace

    init_workspace(tmp_path, "simple_arena")
    (tmp_path / "supplied").mkdir()
    (tmp_path / "supplied/color.png").write_bytes(png())
    (tmp_path / "supplied/normal.png").write_bytes(png())
    path = tmp_path / "game_manifest.json"
    data = json.loads(path.read_text())
    data["materials"][0]["textures"] = [
        dict(kind="base_color", path="supplied/color.png", color_space="srgb"),
        dict(kind="normal", path="supplied/normal.png", color_space="linear"),
    ]
    path.write_text(json.dumps(data))
    return load_manifest(path)


def test_supplied_textures_are_copied_exactly_with_frozen_hash_provenance(tmp_path):
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity import bridge

    model = texture_model(tmp_path / "arena")
    specs = [{"id": "robot", "materials": [{"id": model.data["materials"][0]["id"]}]}]
    project = model.workspace / "UnityProject"
    bridge.copy_material_textures(WorkspacePolicy(model.workspace), project, model, specs)
    for record in specs[0]["materials"][0]["textures"]:
        assert (project / record["path"]).read_bytes() == png()
        assert record["sha256"] == hashlib.sha256(png()).hexdigest()
        assert record["source_path"].startswith("supplied/")
        assert record["color_space"] == ("srgb" if record["kind"] == "base_color" else "linear")
    (model.workspace / "supplied/color.png").write_bytes(png() + b"changed")
    with pytest.raises(InputError):
        bridge.copy_material_textures(WorkspacePolicy(model.workspace), project, model, specs)


def test_texture_dry_run_is_supported_and_has_no_writes(tmp_path):
    from polyforge.blender.build import build_assets

    model = texture_model(tmp_path / "arena")
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    result = build_assets(model.workspace, through="S4", dry_run=True)
    assert result.status == "PASS", result.to_dict()
    assert before == {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "field,value",
    [
        ("srgb", False),
        ("texture_type", "NormalMap"),
        ("sha256", "0" * 64),
        ("path", "Assets/User.png"),
        ("material_texture_path", ""),
        ("convert_to_normal", True),
    ],
)
def test_texture_native_observables_are_independently_checked(field, value):
    request, report = complete_native()
    path = "Assets/PolyForgeGenerated/Textures/robot/blue/base_color.png"
    request["assets"][0]["materials"][0]["textures"] = [
        dict(
            kind="base_color",
            path=path,
            sha256="a" * 64,
            source_path="supplied/color.png",
            color_space="srgb",
        )
    ]
    report["objects"][0]["textures"] = [
        dict(
            material_id="blue",
            kind="base_color",
            path=path,
            sha256="a" * 64,
            srgb=True,
            texture_type="Default",
            material_texture_path=path,
            normal_keyword=False,
            convert_to_normal=False,
            has_texture=True,
        )
    ]
    from test_phase5_contracts import empty_texture_slots

    report["objects"][0]["textures"].append(empty_texture_slots("blue")[1])
    assert reconcile_report(request, report)["status"] == "PASS"
    report["objects"][0]["textures"][0][field] = value
    assert reconcile_report(request, report)["status"] == "FAIL"


def test_requested_texture_observations_cannot_be_omitted():
    request, report = complete_native()
    request["assets"][0]["materials"][0]["textures"] = [
        dict(kind="normal", path="normal.png", sha256="a" * 64)
    ]
    assert reconcile_report(request, report)["status"] == "FAIL"


def test_both_empty_texture_slots_are_observed_and_missing_slots_fail():
    request, report = complete_native()
    report["objects"][0]["textures"] = []
    assert reconcile_report(request, report)["status"] == "FAIL"


def test_empty_texture_slot_observations_pass_without_undeclared_references():
    request, report = complete_native()
    report["objects"][0]["textures"] = [
        dict(
            material_id="blue",
            kind=role,
            path="",
            sha256="",
            srgb=False,
            texture_type="missing",
            material_texture_path="",
            has_texture=False,
            normal_keyword=False,
            convert_to_normal=False,
        )
        for role in ("base_color", "normal")
    ]
    assert reconcile_report(request, report)["status"] == "PASS"
    for field, value in (
        ("has_texture", True),
        ("normal_keyword", True),
        ("material_texture_path", "Assets/unexpected.png"),
    ):
        changed = copy.deepcopy(report)
        changed["objects"][0]["textures"][0][field] = value
        assert reconcile_report(request, changed)["status"] == "FAIL"


def test_original_mutation_ids_remain_stable_and_obstacle_is_m7(tmp_path, monkeypatch):
    from test_phase9_mutations import GAME, populated

    from polyforge.unity.game import score_telemetry

    policy = populated(tmp_path, monkeypatch)
    results = score_telemetry(policy, "runs/probe", GAME)["scenarios"]
    for identifier, mutation_id in {
        "collision_disabled": "M1",
        "restart_disabled": "M2",
        "win_reversed": "M3",
        "damage_no_health": "M4",
        "navigation_stuck": "M5",
        "input_disconnected": "M6",
        "obstacle_collision_disabled": "M7",
    }.items():
        assert results[identifier]["mutation_id"] == mutation_id


def obstacle_trace():
    return dict(
        scenario_id="obstacle_collision",
        frames_executed=100,
        events=[],
        player_radius=0.35,
        obstacle_id="Obstacle_0",
        obstacle_asset_id="crate",
        obstacle_center_m=[0, 0.5, 0],
        obstacle_size_m=[1, 1, 1],
        samples=[
            dict(frame=0, player_position=[-2.85, 0, 0]),
            dict(frame=100, player_position=[-0.88, 0, 0]),
        ],
    )


def test_obstacle_oracle_requires_actual_blocking_and_kills_disabled_obstacle():
    from polyforge.scenarios.arena_oracle import CORE_SCENARIOS, MUTANT_SCENARIOS, evaluate

    assert "obstacle_collision" in CORE_SCENARIOS
    assert MUTANT_SCENARIOS["obstacle_collision_disabled"] == "obstacle_collision"
    trace = obstacle_trace()
    assert evaluate(trace)["status"] == "PASS"
    for final in ([-2.85, 0, 0], [4, 0, 0], [-0.88, 0, 3]):
        changed = copy.deepcopy(trace)
        changed["samples"][-1]["player_position"] = final
        assert evaluate(changed)["status"] == "FAIL"


def test_frozen_acceptance_includes_obstacles():
    from importlib.resources import files

    acceptance = json.loads(files("polyforge").joinpath("data/arena_acceptance.json").read_text())
    assert any(
        "obstacle_collision" in row["oracles"] and "obstacles" in row["original_phrase"]
        for row in acceptance["requirements"]
    )


def test_scene_rotation_uses_the_native_angular_tolerance():
    import math

    request, report = complete_native()
    report["scene_instances"][0]["rotation_xyzw"] = [0, 0.001, 0, math.sqrt(1 - 0.001**2)]
    assert reconcile_report(request, report)["status"] == "FAIL"


def test_s3_supplied_texture_bundle_is_registered_with_source_fingerprints(tmp_path, monkeypatch):
    from polyforge.blender import build
    from polyforge.contracts.results import Result

    model = texture_model(tmp_path / "arena")
    monkeypatch.setattr(
        build,
        "execute_recipe",
        lambda *args, **kwargs: Result(data={"source_blend": "runs/fixture/asset.blend"}),
    )
    result = build.build_assets(model.workspace, through="S3")
    assert result.status == "PASS", result.to_dict()
    folder = model.workspace / "runs" / result.run_id
    registry = json.loads((folder / "artifacts.json").read_text())["artifacts"]
    summary = json.loads((folder / "summary.json").read_text())
    copied = [a for a in registry if a["kind"] == "png"]
    assert copied
    assert (
        summary["input_fingerprints"]["files"]["supplied/color.png"]
        == hashlib.sha256(png()).hexdigest()
    )
    for record in copied:
        assert record["sha256"] == record["source_sha256"] == hashlib.sha256(png()).hexdigest()
        assert record["run_id"] == result.run_id
        assert record["stage"] == "S3"
        assert record["upstream_input_hashes"] == [model.input_digest]
        assert record["artifact_id"] in result.artifact_ids
        assert (model.workspace / record["relative_path"]).read_bytes() == png()


@pytest.mark.parametrize("contents", [b"not an image", png() + b"trailing data"])
def test_invalid_supplied_png_is_rejected_before_any_output(tmp_path, monkeypatch, contents):
    from polyforge.blender import build
    from polyforge.contracts.manifest import load_manifest

    model = texture_model(tmp_path / "arena")
    (model.workspace / "supplied/normal.png").write_bytes(contents)
    model = load_manifest(model.workspace / "game_manifest.json")
    before = {p: p.read_bytes() for p in model.workspace.rglob("*") if p.is_file()}
    monkeypatch.setattr(
        build, "execute_recipe", lambda *a, **k: pytest.fail("Native execution preceded validation")
    )
    with pytest.raises(InputError):
        build.build_assets(model.workspace, through="S3")
    assert before == {p: p.read_bytes() for p in model.workspace.rglob("*") if p.is_file()}


def test_obstacle_telemetry_must_match_frozen_geometry_and_semantic_identity():
    from polyforge.scenarios.arena_oracle import validate_trace

    trace = obstacle_trace()
    trace.update(
        input_digest="a" * 64, scene_id="main", purpose="NOMINAL", seed=42, fixed_delta_seconds=0.02
    )
    for sample in trace["samples"]:
        sample.update(
            round=1,
            state="RUNNING",
            health=100,
            elapsed_seconds=sample["frame"] * 0.02,
            enemy_positions=[dict(id="enemy", position=[3, 0, 3])],
        )
    game = dict(
        input_digest="a" * 64,
        scene_id="main",
        seed=42,
        enemies=[dict(id="enemy")],
        obstacles=[dict(id="Obstacle_0", asset_id="crate", center_m=[0, 0.5, 0], size_m=[1, 1, 1])],
    )
    validate_trace(trace, game, "obstacle_collision", 100)
    for field, value in (
        ("obstacle_id", "other"),
        ("obstacle_size_m", [1, 1, 2]),
        ("obstacle_center_m", [1, 0.5, 0]),
        ("player_radius", 0),
    ):
        changed = copy.deepcopy(trace)
        changed[field] = value
        with pytest.raises(InputError):
            validate_trace(changed, game, "obstacle_collision", 100)
        del changed[field]
        with pytest.raises(InputError):
            validate_trace(changed, game, "obstacle_collision", 100)
