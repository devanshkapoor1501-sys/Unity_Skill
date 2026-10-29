"""Independent source admission before either direct or workforce Unity import."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.review.amendments import read_amendments
from polyforge.runner.locks import FileLock
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.sprites.images import inspect_strip
from polyforge.workforce.permissions import assert_public_path
from polyforge.workforce.workers import check_candidate


def review_sprite_source(
    policy: WorkspacePolicy, inputs: dict[str, Any], *, remember_requirement: bool = False
) -> dict[str, Any]:
    validate_schema(inputs, "sprite_import.schema.json")
    paths = [inputs["metadata_file"], inputs["atlas_file"], *inputs["frame_files"]]
    if len(set(paths)) != 8:
        raise InputError("Sprite evidence paths must be distinct")
    for path in paths:
        assert_public_path(policy, path)
    metadata = load_json(policy.path(inputs["metadata_file"]))
    if (
        not isinstance(metadata, dict)
        or not isinstance(metadata.get("source_license"), str)
        or not metadata["source_license"].strip()
    ):
        raise InputError("Sprite source license required before native import")
    payloads = []
    for name in paths:
        with policy.path(name).open("rb") as stream:
            data = stream.read(16_777_217)
        if len(data) > 16_777_216:
            raise InputError("Sprite source exceeds bounded read budget")
        payloads.append(data)
    if metadata != json.loads(payloads[0]):
        raise InputError("Sprite metadata changed during source inspection")
    inspection = inspect_strip(payloads[2:], payloads[1], metadata)
    if metadata["frame_size"] != 128 or metadata["asset_id"] != inputs["asset_id"]:
        raise InputError("Unsupported native sprite dimensions/semantic identity")
    files = sorted(
        [
            {
                "path": policy.path(name).relative_to(policy.root).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
            for name, data in zip(paths, payloads, strict=True)
        ],
        key=lambda r: r["path"],
    )
    # A source scope is deliberately independent of request prose and optional flags:
    # the same strip cannot escape a refusal through another entry point or task.
    candidate: dict[str, Any] = {
        "schema_version": "1.0.0",
        "artifact_id": "sprite_source_" + canonical_digest(files)[:32],
        "producer_id": "sprite_source",
        "brief_digest": canonical_digest("Technical sprite source: " + inputs["asset_id"]),
        "revision": 1,
        "files": files,
    }
    candidate["candidate_digest"] = canonical_digest(candidate)
    check_candidate(policy, candidate)
    marker = ".polyforge/source-reviews/" + canonical_digest(inputs["asset_id"]) + ".json"
    if remember_requirement and inputs.get("visual_approval_required", False):
        with FileLock(policy, ".polyforge/locks/source-review.lock"):
            atomic_json(policy, marker, {"required": True})
    required = inputs.get("visual_approval_required", False)
    if policy.path(marker).is_file():
        if load_json(policy.path(marker)) != {"required": True}:
            raise InputError("Invalid durable sprite review requirement")
        required = True
    from polyforge.review.board import _human_record

    human_path = policy.path(".polyforge/human-reviews/" + candidate["candidate_digest"] + ".json")
    human = _human_record(load_json(human_path), candidate) if human_path.is_file() else None
    amendments = read_amendments(policy, candidate["brief_digest"])
    required |= any(r["visual_approval_required"] for r in amendments["records"])
    subjective = "REVIEW" if required else "NOT_REQUIRED"
    if human:
        subjective = (
            human["verdict"]
            if human["verdict"] == "REJECTED"
            or human["amendment_digest"] == amendments["chain_digest"]
            else "REVIEW"
        )
    promotion = "APPROVED" if subjective in {"APPROVED", "NOT_REQUIRED"} else subjective
    if any(r["requirements"] for r in amendments["records"]) and promotion != "REJECTED":
        promotion = "REVIEW"
    return {
        "candidate": candidate,
        "review_scope": "SPRITE_SOURCE",
        "technical": "APPROVED",
        "subjective": subjective,
        "promotion": promotion,
        "human_review": human,
        "inspection": inspection,
        "amendment_digest": amendments["chain_digest"],
        "native_import": "NOT_RUN",
        "tool_identity": "polyforge.registered.sprite_source_inspection.v1",
        "independence": "DIFFERENT_ROLE_SAME_HOST",
    }
