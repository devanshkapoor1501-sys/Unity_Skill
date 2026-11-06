"""Make known faults in scratch copies and measure each through the real inspector."""

import importlib.util
import json
import sys
from pathlib import Path

import bmesh
import bpy

source, job_file, inspector_file, destination = map(Path, sys.argv[sys.argv.index("--") + 1 :])
spec = importlib.util.spec_from_file_location("fixed_modeling_inspector", inspector_file)
assert spec is not None and spec.loader is not None
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)
job = json.loads(job_file.read_text(encoding="utf-8"))

for fault in ("pivot", "socket", "open_mesh"):
    bpy.ops.wm.open_mainfile(filepath=str(source), use_scripts=False)
    objects = bpy.context.scene.objects
    if fault == "pivot":
        root = next(obj for obj in objects if obj.get("polyforge_kind") == "root")
        root.location.z += 0.05
    elif fault == "socket":
        socket = next(obj for obj in objects if obj.get("polyforge_kind") == "socket")
        socket.location.z += 0.05
    else:
        floor = next(obj for obj in objects if obj.get("semantic_id") == "floor")
        floor.modifiers.clear()
        mesh = bmesh.new()
        try:
            mesh.from_mesh(floor.data)
            bmesh.ops.delete(mesh, geom=[next(iter(mesh.faces))], context="FACES_ONLY")
            mesh.to_mesh(floor.data)
        finally:
            mesh.free()
    copy = destination / (fault + ".blend")
    bpy.ops.wm.save_as_mainfile(filepath=str(copy), check_existing=False)
    report = inspector.inspect({**job, "source_blend": str(copy)})
    (destination / (fault + ".json")).write_text(json.dumps(report), encoding="utf-8")
