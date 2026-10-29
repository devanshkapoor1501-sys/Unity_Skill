"""Compile the supported public arena contract before any Unity side effects."""

from __future__ import annotations

import hashlib
import json
import shutil
import threading
import zipfile
from contextlib import nullcontext
from dataclasses import replace
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.contracts.manifest import Manifest
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.locks import unity_project_lock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import RunJournal, atomic_json
from polyforge.scenarios.arena_oracle import (
    CORE_SCENARIOS,
    MUTANT_SCENARIOS,
    evaluate,
    validate_trace,
)
from polyforge.scenarios.schema import validate_scenario
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bridge import configuration, launch, reusable_export, unity_tool
from polyforge.unity.evidence import verify_test_xml

GAME_EDIT_TESTS = {
    "PolyForge.Game.Editor.Tests.GameTests.PlayableSceneHasLiveRuntimeBindingsAndFourBoundaries"
}
PLAY_TESTS = {
    "PolyForge.Game.Tests.RuntimeTests.HealthClampsDamageAndResets",
    *{
        "PolyForge.Game.Tests.ScenarioTests." + name
        for name in (
            "PlayerMoves",
            "WallCollision",
            "EnemyPatrols",
            "ContactDealsDamage",
            "HealthFailure",
            "SurvivalWins",
            "RestartResets",
            "KeyboardAdapterMovesPlayer",
            "KeyboardAdapterRestarts",
            "CollisionDisabledMutant",
            "RestartDisabledMutant",
            "ReversedWinMutant",
            "DamageWithoutHealthMutant",
            "NavigationStuckMutant",
            "InputDisconnectedMutant",
        )
    },
}

FEATURE_SCENARIOS = {
    "movement.character_controller.v1": ["player_moves", "keyboard_input"],
    "physics.collision.v1": ["wall_collision", "collision_disabled"],
    "ai.patrol.v1": ["enemy_patrols"],
    "combat.damage.v1": ["contact_damage"],
    "combat.health.v1": ["contact_damage", "health_failure"],
    "objective.survival.v1": ["survival_win"],
    "objective.failure.v1": ["health_failure"],
    "game.restart.v1": ["restart_resets", "keyboard_restart", "restart_disabled"],
}


def compile_game_request(model: Manifest) -> dict[str, Any]:
    data = model.data
    supported = {
        "movement.character_controller.v1",
        "physics.collision.v1",
        "ai.patrol.v1",
        "combat.damage.v1",
        "combat.health.v1",
        "objective.survival.v1",
        "objective.failure.v1",
        "game.restart.v1",
        "geometry.static_assets.v1",
        "audit.multiview.v1",
        "artifact.editable_sources.v1",
    }
    blocked = [
        r["feature_id"]
        for r in data.get("intent", {}).get("requirements", [])
        if r["required"] and r["feature_id"] not in supported
    ]
    if blocked or data.get("animations"):
        raise InputError(
            "Mandatory arena features are not implemented: " + ", ".join(blocked or ["animation"]),
            kind=ErrorKind.PRODUCER_FAILURE,
            code="PF-GAME-MANDATORY-FEATURE",
        )
    if (
        data["project"]["kind"] != "3d"
        or data["project"]["render_pipeline"] != "urp"
        or data["target"]["platform"] != "standalone_windows"
        or data["gameplay"]["win_condition"] != "survive_30_seconds"
        or data["gameplay"]["controls"] != "wasd"
        or data["gameplay"]["restart_key"] != "r"
    ):
        raise InputError("Phase6 supports the 3D WASD / R / thirty-second survival arena")
    ground = next((a for a in data["assets"] if model.recipes[a["id"]]["kind"] == "ground"), None)
    robot = next((a for a in data["assets"] if model.recipes[a["id"]]["kind"] == "robot"), None)
    if ground is None or robot is None:
        raise InputError("Playable arena requires generated ground and robot assets")
    half = [data["scene"]["bounds_m"][0] / 2, data["scene"]["bounds_m"][2] / 2]
    if min(half) < 5 or any(
        ground["target_size_m"][i] < data["scene"]["bounds_m"][i] for i in (0, 2)
    ):
        raise InputError("Arena ground must cover the scene; horizontal dimensions must be >=10m")
    players = [a for a in data["actors"] if a["controller"] == "PlayerController"]
    if len(players) > 1:
        raise InputError("One player controller is supported")
    player = (
        players[0]
        if players
        else {
            "id": "player_01",
            "asset_id": robot["id"],
            "spawn_xyz": [-half[0] * 0.3, 0, -half[1] * 0.3],
        }
    )
    enemies = [a for a in data["actors"] if a["controller"] == "PatrolEnemy"]
    if not enemies:
        raise InputError("Arena requires at least one declared patrol enemy")
    if len(enemies) > 8 or max(half) > 20:
        raise InputError(
            "Phase6 arena budgets: at most eight enemies and 40m horizontal dimensions"
        )
    for actor in [player, *enemies]:
        x, y, z = actor["spawn_xyz"]
        margin = 3 if actor in enemies else 1
        if abs(y) > 0.01 or abs(x) > half[0] - margin or abs(z) > half[1] - margin:
            raise InputError(
                "Actor spawn/patrol must remain on the supported arena floor: " + actor["id"]
            )
    if not players and player["id"] in {a["id"] for a in data["actors"]}:
        raise InputError("Generated player semantic ID collides with a declared actor")
    value = {
        "schema_version": "1.0.0",
        "input_digest": model.input_digest,
        "seed": data["project"]["seed"],
        "scene_id": data["scene"]["id"],
        "player": player,
        "enemies": enemies,
        "static_actors": [a for a in data["actors"] if a["controller"] == "StaticActor"],
        "project_name": data["project"]["name"],
        "ground_id": ground["id"],
        "obstacle_ids": [
            a["id"] for a in data["assets"] if model.recipes[a["id"]]["kind"] == "crate"
        ],
        "half_extents": half,
        "survival_seconds": 30,
        "health": 100,
        "player_speed": 4,
        "enemy_speed": 1.3,
        "damage": 25,
        "fixed_delta_seconds": 0.02,
        "wall_thickness": 0.5,
        "player_origin": "DECLARED" if players else "DERIVED_FROM_ROBOT_FAMILY",
    }
    value["game_contract_digest"] = canonical_digest(value)
    return value


def core_suite(game: dict[str, Any]) -> dict[str, Any]:
    suite: dict[str, Any] = json.loads(
        files("polyforge").joinpath("data/arena_scenarios.json").read_text("utf-8")
    )
    player = game["player"]["id"]
    enemy = game["enemies"][0]
    for case in suite["scenarios"]:
        case["seed"] = game["seed"]
        case["setup"]["scene_id"] = game["scene_id"]
        case["setup"]["entity_ids"] = [player, *[a["id"] for a in game["enemies"]]]
        if case["id"] == "wall_collision":
            case["setup"]["player_position"] = [-game["half_extents"][0] + 3, 0, 0]
        elif case["id"] in {"contact_damage", "health_failure", "restart_resets"}:
            case["setup"]["player_position"] = [
                enemy["spawn_xyz"][0],
                enemy["spawn_xyz"][1],
                enemy["spawn_xyz"][2] - 1,
            ]
        for step in case["steps"]:
            if "actor_id" in step:
                step["actor_id"] = player
        validate_scenario(
            case, scene_id=game["scene_id"], entity_ids=set(case["setup"]["entity_ids"])
        )
    return suite


def validate_game_job(saved: dict[str, Any], current: dict[str, Any]) -> None:
    if any(saved.get(key) != value for key, value in current.items()):
        raise InputError(
            "Saved game request differs from the current compiled contract; rebuild S5",
            kind=ErrorKind.CONTRACT_FAILURE,
        )


def feature_trace(model: Manifest, check_run: str | None, passed: bool) -> dict[str, Any]:
    from polyforge.compiler.contract_compiler import compile_contract

    trace: dict[str, Any] = compile_contract(model)["feature_contract"]
    trace.update(game_status="PARTIAL", check_run_id=check_run)
    static = {"geometry.static_assets.v1", "audit.multiview.v1", "artifact.editable_sources.v1"}
    for feature in trace["requirements"]:
        cases = FEATURE_SCENARIOS.get(feature["feature_id"], [])
        implemented = bool(cases) or feature["feature_id"] in static
        feature["scenario_ids"] = cases
        feature["implementation_status"] = "PASS" if passed and implemented else "NOT_RUN"
        feature["independent_oracle_status"] = "PASS" if cases and passed else "NOT_RUN"
        if implemented:
            feature["support_state"] = "SUPPORTED"
            feature["reason"] = "Observed public development checks; external qualification pending"
    return trace


def register_game_artifacts(policy: WorkspacePolicy, relative: str, digest: str) -> list[str]:
    """Seal run inputs, XML, telemetry and logs with content identities."""
    artifacts: list[dict[str, Any]] = []
    for path in sorted(policy.path(relative).rglob("*")):
        path = policy.path(path)
        if not path.is_file() or "player" in path.relative_to(policy.path(relative)).parts:
            continue
        if path.name == "artifacts.json":
            continue
        name = path.relative_to(policy.root).as_posix()
        artifacts.append(
            {
                "artifact_id": name,
                "relative_path": name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "bytes": path.stat().st_size,
                "input_digest": digest,
            }
        )
    atomic_json(policy, relative + "/artifacts.json", {"artifacts": artifacts})
    return [a["artifact_id"] for a in artifacts]


def score_telemetry(policy: WorkspacePolicy, relative: str, game: dict[str, Any]) -> dict[str, Any]:
    results = {}
    cases = {c["id"]: c for c in core_suite(game)["scenarios"]}
    for identifier in (
        *CORE_SCENARIOS,
        "keyboard_input",
        "keyboard_restart",
        *MUTANT_SCENARIOS,
    ):
        trace = load_json(
            policy.path(relative + "/telemetry/" + identifier + ".json"), max_bytes=33_554_432
        )
        expected_case = {
            "keyboard_input": "player_moves",
            "keyboard_restart": "restart_resets",
            **MUTANT_SCENARIOS,
        }.get(identifier, identifier)
        case = cases[expected_case]
        ticks = (
            sum(s["ticks"] for s in cases["player_moves"]["steps"]) + 1
            if identifier == "keyboard_restart"
            else sum(s["ticks"] for s in case["steps"])
        )
        validate_trace(trace, game, identifier, ticks)
        result = evaluate(trace)
        mutant = identifier in MUTANT_SCENARIOS
        if not mutant:
            for expected in case["expected"]:
                if (
                    sum(e["name"] == expected["event"] for e in trace["events"])
                    < expected["count_gte"]
                ):
                    result["status"] = "FAIL"
                    result["issues"].append(
                        "Declared event expectation unmet: " + expected["event"]
                    )
        results[identifier] = {
            **result,
            "mutant": mutant,
            "mutation_id": "M" + str(list(MUTANT_SCENARIOS).index(identifier) + 1)
            if mutant
            else None,
            "gate_status": "PASS"
            if (result["status"] == "FAIL" if mutant else result["status"] == "PASS")
            else "FAIL",
        }
    return {
        "status": "PASS" if all(r["gate_status"] == "PASS" for r in results.values()) else "FAIL",
        "scenarios": results,
        "hidden_evaluation": "NOT_RUN",
    }


def verify_game(workspace: Path, *, standalone: bool = False, _lock_held: bool = False) -> Result:
    policy = WorkspacePolicy(workspace)
    from polyforge.contracts.manifest import load_manifest

    model = load_manifest(policy.path("game_manifest.json"))
    game = compile_game_request(model)
    latest = load_json(policy.path(".polyforge/game-latest.json"))
    if latest["input_digest"] != game["input_digest"]:
        raise InputError("Game build belongs to an older manifest; rebuild S5")
    job = load_json(policy.path(latest["request"]))
    validate_game_job(job, game)
    from polyforge.unity.repairs import current_request

    current_request(policy)
    wall_path = policy.path("UnityProject/" + job["wall_fbx"])
    if hashlib.sha256(wall_path.read_bytes()).hexdigest() != job["wall_sha256"]:
        raise InputError("Boundary source hash changed", kind=ErrorKind.CONTRACT_FAILURE)
    return execute_game_checks(policy, job, standalone=standalone, _lock_held=_lock_held)


def execute_game_checks(
    policy: WorkspacePolicy,
    game: dict[str, Any],
    *,
    standalone: bool = False,
    cancel: threading.Event | None = None,
    _lock_held: bool = False,
) -> Result:
    config = configuration(policy)
    executable = unity_tool(config)
    run_id = "game-check-" + uuid4().hex[:16]
    relative = "runs/" + run_id
    request = atomic_json(policy, relative + "/game-input.json", game)
    suite = atomic_json(policy, relative + "/scenarios.json", core_suite(game))
    try:
        with (
            nullcontext() if _lock_held else unity_project_lock(policy, policy.path("UnityProject"))
        ):
            edit = policy.path(relative + "/editmode.xml")
            launch(
                policy,
                executable,
                config,
                relative + "/editmode",
                "tests",
                output=edit,
                test_filter="PolyForge.Game.Editor.Tests",
                game_input=request,
                cancel=cancel,
            )
            verify_test_xml(edit, GAME_EDIT_TESTS)
            play = policy.path(relative + "/playmode.xml")
            launch(
                policy,
                executable,
                config,
                relative + "/playmode",
                "tests",
                output=play,
                test_platform="PlayMode",
                test_filter="PolyForge.Game.Tests",
                game_input=request,
                cancel=cancel,
                scenario_input=suite,
                telemetry_directory=policy.path(relative + "/telemetry"),
            )
            verify_test_xml(play, PLAY_TESTS)
            verdict = score_telemetry(policy, relative, game)
            atomic_json(policy, relative + "/public-oracles.json", verdict)
            if verdict["status"] != "PASS":
                return Result(
                    status="FAIL",
                    exit_code=7,
                    error_code="PF-ARENA-ORACLE",
                    run_id=run_id,
                    evaluated_test_status="FAIL",
                    data=verdict,
                    evidence_paths=[relative + "/public-oracles.json"],
                    artifact_ids=register_game_artifacts(policy, relative, game["input_digest"]),
                )
            player_status = "NOT_RUN"
            smoke_status = "NOT_RUN"
            if standalone:
                player_path = policy.path(relative + "/player/PolyForgeArena.exe")
                player_job = {**game, "player_output": str(player_path)}
                player_request = atomic_json(policy, relative + "/player-input.json", player_job)
                launch(
                    policy,
                    executable,
                    config,
                    relative + "/player-build",
                    "player",
                    game_input=player_request,
                    cancel=cancel,
                )
                player_status = "PASS" if player_path.is_file() else "FAIL"
                if player_status != "PASS":
                    raise InputError("Player build produced no executable")
                player_evidence = player_path.parent / "smoke-evidence.json"
                outcome = run_process(
                    [
                        str(player_path),
                        "-batchmode",
                        "-nographics",
                        "-logFile",
                        "-",
                        "-polyforgeSmoke",
                        "-polyforgePlayerEvidence",
                        str(player_evidence),
                    ],
                    policy,
                    relative + "/player-smoke",
                    ProcessPolicy(
                        (player_path,),
                        timeout_seconds=min(60, config.unity_timeout_seconds),
                        max_output_bytes=config.max_output_bytes,
                        memory_limit_mb=config.memory_limit_mb,
                    ),
                    cancel=cancel,
                )
                atomic_json(
                    policy,
                    relative + "/player-smoke/process.json",
                    {
                        "returncode": outcome.returncode,
                        "reason": outcome.reason,
                        "duration_seconds": outcome.duration_seconds,
                    },
                )
                smoke = load_json(player_evidence)
                if (
                    outcome.reason != "exit"
                    or outcome.returncode != 0
                    or smoke.get("smoke_status") != "PASS"
                    or smoke.get("input_digest") != game["input_digest"]
                    or smoke.get("scene") != "PlayableArena"
                    or smoke.get("frames", 0) < 150
                ):
                    raise InputError("Standalone player smoke failed", kind=ErrorKind.TEST_FAILURE)
                smoke_status = "PASS"
            return Result(
                run_id=run_id,
                input_digest=game["input_digest"],
                evaluated_test_status="PASS",
                artifact_ids=register_game_artifacts(policy, relative, game["input_digest"]),
                data={
                    "development_acceptance": "PASS",
                    "oracles": verdict,
                    "manual_review": "REVIEW",
                    "standalone_build": player_status,
                    "player_smoke": smoke_status,
                    "profiling": "NOT_RUN",
                },
                evidence_paths=[
                    relative + "/editmode.xml",
                    relative + "/playmode.xml",
                    relative + "/public-oracles.json",
                ],
            )
    except (InputError, OSError, KeyboardInterrupt) as exc:
        kind = (
            exc.kind
            if isinstance(exc, InputError)
            else ErrorKind.INTERRUPTED
            if isinstance(exc, KeyboardInterrupt)
            else ErrorKind.PRODUCER_FAILURE
        )
        return replace(
            failure(kind, "PF-GAME-VERIFY", str(exc) or "interrupted"),
            run_id=run_id,
            evidence_paths=[relative],
            evaluated_test_status="FAIL" if kind == ErrorKind.TEST_FAILURE else "NOT_RUN",
            artifact_ids=register_game_artifacts(policy, relative, game["input_digest"]),
        )


def build_game(
    model: Manifest,
    recipes: dict[str, Any],
    *,
    dry_run: bool = False,
    allow_package_downloads: bool = False,
    standalone: bool = False,
    cancel: threading.Event | None = None,
) -> Result:
    game = compile_game_request(model)
    core_suite(game)
    if dry_run:
        return Result(
            input_digest=model.input_digest,
            data={
                "through": "S5",
                "dry_run": True,
                "game_contract": game,
                "execution_status": "NOT_RUN",
            },
        )
    from polyforge.unity.bridge import build_unity

    parent = build_unity(
        model, recipes, allow_package_downloads=allow_package_downloads, cancel=cancel
    )
    if parent.status != "PASS":
        return parent
    policy = WorkspacePolicy(model.workspace)
    config = configuration(policy)
    executable = unity_tool(config)
    from polyforge.blender.adapter import execute_recipe
    from polyforge.blender.recipes import expand_recipe
    from polyforge.capabilities.protocol import RunContext

    wall = expand_recipe(
        "wall",
        {
            "schema_version": "1.0.0",
            "asset_id": "arena_boundary",
            "parameters": {"size_m": [20, 1.2, 0.5]},
        },
        seed=game["seed"],
    )
    folder = reusable_export(policy, wall, game["seed"])
    if folder is None:
        result = execute_recipe(
            wall, RunContext(policy.root, seed=game["seed"], cancel=cancel), audit_export=True
        )
        if result.status != "PASS":
            return result
        folder = policy.path(result.data["source_blend"]).parent
    wall_target = policy.path(
        "UnityProject/Assets/PolyForgeGenerated/Game/Models/arena_boundary.fbx"
    )
    static = load_json(policy.path(f"runs/{parent.run_id}/request.json"))
    ground = next(a for a in static["assets"] if a["id"] == game["ground_id"])
    run_id = "game-build-" + uuid4().hex[:16]
    relative = "runs/" + run_id
    journal = RunJournal.create(policy, run_id, retry_limit=0)
    journal.transition("S4", "running")
    active_stage = "S4"
    try:
        with unity_project_lock(policy, policy.path("UnityProject")):
            policy.mkdir(wall_target.parent)
            shutil.copyfile(folder / "asset.fbx", wall_target)
            game.update(
                wall_fbx=wall_target.relative_to(policy.path("UnityProject")).as_posix(),
                wall_material=f"Assets/PolyForgeGenerated/Materials/{ground['id']}/{ground['materials'][0]['id']}.mat",
                wall_source=folder.relative_to(policy.root).as_posix(),
                wall_sha256=hashlib.sha256(wall_target.read_bytes()).hexdigest(),
            )
            request = atomic_json(policy, relative + "/game-input.json", game)
            output = policy.path(relative + "/bindings.json")
            launch(
                policy,
                executable,
                config,
                relative + "/native",
                "game",
                game_input=request,
                cancel=cancel,
                output=output,
            )
            bindings = load_json(output)
            if bindings.get("input_digest") != game["input_digest"] or not bindings.get(
                "scene_guid"
            ):
                raise InputError(
                    "Game scene binding identity mismatch", kind=ErrorKind.CONTRACT_FAILURE
                )
            archive_path = policy.path(relative + "/native-output.zip")
            project = policy.path("UnityProject")
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for scope in ("Assets", "Packages", "ProjectSettings"):
                    for source in sorted(policy.path(project / scope).rglob("*")):
                        source = policy.path(source)
                        if source.is_file():
                            archive.write(source, source.relative_to(project).as_posix())
            atomic_json(
                policy,
                relative + "/inputs.json",
                {
                    "input_digest": model.input_digest,
                    "manifest": model.data,
                    "input_fingerprints": model.input_fingerprints,
                    "parent_static_run": parent.run_id,
                    "unity_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                    "security_scope": "TRUSTED_LOCAL",
                    "isolation_verified": False,
                },
            )
            register_game_artifacts(policy, relative, model.input_digest)
            atomic_json(
                policy,
                ".polyforge/game-latest.json",
                {"input_digest": model.input_digest, "request": relative + "/game-input.json"},
            )
            journal.transition(
                "S4",
                "passed",
                evidence=[relative + "/bindings.json", relative + "/game-input.json"],
            )
        active_stage = "S5"
        journal.transition("S5", "running")
        checked = execute_game_checks(policy, game, standalone=standalone, cancel=cancel)
        atomic_json(
            policy,
            relative + "/feature-trace.json",
            feature_trace(model, checked.run_id, checked.status == "PASS"),
        )
        journal.transition(
            "S5",
            "passed" if checked.status == "PASS" else "failed",
            evidence=checked.evidence_paths if checked.status == "PASS" else [],
            note=checked.error_code or "",
        )
        return replace(
            checked,
            artifact_ids=[
                *checked.artifact_ids,
                *register_game_artifacts(policy, relative, model.input_digest),
            ],
            data={
                **checked.data,
                "through": "S5",
                "build_run_id": run_id,
                "scene": "UnityProject/Assets/PolyForgeGenerated/Game/PlayableArena.unity",
            },
        )
    except (InputError, OSError, KeyboardInterrupt) as exc:
        journal.transition(active_stage, "failed", note=str(exc) or "interrupted")
        kind = (
            exc.kind
            if isinstance(exc, InputError)
            else ErrorKind.INTERRUPTED
            if isinstance(exc, KeyboardInterrupt)
            else ErrorKind.PRODUCER_FAILURE
        )
        return replace(failure(kind, "PF-GAME-BUILD", str(exc)), run_id=run_id)
