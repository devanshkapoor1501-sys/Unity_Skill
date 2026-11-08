"""Observe source and FBX frames in a separate Blender, without saving originals."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import bpy


def observe():
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    result = []
    for obj in bpy.context.scene.objects:
        if obj.type not in {"MESH", "CURVE", "EMPTY"}:
            continue
        row = {
            "name": obj.name,
            "parent": obj.parent.name if obj.parent else None,
            "local_matrix": [list(values) for values in obj.matrix_local],
            "world_matrix": [list(values) for values in obj.matrix_world],
            "parent_inverse": [list(values) for values in obj.matrix_parent_inverse],
            "determinant": obj.matrix_world.determinant(),
            "world_position": list(obj.matrix_world.translation),
        }
        if obj.type in {"MESH", "CURVE"}:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
            try:
                row["source_materials"] = [m.name if m else None for m in obj.data.materials]
                row["evaluated_materials"] = [m.name if m else None for m in mesh.materials]
                mesh.calc_loop_triangles()
                counts = {}
                for triangle in mesh.loop_triangles:
                    material = obj.data.materials[triangle.material_index]
                    name = material.name if material else "<unbound>"
                    counts[name] = counts.get(name, 0) + 1
                row["material_triangles"] = counts
                points = [obj.matrix_world @ vertex.co for vertex in mesh.vertices]
                row["bounds_min"] = [min(v[i] for v in points) for i in range(3)]
                row["bounds_max"] = [max(v[i] for v in points) for i in range(3)]
            finally:
                evaluated.to_mesh_clear()
        result.append(row)
    return result


input_path, output_path = (Path(s) for s in sys.argv[sys.argv.index("--") + 1 :])
inputs = json.loads(input_path.read_text(encoding="utf-8"))
properties = bpy.ops.export_scene.fbx.get_rna_type().properties
receipt = {
    "blender_version": bpy.app.version_string,
    "fbx_defaults": {
        name: properties[name].default
        for name in ("use_space_transform", "bake_space_transform", "apply_unit_scale")
    },
    "models": [],
}
for item in inputs:
    source = Path(item["source"])
    before = hashlib.sha256(source.read_bytes()).hexdigest()
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    record = {"source": str(source), "sha256_before": before, "source_objects": observe()}
    # Force an actual export failure in this scratch process, then ensure that
    # temporary export transforms and evaluated copies have all been unwound.
    spec = importlib.util.spec_from_file_location("fixed_exporter", item["worker"])
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    root = next(o for o in bpy.context.scene.objects if o.get("polyforge_kind") == "root")
    selected = [
        o
        for o in bpy.context.scene.objects
        if o.get("polyforge_kind") == "module" and o.get("polyforge_export")
    ]
    failure = None
    try:
        exporter.export_copies(bpy, selected, source / "invalid-export.fbx", root)
    except (OSError, RuntimeError) as error:
        failure = str(error)
    assert failure, "Expected a real file-as-directory export failure"
    record["export_failure"] = failure
    record["source_objects_after_failure"] = observe()
    assert record["source_objects_after_failure"] == record["source_objects"]
    record["export_failure_rolled_back"] = True
    for kind in ("asset", "lod"):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(source.with_name(kind + ".fbx")))
        record[kind + "_fbx_objects"] = observe()
    record["sha256_after"] = hashlib.sha256(source.read_bytes()).hexdigest()
    assert record["sha256_after"] == before
    receipt["models"].append(record)
Path(output_path).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
