"""Immutable candidate seals and read-only technical review receipts."""

import hashlib
from pathlib import Path
from typing import Any

from polyforge.contracts.results import ErrorKind, Result
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.security.paths import WorkspacePolicy
from polyforge.workforce.models import validate_review


def seal_candidate(policy: WorkspacePolicy, result: Result, brief_digest: str) -> dict[str, Any]:
    if result.status != "PASS" or result.run_id is None:
        raise InputError("Cannot seal unsuccessful/unidentified production")
    registry = load_json(policy.path("runs/" + result.run_id + "/artifacts.json"))
    records = []
    for item in registry["artifacts"]:
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
