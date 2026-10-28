"""Phase6 independent behavior contracts, usable with Unity and models absent."""

from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError


def test_public_movement_oracle_requires_observed_motion_not_success_events():
    from polyforge.scenarios.arena_oracle import evaluate

    trace = {
        "scenario_id": "player_moves",
        "samples": [
            {
                "frame": 0,
                "player_position": [0, 0, 0],
                "health": 100,
                "state": "RUNNING",
                "elapsed_seconds": 0,
            },
            {
                "frame": 50,
                "player_position": [0, 0, 0],
                "health": 100,
                "state": "RUNNING",
                "elapsed_seconds": 1,
            },
        ],
        "events": [{"name": "player_moved"}],
        "frames_executed": 50,
        "input_digest": "a" * 64,
    }
    assert evaluate(trace)["status"] == "FAIL"
    trace["samples"][1]["player_position"] = [0, 0, 4]
    assert evaluate(trace)["status"] == "PASS"


def test_collision_oracle_detects_disabled_walls_and_restart_oracle_requires_state_reset():
    from polyforge.scenarios.arena_oracle import evaluate

    trace = {
        "scenario_id": "wall_collision",
        "samples": [
            {"frame": 0, "player_position": [-7, 0, 0]},
            {"frame": 200, "player_position": [-23, 0, 0]},
        ],
        "events": [],
        "frames_executed": 200,
        "arena_half_extents": [10, 10],
        "player_radius": 0.35,
        "wall_thickness": 0.5,
    }
    assert evaluate(trace)["status"] == "FAIL"
    trace["samples"][-1]["player_position"] = [-9.1, 0, 0]
    assert evaluate(trace)["status"] == "PASS"
    restart = {
        "scenario_id": "restart_resets",
        "frames_executed": 100,
        "samples": [
            {
                "frame": 0,
                "state": "FAILED",
                "health": 0,
                "elapsed_seconds": 2,
                "round": 1,
                "player_position": [3, 0, 3],
            },
            {
                "frame": 100,
                "state": "FAILED",
                "health": 0,
                "elapsed_seconds": 2,
                "round": 1,
                "player_position": [3, 0, 3],
            },
        ],
        "events": [{"name": "restarted"}],
        "baseline_player_position": [-3, 0, -3],
    }
    assert evaluate(restart)["status"] == "FAIL"


def test_unsupported_gameplay_rejected_before_any_writes(tmp_path: Path):
    import json

    from polyforge.contracts.manifest import load_manifest
    from polyforge.unity.game import compile_game_request
    from polyforge.workspace import init_workspace

    root = tmp_path / "arena"
    init_workspace(root, "simple_arena")
    path = root / "game_manifest.json"
    data = json.loads(path.read_text())
    data["gameplay"]["win_condition"] = "collect_objective"
    path.write_text(json.dumps(data))
    before = set(root.rglob("*"))
    with pytest.raises(InputError):
        compile_game_request(load_manifest(path))
    assert set(root.rglob("*")) == before


def test_core_scenario_data_validates_bounded_setup_and_known_entities():
    import json
    from importlib.resources import files

    from polyforge.scenarios.schema import validate_scenario

    suite = json.loads(files("polyforge").joinpath("data/arena_scenarios.json").read_text())
    for scenario in suite["scenarios"]:
        validate_scenario(scenario, scene_id="main", entity_ids={"player_01", "enemy_01"})


def test_patrol_oracle_reads_native_enemy_position_records():
    from polyforge.scenarios.arena_oracle import evaluate

    trace = {
        "scenario_id": "enemy_patrols",
        "frames_executed": 150,
        "events": [],
        "samples": [
            {
                "player_position": [0, 0, 0],
                "enemy_positions": [{"id": "enemy", "position": [3, 0, 3]}],
            },
            {
                "player_position": [0, 0, 0],
                "enemy_positions": [{"id": "enemy", "position": [5, 0, 4]}],
            },
        ],
    }
    assert evaluate(trace)["status"] == "PASS"


def test_playmode_launch_is_distinct_and_rejects_unknown_test_filters_before_writes(
    tmp_path: Path, monkeypatch
):
    from polyforge.config import Config
    from polyforge.runner.processes import ProcessOutcome
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity import bridge

    monkeypatch.setattr(
        bridge,
        "run_process",
        lambda *a, **k: ProcessOutcome(0, "exit", 1, "WINDOWS_JOB", 0, "", "", True),
    )
    result = bridge.launch(
        WorkspacePolicy(tmp_path),
        Path("Unity.exe"),
        Config(),
        "play",
        "tests",
        output=tmp_path / "play.xml",
        test_platform="PlayMode",
        test_filter="PolyForge.Game.Tests",
    )
    assert result["argv"][result["argv"].index("-testPlatform") + 1] == "PlayMode"
    assert "-quit" not in result["argv"]
    before = set(tmp_path.rglob("*"))
    with pytest.raises(InputError):
        bridge.launch(
            WorkspacePolicy(tmp_path),
            Path("Unity.exe"),
            Config(),
            "bad",
            "tests",
            output=tmp_path / "bad.xml",
            test_filter="Fake.Empty.Tests",
        )
    assert set(tmp_path.rglob("*")) == before


def test_s5_dry_run_is_model_free_and_has_no_filesystem_changes(tmp_path: Path):
    from polyforge.blender.build import build_assets
    from polyforge.workspace import init_workspace

    root = tmp_path / "arena"
    init_workspace(root, "simple_arena")
    before = {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()}
    result = build_assets(root, through="S5", dry_run=True)
    assert result.status == "PASS", result.to_dict()
    assert result.data["through"] == "S5"
    assert {str(p): p.read_bytes() for p in root.rglob("*") if p.is_file()} == before


def test_package_upgrade_requires_recorded_old_bytes_and_preserves_modified_user_code(
    tmp_path: Path,
):
    import hashlib
    import zipfile

    from polyforge.runner.state import atomic_json
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity.upgrade import sync_package

    p = WorkspacePolicy(tmp_path)
    folder = p.mkdir("UnityProject/Packages/com.polyforge.engine")
    (folder / "Runtime.cs").write_bytes(b"old reviewed code")
    archive = p.path("runs/unity-old/native-output.zip")
    p.mkdir(archive.parent)
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr("Packages/com.polyforge.engine/Runtime.cs", b"old reviewed code")
    atomic_json(
        p,
        "runs/unity-old/artifacts.json",
        {
            "artifacts": [
                {
                    "relative_path": "runs/unity-old/native-output.zip",
                    "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
                }
            ]
        },
    )
    atomic_json(p, ".polyforge/unity-latest.json", {"run_id": "unity-old"})
    assert sync_package(p, {"Runtime.cs": b"new engine code"}) is not None
    assert (folder / "Runtime.cs").read_bytes() == b"new engine code"
    assert sync_package(p, {"Runtime.cs": b"new engine code"}) is None
    (folder / "Runtime.cs").write_bytes(b"user modification")
    with pytest.raises(InputError):
        sync_package(p, {"Runtime.cs": b"next engine code"})
    assert (folder / "Runtime.cs").read_bytes() == b"user modification"


@pytest.mark.parametrize("fault", ["hash", "missing", "oversized"])
def test_package_upgrade_rejects_unproven_baselines(tmp_path, fault):
    import hashlib
    import zipfile

    from polyforge.runner.state import atomic_json
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity.upgrade import sync_package

    p = WorkspacePolicy(tmp_path)
    folder = p.mkdir("UnityProject/Packages/com.polyforge.engine")
    (folder / "Runtime.cs").write_bytes(b"original")
    archive = p.path("runs/old/native-output.zip")
    p.mkdir(archive.parent)
    with zipfile.ZipFile(archive, "w") as z:
        z.writestr(
            "Packages/com.polyforge.engine/Runtime.cs",
            b"x" * 1048577 if fault == "oversized" else b"original",
        )
    entries = (
        []
        if fault == "missing"
        else [
            {
                "relative_path": "runs/old/native-output.zip",
                "sha256": "0" * 64
                if fault == "hash"
                else hashlib.sha256(archive.read_bytes()).hexdigest(),
            }
        ]
    )
    atomic_json(p, "runs/old/artifacts.json", {"artifacts": entries})
    atomic_json(p, ".polyforge/unity-latest.json", {"run_id": "old"})
    with pytest.raises(InputError):
        sync_package(p, {"Runtime.cs": b"upgrade"})
    assert (folder / "Runtime.cs").read_bytes() == b"original"


def test_package_resources_bootstrap_through_the_same_upgrade_guard(tmp_path):
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity.upgrade import sync_package

    policy = WorkspacePolicy(tmp_path)
    assert sync_package(policy) is not None
    assert policy.path("UnityProject/Packages/com.polyforge.engine/Runtime/Health.cs").is_file()
    assert sync_package(policy) is None


def test_development_benchmark_inventory_has_frozen_briefs_and_separate_task_classes():
    import hashlib
    import json
    from collections import Counter

    from polyforge.contracts.validation import validate_schema

    root = Path(__file__).resolve().parents[1] / "benchmarks/development-v1"
    suite = json.loads((root / "suite.json").read_text())
    assert suite["status"] == "NOT_RUN"
    assert Counter(t["task_type"] for t in suite["tasks"]) == {
        "ASSET": 4,
        "ANIMATION_IMPORT": 2,
        "GAME_MECHANIC": 3,
        "CROSS_ENGINE_REPAIR": 2,
        "COMPLETE_GAME_2D": 1,
    }
    for task in suite["tasks"]:
        validate_schema(task, "benchmark_task.schema.json")
        assert task["ownership"] == "DEV_FIXTURE"
        assert (
            task["original_brief_sha256"]
            == hashlib.sha256(
                (root / "briefs" / (task["task_id"] + ".md")).read_bytes()
            ).hexdigest()
        )


def test_vertical_falling_cannot_satisfy_movement_or_patrol():
    from polyforge.scenarios.arena_oracle import evaluate

    trace = {
        "scenario_id": "player_moves",
        "frames_executed": 50,
        "events": [],
        "samples": [{"player_position": [0, 0, 0]}, {"player_position": [0, -4, 0]}],
    }
    assert evaluate(trace)["status"] == "FAIL"


def test_trace_identity_and_execution_are_required_before_mutant_scoring():
    from polyforge.scenarios.arena_oracle import validate_trace

    game = {"input_digest": "a" * 64, "scene_id": "main", "seed": 42, "enemies": [{"id": "enemy"}]}
    bad = {
        "input_digest": "a" * 64,
        "scenario_id": "wall_collision",
        "purpose": "MUTANT",
        "mutant": "collision_disabled",
        "seed": 42,
        "scene_id": "main",
        "fixed_delta_seconds": 0.02,
        "frames_executed": 0,
        "samples": [],
        "events": [],
    }
    with pytest.raises(InputError):
        validate_trace(bad, game, "collision_disabled", 200)
    bad["input_digest"] = "b" * 64
    with pytest.raises(InputError):
        validate_trace(bad, game, "collision_disabled", 200)


def test_restart_must_restore_enemy_positions_too():
    from polyforge.scenarios.arena_oracle import evaluate

    trace = {
        "scenario_id": "restart_resets",
        "frames_executed": 76,
        "baseline_player_position": [-3, 0, -3],
        "baseline_enemy_positions": [{"id": "enemy", "position": [3, 0, 3]}],
        "events": [],
        "samples": [
            {
                "player_position": [3, 0, 2],
                "health": 25,
                "state": "RUNNING",
                "elapsed_seconds": 0,
                "round": 1,
                "enemy_positions": [{"id": "enemy", "position": [3, 0, 3]}],
            },
            {
                "player_position": [-3, 0, -3],
                "health": 100,
                "state": "RUNNING",
                "elapsed_seconds": 0,
                "round": 2,
                "enemy_positions": [{"id": "enemy", "position": [8, 0, 8]}],
            },
        ],
    }
    assert evaluate(trace)["status"] == "FAIL"


def test_mandatory_unimplemented_features_are_blocked_before_generation(tmp_path: Path):
    import json

    from polyforge.contracts.manifest import load_manifest
    from polyforge.unity.game import compile_game_request
    from polyforge.workspace import init_workspace

    root = tmp_path / "arena"
    init_workspace(root, "simple_arena")
    path = root / "game_manifest.json"
    data = json.loads(path.read_text())
    data["intent"]["requirements"][0]["feature_id"] = "animation.robot.v1"
    path.write_text(json.dumps(data))
    model = load_manifest(path)
    with pytest.raises(InputError):
        compile_game_request(model)


def observed_trace(identifier="player_moves"):
    """Small independent trace for metadata and state validation faults."""
    game = {"input_digest": "a" * 64, "scene_id": "main", "seed": 42, "enemies": [{"id": "enemy"}]}

    def sample(frame):
        return {
            "frame": frame,
            "player_position": [0, 0, frame / 10],
            "health": 100,
            "state": "RUNNING",
            "round": 1,
            "elapsed_seconds": frame * 0.02,
            "enemy_positions": [{"id": "enemy", "position": [3, 0, 3]}],
        }

    trace = {
        **{k: game[k] for k in ("input_digest", "scene_id", "seed")},
        "scenario_id": identifier,
        "purpose": "NOMINAL",
        "mutant": "",
        "fixed_delta_seconds": 0.02,
        "frames_executed": 50,
        "samples": [sample(0), sample(50)],
        "events": [],
    }
    return game, trace


@pytest.mark.parametrize(
    "fault", ["digest", "frames", "health", "state", "enemy", "vector", "round", "time"]
)
def test_observed_trace_rejects_contract_faults(fault):
    from polyforge.scenarios.arena_oracle import validate_trace

    game, trace = observed_trace()
    validate_trace(trace, game, "player_moves", 50)
    if fault == "digest":
        trace["input_digest"] = "b" * 64
    elif fault == "frames":
        trace["samples"][-1]["frame"] = 0
    elif fault == "health":
        trace["samples"][-1]["health"] = -1
    elif fault == "state":
        trace["samples"][-1]["state"] = "ACCEPTED"
    elif fault == "enemy":
        trace["samples"][-1]["enemy_positions"] = []
    elif fault == "vector":
        trace["samples"][-1]["player_position"] = ["x", 0, 0]
    elif fault == "round":
        trace["samples"][-1]["round"] = 0
    else:
        trace["samples"][-1]["elapsed_seconds"] = -1
    with pytest.raises(InputError):
        validate_trace(trace, game, "player_moves", 50)


@pytest.mark.parametrize(
    "identifier", ["contact_damage", "health_failure", "survival_win", "restart_resets"]
)
def test_state_oracles_require_observed_outcomes(identifier):
    from polyforge.scenarios.arena_oracle import evaluate

    _, trace = observed_trace(identifier)
    assert evaluate(trace)["status"] == "FAIL"
    last = trace["samples"][-1]
    if identifier == "contact_damage":
        last["health"] = 75
        trace["events"] = [{"name": "damage"}]
    elif identifier == "health_failure":
        last.update(health=0, state="FAILED")
    elif identifier == "survival_win":
        last.update(elapsed_seconds=30, state="WON")
    else:
        last.update(player_position=[0, 0, 0], elapsed_seconds=0, round=2)
        trace["baseline_player_position"] = [0, 0, 0]
        trace["baseline_enemy_positions"] = [{"id": "enemy", "position": [3, 0, 3]}]
    assert evaluate(trace)["status"] == "PASS"


def test_artifact_registry_seals_evidence_without_copying_player_binaries(tmp_path):
    import hashlib
    import json

    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity.game import register_game_artifacts

    policy = WorkspacePolicy(tmp_path)
    policy.mkdir("runs/check/player")
    policy.path("runs/check/result.xml").write_bytes(b"observed XML")
    policy.path("runs/check/player/arena.exe").write_bytes(b"local player")
    ids = register_game_artifacts(policy, "runs/check", "a" * 64)
    assert ids == ["runs/check/result.xml"]
    registry = json.loads(policy.path("runs/check/artifacts.json").read_text())
    assert registry["artifacts"][0]["sha256"] == hashlib.sha256(b"observed XML").hexdigest()


def test_unknown_or_unexecuted_oracles_fail():
    from polyforge.scenarios.arena_oracle import evaluate

    _, trace = observed_trace("invented")
    assert evaluate(trace)["status"] == "FAIL"
    trace["frames_executed"] = 0
    assert evaluate(trace)["status"] == "FAIL"


@pytest.mark.parametrize(
    "field", ["arena_half_extents", "player_radius", "baseline_enemy_positions", "events"]
)
def test_malformed_mutants_are_invalid_evidence(field):
    from polyforge.scenarios.arena_oracle import validate_trace

    game, trace = observed_trace(
        "wall_collision" if field in {"arena_half_extents", "player_radius"} else "restart_resets"
    )
    identifier = (
        "collision_disabled" if trace["scenario_id"] == "wall_collision" else "restart_disabled"
    )
    trace.update(
        purpose="MUTANT",
        mutant=identifier,
        arena_half_extents=[10, 10],
        player_radius=0.35,
        wall_thickness=0.5,
        baseline_player_position=[0, 0, 0],
        baseline_enemy_positions=[{"id": "enemy", "position": [3, 0, 3]}],
    )
    del trace[field]
    with pytest.raises(InputError):
        validate_trace(trace, game, identifier, 50)


def test_every_declared_enemy_must_patrol_independent_of_record_order():
    from polyforge.scenarios.arena_oracle import evaluate

    _, trace = observed_trace("enemy_patrols")
    trace["samples"][0]["enemy_positions"] = [
        {"id": "first", "position": [0, 0, 0]},
        {"id": "second", "position": [3, 0, 3]},
    ]
    trace["samples"][-1]["enemy_positions"] = [
        {"id": "second", "position": [3, 0, 3]},
        {"id": "first", "position": [2, 0, 0]},
    ]
    assert evaluate(trace)["status"] == "FAIL"
    trace["samples"][-1]["enemy_positions"][0]["position"] = [5, 0, 3]
    assert evaluate(trace)["status"] == "PASS"


def test_game_job_must_match_fresh_contract_and_optional_gaps_remain_visible(tmp_path):
    import copy

    from polyforge.contracts.manifest import load_manifest
    from polyforge.unity.game import compile_game_request, feature_trace, validate_game_job
    from polyforge.workspace import init_workspace

    root = tmp_path / "arena"
    init_workspace(root, "simple_arena")
    model = load_manifest(root / "game_manifest.json")
    compiled = compile_game_request(model)
    old = copy.deepcopy(compiled)
    old["player"]["spawn_xyz"] = [0, 0, 0]
    with pytest.raises(InputError):
        validate_game_job(old, compiled)
    optional = copy.deepcopy(model.data["intent"]["requirements"][0])
    optional.update(id="optional", feature_id="unknown.optional.v1", required=False)
    model.data["intent"]["requirements"].append(optional)
    report = feature_trace(model, "checks", True)
    assert report["requirements"][-1]["implementation_status"] == "NOT_RUN"
