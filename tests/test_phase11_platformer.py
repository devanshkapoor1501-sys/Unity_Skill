"""Public development contract and independent physical platformer oracle tests."""

import copy
import hashlib
import json
from types import SimpleNamespace

import pytest

from polyforge.contracts.validation import InputError
from polyforge.security.paths import WorkspacePolicy


def source_fixture(tmp_path):
    folder = tmp_path / "UnityProject/Assets/PolyForgeGenerated/Sprites"
    folder.mkdir(parents=True)
    for i, name in enumerate(("atlas.png", "Robot2D.prefab", "Walk.anim", "Sprite.controller")):
        (folder / name).write_bytes(name.encode())
        (folder / (name + ".meta")).write_text("guid: " + str(i + 1) * 32)
    receipt = tmp_path / "runs/sprite-test/bindings.json"
    receipt.parent.mkdir(parents=True)
    binding = {
        "status": "PASS",
        "unity_version": "6000.6.3f1",
        "metadata_digest": "a" * 64,
        "atlas_sha256": hashlib.sha256((folder / "atlas.png").read_bytes()).hexdigest(),
        "prefab_guid": "2" * 32,
        "clip_guid": "3" * 32,
        "sprites": [{"name": "frame-" + str(i), "local_id": i + 1} for i in range(6)],
    }
    receipt.write_text(json.dumps(binding))
    (receipt.parent / "approval.json").write_text(
        json.dumps(
            {
                "technical_verdict": "APPROVED",
                "metadata_digest": "a" * 64,
                "source_license": "CC0",
                "source_kind": "SUPPLIED_SPRITES",
            }
        )
    )
    (receipt.parent / "artifacts.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "relative_path": p.relative_to(tmp_path).as_posix(),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "bytes": p.stat().st_size,
                    }
                    for p in (receipt, receipt.parent / "approval.json")
                ]
            }
        )
    )
    return {
        "schema_version": "1.0.0",
        "scene_id": "checkpoint_course",
        "seed": 42,
        "sprite_receipt": "runs/sprite-test/bindings.json",
        "layout": "checkpoint_course_v1",
    }


@pytest.mark.parametrize("local_id", [-(2**63), -1057934527, 2**63 - 1])
def test_unity_signed_local_file_identifiers_are_valid(tmp_path, local_id):
    from polyforge.unity.platformer import compile_platformer_request

    request = source_fixture(tmp_path)
    receipt = tmp_path / request["sprite_receipt"]
    value = json.loads(receipt.read_text())
    value["sprites"][0]["local_id"] = local_id
    receipt.write_text(json.dumps(value))
    registry_path = receipt.parent / "artifacts.json"
    registry = json.loads(registry_path.read_text())
    registry["artifacts"][0]["sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    registry_path.write_text(json.dumps(registry))
    assert compile_platformer_request(request, WorkspacePolicy(tmp_path))["sprite_prefab_guid"]


@pytest.mark.parametrize("local_id", [0, True, "1", 2**63, -(2**63) - 1])
def test_invalid_unity_local_file_identifiers_are_rejected(tmp_path, local_id):
    from polyforge.unity.platformer import compile_platformer_request

    request = source_fixture(tmp_path)
    receipt = tmp_path / request["sprite_receipt"]
    value = json.loads(receipt.read_text())
    value["sprites"][0]["local_id"] = local_id
    receipt.write_text(json.dumps(value))
    registry_path = receipt.parent / "artifacts.json"
    registry = json.loads(registry_path.read_text())
    registry["artifacts"][0]["sha256"] = hashlib.sha256(receipt.read_bytes()).hexdigest()
    registry_path.write_text(json.dumps(registry))
    with pytest.raises(InputError):
        compile_platformer_request(request, WorkspacePolicy(tmp_path))


def test_contract_reuses_existing_sprite_and_dry_run_has_no_writes(tmp_path):
    from polyforge.unity.platformer import build_platformer, compile_platformer_request

    request = source_fixture(tmp_path)
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    game = compile_platformer_request(request, WorkspacePolicy(tmp_path))
    assert game["scene_path"] == "Assets/PolyForgeGenerated/Platformer/SpritePlatformer.unity"
    assert game["sprite_prefab"] == "Assets/PolyForgeGenerated/Sprites/Robot2D.prefab"
    assert game["lives"] == 3 and game["gravity_scale"] > 0 and game["jump_speed"] > 0
    result = build_platformer(tmp_path, request, dry_run=True)
    assert result.status == "PASS" and result.data["execution_status"] == "NOT_RUN"
    assert result.data["game_status"] == "PARTIAL"
    assert before == {
        p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize(
    "change",
    [
        {"layout": "arbitrary_world"},
        {"seed": float("nan")},
        {"scene_id": "../outside"},
        {"platforms": []},
        {"required_features": ["multiplayer"]},
        {"sprite_receipt": "../outside.json"},
    ],
)
def test_unsupported_or_nonfinite_contract_is_rejected_before_writes(tmp_path, change):
    from polyforge.unity.platformer import compile_platformer_request

    request = source_fixture(tmp_path)
    with pytest.raises(InputError):
        compile_platformer_request({**request, **change}, WorkspacePolicy(tmp_path))


@pytest.mark.parametrize("fault", ["atlas", "prefab_guid", "approval", "version", "frames"])
def test_stale_unapproved_or_unsupported_sprite_receipt_is_rejected(tmp_path, fault):
    from polyforge.unity.platformer import compile_platformer_request

    request = source_fixture(tmp_path)
    receipt = tmp_path / request["sprite_receipt"]
    value = json.loads(receipt.read_text())
    if fault == "atlas":
        (tmp_path / "UnityProject/Assets/PolyForgeGenerated/Sprites/atlas.png").write_bytes(
            b"changed"
        )
    elif fault == "prefab_guid":
        value["prefab_guid"] = "f" * 32
    elif fault == "approval":
        (receipt.parent / "approval.json").write_text('{"technical_verdict":"REVIEW"}')
    elif fault == "version":
        value["unity_version"] = "2022.1.1f1"
    else:
        value["sprites"][1]["local_id"] = value["sprites"][0]["local_id"]
    receipt.write_text(json.dumps(value))
    (receipt.parent / "artifacts.json").write_text(
        json.dumps(
            {
                "artifacts": [
                    {
                        "relative_path": p.relative_to(tmp_path).as_posix(),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "bytes": p.stat().st_size,
                    }
                    for p in (receipt, receipt.parent / "approval.json")
                ]
            }
        )
    )
    with pytest.raises(InputError):
        compile_platformer_request(request, WorkspacePolicy(tmp_path))


def trace(case="player_moves"):
    def sample(frame, x, y, **values):
        return {
            "frame": frame,
            "position": [x, y, 0],
            "velocity": [3, 0, 0],
            "grounded": True,
            "health": 3,
            "state": "RUNNING",
            "round": 1,
            "checkpoint": "spawn",
            "elapsed_seconds": frame * 0.02,
            **values,
        }

    return {
        "schema_version": "1.0.0",
        "input_digest": "a" * 64,
        "scene_id": "course",
        "scenario_id": case,
        "purpose": "NOMINAL",
        "mutant": "",
        "seed": 42,
        "fixed_delta_seconds": 0.02,
        "frames_executed": 50,
        "schedule_digest": "b" * 64,
        "spawn": [-8, 0, 0],
        "checkpoint_position": [-2, 0, 0],
        "goal_center": [8, 1, 0],
        "hazard_center": [2, 0.3, 0],
        "hazard_size": [1, 0.6, 1],
        "goal_size": [1, 2, 1],
        "platform_top": 0,
        "samples": [sample(0, -8, 0), sample(50, -5, 0)],
        "events": [],
    }


def test_oracle_requires_physical_movement_even_when_events_claim_success():
    from polyforge.scenarios.platformer_oracle import evaluate

    observed = trace()
    assert evaluate(observed)["status"] == "PASS"
    observed["samples"][-1]["position"] = [-8, 0, 0]
    observed["events"] = [{"name": "player_moves"}]
    assert evaluate(observed)["status"] == "FAIL"


def test_jump_and_airborne_oracles_use_observed_vertical_velocity_and_landing():
    from polyforge.scenarios.platformer_oracle import evaluate

    observed = trace("grounded_jump")
    first, last = observed["samples"]
    observed["samples"] = [
        first,
        {
            **copy.deepcopy(first),
            "frame": 10,
            "position": [-8, 1.4, 0],
            "velocity": [0, 2, 0],
            "grounded": False,
        },
        last,
    ]
    last["position"] = [-8, 0, 0]
    assert evaluate(observed)["status"] == "PASS"
    observed["samples"][1]["position"][1] = 0
    assert evaluate(observed)["status"] == "FAIL"


def test_goal_cannot_win_without_spatial_contact_and_checkpoint_respawn_needs_health_loss():
    from polyforge.scenarios.platformer_oracle import evaluate

    observed = trace("goal_contact")
    observed["samples"][-1]["state"] = "WON"
    assert evaluate(observed)["status"] == "FAIL"
    observed["samples"][-1]["position"] = [8, 0, 0]
    assert evaluate(observed)["status"] == "PASS"
    observed = trace("checkpoint_respawn")
    first, last = observed["samples"]
    middle = {
        **copy.deepcopy(first),
        "frame": 20,
        "position": [2, 0, 0],
        "checkpoint": "checkpoint",
    }
    observed["samples"].insert(
        1, {**copy.deepcopy(first), "frame": 10, "position": [-2, 0, 0], "checkpoint": "checkpoint"}
    )
    last.update(position=[-2, 0, 0], checkpoint="checkpoint", health=2)
    observed["samples"].insert(2, middle)
    assert evaluate(observed)["status"] == "PASS"
    last["health"] = 3
    assert evaluate(observed)["status"] == "FAIL"


def respawn_trace():
    """A contact/reset pair followed by held input, like the native checkpoint run."""
    observed = trace("checkpoint_respawn")
    observed.update(
        checkpoint_position=[-3, 0, 0],
        hazard_center=[0.5, 0.3, 0],
        hazard_size=[0.8, 0.6, 1],
        frames_executed=70,
    )
    base = observed["samples"][0]

    def sample(frame, x, **values):
        return {
            **copy.deepcopy(base),
            "frame": frame,
            "position": [x, 0.015, 0],
            "checkpoint": "checkpoint",
            **values,
        }

    observed["samples"] = [
        sample(2, -4, checkpoint="spawn"),
        sample(8, -3.54),
        sample(49, -0.38755),
        sample(50, -3, health=2, position=[-3, 0, 0], velocity=[0, 0, 0]),
        sample(72, -1.309, health=2),
    ]
    observed["contacts"] = [{"kind": "Hazard", "frame": 50, "position": [-0.3106854, 0.015, 0]}]
    return observed


def test_respawn_is_proven_at_health_loss_even_when_held_input_moves_afterward():
    from polyforge.scenarios.platformer_oracle import evaluate

    # Preserve the native sub-millimetre boundary and later movement after reset.
    assert evaluate(respawn_trace())["status"] == "PASS"


@pytest.mark.parametrize("x,status", [(-0.3199, "PASS"), (-0.3201, "FAIL"), (-0.5, "FAIL")])
def test_hazard_contact_skin_is_bounded_by_two_pinned_physics_contact_offsets(x, status):
    from polyforge.scenarios.platformer_oracle import evaluate

    observed = respawn_trace()
    observed["contacts"][0]["position"][0] = x
    assert evaluate(observed)["status"] == status


@pytest.mark.parametrize(
    "fault",
    ["spawn", "wrong_checkpoint", "label_only", "old_hazard", "late_checkpoint", "late_reset"],
)
def test_respawn_needs_temporally_linked_contact_health_loss_and_correct_reset(fault):
    from polyforge.scenarios.platformer_oracle import evaluate

    observed = respawn_trace()
    # Use an unambiguous overlap here so contact skin cannot mask temporal faults.
    observed["contacts"][0]["position"][0] = -0.29
    if fault == "spawn":
        observed["samples"][3]["position"] = observed["spawn"]
    elif fault == "wrong_checkpoint":
        observed["samples"][3]["position"] = [-2, 0, 0]
    elif fault == "label_only":
        observed["contacts"][0]["position"] = [-5, 0, 0]
        observed["events"] = [{"name": "Hazard"}, {"name": "checkpoint_respawn"}]
    elif fault == "old_hazard":
        observed["contacts"][0]["frame"] = 9
    elif fault == "late_checkpoint":
        observed["samples"][1]["checkpoint"] = "spawn"
        observed["samples"][2]["checkpoint"] = "spawn"
        observed["contacts"].append({"kind": "Checkpoint", "frame": 51, "position": [-3, 0, 0]})
    else:
        observed["samples"][3]["position"] = [-0.29, 0, 0]
        observed["samples"][-1]["position"] = [-3, 0, 0]
    assert evaluate(observed)["status"] == "FAIL"


def test_public_journey_launch_window_clears_hazard_with_ground_friction_margin(tmp_path):
    from polyforge.unity.platformer import compile_platformer_request, core_suite

    game = compile_platformer_request(source_fixture(tmp_path), WorkspacePolicy(tmp_path))
    journey = next(case for case in core_suite(game)["scenarios"] if case["id"] == "journey")
    approach, launch = journey["steps"][:2]
    assert approach.get("move") == launch.get("move") == 1 and launch.get("jump") is True
    # Analytic feasibility guard, not a simulated/native gameplay verdict. Ground
    # contact reduces native horizontal speed by ~4%; bound it by 5% here.
    speed = game["move_speed"]
    left = game["hazard_center"][0] - game["hazard_size"][0] / 2 - 0.4
    right = game["hazard_center"][0] + game["hazard_size"][0] / 2 + 0.4
    top = game["hazard_center"][1] + game["hazard_size"][1] / 2
    for ground_speed in (0.95 * speed, speed):
        start = game["spawn"][0] + ground_speed * approach["ticks"] * 0.02
        assert game["checkpoint_position"][0] < start < left
        for edge in (left, right):
            seconds = (edge - start) / speed
            height = game["jump_speed"] * seconds - 0.5 * 9.81 * 2 * seconds**2
            assert height > top + 0.05, "Jump must clear the whole hazard at either speed bound"


@pytest.mark.parametrize(
    "field,value",
    [
        ("purpose", "MUTANT"),
        ("input_digest", "c" * 64),
        ("schedule_digest", "c" * 64),
        ("frames_executed", 0),
        ("fixed_delta_seconds", 0.1),
    ],
)
def test_trace_identity_and_executed_schedule_cannot_be_forged(field, value):
    from polyforge.scenarios.platformer_oracle import validate_trace

    observed = trace()
    game = {"input_digest": "a" * 64, "scene_id": "course", "seed": 42}
    validate_trace(observed, game, "player_moves", 50, "b" * 64)
    observed[field] = value
    with pytest.raises(InputError):
        validate_trace(observed, game, "player_moves", 50, "b" * 64)


@pytest.mark.parametrize(
    "field",
    ["spawn", "checkpoint_position", "goal_center", "goal_size", "hazard_center", "hazard_size"],
)
def test_frozen_geometry_accepts_float32_round_trip_but_rejects_real_changes(field):
    import struct

    from polyforge.scenarios.platformer_oracle import validate_trace

    observed = trace()
    game = {
        "input_digest": "a" * 64,
        "scene_id": "course",
        "seed": 42,
        field: copy.deepcopy(observed[field]),
    }
    # The same JSON coordinate crosses Unity's float32 Vector3 boundary.
    observed[field] = [struct.unpack("f", struct.pack("f", n))[0] for n in observed[field]]
    validate_trace(observed, game, "player_moves", 50, "b" * 64)
    observed[field][0] += 1e-4
    with pytest.raises(InputError, match="geometry differs"):
        validate_trace(observed, game, "player_moves", 50, "b" * 64)


def test_missing_nan_nonmonotonic_mutant_trace_never_counts_as_detection():
    from polyforge.scenarios.platformer_oracle import validate_trace

    game = {"input_digest": "a" * 64, "scene_id": "course", "seed": 42}
    for fault in ("missing", "nan", "frames"):
        observed = trace()
        observed.update(purpose="MUTANT", mutant="input_disconnected")
        if fault == "missing":
            observed["samples"] = []
        elif fault == "nan":
            observed["samples"][0]["position"][0] = float("nan")
        else:
            observed["samples"][-1]["frame"] = 0
        with pytest.raises(InputError):
            validate_trace(observed, game, "input_disconnected", 50, "b" * 64)


def test_airborne_boost_terminal_motion_and_unobserved_checkpoint_fail():
    from polyforge.scenarios.platformer_oracle import evaluate

    observed = trace("goal_contact")
    observed["samples"][-1].update(state="WON", position=[8, 0, 0])
    observed["samples"].append(
        {**copy.deepcopy(observed["samples"][-1]), "frame": 51, "position": [8.2, 0, 0]}
    )
    assert evaluate(observed)["status"] == "FAIL"
    observed = trace("checkpoint_respawn")
    observed["samples"][-1].update(health=2, checkpoint="checkpoint", position=[-2, 0, 0])
    observed["contacts"] = [{"kind": "Hazard", "position": [2, 0, 0], "frame": 25}]
    assert evaluate(observed)["status"] == "FAIL"


def test_fall_failure_restart_and_unknown_oracle_have_physical_vetoes():
    from polyforge.scenarios.platformer_oracle import evaluate

    observed = trace("ground_collision")
    observed["samples"][0]["position"][1] = 2
    observed["samples"][-1].update(position=[-8, 0, 0], velocity=[0, 0, 0])
    assert evaluate(observed)["status"] == "PASS"
    observed["samples"][-1]["position"][1] = -1
    assert evaluate(observed)["status"] == "FAIL"
    observed = trace("restart_resets")
    observed["samples"][0].update(state="WON", position=[8, 0, 0], velocity=[0, 0, 0])
    observed["samples"][-1].update(
        position=[-8, 0, 0], velocity=[0, 0, 0], round=2, elapsed_seconds=0
    )
    assert evaluate(observed)["status"] == "PASS"
    observed["samples"][-1]["checkpoint"] = "checkpoint"
    assert evaluate(observed)["status"] == "FAIL"
    observed["scenario_id"] = "unsupported"
    assert evaluate(observed)["status"] == "FAIL"
    assert evaluate({})["status"] == "FAIL"


def test_preservation_excludes_only_new_platformer_scope_including_folder_meta(tmp_path):
    from polyforge.unity.platformer import _preserved

    source_fixture(tmp_path)
    policy = WorkspacePolicy(tmp_path)
    before = _preserved(policy)
    generated = tmp_path / "UnityProject/Assets/PolyForgeGenerated"
    (generated / "Platformer").mkdir()
    (generated / "Platformer.meta").write_text("guid: new-owned-folder")
    (generated / "Platformer/new.unity").write_text("new-scene")
    assert _preserved(policy) == before
    (generated / "Sprites/Walk.anim").write_text("changed-original")
    assert _preserved(policy) != before


def native_boundary(monkeypatch, tmp_path):
    """Only process boundaries are simulated; these tests establish no native verdict."""
    import polyforge.unity.platformer as platformer

    calls = []
    executable = tmp_path / "test-unity-boundary.exe"
    executable.write_bytes(b"unit-test-only")
    monkeypatch.setattr(platformer, "unity_tool", lambda _: executable)
    monkeypatch.setattr(
        platformer,
        "configuration",
        lambda _: SimpleNamespace(
            unity_timeout_seconds=120, max_output_bytes=100000, memory_limit_mb=512
        ),
    )
    monkeypatch.setattr(platformer, "sync_package", lambda _: None)

    def launch(policy, executable, config, relative, mode, **kwargs):
        calls.append((mode, kwargs))
        request = json.loads(kwargs["game_input"].read_text())
        if mode == "platformer":
            kwargs["output"].write_text(
                json.dumps(
                    {
                        "input_digest": request["input_digest"],
                        "scene_guid": "1" * 32,
                        "source_prefab_guid": request["sprite_prefab_guid"],
                    }
                )
            )
        elif mode == "platformer-player":
            player = policy.path(request["player_output"])
            player.parent.mkdir(parents=True)
            player.write_bytes(b"unit-player-build-boundary")
        else:
            kwargs["output"].parent.mkdir(parents=True, exist_ok=True)
            kwargs["output"].write_text("test-xml-boundary")

    monkeypatch.setattr(platformer, "launch", launch)
    monkeypatch.setattr(
        platformer, "verify_test_xml", lambda path, expected: {"expected": expected}
    )
    monkeypatch.setattr(
        platformer,
        "score_telemetry",
        lambda *args, **kwargs: {"status": "PASS", "scope": "UNIT_TEST_BOUNDARY"},
    )
    return platformer, calls


def test_build_seals_archive_and_source_preservation_at_native_boundary(monkeypatch, tmp_path):
    platformer, calls = native_boundary(monkeypatch, tmp_path)
    request = source_fixture(tmp_path)
    result = platformer.build_platformer(tmp_path, request)
    assert result.status == "PASS" and result.evaluated_test_status == "PASS"
    assert [mode for mode, _ in calls] == ["platformer", "tests", "tests"]
    assert calls[-1][1]["test_filter"] == "PolyForge.Platformer.Tests"
    latest = json.loads((tmp_path / ".polyforge/platformer-latest.json").read_text())
    assert (tmp_path / latest["archive"]).is_file()
    from polyforge.workforce.workers import seal_candidate

    candidate = seal_candidate(WorkspacePolicy(tmp_path), result, "a" * 64)
    paths = {row["path"] for row in candidate["files"]}
    assert latest["archive"] in paths
    assert "runs/" + result.run_id + "/delivery.json" in paths
    assert result.data["standalone_build"] == "NOT_RUN" and result.game_status == "PARTIAL"


@pytest.mark.parametrize("failure", ["oracles", "native", "interrupt", "standalone_missing"])
def test_native_failure_keeps_evidence_and_does_not_claim_test_pass(monkeypatch, tmp_path, failure):
    platformer, _ = native_boundary(monkeypatch, tmp_path)
    request = source_fixture(tmp_path)
    game = platformer.compile_platformer_request(request, WorkspacePolicy(tmp_path))
    if failure == "oracles":
        monkeypatch.setattr(platformer, "score_telemetry", lambda *a, **k: {"status": "FAIL"})
    elif failure in {"native", "interrupt"}:

        def stop(*a, **k):
            if failure == "interrupt":
                raise KeyboardInterrupt()
            raise OSError("owned process failed")

        monkeypatch.setattr(platformer, "launch", stop)
    else:
        original = platformer.launch

        def missing_player(*args, **kwargs):
            if args[4] != "platformer-player":
                original(*args, **kwargs)

        monkeypatch.setattr(platformer, "launch", missing_player)
    result = platformer.execute_platformer_checks(
        WorkspacePolicy(tmp_path), game, standalone=failure == "standalone_missing"
    )
    assert result.status == "FAIL" and result.evaluated_test_status != "PASS"
    assert (tmp_path / "runs" / result.run_id / "game-input.json").is_file()


@pytest.mark.parametrize("failure", ["none", "smoke", "gameplay"])
def test_standalone_build_smoke_and_gameplay_are_separate_boundary_gates(
    monkeypatch, tmp_path, failure
):
    platformer, calls = native_boundary(monkeypatch, tmp_path)
    request = source_fixture(tmp_path)
    game = platformer.compile_platformer_request(request, WorkspacePolicy(tmp_path))

    def process(argv, policy, relative, process_policy, **kwargs):
        report = policy.path(argv[argv.index("-polyforgePlayerEvidence") + 1])
        report.write_text(
            json.dumps(
                {"input_digest": game["input_digest"], "scene": "SpritePlatformer", "frames": 800}
            )
        )
        from polyforge.runner.processes import ProcessOutcome

        return ProcessOutcome(
            1 if failure == "smoke" else 0, "exit", 123, "UNIT_TEST_BOUNDARY", 1, "", "", False
        )

    monkeypatch.setattr(platformer, "run_process", process)
    monkeypatch.setattr(
        platformer,
        "score_telemetry",
        lambda *a, **k: {
            "status": "FAIL" if failure == "gameplay" and k.get("standalone") else "PASS"
        },
    )
    result = platformer.execute_platformer_checks(WorkspacePolicy(tmp_path), game, standalone=True)
    assert result.status == ("PASS" if failure == "none" else "FAIL")
    assert any(mode == "platformer-player" for mode, _ in calls)
    if failure == "none":
        assert result.data["standalone_gameplay"] == "PASS"
        assert result.data["profiling"] == "NOT_RUN"


def test_malformed_import_registry_is_rejected_as_input_error(tmp_path):
    from polyforge.unity.platformer import compile_platformer_request

    request = source_fixture(tmp_path)
    (tmp_path / "runs/sprite-test/artifacts.json").write_text("{}")
    with pytest.raises(InputError):
        compile_platformer_request(request, WorkspacePolicy(tmp_path))


@pytest.mark.parametrize("fault", ["vector", "state", "geometry", "frozen", "contacts", "contact"])
def test_telemetry_rejects_invalid_physics_and_contact_observations(fault):
    from polyforge.scenarios.platformer_oracle import validate_trace

    observed = trace()
    game = {"input_digest": "a" * 64, "scene_id": "course", "seed": 42}
    if fault == "vector":
        observed["samples"][0]["velocity"] = [True, 0, 0]
    elif fault == "state":
        observed["samples"][0]["health"] = 4
    elif fault == "geometry":
        observed["goal_size"] = [1]
    elif fault == "frozen":
        game["goal_size"] = [2, 2, 1]
    elif fault == "contacts":
        observed["contacts"] = "not-physical-records"
    else:
        observed["contacts"] = [{"kind": "Hazard", "frame": 51, "position": [0, 0, 0]}]
    with pytest.raises(InputError):
        validate_trace(observed, game, "player_moves", 50, "b" * 64)


def test_actual_contact_samples_are_validated_and_airborne_impulse_is_rejected():
    from polyforge.scenarios.platformer_oracle import evaluate, validate_trace

    observed = trace()
    observed["contacts"] = [{"kind": "Checkpoint", "frame": 25, "position": [-2, 0, 0]}]
    validate_trace(
        observed,
        {"input_digest": "a" * 64, "scene_id": "course", "seed": 42},
        "player_moves",
        50,
        "b" * 64,
    )
    observed["samples"][0]["position"][2] = 1
    assert evaluate(observed)["status"] == "FAIL"
    observed = trace("airborne_jump")
    base = observed["samples"][0]
    observed["samples"].insert(
        1,
        {
            **copy.deepcopy(base),
            "frame": 10,
            "grounded": False,
            "position": [-8, 1, 0],
            "velocity": [0, 3, 0],
        },
    )
    observed["samples"].insert(
        2,
        {
            **copy.deepcopy(base),
            "frame": 11,
            "grounded": False,
            "position": [-8, 1.1, 0],
            "velocity": [0, 8, 0],
        },
    )
    observed["samples"][-1]["position"] = [-8, 0, 0]
    assert evaluate(observed)["status"] == "FAIL"
    observed["samples"][2]["velocity"][1] = 2.6
    assert evaluate(observed)["status"] == "PASS"
    observed["frames_executed"] = 0
    assert evaluate(observed)["status"] == "FAIL"


def test_failure_and_default_journey_oracles_need_observed_state_and_progress():
    from polyforge.scenarios.platformer_oracle import evaluate

    observed = trace("health_failure")
    assert evaluate(observed)["status"] == "FAIL"
    observed["samples"][-1].update(health=0, state="FAILED", velocity=[0, 0, 0])
    assert evaluate(observed)["status"] == "PASS"
    observed = trace("journey")
    observed["samples"][-1].update(position=[8, 0, 0], state="WON")
    assert evaluate(observed)["status"] == "FAIL"
    observed["samples"].insert(
        1,
        {
            **copy.deepcopy(observed["samples"][0]),
            "frame": 25,
            "position": [-2, 1, 0],
            "checkpoint": "checkpoint",
        },
    )
    assert evaluate(observed)["status"] == "PASS"


def test_scoring_requires_valid_mutant_execution_and_inverts_only_behavior_failure(
    monkeypatch, tmp_path
):
    import polyforge.unity.platformer as platformer

    monkeypatch.setattr(platformer, "CORE_SCENARIOS", ("player_moves",))
    monkeypatch.setattr(platformer, "INPUT_SCENARIOS", {})
    monkeypatch.setattr(platformer, "MUTANT_SCENARIOS", {"input_disconnected": "player_moves"})
    game = {"input_digest": "a" * 64, "scene_id": "course", "seed": 42}
    case = platformer.core_suite(game)["scenarios"][0]
    directory = tmp_path / "runs/check/telemetry"
    directory.mkdir(parents=True)
    nominal = trace()
    nominal["schedule_digest"] = case["schedule_digest"]
    (directory / "player_moves.json").write_text(json.dumps(nominal))
    mutant = copy.deepcopy(nominal)
    mutant.update(purpose="MUTANT", mutant="input_disconnected")
    mutant["samples"][-1]["position"] = [-8, 0, 0]
    path = directory / "input_disconnected.json"
    path.write_text(json.dumps(mutant))
    policy = WorkspacePolicy(tmp_path)
    assert platformer.score_telemetry(policy, "runs/check", game)["status"] == "PASS"
    mutant["samples"][-1]["position"] = [-5, 0, 0]
    path.write_text(json.dumps(mutant))
    assert platformer.score_telemetry(policy, "runs/check", game)["status"] == "FAIL"
    mutant["frames_executed"] = 0
    path.write_text(json.dumps(mutant))
    with pytest.raises(InputError):
        platformer.score_telemetry(policy, "runs/check", game)
    assert (
        platformer.score_telemetry(policy, "runs/check", game, standalone=True)["status"] == "PASS"
    )


@pytest.mark.parametrize("fault", ["receipt_hash", "missing_asset"])
def test_unsealed_receipt_or_missing_sprite_asset_cannot_launch(tmp_path, fault):
    from polyforge.unity.platformer import compile_platformer_request

    request = source_fixture(tmp_path)
    if fault == "receipt_hash":
        (tmp_path / request["sprite_receipt"]).write_text("{}")
    else:
        (tmp_path / "UnityProject/Assets/PolyForgeGenerated/Sprites/Walk.anim").unlink()
    with pytest.raises(InputError):
        compile_platformer_request(request, WorkspacePolicy(tmp_path))


@pytest.mark.parametrize("fault", ["bindings", "preservation", "identity_race"])
def test_build_refuses_wrong_native_identity_and_modified_existing_assets(
    monkeypatch, tmp_path, fault
):
    platformer, calls = native_boundary(monkeypatch, tmp_path)
    request = source_fixture(tmp_path)
    if fault == "identity_race":
        original_compile = platformer.compile_platformer_request
        count = 0

        def changed(*args):
            nonlocal count
            count += 1
            game = original_compile(*args)
            return game if count == 1 else {**game, "seed": 43}

        monkeypatch.setattr(platformer, "compile_platformer_request", changed)
    else:
        original_launch = platformer.launch

        def changed_launch(*args, **kwargs):
            original_launch(*args, **kwargs)
            if args[4] == "platformer":
                if fault == "bindings":
                    kwargs["output"].write_text("{}")
                else:
                    (
                        tmp_path / "UnityProject/Assets/PolyForgeGenerated/Sprites/Walk.anim"
                    ).write_text("changed")

        monkeypatch.setattr(platformer, "launch", changed_launch)
    with pytest.raises(InputError):
        platformer.build_platformer(tmp_path, request)
    assert not any(mode == "tests" for mode, _ in calls)
