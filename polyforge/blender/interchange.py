"""Explicit FBX float32 tolerance, shared with the standalone Blender worker."""

from __future__ import annotations

import math
from typing import Any


def coordinates_match(expected: Any, actual: Any) -> bool:
    """Compare coordinate containers: 10 micrometres absolute, 1 ppm relative."""
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and expected.keys() == actual.keys()
            and all(coordinates_match(value, actual[key]) for key, value in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(expected) == len(actual)
            and all(coordinates_match(a, b) for a, b in zip(expected, actual, strict=True))
        )
    return (
        type(expected) in {int, float}
        and type(actual) in {int, float}
        and math.isfinite(expected)
        and math.isfinite(actual)
        and math.isclose(expected, actual, abs_tol=1e-5, rel_tol=1e-6)
    )
