"""Trusted test-only corruption probe; never exposed by CLI or recipe inputs."""

import importlib
import importlib.util
import json
import sys
from pathlib import Path

bpy = importlib.import_module("bpy")
job_path, output = map(Path, sys.argv[sys.argv.index("--") + 1 :])
job = json.loads(job_path.read_text("utf-8"))
spec = importlib.util.spec_from_file_location("reviewed_worker", job["worker"])
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
results = {}
for fault in (
    "missing_uv",
    "degenerate_face",
    "reversed_socket",
    "budget",
    "translated_root",
    "offset_meshes",
    "units_changed",
):
    bpy.ops.wm.open_mainfile(filepath=job["source"], load_ui=False, use_scripts=False)
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if fault == "missing_uv":
        meshes[0].data.uv_layers.remove(meshes[0].data.uv_layers.active)
    elif fault == "degenerate_face":
        mesh = meshes[0].data
        for index in mesh.polygons[0].vertices:
            mesh.vertices[index].co = mesh.vertices[mesh.polygons[0].vertices[0]].co
        mesh.update()
    elif fault == "reversed_socket":
        left = next(
            o
            for o in bpy.context.scene.objects
            if o.get("polyforge_kind") == "socket" and o.get("semantic_id") == "hand_l"
        )
        matrix = left.matrix_world.copy()
        matrix.translation.x = 20
        left.matrix_world = matrix
    elif fault == "translated_root":
        next(
            o for o in bpy.context.scene.objects if o.get("polyforge_kind") == "asset"
        ).location.x = 2
    elif fault == "offset_meshes":
        next(
            o
            for o in bpy.context.scene.objects
            if o.get("polyforge_kind") == "module" and o.get("semantic_id") == "body"
        ).location.x += 2
    elif fault == "units_changed":
        bpy.context.scene.unit_settings.scale_length = 0.01
    report = worker.measure(job["recipe"])
    results[fault] = report
output.write_text(json.dumps(results, indent=2, allow_nan=False), encoding="utf-8")
