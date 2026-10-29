"""Approved six-frame sprite import, native slicing and separate 2D behavior tests."""

import hashlib
from typing import Any
from uuid import uuid4

from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import ErrorKind, Result
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.runner.locks import unity_project_lock
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.sprites.contracts import route_2d
from polyforge.sprites.images import inspect_strip
from polyforge.unity.bootstrap import check_project_idle, installed_template, prepare_project
from polyforge.unity.bridge import configuration, launch, unity_tool
from polyforge.unity.evidence import verify_test_xml
from polyforge.unity.upgrade import sync_package

EDIT_TESTS = {
    "PolyForge.Sprite.Editor.Tests.SpriteTests." + n
    for n in (
        "ImportedSpritesKeepSixRectsPivotsAndStableIds",
        "FlipbookUsesActualSpriteReferencesAndOneSecondLoop",
        "MissingSpriteCurveIsRejected",
        "ReorderedSpriteReferenceCurveIsRejected",
        "ReplacingInputDisposesPreviousSubscription",
    )
}
PLAY_TESTS = {
    "PolyForge.Sprite.Tests.SpriteMotionTests." + n
    for n in (
        "LoopActuallyChangesImportedSpriteAndWraps",
        "InjectedInputMovesAndReal2DWallStopsPlayer",
        "KeyboardWASDControlsThe2DFixture",
        "DestroyedPlayerReleasesInputSubscription",
    )
}


def import_strip(inputs: dict[str, Any], context: RunContext) -> Result:
    validate_schema(inputs, "sprite_import.schema.json")
    policy = WorkspacePolicy(context.workspace)
    from polyforge.review.sprite_source import review_sprite_source

    source_review = review_sprite_source(policy, inputs, remember_requirement=not context.dry_run)
    if source_review["promotion"] != "APPROVED":
        return Result(status="REVIEW", exit_code=4, data={"source_review": source_review})
    route = route_2d({"output": "UNITY_2D", "source": inputs["source_kind"]})
    metadata = load_json(policy.path(inputs["metadata_file"]))
    if (
        not isinstance(metadata.get("source_license"), str)
        or not metadata["source_license"].strip()
    ):
        raise InputError("Sprite source license required before native import")
    frames = []
    for path in inputs["frame_files"]:
        source = policy.path(path)
        if source.stat().st_size > 16_777_216:
            raise InputError("Sprite frame exceeds bounded PNG budget")
        frames.append(source.read_bytes())
    atlas = policy.path(inputs["atlas_file"])
    if atlas.stat().st_size > 16_777_216:
        raise InputError("Sprite atlas exceeds bounded PNG budget")
    sheet = atlas.read_bytes()
    inspection = inspect_strip(frames, sheet, metadata)
    if metadata["frame_size"] != 128 or metadata["asset_id"] != inputs["asset_id"]:
        raise InputError("Unsupported native sprite dimensions/semantic identity")
    input_digest = canonical_digest(
        {
            "request": inputs,
            "metadata": metadata,
            "atlas_sha256": hashlib.sha256(sheet).hexdigest(),
            "frame_sha256": [hashlib.sha256(f).hexdigest() for f in frames],
        }
    )
    if context.dry_run:
        return Result(
            input_digest=input_digest,
            data={
                "dry_run": True,
                "execution_status": "NOT_RUN",
                "route": route,
                "inspection": inspection,
            },
        )
    config = configuration(policy)
    executable = unity_tool(config)
    project = prepare_project(policy, installed_template(executable), dry_run=True)
    marker = policy.path(".polyforge/unity-network-approval.json")
    authorized = marker.is_file() and load_json(marker).get("package_downloads_authorized") is True
    if not authorized and not inputs.get("allow_package_downloads", False):
        raise InputError(
            "Fresh 2D project needs explicit Unity template package download authorization",
            kind=ErrorKind.POLICY_DENIED,
        )
    check_project_idle(policy)
    run_id = "sprite-unity-" + (context.run_id or uuid4().hex[:16])
    relative = "runs/" + run_id
    # Keep byte comparisons for every preexisting 3D scene, not only the fixture's label.
    originals = {
        p.relative_to(policy.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in policy.path(project / "Assets/PolyForgeGenerated").rglob("*.unity")
        if "/Sprites/" not in p.as_posix()
    }
    with unity_project_lock(policy, policy.path("UnityProject"), cancel=context.cancel):
        if review_sprite_source(policy, inputs) != source_review:
            raise InputError("Sprite source approval changed before project lock")
        source_hashes = {f["path"]: f["sha256"] for f in source_review["candidate"]["files"]}
        for name, payload in [
            (inputs["atlas_file"], sheet),
            *zip(inputs["frame_files"], frames, strict=True),
        ]:
            if (
                source_hashes[policy.path(name).relative_to(policy.root).as_posix()]
                != hashlib.sha256(payload).hexdigest()
            ):
                raise InputError("Sprite bytes changed after source approval")
        if canonical_digest(metadata) != canonical_digest(
            load_json(policy.path(inputs["metadata_file"]))
        ):
            raise InputError("Sprite metadata changed after source approval")
        prepare_project(policy, installed_template(executable))
        if inputs.get("allow_package_downloads", False):
            atomic_json(
                policy,
                marker,
                {
                    "package_downloads_authorized": True,
                    "scope": "managed Unity project package resolution",
                    "trust": "TRUSTED_LOCAL",
                },
            )
        sync_package(policy)
        target = policy.path(project / "Assets/PolyForgeGenerated/Sprites/atlas.png")
        policy.mkdir(target.parent)
        if (
            not target.is_file()
            or hashlib.sha256(target.read_bytes()).hexdigest() != hashlib.sha256(sheet).hexdigest()
        ):
            target.write_bytes(sheet)
        digest = canonical_digest(metadata)
        request = atomic_json(
            policy,
            relative + "/input.json",
            {
                **metadata,
                "atlas_sha256": hashlib.sha256(sheet).hexdigest(),
                "metadata_digest": digest,
            },
        )
        atomic_json(
            policy,
            relative + "/approval.json",
            {
                "reviewer_id": "sprite_quality_inspector",
                "producer_id": "sprite_source",
                "independence": "DIFFERENT_ROLE_SAME_HOST",
                "technical_verdict": "APPROVED",
                "visual_review": "REVIEW",
                "metadata_digest": digest,
                "inspection": inspection,
                "source_kind": inputs["source_kind"],
                "source_license": metadata["source_license"],
            },
        )
        output = policy.path(relative + "/bindings.json")
        launch(
            policy,
            executable,
            config,
            relative + "/build",
            "sprites",
            game_input=request,
            output=output,
            cancel=context.cancel,
        )
        bindings = load_json(output)
        if (
            bindings["metadata_digest"] != digest
            or bindings["atlas_sha256"] != hashlib.sha256(sheet).hexdigest()
            or len(bindings["sprites"]) != 6
            or len({s["local_id"] for s in bindings["sprites"]}) != 6
        ):
            raise InputError(
                "Native sprite reference identity mismatch", kind=ErrorKind.CONTRACT_FAILURE
            )
        tests = {}
        for platform, expected, namespace in [
            ("EditMode", EDIT_TESTS, "PolyForge.Sprite.Editor.Tests"),
            ("PlayMode", PLAY_TESTS, "PolyForge.Sprite.Tests"),
        ]:
            xml = policy.path(relative + "/" + platform.lower() + ".xml")
            launch(
                policy,
                executable,
                config,
                relative + "/" + platform.lower(),
                "tests",
                game_input=request,
                output=xml,
                test_platform=platform,
                test_filter=namespace,
                cancel=context.cancel,
            )
            tests[platform] = verify_test_xml(xml, expected)
        for path, sha in originals.items():
            if hashlib.sha256(policy.path(path).read_bytes()).hexdigest() != sha:
                raise InputError(
                    "Preexisting 3D scene changed during sprite import",
                    kind=ErrorKind.CONTRACT_FAILURE,
                )
        atomic_json(policy, relative + "/preservation.json", {"before_and_after_sha256": originals})
        atomic_json(policy, relative + "/tests.json", tests)
        if review_sprite_source(policy, inputs) != source_review:
            raise InputError("Sprite source approval changed during native import")
        registered = [
            policy.path(relative + "/" + name)
            for name in (
                "bindings.json",
                "approval.json",
                "editmode.xml",
                "playmode.xml",
                "preservation.json",
            )
        ] + [
            policy.path(path)
            for path in [inputs["metadata_file"], inputs["atlas_file"], *inputs["frame_files"]]
        ]
        atomic_json(
            policy,
            relative + "/artifacts.json",
            {
                "artifacts": [
                    {
                        "relative_path": p.relative_to(policy.root).as_posix(),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "bytes": p.stat().st_size,
                    }
                    for p in registered
                ]
            },
        )
        return Result(
            run_id=run_id,
            input_digest=input_digest,
            evaluated_test_status="PASS",
            data={
                "bindings": bindings,
                "scene": "UnityProject/Assets/PolyForgeGenerated/Sprites/SpriteArena.unity",
                "route": route,
                "inspection": inspection,
                "visual_review": "REVIEW",
                "original_3d_scenes_preserved": True,
            },
            evidence_paths=[
                relative + "/bindings.json",
                relative + "/approval.json",
                relative + "/editmode.xml",
                relative + "/playmode.xml",
                relative + "/preservation.json",
            ],
        )
