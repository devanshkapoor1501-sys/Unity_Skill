"""Immutable candidate seals and read-only technical review receipts."""

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Any

from polyforge.contracts.results import ErrorKind, Result
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.security.paths import WorkspacePolicy
from polyforge.workforce.models import validate_review
from polyforge.workforce.permissions import assert_public_path


def verify_platformer_archive(path: Path, game: dict[str, Any], scene_guid: str) -> None:
    """Read bounded editable-delivery members, without extraction or code execution."""
    try:
        if path.stat().st_size > 1_073_741_824:
            raise InputError("Editable platformer archive exceeds its byte budget")
        with zipfile.ZipFile(path) as archive:
            entries = archive.infolist()
            if len(entries) > 8192 or len({item.filename for item in entries}) != len(entries):
                raise InputError("Ambiguous or oversized editable platformer archive")
            names = {item.filename for item in entries}
            scene, prefab = game["scene_path"], game["sprite_prefab"]
            atlas = "Assets/PolyForgeGenerated/Sprites/atlas.png"
            if not {scene, scene + ".meta", prefab, prefab + ".meta", atlas} <= names:
                raise InputError("Editable platformer archive lacks its scene/sprite sources")
            if not 0 < archive.getinfo(scene).file_size <= 16_777_216:
                raise InputError("Editable platformer scene is empty or oversized")

            def read(name: str, limit: int) -> bytes:
                if archive.getinfo(name).file_size > limit:
                    raise InputError("Editable source exceeds its bounded read budget")
                with archive.open(name) as stream:
                    data = stream.read(limit + 1)
                if len(data) > limit:
                    raise InputError("Editable source exceeds its bounded read budget")
                return data

            for name, expected in ((scene, scene_guid), (prefab, game["sprite_prefab_guid"])):
                meta = read(name + ".meta", 4096).decode("utf-8-sig")
                if re.findall(r"(?m)^guid:\s*([a-f0-9]{32})\s*$", meta) != [expected]:
                    raise InputError("Editable scene/prefab GUID differs from native bindings")
            if hashlib.sha256(read(atlas, 16_777_216)).hexdigest() != game["atlas_sha256"]:
                raise InputError("Editable sprite atlas differs from the approved native source")
            for source, digest in game.get("source_hashes", {}).items():
                if source.startswith("UnityProject/"):
                    name = source.removeprefix("UnityProject/")
                    if (
                        name not in names
                        or hashlib.sha256(read(name, 16_777_216)).hexdigest() != digest
                    ):
                        raise InputError(
                            "Editable imported source differs from its frozen fingerprint"
                        )
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        raise InputError("Invalid editable platformer archive: " + str(exc)) from exc


def seal_candidate(policy: WorkspacePolicy, result: Result, brief_digest: str) -> dict[str, Any]:
    if result.status != "PASS" or result.run_id is None:
        raise InputError("Cannot seal unsuccessful/unidentified production")
    registry = load_json(policy.path("runs/" + result.run_id + "/artifacts.json"))
    records = []
    for item in registry["artifacts"]:
        assert_public_path(policy, item["relative_path"])
        path = policy.path(item["relative_path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise InputError("Candidate source digest mismatch", kind=ErrorKind.CONTRACT_FAILURE)
        records.append({"path": path.relative_to(policy.root).as_posix(), "sha256": item["sha256"]})
    candidate = {
        "schema_version": "1.0.0",
        "artifact_id": result.run_id.replace("-", "_"),
        "production_run_id": result.run_id,
        "producer_id": "producer",
        "brief_digest": brief_digest,
        "revision": 1,
        "files": sorted(records, key=lambda r: r["path"]),
    }
    candidate["candidate_digest"] = canonical_digest(candidate)
    validate_schema(candidate, "handoff.schema.json")
    return candidate


def check_candidate(policy: WorkspacePolicy, candidate: dict[str, Any]) -> None:
    validate_schema(candidate, "handoff.schema.json")
    identity = {k: v for k, v in candidate.items() if k != "candidate_digest"}
    if canonical_digest(identity) != candidate["candidate_digest"]:
        raise InputError("Candidate handoff digest mismatch", kind=ErrorKind.CONTRACT_FAILURE)
    for item in candidate["files"]:
        assert_public_path(policy, item["path"])
    for item in candidate["files"]:
        if hashlib.sha256(policy.path(item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise InputError("Candidate changed after sealing", kind=ErrorKind.CONTRACT_FAILURE)


def inspect_candidate(
    policy: WorkspacePolicy,
    candidate: dict[str, Any],
    request: dict[str, Any],
    *,
    technical_only: bool = False,
) -> dict[str, Any]:
    check_candidate(policy, candidate)
    if request.get("task_class") not in {"ANIMATE", "CREATE_ASSET", "BUILD_GAME"}:
        raise InputError("No technical inspector for this task class")
    if candidate["brief_digest"] != canonical_digest(request["brief"]):
        raise InputError("Review brief differs from the sealed original brief")
    inventory = {item["path"] for item in candidate["files"]}
    roots = {
        parts[1]
        for item in candidate["files"]
        if len(parts := Path(item["path"]).parts) >= 3
        and parts[0] == "runs"
        and parts[1].replace("-", "_") == candidate["artifact_id"]
    }
    run = candidate.get("production_run_id")
    if run is None and len(roots) == 1:
        run = next(iter(roots))  # Backward compatibility for older sealed handoffs.
    if run not in roots:
        raise InputError("Candidate lacks a unique sealed production-run identity")
    if request["task_class"] == "ANIMATE":
        from polyforge.animation.contract import inspect_motion

        required = {
            "runs/" + run + "/asset/" + name
            for name in ("motion.json", "source.blend", "robot.fbx")
        }
        if not required <= inventory or request["capability_id"] != "animation.robot.rig.v1":
            raise InputError("Animation review requires the complete sealed source bundle")
        motion = load_json(policy.path("runs/" + run + "/asset/motion.json"))
        if motion["asset_id"] != request["input"]["asset_id"]:
            raise InputError("Motion semantic asset identity mismatch")
        inspect_motion(motion)
    elif request.get("capability_id") == "asset.package.build.v1":
        from polyforge.assets.contracts import require_bundle_approval

        prefix = "runs/" + run + "/"
        required = {prefix + n for n in ("spec.json", "bundle.json", "review.json")}
        if not required <= inventory:
            raise InputError("Asset review lacks sealed specification/bundle/inspection")
        spec = load_json(policy.path(prefix + "spec.json"))
        for reference in spec.get("references", []):
            if isinstance(reference, dict) and isinstance(reference.get("path"), str):
                assert_public_path(policy, reference["path"])
        if spec != request["input"]["spec"] or spec["brief"] != request["brief"]:
            raise InputError("Specialist specification differs from the original request")
        bundle = load_json(policy.path(prefix + "bundle.json"))
        if not {item["path"] for item in bundle["slots"].values()} <= inventory:
            raise InputError("Asset source slot is not sealed in the candidate")
        if technical_only:
            from polyforge.assets.contracts import inspect_bundle

            observed = inspect_bundle(policy.root, bundle, spec)
            if observed["technical_verdict"] != "APPROVED":
                raise InputError("Asset technical review failed")
        else:
            require_bundle_approval(
                policy.root, bundle, load_json(policy.path(prefix + "review.json")), spec
            )
    elif request.get("capability_id", "").startswith("sprite."):
        from polyforge.sprites.images import inspect_strip

        if request["capability_id"] == "sprite.robot.bake.v1":
            folder = "runs/" + run + "/asset/"
            metadata_file = folder + "atlas.json"
            atlas_file = folder + "atlas.png"
            frame_files = [folder + f"frame-{i}.png" for i in range(6)]
        else:
            metadata_file = request["input"]["metadata_file"]
            atlas_file = request["input"]["atlas_file"]
            frame_files = request["input"]["frame_files"]
            from polyforge.sprites.integration import EDIT_TESTS, PLAY_TESTS
            from polyforge.unity.evidence import verify_test_xml

            for name, tests in [("editmode.xml", EDIT_TESTS), ("playmode.xml", PLAY_TESTS)]:
                if "runs/" + run + "/" + name not in inventory:
                    raise InputError("Sprite review lacks sealed native test evidence")
                verify_test_xml(policy.path("runs/" + run + "/" + name), tests)
        if not {metadata_file, atlas_file, *frame_files} <= inventory:
            raise InputError("Sprite sources are not completely sealed")
        metadata = load_json(policy.path(metadata_file))
        if metadata.get("asset_id") != request["input"]["asset_id"] or not metadata.get(
            "source_license"
        ):
            raise InputError("Sprite semantic identity/license mismatch")
        inspect_strip(
            [policy.path(p).read_bytes() for p in frame_files],
            policy.path(atlas_file).read_bytes(),
            metadata,
        )
    elif request["task_class"] == "CREATE_ASSET":
        from polyforge.blender.recipes import RECIPES, expand_recipe, validate_geometry

        kind = next(k for k, v in RECIPES.items() if v == request["capability_id"])
        recipe = expand_recipe(kind, request["input"], seed=request.get("seed", 42))
        validate_geometry(recipe, load_json(policy.path("runs/" + run + "/asset/metrics.json")))
    elif request.get("capability_id") == "unity.game.platformer.v1":
        from polyforge.unity.evidence import verify_test_xml
        from polyforge.unity.platformer import (
            EDIT_TESTS,
            PLAY_TESTS,
            compile_platformer_request,
            score_telemetry,
        )

        prefix = "runs/" + run + "/"
        expected = {
            prefix + n for n in ("game-input.json", "editmode.xml", "playmode.xml", "delivery.json")
        }
        if not expected <= inventory:
            raise InputError("Platformer review lacks sealed native contract/test evidence")
        current = compile_platformer_request(request["input"], policy)
        if load_json(policy.path(prefix + "game-input.json")) != current:
            raise InputError("Platformer sources differ from the sealed native contract")
        delivery = load_json(policy.path(prefix + "delivery.json"))
        if (
            not isinstance(delivery, dict)
            or delivery.get("schema_version") != "1.0.0"
            or delivery.get("input_digest") != current["input_digest"]
            or not isinstance(delivery.get("build_run_id"), str)
            or not re.fullmatch(r"platformer-build-[a-f0-9]{16}", delivery["build_run_id"])
            or type(delivery.get("standalone_requested")) is not bool
        ):
            raise InputError("Platformer delivery lacks its matching build identity")
        build_prefix = "runs/" + delivery["build_run_id"] + "/"
        required_build = {
            build_prefix + name
            for name in (
                "native-output.zip",
                "bindings.json",
                "game-input.json",
                "inputs.json",
                "preservation.json",
            )
        }
        if not required_build <= inventory:
            raise InputError("Platformer review lacks sealed editable production evidence")
        if (
            load_json(policy.path(build_prefix + "game-input.json")) != current
            or load_json(policy.path(build_prefix + "inputs.json")) != request["input"]
        ):
            raise InputError("Editable production belongs to a different platformer request")
        bindings = load_json(policy.path(build_prefix + "bindings.json"))
        if (
            not isinstance(bindings, dict)
            or not bindings.get("scene_guid")
            or bindings.get("input_digest") != current["input_digest"]
            or bindings.get("source_prefab_guid") != current["sprite_prefab_guid"]
        ):
            raise InputError("Editable platformer bindings differ from its approved sources")
        verify_platformer_archive(
            policy.path(build_prefix + "native-output.zip"), current, bindings["scene_guid"]
        )
        from polyforge.scenarios.platformer_oracle import (
            CORE_SCENARIOS,
            INPUT_SCENARIOS,
            MUTANT_SCENARIOS,
        )

        traces = {
            prefix + "telemetry/" + name + ".json"
            for name in (*CORE_SCENARIOS, *INPUT_SCENARIOS, *MUTANT_SCENARIOS)
        }
        if not traces <= inventory:
            raise InputError("Platformer review lacks sealed physical scenario evidence")
        verify_test_xml(policy.path(prefix + "editmode.xml"), EDIT_TESTS)
        verify_test_xml(policy.path(prefix + "playmode.xml"), PLAY_TESTS)
        if score_telemetry(policy, prefix.rstrip("/"), current)["status"] != "PASS":
            raise InputError("Platformer independent physical review failed")
        if request["input"].get("standalone", False) and not delivery["standalone_requested"]:
            raise InputError("Platformer delivery omitted requested standalone verification")
        if delivery["standalone_requested"]:
            standalone_prefix = prefix + "standalone/"
            required_player = {
                standalone_prefix + name for name in ("smoke.json", "process/process.json")
            }
            required_player.update(
                standalone_prefix + "telemetry/" + name + ".json" for name in CORE_SCENARIOS
            )
            if not required_player <= inventory:
                raise InputError("Platformer review lacks sealed standalone gameplay evidence")
            process = load_json(policy.path(standalone_prefix + "process/process.json"))
            smoke = load_json(policy.path(standalone_prefix + "smoke.json"))
            if (
                not isinstance(process, dict)
                or process.get("reason") != "exit"
                or type(process.get("returncode")) is not int
                or process["returncode"] != 0
                or not isinstance(smoke, dict)
                or smoke.get("scene") != "SpritePlatformer"
                or smoke.get("input_digest") != current["input_digest"]
                or type(smoke.get("frames")) is not int
                or smoke["frames"] < 100
                or score_telemetry(policy, standalone_prefix.rstrip("/"), current, standalone=True)[
                    "status"
                ]
                != "PASS"
            ):
                raise InputError("Platformer standalone process or physical review failed")
    else:
        from polyforge.unity.evidence import verify_test_xml
        from polyforge.unity.game import GAME_EDIT_TESTS, PLAY_TESTS

        expected = {
            "runs/" + run + "/" + name
            for name in ("public-oracles.json", "editmode.xml", "playmode.xml")
        }
        if (
            not expected <= inventory
            or load_json(policy.path("runs/" + run + "/public-oracles.json"))["status"] != "PASS"
        ):
            raise InputError("Game review lacks passing sealed behavior evidence")
        verify_test_xml(policy.path("runs/" + run + "/editmode.xml"), GAME_EDIT_TESTS)
        verify_test_xml(policy.path("runs/" + run + "/playmode.xml"), PLAY_TESTS)
    review = {
        "schema_version": "1.0.0",
        "artifact_id": candidate["artifact_id"],
        "candidate_digest": candidate["candidate_digest"],
        "producer_id": candidate["producer_id"],
        "reviewer_id": "inspector",
        "verdict": "APPROVED",
        "independence": "DIFFERENT_ROLE_SAME_HOST",
        "evidence": [f["path"] for f in candidate["files"]],
        "request": request,
    }
    validate_review(review)
    return review


def require_approval(
    policy: WorkspacePolicy, candidate: dict[str, Any], review: dict[str, Any]
) -> None:
    check_candidate(policy, candidate)
    validate_review(review)
    if (
        "request" not in review
        or inspect_candidate(policy, candidate, review["request"], technical_only=True) != review
    ):
        raise InputError(
            "Approval lacks a matching registered technical inspection",
            kind=ErrorKind.POLICY_DENIED,
        )
    if (
        review["verdict"] != "APPROVED"
        or review["candidate_digest"] != candidate["candidate_digest"]
        or review["artifact_id"] != candidate["artifact_id"]
        or review["producer_id"] != candidate["producer_id"]
    ):
        raise InputError(
            "Integration needs approval bound to this exact candidate", kind=ErrorKind.POLICY_DENIED
        )
    from polyforge.review.board import require_promotion, review_candidate

    require_promotion(policy, candidate, review_candidate(policy, candidate, review["request"]))
