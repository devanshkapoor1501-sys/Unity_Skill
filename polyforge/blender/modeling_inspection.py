"""Validate independently measured modeling evidence against the compiled plan."""

from __future__ import annotations

import math
import re
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest


def _reject(message: str) -> None:
    raise InputError(message, kind=ErrorKind.CONTRACT_FAILURE, code="PF-MODELING-INSPECTION")


def _number(value: Any) -> float:
    if type(value) not in {int, float} or not math.isfinite(value) or abs(value) > 1e15:
        _reject("Modeling observation requires a bounded finite number")
    return float(value)


def _count(value: Any, *, positive: bool = False) -> int:
    if type(value) is not int or not (1 if positive else 0) <= value <= 10_000_000:
        _reject("Modeling observation requires a bounded integer count")
    return int(value)


def _vector(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        _reject("Modeling observation requires three coordinates")
    return [_number(n) for n in value]


def _near(actual: Any, expected: Any, *, angle: bool = False) -> None:
    a, b = _vector(actual), _vector(expected)
    for found, want in zip(a, b, strict=True):
        delta = (found - want + 180) % 360 - 180 if angle else found - want
        if abs(delta) > (0.001 if angle else 0.0001):
            _reject("Modeling transform or binding differs from the plan")


def _indexed(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 256:
        _reject("Modeling report inventory is missing or exceeds its bound")
    result = {}
    for row in value:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str) or row["id"] in result:
            _reject("Modeling report has malformed or duplicate identities")
        result[row["id"]] = row
    return result


def _modifiers(expected: list[dict[str, Any]], observed: Any) -> None:
    if not isinstance(observed, list) or len(observed) != len(expected):
        _reject("Editable modifier chain is absent or changed")
    for want, found in zip(expected, observed, strict=True):
        if not isinstance(found, dict) or set(found) != set(want):
            _reject("Editable modifier observation differs from its descriptor")
        for key, value in want.items():
            if type(value) in {int, float}:
                if type(value) is int and type(found[key]) is not int:
                    _reject("Editable modifier integer parameter has the wrong type")
                if abs(_number(found[key]) - value) > 0.00001:
                    _reject("Editable modifier parameters differ from the plan")
            elif found[key] != value:
                _reject("Editable modifier type or binding differs from the plan")


def validate_modeling_report(plan: dict[str, Any], report: Any) -> None:
    """Fail closed on absent measurements, invalid geometry and altered editable bindings."""
    canonical_digest(report)
    try:
        _validate(plan, report)
    except (KeyError, TypeError, ValueError, IndexError, OverflowError) as exc:
        if isinstance(exc, InputError):
            raise
        _reject(f"Malformed modeling inspection evidence: {exc}")


def _validate(plan: dict[str, Any], report: Any) -> None:
    if not isinstance(report, dict):
        _reject("Modeling report must be an object")
    if (
        report.get("schema_version") != "1.0.0"
        or report.get("asset_id") != plan["asset_id"]
        or report.get("input_digest") != plan["input_digest"]
        or report.get("technical_status") != "PASS"
        or report.get("artistic_status") != "REVIEW"
        or report.get("issues") != []
        or report.get("source_unchanged") is not True
        or report.get("coordinate_basis") != {"up": "Z", "forward": "-Y", "meters_per_unit": 1.0}
    ):
        _reject("Modeling inspection identity, status or source contract failed")
    digest = report.get("source_sha256_before")
    _number(report["coordinate_basis"]["meters_per_unit"])
    if (
        not isinstance(digest, str)
        or re.fullmatch(r"[a-f0-9]{64}", digest) is None
        or report.get("source_sha256_after") != digest
    ):
        _reject("Editable source changed during inspection")
    root = report["root"]
    if root["semantic_id"] != plan["asset_id"]:
        _reject("Asset root identity changed")
    _near(root["location_unity"], [0, 0, 0])
    _near(root["rotation_deg"], [0, 0, 0], angle=True)
    _near(root["scale"], [1, 1, 1])
    expected_materials, materials = _indexed(plan["materials"]), _indexed(report["materials"])
    if set(materials) != set(expected_materials):
        _reject("Material identity inventory differs")
    for key, want in expected_materials.items():
        colors = materials[key]["color_rgba"]
        if (
            not isinstance(colors, list)
            or len(colors) != 4
            or any(
                abs(_number(a) - b) > 0.0001
                for a, b in zip(colors, want["color_rgba"], strict=True)
            )
        ):
            _reject("Material color differs from the plan")
    expected, actual = _indexed(plan["objects"]), _indexed(report["objects"])
    if set(expected) != set(actual):
        _reject("Semantic object inventory differs")
    exported = []
    for identifier, want in expected.items():
        row = actual[identifier]
        if (
            row["primitive"] != want["primitive"]
            or type(row["export"]) is not bool
            or row["export"] != want["export"]
            or row["parent_id"] != plan["asset_id"]
            or row["material_ids"] != [want["material_id"]]
        ):
            _reject("Object semantic, parent, material or export binding differs")
        _near(row["location_unity"], want["location"])
        _near(row["rotation_deg"], want["rotation_deg"], angle=True)
        _near(row["scale"], [1, 1, 1])
        source = row["source_geometry"]
        if want["primitive"] == "curve":
            if source.get("spline_type") != "POLY" or source.get("closed_caps") is not True:
                _reject("Editable curve structure differs from the plan")
            if abs(_number(source["bevel_m"]) - want["bevel_m"]) > 0.000001:
                _reject("Editable curve bevel differs from the plan")
            points = source["points"]
            if not isinstance(points, list) or len(points) != len(want["points"]):
                _reject("Editable curve control point inventory differs")
            for point, target in zip(points, want["points"], strict=True):
                _near(point, target)
        else:
            _near(source["size_m"], want["size_m"])
        modifiers = list(want["modifiers"])
        if want["primitive"] == "grid":
            modifiers.insert(0, {"type": "geometry_nodes", "detail": want.get("detail", 1)})
        if want["primitive"] == "curve":
            modifiers.insert(0, {"type": "weld", "merge_threshold_m": 0.000001})
        _modifiers(modifiers, row["modifiers"])
        if row["modifiers_enabled"] is not True:
            _reject("Editable modifiers are disabled in evaluation or rendering")
        for key in ("vertices", "polygons", "triangles"):
            _count(row[key], positive=True)
        for key in (
            "nonmanifold_edges",
            "degenerate_faces",
            "nonfinite_values",
            "normal_inconsistencies",
            "uv_nonfinite_values",
            "invalid_material_faces",
        ):
            if _count(row[key]) != 0:
                _reject(f"Invalid evaluated modeling geometry: {key}")
        if _number(row["signed_volume"]) <= 0:
            _reject("Evaluated mesh has nonpositive signed volume")
        if _count(row["uv_layers"]) < 1:
            _reject("Required UV preflight failed")
        low, high = _vector(row["bounds_min_unity"]), _vector(row["bounds_max_unity"])
        if any(a >= b for a, b in zip(low, high, strict=True)):
            _reject("Evaluated bounds are collapsed or reversed")
        if row["export"]:
            exported.append(row)
    if not exported:
        _reject("No exported mesh was inspected")
    aggregate = report["aggregate"]
    for key in ("vertices", "polygons", "triangles"):
        if _count(aggregate[key], positive=True) != sum(row[key] for row in exported):
            _reject("Aggregate mesh counts do not match observations")
    if aggregate["polygons"] > plan["max_polygons"]:
        _reject("Evaluated mesh exceeds its polygon budget")
    lo = [min(row["bounds_min_unity"][i] for row in exported) for i in range(3)]
    hi = [max(row["bounds_max_unity"][i] for row in exported) for i in range(3)]
    _near(aggregate["bounds_min_unity"], lo)
    _near(aggregate["bounds_max_unity"], hi)
    w, h, d = plan["size_m"]
    envelope_lo, envelope_hi = [-w / 2, 0, -d / 2], [w / 2, h, d / 2]
    if any(a < b - 0.001 for a, b in zip(lo, envelope_lo, strict=True)) or any(
        a > b + 0.001 for a, b in zip(hi, envelope_hi, strict=True)
    ):
        _reject("Evaluated mesh leaves the declared base-centered envelope")
    if plan.get("expected_bounds", True):
        _near(lo, envelope_lo)
        _near(hi, envelope_hi)
    if plan["overlap_policy"] == "DISALLOW":
        for index, row in enumerate(exported):
            for other in exported[index + 1 :]:
                if all(
                    min(row["bounds_max_unity"][i], other["bounds_max_unity"][i])
                    - max(row["bounds_min_unity"][i], other["bounds_min_unity"][i])
                    > 0.0001
                    for i in range(3)
                ):
                    _reject("Disallowed conservative bounding-box overlap")
    expected_sockets, sockets = _indexed(plan["sockets"]), _indexed(report["sockets"])
    if set(sockets) != set(expected_sockets):
        _reject("Socket inventory differs")
    for key, want in expected_sockets.items():
        if sockets[key]["parent_id"] != plan["asset_id"]:
            _reject("Socket parent identity differs")
        _near(sockets[key]["position_unity"], want["position"])
    lod = report["lod"]
    polygons = _count(lod["polygons"], positive=True)
    for key in (
        "nonmanifold_edges",
        "degenerate_faces",
        "nonfinite_values",
        "normal_inconsistencies",
    ):
        if _count(lod[key]) != 0:
            _reject(f"Invalid reduced LOD geometry: {key}")
    if _number(lod["signed_volume"]) <= 0:
        _reject("Reduced LOD has nonpositive signed volume")
    if lod["source_polygons"] != aggregate["polygons"] or type(lod["source_polygons"]) is not int:
        _reject("LOD source counts differ")
    ratio = polygons / aggregate["polygons"]
    if (
        abs(_number(lod["ratio"]) - ratio) > 1e-6
        or ratio > plan["lod_ratio"] + 1 / aggregate["polygons"]
    ):
        _reject("LOD reduction does not meet the requested ratio")
