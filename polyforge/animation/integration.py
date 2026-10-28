"""Native animation import only after a digest-bound candidate approval."""

import hashlib
import shutil
import threading
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.locks import FileLock
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bootstrap import check_project_idle, installed_template, prepare_project
from polyforge.unity.bridge import configuration, launch, unity_tool
from polyforge.unity.evidence import verify_test_xml
from polyforge.unity.upgrade import sync_package
from polyforge.workforce.workers import check_candidate


def validate_import_source(
    policy: WorkspacePolicy, candidate: dict[str, Any], produced: dict[str, Any]
) -> Path:
    check_candidate(policy, candidate)
    relative = produced.get("data", {}).get("fbx_path")
    records = [
        f for f in candidate["files"] if f["path"] == relative and f["path"].endswith("/robot.fbx")
    ]
    if produced.get("status") != "PASS" or len(records) != 1:
        raise InputError(
            "FBX source is not a member of the approved candidate", kind=ErrorKind.CONTRACT_FAILURE
        )
    source = policy.path(relative)
    if hashlib.sha256(source.read_bytes()).hexdigest() != records[0]["sha256"]:
        raise InputError("Approved FBX changed", kind=ErrorKind.CONTRACT_FAILURE)
    return source


EDIT_TESTS = {
    "PolyForge.Animation.Editor.Tests.AnimationTests." + name
    for name in (
        "ImportedRigHasTwoLoopingClipsAndNativeSkinBindings",
        "AnimatorGraphHasBothTransitionsAndInPlaceRootPolicy",
        "WrongBoneMappingIsRejected",
        "DisconnectedLimbIsRejected",
        "MissingTransitionIsRejected",
    )
}
PLAY_TESTS = {
    "PolyForge.Animation.Tests.MotionTests." + name
    for name in (
        "IdleWalkIdleChangesActualSkinAndKeepsRootInPlace",
        "PatrolDrivesWalkAndTerminalStateDrivesIdle",
    )
}


def integrate_animation(
    workspace: Path,
    candidate: dict[str, Any],
    produced: dict[str, Any],
    *,
    cancel: threading.Event | None = None,
    operation_id: str | None = None,
) -> Result:
    policy = WorkspacePolicy(workspace)
    check_candidate(policy, candidate)
    source = validate_import_source(policy, candidate, produced)
    config = configuration(policy)
    executable = unity_tool(config)
    project = prepare_project(policy, installed_template(executable), dry_run=True)
    scene = policy.path(project / "Assets/PolyForgeGenerated/Game/PlayableArena.unity")
    if not scene.is_file():
        raise InputError("Animation arena integration needs an existing verified S5 arena")
    from polyforge.contracts.manifest import load_manifest
    from polyforge.unity.game import compile_game_request, validate_game_job
    from polyforge.unity.repairs import current_request

    current_request(policy)
    current = compile_game_request(load_manifest(policy.path("game_manifest.json")))
    saved = load_json(policy.path(load_json(policy.path(".polyforge/game-latest.json"))["request"]))
    validate_game_job(saved, current)
    original = hashlib.sha256(scene.read_bytes()).hexdigest()
    run_id = "animation-" + (operation_id[3:] if operation_id else uuid4().hex[:16])
    relative = "runs/" + run_id
    check_project_idle(policy)
    with FileLock(policy, ".polyforge/locks/unity-project.lock"):
        sync_package(policy)
        model = "Assets/PolyForgeGenerated/Animation/robot.fbx"
        target = policy.path(project / model)
        policy.mkdir(target.parent)
        expected_source = hashlib.sha256(source.read_bytes()).hexdigest()
        existing = policy.path(relative + "/bindings.json")
        recovered = False
        if existing.is_file():
            prior = load_json(existing)
            recovered = (
                prior.get("candidate_digest") == candidate["candidate_digest"]
                and all(
                    hashlib.sha256(policy.path(project / item["path"]).read_bytes()).hexdigest()
                    == item["sha256"]
                    for item in prior.get("output_files", [])
                )
                and bool(prior.get("output_files"))
            )
            if not recovered:
                raise InputError(
                    "Interrupted native output differs from its operation receipt",
                    kind=ErrorKind.CONTRACT_FAILURE,
                )
        if not recovered:
            shutil.copyfile(source, target)
        if hashlib.sha256(target.read_bytes()).hexdigest() != expected_source:
            raise InputError(
                "Copied FBX differs from approved bytes", kind=ErrorKind.CONTRACT_FAILURE
            )
        motion = next(f for f in candidate["files"] if f["path"].endswith("/motion.json"))
        request = atomic_json(
            policy,
            relative + "/input.json",
            {
                "candidate_digest": candidate["candidate_digest"],
                "model_path": model,
                "asset_id": load_json(policy.path(motion["path"]))["asset_id"],
                "expected_fbx_sha256": expected_source,
                "input_digest": current["input_digest"],
            },
        )
        output = policy.path(relative + "/bindings.json")
        try:
            if not recovered:
                launch(
                    policy,
                    executable,
                    config,
                    relative + "/build",
                    "animation",
                    game_input=request,
                    output=output,
                    cancel=cancel,
                )
            bindings = load_json(output)
            if bindings["candidate_digest"] != candidate["candidate_digest"] or not all(
                bindings[k] for k in ("model_guid", "prefab_guid", "scene_guid")
            ):
                raise InputError(
                    "Native animation candidate binding mismatch", kind=ErrorKind.CONTRACT_FAILURE
                )
            for platform, expected, namespace in [
                ("EditMode", EDIT_TESTS, "PolyForge.Animation.Editor.Tests"),
                ("PlayMode", PLAY_TESTS, "PolyForge.Animation.Tests"),
            ]:
                xml = policy.path(relative + "/" + platform.lower() + ".xml")
                launch(
                    policy,
                    executable,
                    config,
                    relative + "/" + platform.lower(),
                    "tests",
                    test_platform=platform,
                    test_filter=namespace,
                    game_input=request,
                    output=xml,
                    cancel=cancel,
                )
                verify_test_xml(xml, expected)
            if hashlib.sha256(scene.read_bytes()).hexdigest() != original:
                raise InputError("Original Phase6 scene changed", kind=ErrorKind.CONTRACT_FAILURE)
            atomic_json(
                policy,
                relative + "/preservation.json",
                {
                    "playable_scene_sha256": original,
                    "after_sha256": hashlib.sha256(scene.read_bytes()).hexdigest(),
                },
            )
            return Result(
                run_id=run_id,
                evaluated_test_status="PASS",
                data={
                    "bindings": bindings,
                    "scene": "UnityProject/Assets/PolyForgeGenerated/Animation/"
                    "AnimationArena.unity",
                    "original_arena_preserved": True,
                },
                evidence_paths=[
                    relative + "/bindings.json",
                    relative + "/editmode.xml",
                    relative + "/playmode.xml",
                    relative + "/preservation.json",
                ],
            )
        except InputError as exc:
            result = failure(exc.kind, exc.code, str(exc))
            from dataclasses import replace

            return replace(result, run_id=run_id, evidence_paths=[relative])
