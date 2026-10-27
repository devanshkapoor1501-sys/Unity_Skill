"""Bounded independent RGBA8 PNG decoding for generated audit evidence."""

from __future__ import annotations

import struct
import zlib
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError


def inspect_png(content: bytes, *, expected_size: int | None = None) -> dict[str, Any]:
    """Decode checked PNG chunks and all five scanline filters; never trust worker stats."""

    def invalid(message: str) -> None:
        raise InputError("$.view: " + message, kind=ErrorKind.CONTRACT_FAILURE, code="PF-AUDIT-PNG")

    if len(content) > 16_777_216 or not content.startswith(b"\x89PNG\r\n\x1a\n"):
        invalid("invalid PNG signature/size")
    cursor = 8
    compressed = bytearray()
    width = height = 0
    ended = False
    seen = False
    while cursor < len(content):
        if cursor + 12 > len(content):
            invalid("truncated PNG chunk")
        size = struct.unpack_from(">I", content, cursor)[0]
        kind = content[cursor + 4 : cursor + 8]
        data = content[cursor + 8 : cursor + 8 + size]
        if (
            cursor + 12 + size > len(content)
            or zlib.crc32(kind + data) != struct.unpack_from(">I", content, cursor + 8 + size)[0]
        ):
            invalid("truncated PNG or CRC mismatch")
        if kind == b"IHDR":
            if cursor != 8 or size != 13 or seen:
                invalid("invalid PNG header")
            width, height, depth, color, packing, filtering, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            if (
                depth != 8
                or color != 6
                or packing
                or filtering
                or interlace
                or not 1 <= width <= 1024
                or not 1 <= height <= 1024
            ):
                invalid("only bounded noninterlaced RGBA8 is supported")
            if expected_size is not None and (width != expected_size or height != expected_size):
                invalid("unexpected view dimensions")
            seen = True
        elif kind == b"IDAT":
            if not seen:
                invalid("image data precedes header")
            compressed.extend(data)
        elif kind == b"IEND":
            if size or cursor + 12 != len(content):
                invalid("invalid PNG end/trailing data")
            ended = True
            break
        elif kind[0] & 32 == 0:
            invalid("unsupported critical PNG chunk")
        cursor += size + 12
    if not ended or not seen or not compressed:
        invalid("missing required PNG chunks")
    limit = (width * 4 + 1) * height
    try:
        decoder = zlib.decompressobj()
        raw = decoder.decompress(compressed, limit + 1)
        if len(raw) != limit or not decoder.eof or decoder.unused_data:
            invalid("invalid decoded PNG size")
    except zlib.error as exc:
        raise InputError(
            "$.view: corrupt PNG compression", kind=ErrorKind.CONTRACT_FAILURE
        ) from exc
    stride = width * 4
    previous = bytearray(stride)
    foreground = []
    colors = set()
    opaque = 0
    for y in range(height):
        offset = y * (stride + 1)
        mode = raw[offset]
        row = bytearray(raw[offset + 1 : offset + stride + 1])
        if mode > 4:
            invalid("unknown PNG filter")
        for x in range(stride):
            a = row[x - 4] if x >= 4 else 0
            b = previous[x]
            c = previous[x - 4] if x >= 4 else 0
            p = a + b - c
            distances = [abs(p - a), abs(p - b), abs(p - c)]
            prediction = (0, a, b, (a + b) // 2, (a, b, c)[distances.index(min(distances))])[mode]
            row[x] = (row[x] + prediction) % 256
        for x in range(width):
            pixel = row[x * 4 : x * 4 + 4]
            if pixel[3] >= 16:
                opaque += 1
                foreground.append((x, y))
                colors.add(bytes(pixel[:3]))
        previous = row
    bounds = (
        [
            min(p[0] for p in foreground),
            min(p[1] for p in foreground),
            max(p[0] for p in foreground),
            max(p[1] for p in foreground),
        ]
        if foreground
        else None
    )
    framed = (
        bounds is not None
        and bounds[0] > 0
        and bounds[1] > 0
        and bounds[2] < width - 1
        and bounds[3] < height - 1
    )
    return {
        "width": width,
        "height": height,
        "opaque_pixels": opaque,
        "foreground_bounds_px": bounds,
        "distinct_foreground_colors": len(colors),
        "nonblank": opaque >= max(1, width * height // 1000) and len(colors) > 1,
        "framing_pass": framed,
        "alpha_coverage": opaque / (width * height),
    }
