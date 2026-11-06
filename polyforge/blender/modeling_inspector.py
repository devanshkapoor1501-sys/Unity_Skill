"""Fixed Blender inspection process that independently reopens editable modeling sources."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import sys
from pathlib import Path
from typing import Any


def _hash(path: Path) -> str:
    if not path.is_file() or path.stat().st_size > 536_870_912:
        raise ValueError("Inspector source must be a bounded existing file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(1_048_576):
            digest.update(block)
    return digest.hexdigest()


def _unity(vector: Any) -> list[float]:
    return [float(vector[0]), float(vector[2]), -float(vector[1])]


def _rotation(obj: Any) -> list[float]:
    mathutils: Any = importlib.import_module("mathutils")
    basis = mathutils.Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
    native = obj.matrix_world.to_quaternion().to_matrix()
    canonical = basis.inverted() @ native @ basis
    return [math.degrees(value) for value in canonical.to_euler("XYZ")]


def _source_geometry(obj: Any) -> dict[str, Any]:
    if obj.get("polyforge_primitive") == "curve":
        if obj.type != "CURVE" or len(obj.data.splines) != 1:
            raise ValueError("Expected one editable POLY curve")
        spline = obj.data.splines[0]
        return {
            "points": [_unity(point.co) for point in spline.points],
            "bevel_m": float(obj.data.bevel_depth),
            "closed_caps": bool(obj.data.use_fill_caps),
            "spline_type": spline.type,
        }
    if obj.get("polyforge_primitive") == "grid":
        cubes = [
            node
            for modifier in obj.modifiers
            if modifier.type == "NODES" and modifier.node_group is not None
            for node in modifier.node_group.nodes
            if node.bl_idname == "GeometryNodeMeshCube"
        ]
        if len(cubes) != 1:
            raise ValueError("Expected one editable Geometry Nodes cube")
        size = cubes[0].inputs["Size"].default_value
        return {"size_m": [float(size[0]), float(size[2]), float(size[1])]}
    if obj.type != "MESH" or not obj.data.vertices:
        raise ValueError("Expected editable mesh source geometry")
    points = [_unity(vertex.co) for vertex in obj.data.vertices]
    return {"size_m": [max(p[i] for p in points) - min(p[i] for p in points) for i in range(3)]}


def _modifiers(obj: Any) -> list[dict[str, Any]]:
    observed: list[dict[str, Any]] = []
    for modifier in obj.modifiers:
        row: dict[str, Any]
        if modifier.type == "BEVEL":
            row = {"type": "bevel", "width_m": modifier.width, "segments": modifier.segments}
        elif modifier.type == "SUBSURF":
            row = {"type": "subdivision", "levels": modifier.levels}
        elif modifier.type == "MIRROR":
            axes = [i for i, active in enumerate(modifier.use_axis) if active]
            # Native Y/Z axes correspond to canonical Z/Y respectively.
            row = {"type": "mirror", "axis": (0, 2, 1)[axes[0]] if len(axes) == 1 else -1}
        elif modifier.type == "SOLIDIFY":
            row = {"type": "solidify", "thickness_m": modifier.thickness}
        elif modifier.type == "BOOLEAN":
            row = {
                "type": "boolean",
                "target": modifier.object.get("semantic_id")
                if modifier.object is not None
                else None,
                "operation": modifier.operation,
            }
        elif modifier.type == "WELD":
            row = {"type": "weld", "merge_threshold_m": modifier.merge_threshold}
        elif modifier.type == "NODES" and modifier.node_group is not None:
            cubes = [
                node
                for node in modifier.node_group.nodes
                if node.bl_idname == "GeometryNodeMeshCube"
            ]
            if len(cubes) == 1:
                values = [
                    int(cubes[0].inputs[name].default_value)
                    for name in ("Vertices X", "Vertices Y", "Vertices Z")
                ]
                row = {
                    "type": "geometry_nodes",
                    "detail": values[0] - 1 if len(set(values)) == 1 else -1,
                }
            else:
                row = {"type": "UNSUPPORTED_GEOMETRY_NODES"}
        else:
            row = {"type": "UNSUPPORTED", "native_type": modifier.type}
        observed.append(row)
    return observed


def _geometry(obj: Any, depsgraph: Any) -> dict[str, Any]:
    bmesh: Any = importlib.import_module("bmesh")
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    if mesh is None or not mesh.vertices or not mesh.polygons:
        if mesh is not None:
            evaluated.to_mesh_clear()
        raise ValueError("Inspected object has no evaluated polygon mesh")
    bm = bmesh.new()
    try:
        if len(mesh.vertices) > 2_000_000 or len(mesh.polygons) > 2_000_000:
            raise ValueError("Inspected mesh exceeds the native inspection budget")
        bm.from_mesh(mesh)
        bm.normal_update()
        points = [_unity(obj.matrix_world @ v.co) for v in mesh.vertices]
        finite = sum(not math.isfinite(value) for point in points for value in point)
        # Inspect each closed component so a reversed island cannot hide in positive total volume.
        remaining = set(bm.faces)
        inverted = 0
        while remaining:
            first = remaining.pop()
            pending = [first]
            volume = 0.0
            while pending:
                face = pending.pop()
                vertices = [v.co for v in face.verts]
                for index in range(1, len(vertices) - 1):
                    volume += vertices[0].dot(vertices[index].cross(vertices[index + 1])) / 6
                for edge in face.edges:
                    for other in edge.link_faces:
                        if other in remaining:
                            remaining.remove(other)
                            pending.append(other)
            if volume <= 0:
                inverted += 1
        uv_nonfinite = sum(
            not math.isfinite(value)
            for layer in mesh.uv_layers
            for loop in layer.data
            for value in loop.uv
        )
        mesh.calc_loop_triangles()
        return {
            "vertices": len(mesh.vertices),
            "polygons": len(mesh.polygons),
            "triangles": len(mesh.loop_triangles),
            "nonmanifold_edges": sum(not edge.is_manifold for edge in bm.edges),
            "degenerate_faces": sum(face.calc_area() <= 1e-12 for face in bm.faces),
            "nonfinite_values": finite,
            "normal_inconsistencies": inverted
            + sum(edge.is_manifold and not edge.is_contiguous for edge in bm.edges),
            "signed_volume": bm.calc_volume(signed=True),
            "uv_layers": len(mesh.uv_layers),
            "uv_nonfinite_values": uv_nonfinite,
            "invalid_material_faces": sum(
                face.material_index >= len(mesh.materials) for face in mesh.polygons
            ),
            "bounds_min_unity": [min(point[i] for point in points) for i in range(3)],
            "bounds_max_unity": [max(point[i] for point in points) for i in range(3)],
        }
    finally:
        bm.free()
        evaluated.to_mesh_clear()


def inspect(job: dict[str, Any]) -> dict[str, Any]:
    bpy: Any = importlib.import_module("bpy")
    source = Path(job["source_blend"])
    output = Path(job["output_dir"])
    if not source.is_absolute() or not output.is_absolute() or not output.is_dir():
        raise ValueError("Inspector requires absolute owned source and existing output paths")
    before = _hash(source)
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    bpy.context.view_layer.update()
    plan = job["plan"]
    depsgraph = bpy.context.evaluated_depsgraph_get()
    objects = []
    sockets = []
    roots = []
    lods = []
    issues = []
    for obj in bpy.context.scene.objects:
        kind = obj.get("polyforge_kind")
        if kind == "root":
            roots.append(obj)
        elif kind == "module":
            objects.append(
                {
                    "id": obj.get("semantic_id"),
                    "primitive": obj.get("polyforge_primitive"),
                    "parent_id": obj.parent.get("semantic_id") if obj.parent else None,
                    "export": obj.get("polyforge_export"),
                    "location_unity": _unity(obj.matrix_world.translation),
                    "rotation_deg": _rotation(obj),
                    "scale": list(obj.matrix_world.to_scale()),
                    "material_ids": [
                        material.get("semantic_id") if material else None
                        for material in obj.data.materials
                    ],
                    "modifiers": _modifiers(obj),
                    "source_geometry": _source_geometry(obj),
                    "modifiers_enabled": all(
                        m.show_viewport and m.show_render for m in obj.modifiers
                    ),
                    **_geometry(obj, depsgraph),
                }
            )
        elif kind == "socket":
            sockets.append(
                {
                    "id": obj.get("semantic_id"),
                    "parent_id": obj.parent.get("semantic_id") if obj.parent else None,
                    "position_unity": _unity(obj.matrix_world.translation),
                }
            )
        elif kind == "lod":
            lods.append(_geometry(obj, depsgraph))
        elif obj.type in {"MESH", "CURVE", "ARMATURE"}:
            issues.append("Unexpected geometry object outside semantic modeling inventory")
    if len(roots) != 1 or len(lods) != 1:
        raise ValueError("Inspector requires exactly one asset root and one evaluated LOD")
    root = roots[0]
    exports = [row for row in objects if row["export"] is True]
    if not exports:
        raise ValueError("Inspector found no exportable modeling modules")
    for row in [*objects, *lods]:
        for key in (
            "nonmanifold_edges",
            "degenerate_faces",
            "nonfinite_values",
            "normal_inconsistencies",
        ):
            if row[key]:
                issues.append(f"{row.get('id', 'lod')}: {key}={row[key]}")
        if row["signed_volume"] <= 0:
            issues.append(f"{row.get('id', 'lod')}: nonpositive signed volume")
    for row in objects:
        if row["uv_layers"] < 1 or row["uv_nonfinite_values"]:
            issues.append(f"{row['id']}: required UV preflight failed")
        if row["invalid_material_faces"]:
            issues.append(f"{row['id']}: invalid material slot index")
    total_polygons = sum(row["polygons"] for row in exports)
    after = _hash(source)
    return {
        "schema_version": "1.0.0",
        "asset_id": plan["asset_id"],
        "input_digest": plan["input_digest"],
        "technical_status": "FAIL" if issues else "PASS",
        "artistic_status": "REVIEW",
        "source_unchanged": before == after,
        "source_sha256_before": before,
        "source_sha256_after": after,
        "coordinate_basis": {
            "up": "Z",
            "forward": "-Y",
            "meters_per_unit": bpy.context.scene.unit_settings.scale_length,
        },
        "root": {
            "semantic_id": root.get("semantic_id"),
            "location_unity": _unity(root.matrix_world.translation),
            "rotation_deg": _rotation(root),
            "scale": list(root.matrix_world.to_scale()),
        },
        "materials": [
            {"id": m.get("semantic_id"), "color_rgba": list(m.diffuse_color)}
            for m in bpy.data.materials
            if m.get("semantic_id") is not None
        ],
        "objects": objects,
        "sockets": sockets,
        "aggregate": {
            **{
                key: sum(row[key] for row in exports)
                for key in ("vertices", "polygons", "triangles")
            },
            "bounds_min_unity": [
                min(row["bounds_min_unity"][i] for row in exports) for i in range(3)
            ],
            "bounds_max_unity": [
                max(row["bounds_max_unity"][i] for row in exports) for i in range(3)
            ],
        },
        "lod": {
            **lods[0],
            "polygons": lods[0]["polygons"],
            "source_polygons": total_polygons,
            "ratio": lods[0]["polygons"] / total_polygons,
        },
        "issues": issues,
    }


def main() -> None:
    arguments = sys.argv[sys.argv.index("--") + 1 :]
    if len(arguments) != 1:
        raise ValueError("Inspector requires exactly one owned job file")
    job = json.loads(Path(arguments[0]).read_text(encoding="utf-8"))
    report = inspect(job)
    (Path(job["output_dir"]) / "inspection.json").write_text(
        json.dumps(report, allow_nan=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
