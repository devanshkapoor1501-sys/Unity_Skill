"""Both direct and workforce entry points veto before touching Unity."""

import hashlib

import pytest

from polyforge.capabilities.protocol import RunContext
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.sprites.images import atlas, encode_rgba


def sprite_fixture(tmp_path):
    p = WorkspacePolicy(tmp_path)
    frames = []
    for i in range(6):
        pixels = bytearray(128 * 128 * 4)
        for y in range(20, 105):
            for x in range(35, 95):
                offset = (y * 128 + x) * 4
                pixels[offset : offset + 4] = bytes((40 + i * 15, 80 + y, 120, 255))
        frames.append(encode_rgba(128, 128, bytes(pixels)))
        p.path(f"frame-{i}.png").write_bytes(frames[-1])
    p.path("atlas.png").write_bytes(atlas(frames))
    atomic_json(
        p,
        "atlas.json",
        {
            "schema_version": "1.0.0",
            "asset_id": "robot_a",
            "frame_size": 128,
            "frame_count": 6,
            "pixels_per_unit": 64,
            "fps": 6,
            "pivot": [0.5, 0.1],
            "trim": "NONE",
            "order": list(range(6)),
            "frame_sha256": [hashlib.sha256(f).hexdigest() for f in frames],
            "source_sha256": "a" * 64,
            "framing": "FIXED_ORTHOGRAPHIC",
            "source_license": "USER_PROVIDED",
        },
    )
    inputs = {
        "schema_version": "1.0.0",
        "asset_id": "robot_a",
        "source_kind": "DIRECT_SPRITES",
        "atlas_file": "atlas.png",
        "metadata_file": "atlas.json",
        "frame_files": [f"frame-{i}.png" for i in range(6)],
        "visual_approval_required": True,
    }
    return p, inputs


@pytest.mark.parametrize("entry", ["direct", "workforce"])
def test_required_sprite_review_vetoes_before_native_import(tmp_path, entry):
    from polyforge.capabilities.dispatch import execute
    from polyforge.workforce.orchestrator import run_task

    p, inputs = sprite_fixture(tmp_path)
    if entry == "direct":
        result = execute("sprite.unity.strip.v1", inputs, RunContext(tmp_path))
    else:
        result = run_task(
            tmp_path,
            {
                "schema_version": "1.0.0",
                "brief": "Import these sprites",
                "task_class": "CREATE_ASSET",
                "domain_tags": ["unity", "2d"],
                "feature_ids": ["control_2d"],
                "capability_id": "sprite.unity.strip.v1",
                "input": inputs,
            },
        )
    assert result.status == "REVIEW"
    assert not p.path("UnityProject").exists()
    assert result.data["source_review"]["subjective"] == "REVIEW"


def test_rejection_and_required_marker_cannot_be_bypassed_by_legacy_input(tmp_path):
    from polyforge.review.board import record_human_review
    from polyforge.review.sprite_source import review_sprite_source
    from polyforge.sprites.integration import import_strip

    p, inputs = sprite_fixture(tmp_path)
    review = review_sprite_source(p, inputs)
    assert review["promotion"] == "REVIEW"
    import_strip(inputs, RunContext(tmp_path))
    legacy = {k: v for k, v in inputs.items() if k != "visual_approval_required"}
    assert review_sprite_source(p, legacy)["promotion"] == "REVIEW"
    record_human_review(
        p, review["candidate"], verdict="APPROVED", operator="owner", reason="Viewed actual strip"
    )
    assert review_sprite_source(p, legacy)["promotion"] == "APPROVED"
    assert import_strip(legacy, RunContext(tmp_path, dry_run=True)).data["dry_run"]
    record_human_review(
        p, review["candidate"], verdict="REJECTED", operator="owner", reason="Wrong appearance"
    )
    assert import_strip(legacy, RunContext(tmp_path)).status == "REVIEW"
    assert not p.path("UnityProject").exists()


def test_source_receipt_cannot_approve_changed_sprite_bytes(tmp_path):
    from polyforge.review.board import record_human_review
    from polyforge.review.sprite_source import review_sprite_source

    p, inputs = sprite_fixture(tmp_path)
    review = review_sprite_source(p, inputs)
    record_human_review(
        p, review["candidate"], verdict="APPROVED", operator="owner", reason="Viewed"
    )
    from polyforge.contracts.validation import InputError

    p.path("frame-0.png").write_bytes(b"changed")
    with pytest.raises(InputError):
        review_sprite_source(p, inputs)


@pytest.mark.parametrize("damage", ["duplicate", "oversized", "metadata", "marker"])
def test_invalid_source_or_requirement_record_never_reaches_unity(tmp_path, damage):
    from polyforge.contracts.validation import InputError, canonical_digest
    from polyforge.review.sprite_source import review_sprite_source

    p, inputs = sprite_fixture(tmp_path)
    if damage == "duplicate":
        inputs["atlas_file"] = inputs["frame_files"][0]
    elif damage == "oversized":
        p.path(inputs["atlas_file"]).write_bytes(b"x" * 16_777_217)
    elif damage == "metadata":
        atomic_json(p, "atlas.json", [])
    else:
        atomic_json(
            p,
            ".polyforge/source-reviews/" + canonical_digest(inputs["asset_id"]) + ".json",
            {"required": False},
        )
    with pytest.raises(InputError):
        review_sprite_source(p, inputs)
    assert not p.path("UnityProject").exists()


def test_produced_sprite_board_preserves_source_and_candidate_rejection_vetoes(tmp_path):
    import xml.etree.ElementTree as ET

    from polyforge.contracts.results import Result
    from polyforge.contracts.validation import canonical_digest
    from polyforge.review.board import record_human_review, review_candidate
    from polyforge.review.sprite_source import review_sprite_source
    from polyforge.sprites.integration import EDIT_TESTS, PLAY_TESTS
    from polyforge.workforce.workers import seal_candidate

    p, inputs = sprite_fixture(tmp_path)
    p.mkdir("runs/native")
    for name, expected in [("editmode.xml", EDIT_TESTS), ("playmode.xml", PLAY_TESTS)]:
        root = ET.Element("test-run", result="Passed")
        for test in sorted(expected):
            ET.SubElement(root, "test-case", fullname=test, result="Passed")
        p.path("runs/native/" + name).write_bytes(ET.tostring(root))
    paths = [
        inputs["metadata_file"],
        inputs["atlas_file"],
        *inputs["frame_files"],
        "runs/native/editmode.xml",
        "runs/native/playmode.xml",
    ]
    atomic_json(
        p,
        "runs/native/artifacts.json",
        {
            "artifacts": [
                {
                    "relative_path": name,
                    "sha256": hashlib.sha256(p.path(name).read_bytes()).hexdigest(),
                }
                for name in paths
            ]
        },
    )
    task = {
        "schema_version": "1.0.0",
        "brief": "Import supplied strip",
        "task_class": "CREATE_ASSET",
        "domain_tags": ["unity", "2d"],
        "feature_ids": [],
        "capability_id": "sprite.unity.strip.v1",
        "input": inputs,
    }
    candidate = seal_candidate(p, Result(run_id="native"), canonical_digest(task["brief"]))
    assert review_candidate(p, candidate, task)["promotion"] == "REVIEW"
    source = review_sprite_source(p, inputs)["candidate"]
    record_human_review(p, source, verdict="APPROVED", operator="owner", reason="Viewed source")
    assert review_candidate(p, candidate, task)["promotion"] == "APPROVED"
    record_human_review(
        p, candidate, verdict="REJECTED", operator="owner", reason="Wrong integrated appearance"
    )
    assert review_candidate(p, candidate, task)["promotion"] == "REJECTED"
