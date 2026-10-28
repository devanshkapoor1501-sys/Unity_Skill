"""Versioned static families expand to bounded data, never user Python."""

from __future__ import annotations

import math
import random
import re
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest, validate_schema
from polyforge.planner.dag import topological_order

RECIPES = {
    "robot": "mesh.robot.modular.v1",
    "crate": "mesh.props.crate.v1",
    "wall": "mesh.architecture.wall.v1",
    "doorway": "mesh.architecture.doorway.v1",
    "ground": "mesh.environment.tile.v1",
}


def validate_recipe(value: Any) -> dict[str, Any]:
    validate_schema(value, "recipe.schema.json")
    if RECIPES[value["kind"]] != value["capability_id"]:
        raise InputError("$.recipe.capability_id: mismatched recipe family")
    modules = {m["id"]: m for m in value["modules"]}
    sockets = {s["id"]: s for s in value["sockets"]}
    materials = {m["id"] for m in value.get("materials", [])}
    if len(modules) != len(value["modules"]) or len(sockets) != len(value["sockets"]):
        raise InputError("$.recipe: duplicate module/socket IDs")
    if len(materials) != len(value.get("materials", [])):
        raise InputError("$.recipe.materials: duplicate IDs")
    topological_order({key: [m["parent"]] if "parent" in m else [] for key, m in modules.items()})
    for socket in sockets.values():
        if socket["module_id"] not in modules:
            raise InputError("$.recipe.sockets.module_id: missing parent")
        size = modules[socket["module_id"]].get("size_m", value["parameters"]["size_m"])
        if any(
            abs(p) > dimension / 2 + 0.00001
            for p, dimension in zip(socket["position"], size, strict=True)
        ):
            raise InputError("$.recipe.sockets.position: socket must lie on/in its module")
    for module in modules.values():
        if "material_id" in module and module["material_id"] not in materials:
            raise InputError("$.recipe.modules.material_id: dangling reference")
        if "attach_to" in module:
            socket = sockets.get(module["attach_to"])
            if socket is None or socket["module_id"] != module.get("parent"):
                raise InputError("$.recipe.modules.attach_to: socket must belong to parent")
        size = module.get("size_m", value["parameters"]["size_m"])
        if module.get("bevel_m", 0) >= min(size) / 2:
            raise InputError("$.recipe.modules.bevel_m: bevel exceeds smallest half-extent")
    result: dict[str, Any] = value
    return result


def expand_recipe(kind: str, request: Any, *, seed: int) -> dict[str, Any]:
    validate_schema(request, "recipe_request.schema.json")
    if kind not in RECIPES or type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise InputError("$.recipe: unknown family or invalid uint32 seed")
    parameters = request["parameters"]
    if kind != "doorway" and set(parameters) != {"size_m"}:
        raise InputError("$.parameters: opening parameters belong to doorway only")
    w, h, d = parameters["size_m"]
    modules: list[dict[str, Any]] = []
    sockets: list[dict[str, Any]] = []
    bevel_ratio = random.Random(seed).uniform(0.025, 0.045)

    def part(
        identifier: str,
        size: list[float],
        location: list[float],
        *,
        parent: str | None = None,
        attach: str | None = None,
        primitive: str = "beveled_box",
        material: str = "base",
    ) -> None:
        module: dict[str, Any] = {
            "id": identifier,
            "primitive": primitive,
            "size_m": size,
            "location": location,
            "material_id": material,
        }
        if parent:
            module["parent"] = parent
        if attach:
            module["attach_to"] = attach
        if primitive == "beveled_box":
            module["bevel_m"] = min(size) * bevel_ratio
        modules.append(module)

    def socket(identifier: str, owner: str, position: list[float]) -> None:
        sockets.append({"id": identifier, "module_id": owner, "position": position})

    if kind == "robot":
        part("body", [0.45 * w, 0.35 * h, 0.6 * d], [0, 0.55 * h, 0])
        socket("neck", "body", [0, 0.175 * h, 0])
        part(
            "head",
            [0.35 * w, 0.3 * h, 0.6 * d],
            [0, 0.15 * h, 0],
            parent="body",
            attach="neck",
            material="trim",
        )
        part("hips", [0.4 * w, 0.1 * h, 0.5 * d], [0, -0.22 * h, 0], parent="body")
        part(
            "core",
            [0.18 * w, 0.12 * h, 0.08 * d],
            [0, 0, 0.31 * d],
            parent="body",
            primitive="cylinder",
            material="accent",
        )
        for side, sign in (("l", -1), ("r", 1)):
            socket("shoulder_" + side, "body", [sign * 0.225 * w, 0.1 * h, 0])
            part(
                "upper_arm_" + side,
                [0.2 * w, 0.22 * h, 0.5 * d],
                [sign * 0.1 * w, -0.08 * h, 0],
                parent="body",
                attach="shoulder_" + side,
            )
            socket("elbow_" + side, "upper_arm_" + side, [0, -0.11 * h, 0])
            part(
                "forearm_" + side,
                [0.17 * w, 0.2 * h, 0.45 * d],
                [0, -0.1 * h, 0],
                parent="upper_arm_" + side,
                attach="elbow_" + side,
                material="trim",
            )
            socket("wrist_" + side, "forearm_" + side, [0, -0.1 * h, 0])
            part(
                "hand_" + side,
                [0.22 * w, 0.08 * h, 0.5 * d],
                [0, -0.04 * h, 0],
                parent="forearm_" + side,
                attach="wrist_" + side,
            )
            socket("hand_" + side, "hand_" + side, [0, -0.04 * h, 0])
            socket("hip_" + side, "hips", [sign * 0.11 * w, -0.05 * h, 0])
            part(
                "thigh_" + side,
                [0.18 * w, 0.24 * h, 0.5 * d],
                [0, -0.12 * h, 0],
                parent="hips",
                attach="hip_" + side,
            )
            socket("knee_" + side, "thigh_" + side, [0, -0.12 * h, 0])
            part(
                "shin_" + side,
                [0.18 * w, 0.2 * h, 0.5 * d],
                [0, -0.1 * h, 0],
                parent="thigh_" + side,
                attach="knee_" + side,
                material="trim",
            )
            part(
                "foot_" + side,
                [0.25 * w, 0.07 * h, d],
                [0, -0.135 * h, 0.15 * d],
                parent="shin_" + side,
            )
            part(
                "eye_" + side,
                [0.08 * w, 0.05 * h, 0.08 * d],
                [sign * 0.08 * w, 0.04 * h, 0.3 * d],
                parent="head",
                primitive="sphere",
                material="accent",
            )
    elif kind == "doorway":
        opening_w = parameters.get("opening_width_m", 0.65 * w)
        opening_h = parameters.get("opening_height_m", 0.8 * h)
        if opening_w >= 0.95 * w or opening_h >= 0.95 * h:
            raise InputError("$.parameters: doorway opening leaves no usable frame")
        side_w = (w - opening_w) / 2
        for name, sign in (("left", -1), ("right", 1)):
            part(name, [side_w, h, d], [sign * (opening_w + side_w) / 2, h / 2, 0])
            socket("join_" + name, name, [sign * side_w / 2, 0, 0])
        part("lintel", [opening_w, h - opening_h, d], [0, (h + opening_h) / 2, 0], material="trim")
        socket("top", "lintel", [0, (h - opening_h) / 2, 0])
    else:
        part("body", [w, h, d], [0, h / 2, 0])
        socket("top", "body", [0, h / 2, 0])
        socket("front", "body", [0, 0, d / 2])
        if kind == "crate":
            for name, sign in (("left", -1), ("right", 1)):
                part(
                    "brace_" + name,
                    [0.12 * w, 0.96 * h, 0.08 * d],
                    [sign * 0.36 * w, 0, 0.49 * d],
                    parent="body",
                    material="trim",
                )
        if kind in {"wall", "ground"}:
            socket("join_left", "body", [-w / 2, 0, 0])
            socket("join_right", "body", [w / 2, 0, 0])
        if kind == "wall":
            part("cap", [w, 0.08 * h, d * 1.1], [0, 0.46 * h, 0], parent="body", material="trim")
    value = {
        "schema_version": "1.0.0",
        "asset_id": request["asset_id"],
        "kind": kind,
        "capability_id": RECIPES[kind],
        "parameters": {"size_m": [w, h, d]},
        "modules": modules,
        "sockets": sockets,
        "pivot": "base_center",
        "max_polygons": request.get("max_polygons", 25000),
        "materials": [
            {"id": "base", "color_rgba": [0.12, 0.3, 0.5, 1]},
            {"id": "trim", "color_rgba": [0.05, 0.07, 0.09, 1]},
            {"id": "accent", "color_rgba": [0.9, 0.55, 0.05, 1]},
        ],
    }
    return validate_recipe(value)


def validate_geometry(
    recipe: dict[str, Any], metrics: Any, *, dimension_tolerance_m: float | None = None
) -> None:
    """Independent report checks; output validation never trusts worker status alone."""

    def reject(message: str) -> None:
        raise InputError(
            "$.geometry: " + message, kind=ErrorKind.CONTRACT_FAILURE, code="PF-GEOMETRY-CONTRACT"
        )

    if dimension_tolerance_m is not None and (
        type(dimension_tolerance_m) not in {int, float}
        or not math.isfinite(dimension_tolerance_m)
        or not 0 < dimension_tolerance_m <= 0.01
    ):
        reject("invalid explicit dimension tolerance")
    absolute = 1e-5 if dimension_tolerance_m is None else dimension_tolerance_m
    relative = 1e-5 if dimension_tolerance_m is None else 0.0
    try:
        canonical_digest(metrics)
    except InputError:
        reject("producer payload is not finite JSON")
    if (
        not isinstance(metrics, dict)
        or metrics.get("asset_id") != recipe["asset_id"]
        or metrics.get("status") != "PASS"
    ):
        reject("wrong asset identity or failed worker")
    for count in ("degenerate_faces", "invalid_uv_faces", "nonfinite_values"):
        if type(metrics.get(count)) is not int or metrics[count] != 0:
            reject(count)
    polygons = metrics.get("polygon_count")
    if type(polygons) is not int or not 1 <= polygons <= recipe["max_polygons"]:
        reject("polygon budget exceeded/invalid")
    for report_key, recipe_key in (
        ("module_ids", "modules"),
        ("socket_ids", "sockets"),
        ("material_ids", "materials"),
    ):
        actual = metrics.get(report_key)
        expected = {item["id"] for item in recipe.get(recipe_key, [])}
        if (
            not isinstance(actual, list)
            or any(not isinstance(v, str) for v in actual)
            or set(actual) != expected
            or len(actual) != len(set(actual))
        ):
            reject(report_key + " missing/duplicate semantic bindings")
    bounds = metrics.get("bounds_unity_m")
    if (
        not isinstance(bounds, list)
        or len(bounds) != 3
        or any(
            type(v) not in {int, float}
            or not math.isclose(v, want, rel_tol=relative, abs_tol=absolute)
            for v, want in zip(bounds, recipe["parameters"]["size_m"], strict=True)
        )
    ):
        reject("target bounds mismatch")
    if (
        metrics.get("pivot_unity_m") != [0, 0, 0]
        or not isinstance(metrics.get("geometry_digest"), str)
        or not re.fullmatch(r"[a-f0-9]{64}", metrics["geometry_digest"])
    ):
        reject("invalid pivot/hash")
    if (
        metrics.get("coordinate_basis") != {"up": "Z", "forward": "-Y"}
        or metrics.get("meters_per_unit") != 1
    ):
        reject("source axes/units mismatch")
    minimum = metrics.get("minimum_native_m")
    w, h, d = recipe["parameters"]["size_m"]
    if (
        not isinstance(minimum, list)
        or len(minimum) != 3
        or any(
            type(v) not in {int, float}
            or not math.isclose(v, want, rel_tol=relative, abs_tol=absolute)
            for v, want in zip(minimum, [-w / 2, -d / 2, 0], strict=True)
        )
    ):
        reject("geometry does not obey base-center pivot bounds")
    if recipe["kind"] == "robot":
        positions = metrics.get("socket_positions_unity_m", {})
        if not isinstance(positions, dict) or any(
            not isinstance(positions.get(key), list)
            or len(positions[key]) != 3
            or any(type(v) not in {int, float} for v in positions[key])
            for key in ("hand_l", "hand_r")
        ):
            reject("robot hand sockets absent")
        if positions["hand_l"][0] >= positions["hand_r"][0]:
            reject("left/right sockets reversed")
