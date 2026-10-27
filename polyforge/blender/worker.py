"""Reviewed Blender-only worker. Inputs are prevalidated data; no user code imports."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def name_for(identifier: str) -> str:
    return identifier if len(identifier) <= 60 else identifier[:48] + "_" + digest(identifier)[:10]


def canonical_faces(
    vertices: list[list[float]], faces: list[list[int]], uv_faces: list[list[list[float]]]
) -> list[list[list[float]]]:
    """Address oriented polygons by coordinates/UVs, not Blender's storage indices."""
    result = []
    for indices, uvs in zip(faces, uv_faces, strict=True):
        if not uvs:
            uvs = [[0.0, 0.0] for _ in indices]  # Missing UVs are reported separately as failures.
        corners = [vertices[index] + uv for index, uv in zip(indices, uvs, strict=True)]
        result.append(min(corners[i:] + corners[:i] for i in range(len(corners))))
    return sorted(result)


def build(recipe: dict[str, Any]) -> None:
    bpy: Any = importlib.import_module("bpy")
    mathutils: Any = importlib.import_module("mathutils")
    Vector, Matrix = mathutils.Vector, mathutils.Matrix
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1
    root = bpy.data.objects.new(name_for(recipe["asset_id"]), None)
    bpy.context.collection.objects.link(root)
    root["semantic_id"] = recipe["asset_id"]
    root["polyforge_kind"] = "asset"
    root["pivot_rule"] = "base_center"
    root["source_up"] = "Z"
    root["source_forward"] = "-Y"
    materials = {}
    for material in recipe["materials"]:
        item = bpy.data.materials.new(material["id"])
        item.use_fake_user = True  # Preserve the declared editable palette across source reloads.
        item.diffuse_color = material["color_rgba"]
        item.metallic = material.get("metallic", 0.0)
        item.roughness = material.get("roughness", 0.65)
        item["semantic_id"] = material["id"]
        materials[material["id"]] = item
    objects: dict[str, Any] = {}
    sockets = {s["id"]: s for s in recipe["sockets"]}
    remaining = list(recipe["modules"])
    parent_ids: dict[str, str | None] = {}

    def native(values: list[float]) -> Any:
        return Vector((values[0], -values[2], values[1]))

    while remaining:
        ready = [m for m in remaining if m.get("parent") in {None, *objects}]
        if not ready:
            raise ValueError("cyclic module parents")
        for module in ready:
            remaining.remove(module)
            primitive = module["primitive"]
            if primitive in {"cube", "beveled_box"}:
                bpy.ops.mesh.primitive_cube_add(size=1, calc_uvs=True)
            elif primitive == "sphere":
                bpy.ops.mesh.primitive_uv_sphere_add(
                    segments=16, ring_count=8, radius=0.5, calc_uvs=True
                )
            elif primitive == "cylinder":
                bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=0.5, depth=1, calc_uvs=True)
            elif primitive == "plane":
                bpy.ops.mesh.primitive_plane_add(size=1, calc_uvs=True)
            else:
                raise ValueError("unknown primitive")
            obj = bpy.context.object
            obj.name = name_for(recipe["asset_id"] + ":module:" + module["id"])
            obj["semantic_id"] = module["id"]
            obj["polyforge_kind"] = "module"
            size = module.get("size_m", recipe["parameters"]["size_m"])
            obj.scale = (size[0], size[2], size[1])
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            if primitive == "beveled_box":
                modifier = obj.modifiers.new("reviewed_bevel", "BEVEL")
                modifier.width = module.get("bevel_m", min(size) * 0.03)
                modifier.segments = 2
                bpy.ops.object.modifier_apply(modifier=modifier.name)
            obj.data.materials.append(materials[module.get("material_id", next(iter(materials)))])
            obj.location = native(module.get("location", [0, 0, 0]))
            parent_id = module.get("parent")
            if parent_id:
                obj.location += objects[parent_id].location
                if "attach_to" in module:
                    obj.location += native(sockets[module["attach_to"]]["position"])
            bpy.context.view_layer.update()
            objects[module["id"]] = obj
            parent_ids[module["id"]] = parent_id
    for socket in recipe["sockets"]:
        obj = bpy.data.objects.new(name_for(recipe["asset_id"] + ":socket:" + socket["id"]), None)
        bpy.context.collection.objects.link(obj)
        obj.empty_display_type = "ARROWS"
        obj.empty_display_size = 0.05
        obj["semantic_id"] = socket["id"]
        obj["polyforge_kind"] = "socket"
        obj.location = objects[socket["module_id"]].location + native(socket["position"])
        objects["socket:" + socket["id"]] = obj
        parent_ids["socket:" + socket["id"]] = socket["module_id"]
    bpy.context.view_layer.update()
    points = [
        obj.matrix_world @ vertex.co
        for obj in objects.values()
        if obj.type == "MESH"
        for vertex in obj.data.vertices
    ]
    minimum = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    maximum = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    extent = maximum - minimum
    target = recipe["parameters"]["size_m"]
    dimensions = [target[0], target[2], target[1]]
    if any(e <= 1e-8 or not math.isfinite(e) for e in extent):
        raise ValueError("zero/nonfinite asset bounds")
    fit = Matrix.Diagonal(Vector(tuple(dimensions[i] / extent[i] for i in range(3)) + (1,)))
    shift = Vector((-(minimum.x + maximum.x) / 2, -(minimum.y + maximum.y) / 2, -minimum.z))
    centers = {}
    for key, obj in objects.items():
        center = fit.to_3x3() @ (obj.location + shift)
        if obj.type == "MESH":
            obj.data.transform(fit)
        obj.location = center
        centers[key] = center
    # Restore explicit hierarchy after baking the fit into mesh data; scales stay one.
    for key, obj in objects.items():
        parent_id = parent_ids[key]
        obj.parent = objects[parent_id] if parent_id is not None else root
        obj.matrix_world = Matrix.Translation(centers[key])
        bpy.context.view_layer.update()
    for obj in objects.values():
        if obj.type != "MESH":
            continue
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.cube_project(cube_size=1)
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.scene["polyforge_asset_id"] = recipe["asset_id"]


def measure(recipe: dict[str, Any], logical_path: Path | None = None) -> dict[str, Any]:
    bpy: Any = importlib.import_module("bpy")
    bpy.context.view_layer.update()
    meshes = sorted(
        (o for o in bpy.context.scene.objects if o.get("polyforge_kind") == "module"),
        key=lambda o: o["semantic_id"],
    )
    sockets = sorted(
        (o for o in bpy.context.scene.objects if o.get("polyforge_kind") == "socket"),
        key=lambda o: o["semantic_id"],
    )
    roots = [o for o in bpy.context.scene.objects if o.get("polyforge_kind") == "asset"]
    if len(roots) != 1 or roots[0].get("semantic_id") != recipe["asset_id"]:
        raise ValueError("Source requires exactly one identified asset root")
    root = roots[0]
    pivot = root.matrix_world.translation
    points, logical, bad_uv, degenerate, nonfinite = [], [], 0, 0, 0
    for obj in meshes:
        mesh = obj.data
        world = [obj.matrix_world @ v.co for v in mesh.vertices]
        points.extend(world)
        nonfinite += sum(not math.isfinite(c) for v in world for c in v)
        degenerate += sum(p.area <= 1e-12 for p in mesh.polygons)
        uv = mesh.uv_layers.active
        uv_faces = []
        for polygon in mesh.polygons:
            values = [list(uv.data[index].uv) for index in polygon.loop_indices] if uv else []
            area = (
                abs(
                    sum(
                        a[0] * b[1] - b[0] * a[1]
                        for a, b in zip(values, values[1:] + values[:1], strict=True)
                    )
                )
                / 2
            )
            bad_uv += (
                not values or area <= 1e-12 or any(not math.isfinite(n) for p in values for n in p)
            )
            uv_faces.append([[round(n, 6) for n in p] for p in values])
        vertices = [[round(c, 6) for c in v] for v in world]
        faces = [list(p.vertices) for p in mesh.polygons]
        logical.append(
            {
                "id": obj["semantic_id"],
                "parent": obj.parent.get("semantic_id") if obj.parent else None,
                "vertices": sorted(vertices),
                "faces": canonical_faces(vertices, faces, uv_faces),
                "materials": [m["semantic_id"] for m in mesh.materials],
            }
        )
    minimum = [min(p[i] for p in points) for i in range(3)]
    maximum = [max(p[i] for p in points) for i in range(3)]
    bounds = [round(maximum[i] - minimum[i], 6) for i in range(3)]
    positions = {
        o["semantic_id"]: [
            round(o.matrix_world.translation.x, 6),
            round(o.matrix_world.translation.z, 6),
            round(-o.matrix_world.translation.y, 6),
        ]
        for o in sockets
    }
    logical_payload = {"modules": logical, "sockets": positions}
    if logical_path is not None:
        logical_path.write_text(
            json.dumps(logical_payload, sort_keys=True, allow_nan=False), encoding="utf-8"
        )
    metrics = {
        "schema_version": "1.0.0",
        "status": "PASS",
        "asset_id": recipe["asset_id"],
        "blender_version": ".".join(str(v) for v in bpy.app.version),
        "blender_version_label": bpy.app.version_string,
        "worker_python_version": sys.version,
        "blender_build_hash": bpy.app.build_hash.decode(),
        "coordinate_basis": {"up": root.get("source_up"), "forward": root.get("source_forward")},
        "meters_per_unit": bpy.context.scene.unit_settings.scale_length,
        "bounds_m": bounds,
        "bounds_unity_m": [bounds[0], bounds[2], bounds[1]],
        "pivot_unity_m": [round(pivot.x, 6), round(pivot.z, 6), round(-pivot.y, 6)],
        "minimum_native_m": [round(n, 6) for n in minimum],
        "polygon_count": sum(len(o.data.polygons) for o in meshes),
        "vertex_count": sum(len(o.data.vertices) for o in meshes),
        "degenerate_faces": degenerate,
        "invalid_uv_faces": bad_uv,
        "nonfinite_values": nonfinite,
        "module_ids": [o["semantic_id"] for o in meshes],
        "socket_ids": [o["semantic_id"] for o in sockets],
        "material_ids": sorted(m["semantic_id"] for m in bpy.data.materials if "semantic_id" in m),
        "socket_positions_unity_m": positions,
        "geometry_digest": digest(logical_payload),
        "object_names": sorted(o.name for o in bpy.context.scene.objects),
    }
    metrics["logical_metrics"] = {
        key: metrics[key]
        for key in (
            "bounds_m",
            "polygon_count",
            "vertex_count",
            "module_ids",
            "socket_ids",
            "geometry_digest",
        )
    }
    return metrics


def main() -> None:
    bpy: Any = importlib.import_module("bpy")
    job_path, output = map(Path, sys.argv[sys.argv.index("--") + 1 :])
    job = json.loads(job_path.read_text("utf-8"))
    if bpy.app.version != (5, 2, 2):
        raise RuntimeError("Pinned Blender 5.2.2 is required; found " + bpy.app.version_string)
    recipe = job["recipe"]
    if job.get("source"):
        bpy.ops.wm.open_mainfile(
            filepath=str(output / "source.blend"), load_ui=False, use_scripts=False
        )
    else:
        build(recipe)
    first = measure(recipe)
    if not job.get("source"):
        bpy.ops.wm.save_as_mainfile(
            filepath=str(output / "source.blend"), check_existing=False, compress=False
        )
    bpy.ops.wm.open_mainfile(
        filepath=str(output / "source.blend"), load_ui=False, use_scripts=False
    )
    second = measure(recipe, output / "logical-geometry.json")
    if first["geometry_digest"] != second["geometry_digest"]:
        raise RuntimeError("Saved source roundtrip changed logical geometry")
    second["saved_roundtrip_verified"] = True
    (output / "metrics.json").write_text(
        json.dumps(second, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    if job.get("audit_export"):
        spec = importlib.util.spec_from_file_location(
            "reviewed_audit", Path(__file__).with_name("audit_worker.py")
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Reviewed audit worker unavailable")
        audit = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(audit)
        audit.run(recipe, second, output, job["preview_resolution"], measure)


if __name__ == "__main__":
    main()
