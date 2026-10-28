"""Bounded RGBA codec and independent six-frame atlas checks."""

import hashlib
import struct
import zlib
from typing import Any

from polyforge.contracts.images import inspect_png
from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest


def encode_rgba(width: int, height: int, pixels: bytes) -> bytes:
    if not 1 <= width <= 1024 or not 1 <= height <= 1024 or len(pixels) != width * height * 4:
        raise InputError("Invalid bounded RGBA dimensions")

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    rows = b"".join(b"\0" + pixels[y * width * 4 : (y + 1) * width * 4] for y in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


def atlas(frames: list[bytes]) -> bytes:
    if len(frames) != 6:
        raise InputError("Exactly six frames required")
    decoded = [inspect_png(f, include_pixels=True) for f in frames]
    size = decoded[0]["width"]
    if not 16 <= size <= 128 or any(d["width"] != size or d["height"] != size for d in decoded):
        raise InputError("Frames must share bounded square dimensions")
    pixels = b"".join(
        d["rgba"][y * size * 4 : (y + 1) * size * 4] for y in range(size) for d in decoded
    )
    return encode_rgba(size * 6, size, pixels)


def inspect_strip(frames: list[bytes], sheet: bytes, metadata: dict[str, Any]) -> dict[str, Any]:
    canonical_digest(metadata)
    if (
        len(frames) != 6
        or metadata.get("frame_count") != 6
        or metadata.get("order") != list(range(6))
        or metadata.get("pivot") != [0.5, 0.1]
        or metadata.get("trim") != "NONE"
        or metadata.get("framing") != "FIXED_ORTHOGRAPHIC"
        or metadata.get("fps") != 6
        or metadata.get("pixels_per_unit") != 64
        or metadata.get("frame_sha256") != [hashlib.sha256(f).hexdigest() for f in frames]
    ):
        raise InputError(
            "Sprite order/pivot/timing/source contract mismatch", kind=ErrorKind.CONTRACT_FAILURE
        )
    decoded = [
        inspect_png(f, expected_size=metadata["frame_size"], include_pixels=True) for f in frames
    ]
    if any(
        not d["nonblank"] or not d["framing_pass"] or not 0 < d["alpha_coverage"] < 0.9
        for d in decoded
    ):
        raise InputError(
            "Sprite blank/cropped/missing transparency", kind=ErrorKind.CONTRACT_FAILURE
        )
    observed = inspect_png(sheet, include_pixels=True)
    expected = inspect_png(atlas(frames), include_pixels=True)
    if (
        observed["width"] != expected["width"]
        or observed["height"] != expected["height"]
        or observed["rgba"] != expected["rgba"]
    ):
        raise InputError("Atlas pixels differ from ordered frames", kind=ErrorKind.CONTRACT_FAILURE)
    return {
        "status": "PASS",
        "frame_count": 6,
        "frame_bounds_px": [d["foreground_bounds_px"] for d in decoded],
        "alpha_coverage": [d["alpha_coverage"] for d in decoded],
        "pivot": [0.5, 0.1],
        "visual_review": "REVIEW",
        "visual_confidence": None,
    }
