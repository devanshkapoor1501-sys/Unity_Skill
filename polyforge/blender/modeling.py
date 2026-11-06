"""Compile versioned modeling requests into bounded, editable native plans."""

from __future__ import annotations

import copy
import math
from typing import Any

from polyforge.contracts.validation import InputError, canonical_digest, validate_schema
from polyforge.planner.dag import topological_order

MODELING_CAPABILITIES = {
    "room_kit": "mesh.modeling.room_kit.v1",
    "vehicle": "mesh.modeling.vehicle.v1",
    "mechanical_prop": "mesh.modeling.mechanical_prop.v1",
    "organic": "mesh.modeling.organic.v1",
    "compose": "mesh.modeling.compose.v1",
}
MATERIALS = [
    {"id": "base", "color_rgba": [0.18, 0.32, 0.48, 1.0]},
    {"id": "trim", "color_rgba": [0.08, 0.1, 0.13, 1.0]},
    {"id": "accent", "color_rgba": [0.9, 0.42, 0.08, 1.0]},
]


def _object(
    identifier: str,
    size: list[float],
    location: list[float],
    *,
    primitive: str = "box",
    material: str = "base",
    modifiers: list[dict[str, Any]] | None = None,
    rotation: list[float] | None = None,
    export: bool = True,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "primitive": primitive,
        "size_m": size,
        "location": location,
        "rotation_deg": rotation or [0.0, 0.0, 0.0],
        "material_id": material,
        "export": export,
        "modifiers": modifiers or [],
    }


def _bevel(size: list[float], detail: int) -> list[dict[str, Any]]:
    return [{"type": "bevel", "width_m": min(size) * 0.06, "segments": detail}]


def _families(
    kind: str, size: list[float], detail: int, thickness: float
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    w, h, d = size
    objects: list[dict[str, Any]] = []
    sockets = [
        {"id": "base", "position": [0.0, 0.0, 0.0]},
        {"id": "top", "position": [0.0, h, 0.0]},
    ]

    def box(
        identifier: str, dimensions: list[float], location: list[float], material: str = "base"
    ) -> None:
        objects.append(
            _object(
                identifier,
                dimensions,
                location,
                material=material,
                modifiers=_bevel(dimensions, detail),
            )
        )

    if kind == "room_kit":
        t = thickness
        box("floor", [w, t, d], [0.0, t / 2, 0.0], "trim")
        box("wall_back", [w, h - t, t], [0.0, (h + t) / 2, -(d - t) / 2])
        for side, sign in (("left", -1), ("right", 1)):
            box("wall_" + side, [t, h - t, d - t], [sign * (w - t) / 2, (h + t) / 2, t / 2])
            box("door_" + side, [w * 0.25, h - t, t], [sign * w * 0.375, (h + t) / 2, (d - t) / 2])
        box("lintel", [w * 0.5, h * 0.2, t], [0.0, h * 0.9, (d - t) / 2], "accent")
        for index in range(detail):
            box(
                f"ceiling_beam_{index}",
                [w - 2 * t, t / 2, t],
                [0.0, h - t / 4, -d * 0.3 + index * d * 0.3 / detail],
                "trim",
            )
        sockets.append({"id": "doorway", "position": [0.0, t, d / 2]})
    elif kind == "vehicle":
        box("chassis", [w, h * 0.24, d * 0.8], [0.0, h * 0.38, 0.0])
        box("cabin", [w * 0.58, h * 0.4, d * 0.45], [0.0, h * 0.8, -d * 0.08], "accent")
        radius = min(h * 0.18, d * 0.2)
        axle_width = w * 0.12
        for side, sign in (("left", -1), ("right", 1)):
            for end, z in (("front", d / 2 - radius), ("back", -d / 2 + radius)):
                objects.append(
                    _object(
                        f"wheel_{side}_{end}",
                        [2 * radius, axle_width, 2 * radius],
                        [sign * (w - axle_width) / 2, radius, z],
                        primitive="cylinder",
                        rotation=[0.0, 0.0, 90.0],
                        material="trim",
                    )
                )
        for index in range(detail):
            box(
                f"hood_vent_{index}",
                [w * 0.55, h * 0.03, d * 0.02],
                [0.0, h * 0.515, d * (0.18 + index * 0.08)],
                "trim",
            )
        sockets.append({"id": "front", "position": [0.0, h * 0.3, d / 2]})
    elif kind == "mechanical_prop":
        base = _object(
            "base_plate", [w, h * 0.1, d], [0.0, h * 0.05, 0.0], primitive="grid", material="trim"
        )
        base["detail"] = detail
        objects.append(base)
        core = _object(
            "housing", [w * 0.65, h * 0.7, d * 0.65], [0.0, h * 0.45, 0.0], primitive="cylinder"
        )
        core["modifiers"] = [{"type": "boolean", "target": "bore", "operation": "DIFFERENCE"}]
        objects.append(core)
        objects.append(
            _object(
                "bore",
                [w * 0.22, h * 0.74, d * 0.22],
                [0.0, h * 0.45, 0.0],
                primitive="cylinder",
                export=False,
            )
        )
        box("cap", [w * 0.8, h * 0.2, d * 0.8], [0.0, h * 0.9, 0.0], "accent")
        for index in range(detail):
            for sign, side in ((-1, "left"), (1, "right")):
                box(
                    f"mount_{side}_{index}",
                    [w * 0.08, h * 0.06, d * 0.08],
                    [sign * w * 0.38, h * 0.13, d * (-0.25 + index * 0.2)],
                    "accent",
                )
        sockets.append({"id": "shaft", "position": [0.0, h, 0.0]})
    else:
        objects.append(_object("body", [w, h, d], [0.0, h / 2, 0.0], primitive="sphere"))
        objects.append(
            _object(
                "crown",
                [w * 0.35, h * 0.3, d * 0.35],
                [0.0, h * 0.65, d * 0.1],
                primitive="sphere",
                material="accent",
                modifiers=[{"type": "subdivision", "levels": min(detail, 2)}],
            )
        )
        for index in range(detail):
            r = min(w, h, d) * 0.012
            curve = _object(
                f"ridge_{index}",
                [w * 0.4, h * 0.4, d * 0.2],
                [w * (-0.1 + index * 0.1), h * 0.5, d * 0.3],
                primitive="curve",
                material="trim",
            )
            curve.update(
                points=[
                    [-w * 0.1, -h * 0.15, -d * 0.03],
                    [0.0, 0.0, d * 0.06],
                    [w * 0.1, h * 0.15, -d * 0.03],
                ],
                bevel_m=r,
            )
            objects.append(curve)
    return objects, sockets


def _integer(value: Any, description: str) -> None:
    if type(value) is not int:
        raise InputError(f"{description} must be an integer, excluding booleans")


def _rotate(point: list[float], angles: list[float]) -> list[float]:
    x, y, z = point
    for axis, degrees in enumerate(angles):
        c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
        if axis == 0:
            y, z = y * c - z * s, y * s + z * c
        elif axis == 1:
            x, z = x * c + z * s, -x * s + z * c
        else:
            x, y = x * c - y * s, x * s + y * c
    return [x, y, z]


def _bounds(obj: dict[str, Any]) -> tuple[list[float], list[float]]:
    half = [v / 2 for v in obj["size_m"]]
    padding = sum(m["thickness_m"] for m in obj["modifiers"] if m["type"] == "solidify")
    corners = [
        [sx * (half[0] + padding), sy * (half[1] + padding), sz * (half[2] + padding)]
        for sx in (-1, 1)
        for sy in (-1, 1)
        for sz in (-1, 1)
    ]
    transformed = [_rotate(point, obj["rotation_deg"]) for point in corners]
    return (
        [min(point[i] for point in transformed) + obj["location"][i] for i in range(3)],
        [max(point[i] for point in transformed) + obj["location"][i] for i in range(3)],
    )


def _validate_objects(
    objects: list[dict[str, Any]],
    sockets: list[dict[str, Any]],
    size: list[float],
    expected_bounds: bool,
) -> dict[str, list[str]]:
    by_id = {obj["id"]: obj for obj in objects}
    if len(by_id) != len(objects):
        raise InputError("Modeling objects require unique stable IDs")
    socket_ids = {socket["id"] for socket in sockets}
    if len(socket_ids) != len(sockets) or socket_ids & by_id.keys():
        raise InputError("Modeling sockets require unique IDs distinct from objects")
    if not any(obj["export"] for obj in objects):
        raise InputError("Modeling plan requires an exported mesh")
    low = [-size[0] / 2, 0.0, -size[2] / 2]
    high = [size[0] / 2, size[1], size[2] / 2]
    for socket in sockets:
        if any(
            v < lo - 1e-9 or v > hi + 1e-9
            for v, lo, hi in zip(socket["position"], low, high, strict=True)
        ):
            raise InputError("Modeling socket lies outside the requested envelope")
    dependencies: dict[str, list[str]] = {}
    exported_bounds = []
    for obj in objects:
        dependencies[obj["id"]] = []
        dimensions = obj["size_m"]
        if obj["primitive"] == "grid":
            _integer(obj.get("detail", 1), "Grid detail")
        if obj["primitive"] == "curve":
            points = obj["points"]
            if len({tuple(p) for p in points}) != len(points):
                raise InputError("Curve points must be distinct with nonzero segment lengths")
            if any(
                math.dist(first, second) < max(1e-6, min(dimensions) * 1e-6)
                for first, second in zip(points, points[1:], strict=False)
            ):
                raise InputError("Curve segment collapses below supported native precision")
            radius = obj["bevel_m"]
            if any(
                abs(value) + radius > dimension / 2 + 1e-9
                for point in points
                for value, dimension in zip(point, dimensions, strict=True)
            ):
                raise InputError("Curve points and bevel must stay inside declared local bounds")
            if any(m["type"] != "mirror" for m in obj["modifiers"]):
                raise InputError("Curve mesh modifiers require an unsupported source conversion")
        for modifier in obj["modifiers"]:
            kind = modifier["type"]
            if kind == "bevel":
                _integer(modifier["segments"], "Bevel segments")
                if modifier["width_m"] >= min(dimensions) / 2:
                    raise InputError("Bevel width exceeds the primitive's smallest half extent")
            elif kind == "subdivision":
                _integer(modifier["levels"], "Subdivision levels")
            elif kind == "mirror":
                _integer(modifier["axis"], "Mirror axis")
            elif kind == "boolean":
                target = modifier["target"]
                if target not in by_id or target == obj["id"]:
                    raise InputError("Boolean target must refer to a different known object")
                if by_id[target]["primitive"] == "curve":
                    raise InputError("Boolean target must be an evaluated mesh primitive")
                dependencies[obj["id"]].append(target)
        lower, upper = _bounds(obj)
        if obj["export"]:
            exported_bounds.append((lower, upper))
        if any(
            a < lo - 1e-8 or b > hi + 1e-8
            for a, b, lo, hi in zip(lower, upper, low, high, strict=True)
        ):
            raise InputError("Transformed modeling geometry lies outside the requested envelope")
    if expected_bounds:
        for axis in range(3):
            if (
                abs(min(bounds[0][axis] for bounds in exported_bounds) - low[axis]) > 1e-8
                or abs(max(bounds[1][axis] for bounds in exported_bounds) - high[axis]) > 1e-8
            ):
                raise InputError(
                    "Declared exported object bounds do not span the requested envelope"
                )
    topological_order(dependencies)
    return dependencies


def _estimate(
    objects: list[dict[str, Any]], dependencies: dict[str, list[str]], budget: int
) -> int:
    by_id = {obj["id"]: obj for obj in objects}
    estimates: dict[str, int] = {}
    for identifier in topological_order(dependencies):
        obj = by_id[identifier]
        primitive = obj["primitive"]
        if primitive == "curve":
            faces = 8 * (len(obj["points"]) - 1) + 2
        elif primitive == "grid":
            faces = 6 * obj.get("detail", 1) ** 2
        else:
            faces = {"box": 6, "cylinder": 34, "sphere": 512}[primitive]
        for modifier in obj["modifiers"]:
            kind = modifier["type"]
            if kind == "bevel":
                faces *= 1 + 8 * modifier["segments"]
            elif kind == "subdivision":
                faces *= 4 ** modifier["levels"]
            elif kind == "mirror":
                faces *= 2
            elif kind == "solidify":
                faces *= 6
            else:
                faces = 8 * faces * estimates[modifier["target"]]
            if faces > budget:
                raise InputError("Conservative evaluated polygon estimate exceeds modeling budget")
        estimates[identifier] = faces
    total = sum(estimates.values())
    if total > budget:
        raise InputError("Total polygon estimate including cutters exceeds modeling budget")
    return total


def compile_modeling(kind: str, request: dict[str, Any], *, seed: int = 42) -> dict[str, Any]:
    """Produce deterministic data only, preserving source request and stable IDs."""
    if (
        not isinstance(kind, str)
        or kind not in MODELING_CAPABILITIES
        or type(seed) is not int
        or not 0 <= seed < 2**32
    ):
        raise InputError("Unknown modeling workflow or invalid uint32 seed")
    validate_schema(request, "modeling_request.schema.json")
    parameters = request["parameters"]
    if kind != "room_kit" and "wall_thickness_m" in parameters:
        raise InputError("wall_thickness_m applies only to the room_kit workflow")
    size = [float(v) for v in parameters["size_m"]]
    detail = parameters.get("detail", 1)
    _integer(detail, "Modeling detail")
    _integer(parameters.get("max_polygons", 50000), "Polygon budget")
    thickness = parameters.get("wall_thickness_m", min(size) * 0.06)
    if thickness >= min(size) / 3:
        raise InputError("Wall thickness leaves insufficient room dimensions")
    if kind == "compose":
        if "objects" not in request:
            raise InputError("Compose workflow requires explicit typed objects")
        if "detail" in parameters:
            raise InputError("Compose detail belongs to individual grid objects")
        objects = copy.deepcopy(request["objects"])
        sockets = copy.deepcopy(request.get("sockets", []))
    else:
        if set(request) - {"schema_version", "asset_id", "parameters"}:
            raise InputError("Explicit objects and QA policies belong to compose only")
        objects, sockets = _families(kind, size, detail, thickness)
    dependencies = _validate_objects(
        objects, sockets, size, request.get("expected_bounds", kind != "compose")
    )
    estimated_polygons = _estimate(objects, dependencies, parameters.get("max_polygons", 50000))
    plan = {
        "schema_version": "1.0.0",
        "asset_id": request["asset_id"],
        "workflow": kind,
        "seed": seed,
        "size_m": size,
        "max_polygons": parameters.get("max_polygons", 50000),
        "lod_ratio": parameters.get("lod_ratio", 0.5),
        "estimated_polygons": estimated_polygons,
        "objects": objects,
        "materials": copy.deepcopy(MATERIALS),
        "sockets": sockets,
        "overlap_policy": request.get("overlap_policy", "ASSEMBLY_CONTACTS"),
        "expected_bounds": request.get("expected_bounds", kind != "compose"),
        "input_digest": canonical_digest({"workflow": kind, "request": request, "seed": seed}),
    }
    return plan
