"""Reviewed test-only in-memory source corruption; never exposed as recipe flags."""

import importlib
import importlib.util
import json
import sys
from pathlib import Path

bpy = importlib.import_module("bpy")
job_path, output = map(Path, sys.argv[sys.argv.index("--") + 1 :])
job = json.loads(job_path.read_text("utf-8"))
spec = importlib.util.spec_from_file_location("reviewed_audit", job["worker"])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
results = {}
for fault in (
    "reversed_normals",
    "nonuniform_scale",
    "missing_uv",
    "orientation",
    "absent_socket",
    "material",
):
    bpy.ops.wm.open_mainfile(filepath=job["source"], load_ui=False, use_scripts=False)
    obj = next(
        o
        for o in bpy.context.scene.objects
        if o.get("polyforge_kind") == "module" and o.get("semantic_id") == "body"
    )
    if fault == "reversed_normals":
        bmesh = importlib.import_module("bmesh")
        bm = bmesh.new()
        bm.from_mesh(obj.data)
        bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
        bm.to_mesh(obj.data)
        bm.free()
    elif fault == "nonuniform_scale":
        obj.scale.x = 2
    elif fault == "missing_uv":
        obj.data.uv_layers.remove(obj.data.uv_layers.active)
    elif fault == "orientation":
        obj.rotation_euler.z = 0.5
    elif fault == "absent_socket":
        missing = next(o for o in bpy.context.scene.objects if o.get("polyforge_kind") == "socket")
        bpy.data.objects.remove(missing, do_unlink=True)
    elif fault == "material":
        obj.data.materials.clear()
    results[fault] = module.diagnostics(job["recipe"])
output.write_text(json.dumps(results, indent=2), encoding="utf-8")
