"""Actual pixel and frame identity checks for bounded transparent sprite strips."""

import hashlib

import pytest

from polyforge.contracts.validation import InputError


def sample(index, *, cropped=False):
    from polyforge.sprites.images import encode_rgba

    pixels = bytearray(32 * 32 * 4)
    for y in range(0 if cropped else 5, 26):
        for x in range(7, 24):
            offset = (y * 32 + x) * 4
            pixels[offset : offset + 4] = bytes((50 + index * 20, 80 + y, 180, 255))
    return encode_rgba(32, 32, bytes(pixels))


def test_png_dimensions_truncation_and_mixed_frames_are_rejected():
    from polyforge.sprites.images import atlas, encode_rgba

    for width, height, pixels in [(0, 1, b""), (1025, 1, b""), (1, 1, b"abc")]:
        with pytest.raises(InputError):
            encode_rgba(width, height, pixels)
    with pytest.raises(InputError):
        atlas([sample(i) for i in range(5)])
    with pytest.raises(InputError):
        atlas([b"invalid", *[sample(i) for i in range(5)]])
    with pytest.raises(InputError):
        atlas([sample(i) for i in range(5)] + [encode_rgba(16, 16, b"\0" * 1024)])


def test_six_frame_atlas_pixel_order_alpha_and_pivot_are_independently_checked(tmp_path):
    from polyforge.sprites.images import atlas, inspect_strip

    frames = [sample(i) for i in range(6)]
    metadata = {
        "schema_version": "1.0.0",
        "asset_id": "robot_a",
        "frame_size": 32,
        "frame_count": 6,
        "pixels_per_unit": 64,
        "fps": 6,
        "pivot": [0.5, 0.1],
        "trim": "NONE",
        "order": [0, 1, 2, 3, 4, 5],
        "frame_sha256": [hashlib.sha256(f).hexdigest() for f in frames],
        "source_sha256": "a" * 64,
        "framing": "FIXED_ORTHOGRAPHIC",
    }
    assert inspect_strip(frames, atlas(frames), metadata)["status"] == "PASS"
    for field, value in [
        ("order", [1, 0, 2, 3, 4, 5]),
        ("pivot", [0.51, 0.1]),
        ("fps", 0),
        ("frame_count", 5),
        ("trim", "AUTO"),
    ]:
        with pytest.raises(InputError):
            inspect_strip(frames, atlas(frames), {**metadata, field: value})
    wrong = list(frames)
    wrong[0], wrong[1] = wrong[1], wrong[0]
    with pytest.raises(InputError):
        inspect_strip(wrong, atlas(wrong), metadata)
    with pytest.raises(InputError):
        inspect_strip([sample(0, cropped=True), *frames[1:]], atlas(frames), metadata)
    cropped = [sample(0, cropped=True), *frames[1:]]
    with pytest.raises(InputError):
        inspect_strip(
            cropped,
            atlas(cropped),
            {**metadata, "frame_sha256": [hashlib.sha256(f).hexdigest() for f in cropped]},
        )
    with pytest.raises(InputError):
        inspect_strip(frames, atlas(list(reversed(frames))), metadata)


def test_native_2d_route_does_not_discover_or_require_blender(tmp_path):
    from polyforge.sprites.contracts import route_2d

    assert route_2d({"output": "UNITY_2D", "source": "DIRECT_SPRITES"}) == [
        "sprite.inspect",
        "unity.2d",
    ]
    assert route_2d({"output": "UNITY_2D", "source": "BAKED_ROBOT"}) == [
        "blender.bake",
        "sprite.inspect",
        "unity.2d",
    ]
    with pytest.raises(InputError):
        route_2d({"output": "UNITY_2D", "source": "UNKNOWN"})
    with pytest.raises(InputError):
        route_2d({"output": "3D", "source": "DIRECT_SPRITES"})


def test_sprite_bake_rejects_unregistered_source_before_writes(tmp_path):
    from polyforge.capabilities.protocol import RunContext
    from polyforge.sprites.bake import bake_robot

    source = tmp_path / "source.blend"
    source.write_bytes(b"unregistered")
    request = {
        "schema_version": "1.0.0",
        "asset_id": "robot_a",
        "source_blend": "source.blend",
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
    }
    with pytest.raises(InputError):
        bake_robot(request, RunContext(tmp_path))
    assert list(tmp_path.iterdir()) == [source]


def test_native_2d_missing_license_and_dry_run_have_no_side_effects(tmp_path):
    import json

    from polyforge.capabilities.protocol import RunContext
    from polyforge.sprites.images import atlas
    from polyforge.sprites.integration import import_strip

    frames = [sample(i) for i in range(6)]
    for i, frame in enumerate(frames):
        (tmp_path / f"frame-{i}.png").write_bytes(frame)
    (tmp_path / "atlas.png").write_bytes(atlas(frames))
    metadata = {
        "schema_version": "1.0.0",
        "asset_id": "robot_a",
        "frame_size": 32,
        "frame_count": 6,
        "pixels_per_unit": 64,
        "fps": 6,
        "pivot": [0.5, 0.1],
        "trim": "NONE",
        "order": list(range(6)),
        "frame_sha256": [hashlib.sha256(f).hexdigest() for f in frames],
        "source_sha256": "a" * 64,
        "framing": "FIXED_ORTHOGRAPHIC",
    }
    (tmp_path / "atlas.json").write_text(json.dumps(metadata))
    request = {
        "schema_version": "1.0.0",
        "asset_id": "robot_a",
        "source_kind": "DIRECT_SPRITES",
        "atlas_file": "atlas.png",
        "metadata_file": "atlas.json",
        "frame_files": [f"frame-{i}.png" for i in range(6)],
    }
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    with pytest.raises(InputError):
        import_strip(request, RunContext(tmp_path))
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
    from polyforge.workforce.router import plan_task

    task = {
        "schema_version": "1.0.0",
        "brief": "Use these six existing sprites in a controllable Unity 2D fixture.",
        "task_class": "CREATE_ASSET",
        "domain_tags": ["unity", "2d"],
        "feature_ids": ["control_2d"],
        "capability_id": "sprite.unity.strip.v1",
        "input": request,
    }
    plan = plan_task(task, workspace=tmp_path)
    assert plan["stages"] == ["S0", "S1", "S4", "S5"]
    assert plan["jobs"][1]["role_id"] == "unity_integration"
    metadata["source_license"] = "USER_PROVIDED"
    # A valid direct sprite dry run needs no installed/discovered Blender or Unity.
    from polyforge.sprites.images import encode_rgba

    for i in range(6):
        pixels = bytearray(128 * 128 * 4)
        for y in range(20, 105):
            for x in range(35, 95):
                pixels[(y * 128 + x) * 4 : (y * 128 + x) * 4 + 4] = bytes(
                    (40 + i * 15, 80 + y, 120, 255)
                )
        frames[i] = encode_rgba(128, 128, bytes(pixels))
        (tmp_path / f"frame-{i}.png").write_bytes(frames[i])
    metadata["frame_size"] = 128
    metadata["frame_sha256"] = [hashlib.sha256(f).hexdigest() for f in frames]
    (tmp_path / "atlas.png").write_bytes(atlas(frames))
    (tmp_path / "atlas.json").write_text(json.dumps(metadata))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    result = import_strip(request, RunContext(tmp_path, dry_run=True))
    assert result.data["route"] == ["sprite.inspect", "unity.2d"]
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
