"""A bounded checkpoint platformer using an already imported approved sprite prefab."""

from __future__ import annotations

import hashlib
import json
import re
import threading
import zipfile
from contextlib import nullcontext
from dataclasses import asdict, replace
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.runner.locks import unity_project_lock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import atomic_json
from polyforge.scenarios.platformer_oracle import (
    CORE_SCENARIOS,
    INPUT_SCENARIOS,
    MUTANT_SCENARIOS,
    evaluate,
    validate_trace,
)
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bridge import configuration, launch, unity_tool
from polyforge.unity.evidence import verify_test_xml
from polyforge.unity.game import register_game_artifacts
from polyforge.unity.upgrade import sync_package

EDIT_TESTS = {
    "PolyForge.Platformer.Editor.Tests.PlatformerTests." + n
    for n in (
        "SceneHasSpriteAnimationGroundsAndExplicitBindings",
        "ReplacingInputDisposesSubscription",
    )
}
PLAY_TESTS = {
    "PolyForge.Platformer.Tests.PlatformerTests." + n
    for n in (
        "PlayerMoves",
        "GroundCollision",
        "GroundedJump",
        "AirborneJump",
        "CheckpointRespawn",
        "HazardDamage",
        "HealthFailure",
        "GoalContact",
        "RestartResets",
        "RestartFailure",
        "Journey",
        "KeyboardMove",
        "KeyboardLeftMovesPlayer",
        "KeyboardJump",
        "KeyboardRestart",
        "InputDisconnectedMutant",
        "JumpDisabledMutant",
        "PlatformDisabledMutant",
        "CheckpointDisabledMutant",
        "DamageWithoutHealthMutant",
        "GoalDisabledMutant",
        "PrematureWinMutant",
        "RestartDisabledMutant",
        "DestroyedPlayerDisposesSubscription",
    )
}


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compile_platformer_request(inputs: dict[str, Any], policy: WorkspacePolicy) -> dict[str, Any]:
    validate_schema(inputs, "platformer.schema.json")
    receipt = policy.path(inputs["sprite_receipt"])
    report = load_json(receipt)
    approval_path = policy.path(receipt.parent / "approval.json")
    approval = load_json(approval_path)
    registry = load_json(policy.path(receipt.parent / "artifacts.json"))
    if (
        not isinstance(report, dict)
        or not isinstance(approval, dict)
        or not isinstance(registry, dict)
        or not isinstance(registry.get("artifacts"), list)
        or len(registry["artifacts"]) > 16384
        or any(
            not isinstance(r, dict)
            or not isinstance(r.get("relative_path"), str)
            or not isinstance(r.get("sha256"), str)
            for r in registry["artifacts"]
        )
    ):
        raise InputError("Malformed imported sprite receipt/approval registry")
    for path in (receipt, approval_path):
        relative = path.relative_to(policy.root).as_posix()
        matching = [r for r in registry["artifacts"] if r["relative_path"] == relative]
        if len(matching) != 1 or matching[0]["sha256"] != _hash(path):
            raise InputError("Sprite receipt/approval does not match imported artifact registry")
    if (
        report.get("status") != "PASS"
        or report.get("unity_version") != "6000.6.3f1"
        or approval.get("technical_verdict") != "APPROVED"
        or approval.get("metadata_digest") != report.get("metadata_digest")
        or not approval.get("source_license")
    ):
        raise InputError("Approved Unity 6000.6.3f1 sprite receipt required")
    folder = policy.path("UnityProject/Assets/PolyForgeGenerated/Sprites")
    sources = {}
    for name in ("atlas.png", "Robot2D.prefab", "Walk.anim", "Sprite.controller"):
        for suffix in ("", ".meta"):
            path = policy.path(folder / (name + suffix))
            if not path.is_file() or path.stat().st_size > 16_777_216:
                raise InputError("Missing/bounded imported sprite asset: " + name + suffix)
            sources[path.relative_to(policy.root).as_posix()] = _hash(path)
    if _hash(policy.path(folder / "atlas.png")) != report["atlas_sha256"]:
        raise InputError("Imported atlas changed after source receipt")
    for name, field in (("Robot2D.prefab", "prefab_guid"), ("Walk.anim", "clip_guid")):
        meta = policy.path(folder / (name + ".meta")).read_text("utf-8")
        match = re.search(r"(?m)^guid: ([0-9a-f]{32})\s*$", meta)
        if not match or match[1] != report.get(field):
            raise InputError("Imported prefab/animation GUID changed")
    sprites = report.get("sprites", [])
    if (
        not isinstance(sprites, list)
        or len(sprites) != 6
        or any(
            not isinstance(s, dict)
            or type(s.get("local_id")) is not int
            or s["local_id"] == 0
            or not -(2**63) <= s["local_id"] < 2**63
            for s in sprites
        )
        or {s.get("name") for s in sprites} != {f"frame-{i}" for i in range(6)}
        or len({s.get("local_id") for s in sprites}) != 6
    ):
        raise InputError("Six stable imported sprite frame references required")
    for path in (receipt, approval_path):
        sources[path.relative_to(policy.root).as_posix()] = _hash(path)
    game = {
        "schema_version": "1.0.0",
        "scene_id": inputs["scene_id"],
        "seed": inputs["seed"],
        "scene_path": "Assets/PolyForgeGenerated/Platformer/SpritePlatformer.unity",
        "sprite_prefab": "Assets/PolyForgeGenerated/Sprites/Robot2D.prefab",
        "sprite_prefab_guid": report["prefab_guid"],
        "atlas_sha256": report["atlas_sha256"],
        "metadata_digest": report["metadata_digest"],
        "source_hashes": sources,
        "spawn": [-8, 0, 0],
        "checkpoint_position": [-3, 0, 0],
        "goal_center": [8, 1, 0],
        "goal_size": [1, 2, 1],
        "hazard_center": [0.5, 0.3, 0],
        "hazard_size": [0.8, 0.6, 1],
        "platforms": [
            {"id": "ground_" + str(i), "center": [x, -0.25, 0], "size": [w, 0.5, 1]}
            for i, (x, w) in enumerate(((-7, 6), (-1, 6), (4, 2), (8, 4)))
        ],
        "lives": 3,
        "gravity_scale": 2,
        "jump_speed": 8,
        "move_speed": 4,
        "fixed_delta_seconds": 0.02,
        "layout": inputs["layout"],
    }
    game["input_digest"] = canonical_digest({"request": inputs, "source_hashes": sources})
    game["game_contract_digest"] = canonical_digest(game)
    return game


def core_suite(game: dict[str, Any]) -> dict[str, Any]:
    suite: dict[str, Any] = json.loads(
        files("polyforge").joinpath("data/platformer_scenarios.json").read_text("utf-8")
    )
    for case in suite["scenarios"]:
        case["schedule_digest"] = canonical_digest(case)
    return suite


def score_telemetry(
    policy: WorkspacePolicy, relative: str, game: dict[str, Any], *, standalone: bool = False
) -> dict[str, Any]:
    cases = {c["id"]: c for c in core_suite(game)["scenarios"]}
    results = {}
    identifiers = (
        CORE_SCENARIOS if standalone else (*CORE_SCENARIOS, *INPUT_SCENARIOS, *MUTANT_SCENARIOS)
    )
    for identifier in identifiers:
        case = cases[MUTANT_SCENARIOS.get(identifier, INPUT_SCENARIOS.get(identifier, identifier))]
        trace = load_json(
            policy.path(relative + "/telemetry/" + identifier + ".json"), max_bytes=8_388_608
        )
        validate_trace(
            trace, game, identifier, sum(s["ticks"] for s in case["steps"]), case["schedule_digest"]
        )
        scored = evaluate(trace)
        mutant = identifier in MUTANT_SCENARIOS
        results[identifier] = {
            **scored,
            "mutant": mutant,
            "gate_status": "PASS"
            if (scored["status"] == ("FAIL" if mutant else "PASS"))
            else "FAIL",
        }
    return {
        "status": "PASS" if all(r["gate_status"] == "PASS" for r in results.values()) else "FAIL",
        "scenarios": results,
        "scope": "PUBLIC_DEVELOPMENT",
        "hidden_evaluation": "NOT_RUN",
    }


def _preserved(policy: WorkspacePolicy) -> dict[str, str]:
    root = policy.path("UnityProject/Assets/PolyForgeGenerated")
    return {
        p.relative_to(policy.root).as_posix(): _hash(policy.path(p))
        for p in root.rglob("*")
        if p.is_file()
        and "Platformer" not in p.relative_to(root).parts
        and p.relative_to(root).as_posix() != "Platformer.meta"
    }


def execute_platformer_checks(
    policy: WorkspacePolicy,
    game: dict[str, Any],
    *,
    standalone: bool = False,
    cancel: threading.Event | None = None,
    _lock_held: bool = False,
) -> Result:
    config = configuration(policy)
    executable = unity_tool(config)
    run_id = "platformer-check-" + uuid4().hex[:16]
    relative = "runs/" + run_id
    request = atomic_json(policy, relative + "/game-input.json", game)
    suite = atomic_json(policy, relative + "/scenarios.json", core_suite(game))
    try:
        with (
            nullcontext()
            if _lock_held
            else unity_project_lock(policy, policy.path("UnityProject"), cancel=cancel)
        ):
            for platform, expected, namespace in (
                ("EditMode", EDIT_TESTS, "PolyForge.Platformer.Editor.Tests"),
                ("PlayMode", PLAY_TESTS, "PolyForge.Platformer.Tests"),
            ):
                xml = policy.path(relative + "/" + platform.lower() + ".xml")
                launch(
                    policy,
                    executable,
                    config,
                    relative + "/" + platform.lower(),
                    "tests",
                    output=xml,
                    test_platform=platform,
                    test_filter=namespace,
                    game_input=request,
                    scenario_input=suite,
                    telemetry_directory=policy.path(relative + "/telemetry"),
                    cancel=cancel,
                )
                verify_test_xml(xml, expected)
            verdict = score_telemetry(policy, relative, game)
            atomic_json(policy, relative + "/public-oracles.json", verdict)
            if verdict["status"] != "PASS":
                raise InputError(
                    "Platformer physical behavior or mutation gate failed",
                    kind=ErrorKind.TEST_FAILURE,
                )
            player_status = smoke_status = gameplay_status = "NOT_RUN"
            player_path = None
            if standalone:
                player_path = policy.path(relative + "/player/PolyForgePlatformer.exe")
                player_request = atomic_json(
                    policy,
                    relative + "/player-input.json",
                    {**game, "player_output": str(player_path)},
                )
                launch(
                    policy,
                    executable,
                    config,
                    relative + "/player-build",
                    "platformer-player",
                    game_input=player_request,
                    cancel=cancel,
                )
                if not player_path.is_file():
                    raise InputError("Standalone build produced no platformer executable")
                player_status = "PASS"
                player_relative = relative + "/standalone"
                player_report = policy.path(player_relative + "/smoke.json")
                policy.mkdir(player_relative + "/telemetry")
                outcome = run_process(
                    [
                        str(player_path),
                        "-batchmode",
                        "-nographics",
                        "-logFile",
                        "-",
                        "-polyforgePlatformerSmoke",
                        "-polyforgeScenarioInput",
                        str(suite),
                        "-polyforgeTelemetry",
                        str(policy.path(player_relative + "/telemetry")),
                        "-polyforgePlayerEvidence",
                        str(player_report),
                    ],
                    policy,
                    player_relative + "/process",
                    ProcessPolicy(
                        (player_path,),
                        timeout_seconds=min(60, config.unity_timeout_seconds),
                        max_output_bytes=config.max_output_bytes,
                        memory_limit_mb=config.memory_limit_mb,
                    ),
                    cancel=cancel,
                )
                atomic_json(policy, player_relative + "/process/process.json", asdict(outcome))
                smoke = load_json(player_report)
                if (
                    outcome.reason != "exit"
                    or outcome.returncode != 0
                    or smoke.get("input_digest") != game["input_digest"]
                    or smoke.get("scene") != "SpritePlatformer"
                    or smoke.get("frames", 0) < 100
                ):
                    raise InputError(
                        "Standalone platformer smoke failed", kind=ErrorKind.TEST_FAILURE
                    )
                smoke_status = "PASS"
                player_verdict = score_telemetry(policy, player_relative, game, standalone=True)
                atomic_json(policy, player_relative + "/public-oracles.json", player_verdict)
                gameplay_status = player_verdict["status"]
                if gameplay_status != "PASS":
                    raise InputError(
                        "Standalone platformer gameplay failed", kind=ErrorKind.TEST_FAILURE
                    )
            return Result(
                run_id=run_id,
                input_digest=game["input_digest"],
                evaluated_test_status="PASS",
                data={
                    "development_acceptance": "PASS",
                    "oracles": verdict,
                    "standalone_build": player_status,
                    "player_smoke": smoke_status,
                    "standalone_gameplay": gameplay_status,
                    "player_path": str(player_path) if player_path else None,
                    "profiling": "NOT_RUN",
                    "manual_review": "REVIEW",
                    "game_status": "PARTIAL",
                },
                evidence_paths=[relative + "/public-oracles.json"],
                artifact_ids=register_game_artifacts(policy, relative, game["input_digest"]),
            )
    except (InputError, OSError, KeyboardInterrupt) as exc:
        kind = (
            exc.kind
            if isinstance(exc, InputError)
            else (
                ErrorKind.INTERRUPTED
                if isinstance(exc, KeyboardInterrupt)
                else ErrorKind.PRODUCER_FAILURE
            )
        )
        return replace(
            failure(kind, "PF-PLATFORMER-VERIFY", str(exc)),
            run_id=run_id,
            evaluated_test_status="FAIL" if kind == ErrorKind.TEST_FAILURE else "NOT_RUN",
            artifact_ids=register_game_artifacts(policy, relative, game["input_digest"]),
        )


def build_platformer(
    workspace: Path,
    inputs: dict[str, Any],
    *,
    dry_run: bool = False,
    standalone: bool = False,
    cancel: threading.Event | None = None,
) -> Result:
    policy = WorkspacePolicy(workspace)
    game = compile_platformer_request(inputs, policy)
    standalone = standalone or inputs.get("standalone", False)
    if dry_run:
        return Result(
            input_digest=game["input_digest"],
            data={
                "dry_run": True,
                "game_contract": game,
                "execution_status": "NOT_RUN",
                "game_status": "PARTIAL",
            },
        )
    config = configuration(policy)
    executable = unity_tool(config)
    run_id = "platformer-build-" + uuid4().hex[:16]
    relative = "runs/" + run_id
    with unity_project_lock(policy, policy.path("UnityProject"), cancel=cancel):
        if compile_platformer_request(inputs, policy) != game:
            raise InputError("Sprite source identity changed before native lock")
        before = _preserved(policy)
        sync_package(policy)
        request = atomic_json(policy, relative + "/game-input.json", game)
        atomic_json(policy, relative + "/inputs.json", inputs)
        output = policy.path(relative + "/bindings.json")
        launch(
            policy,
            executable,
            config,
            relative + "/native",
            "platformer",
            game_input=request,
            output=output,
            cancel=cancel,
        )
        bindings = load_json(output)
        if (
            bindings.get("input_digest") != game["input_digest"]
            or not bindings.get("scene_guid")
            or bindings.get("source_prefab_guid") != game["sprite_prefab_guid"]
        ):
            raise InputError(
                "Platformer native binding identity mismatch", kind=ErrorKind.CONTRACT_FAILURE
            )
        if before != _preserved(policy):
            raise InputError(
                "Platformer build changed a preexisting generated asset",
                kind=ErrorKind.CONTRACT_FAILURE,
            )
        atomic_json(policy, relative + "/preservation.json", {"before_and_after_sha256": before})
        archive = policy.path(relative + "/native-output.zip")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as saved:
            for scope in ("Assets", "Packages", "ProjectSettings"):
                for p in sorted(policy.path("UnityProject/" + scope).rglob("*")):
                    p = policy.path(p)
                    if p.is_file():
                        saved.write(p, p.relative_to(policy.path("UnityProject")).as_posix())
        atomic_json(
            policy,
            ".polyforge/platformer-latest.json",
            {
                "input_digest": game["input_digest"],
                "request": relative + "/game-input.json",
                "inputs": relative + "/inputs.json",
                "archive": relative + "/native-output.zip",
            },
        )
        built_artifacts = register_game_artifacts(policy, relative, game["input_digest"])
    checked = execute_platformer_checks(policy, game, standalone=standalone, cancel=cancel)
    if checked.status == "PASS":
        check_relative = "runs/" + str(checked.run_id)
        atomic_json(
            policy,
            check_relative + "/delivery.json",
            {
                "schema_version": "1.0.0",
                "build_run_id": run_id,
                "input_digest": game["input_digest"],
                "standalone_requested": standalone,
            },
        )
        register_game_artifacts(policy, check_relative, game["input_digest"])
        built_registry = load_json(policy.path(relative + "/artifacts.json"))
        checked_registry = load_json(policy.path(check_relative + "/artifacts.json"))
        # A handoff must include editable production, not only passing check labels.
        all_records = [*built_registry["artifacts"], *checked_registry["artifacts"]]
        atomic_json(policy, check_relative + "/artifacts.json", {"artifacts": all_records})
        checked = replace(checked, artifact_ids=[row["artifact_id"] for row in all_records])
    return replace(
        checked,
        artifact_ids=list(dict.fromkeys([*built_artifacts, *checked.artifact_ids])),
        data={
            **checked.data,
            "build_run_id": run_id,
            "scene": "UnityProject/" + game["scene_path"],
        },
    )
