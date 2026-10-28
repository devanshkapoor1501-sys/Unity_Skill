"""Reviewed Blender-only rig author; never loads task-provided Python."""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def run(job: dict[str, Any], output: Path) -> None:
    bpy: Any = importlib.import_module("bpy")
    Vector: Any = importlib.import_module("mathutils").Vector
    if bpy.app.version[:3] != (5, 2, 2):
        raise ValueError("Pinned Blender 5.2.2 required")
    worker_path = Path(__file__).resolve().parents[1] / "blender" / "worker.py"
    spec = importlib.util.spec_from_file_location("polyforge_static_worker", worker_path)
    if spec is None or spec.loader is None:
        raise ValueError("Missing reviewed geometry worker")
    static = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(static)
    static.build(job["recipe"])
    asset = job["recipe"]["asset_id"]
    meshes = {
        o["semantic_id"]: o
        for o in bpy.context.scene.objects
        if o.get("polyforge_kind") == "module"
    }
    sockets = [o for o in bpy.context.scene.objects if o.get("polyforge_kind") == "socket"]
    arm = bpy.data.armatures.new(asset + "_skeleton")
    rig = bpy.data.objects.new(asset + "_rig", arm)
    bpy.context.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    rig.select_set(True)
    rig["semantic_id"] = asset
    rig["family"] = "robot.modular.rigid.v1"
    bpy.ops.object.mode_set(mode="EDIT")
    root = arm.edit_bones.new("root")
    root.head = (0, 0, 0)
    root.tail = (0, 0, 0.1)
    original = {m["id"]: m for m in job["recipe"]["modules"]}
    for identifier, obj in meshes.items():
        bone = arm.edit_bones.new(identifier)
        top = obj.matrix_world.translation.copy()
        if identifier.startswith(("upper_arm", "forearm", "thigh", "shin")):
            top.z += obj.dimensions.z / 2
        bone.head = top
        bone.tail = top + Vector((0, 0, -max(0.03, obj.dimensions.z * 0.5)))
    for identifier in meshes:
        arm.edit_bones[identifier].parent = arm.edit_bones[
            original[identifier].get("parent", "root")
        ]
    bpy.ops.object.mode_set(mode="OBJECT")
    bindings = {}
    for identifier, obj in meshes.items():
        matrix = obj.matrix_world.copy()
        obj.parent = rig
        obj.matrix_world = matrix
        group = obj.vertex_groups.new(name=identifier)
        group.add(list(range(len(obj.data.vertices))), 1.0, "REPLACE")
        modifier = obj.modifiers.new("PolyForgeRigidSkin", "ARMATURE")
        modifier.object = rig
        bindings[identifier] = identifier
    for obj in sockets:
        matrix = obj.matrix_world.copy()
        owner = obj.parent["semantic_id"]
        obj.parent = rig
        obj.parent_type = "BONE"
        obj.parent_bone = owner
        obj.matrix_world = matrix
    bpy.context.view_layer.update()
    # Preserve exact rest coordinates for independently measured evaluated skin/socket errors.
    rest_vertex = {k: o.matrix_world @ o.data.vertices[0].co for k, o in meshes.items()}
    rest_bone = {k: (rig.matrix_world @ arm.bones[k].matrix_local) for k in meshes}
    rest_socket = {o.name: o.matrix_world.translation.copy() for o in sockets}
    bpy.context.scene.render.fps = 24
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = 25
    anim = rig.animation_data_create()
    helper: Any = importlib.import_module("bpy_extras.anim_utils")
    actions = {}
    for name in ("Idle", "Walk"):
        action = bpy.data.actions.new(name)
        action.use_fake_user = True
        slot = action.slots.new(id_type="OBJECT", name=rig.name)
        bag = helper.action_ensure_channelbag_for_slot(action, slot)
        anim.action = action
        anim.action_slot = slot
        for identifier in arm.bones.keys():
            pose = rig.pose.bones[identifier]
            pose.rotation_mode = "XYZ"
            curve = bag.fcurves.new(data_path=pose.path_from_id("rotation_euler"), index=0)
            for frame, phase in ((1, 0), (7, 1), (13, 0), (19, -1), (25, 0)):
                amplitude = 0.02 if name == "Idle" and identifier == "body" else 0.0
                if name == "Walk" and identifier.startswith(("upper_arm", "thigh")):
                    amplitude = (
                        0.45
                        * (-1 if identifier.endswith("_r") else 1)
                        * (-1 if identifier.startswith("upper_arm") else 1)
                    )
                key = curve.keyframe_points.insert(frame, phase * amplitude)
                key.interpolation = "LINEAR"
        actions[name] = action
    anim.action = actions["Idle"]
    anim.action_slot = actions["Idle"].slots[0]
    bpy.context.scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "source.blend"), check_existing=False)
    bpy.ops.wm.open_mainfile(
        filepath=str(output / "source.blend"), load_ui=False, use_scripts=False
    )
    rig = bpy.data.objects[asset + "_rig"]
    meshes = {
        o["semantic_id"]: o
        for o in bpy.context.scene.objects
        if o.type == "MESH" and o.get("polyforge_kind") == "module"
    }
    sockets = [o for o in bpy.context.scene.objects if o.get("polyforge_kind") == "socket"]
    report = {
        "schema_version": "1.0.0",
        "asset_id": asset,
        "family": rig["family"],
        "blender_version": bpy.app.version_string.split()[0],
        "root_motion": "IN_PLACE",
        "bones": {
            b.name: {"head": list(b.head_local), "parent": b.parent.name if b.parent else ""}
            for b in rig.data.bones
        },
        "bindings": bindings,
        "clips": {},
        "source_reopened": True,
        "weights_complete": all(
            len(o.vertex_groups) == 1
            and all(
                len(v.groups) == 1 and abs(v.groups[0].weight - 1) < 1e-6 for v in o.data.vertices
            )
            for o in meshes.values()
        ),
        "sockets_preserved": len(sockets) == len(job["recipe"]["sockets"]),
        "api_probe": {
            "slot_api": str(type(rig.animation_data.action.slots[0]).__name__),
            "helper": helper.action_ensure_channelbag_for_slot.__name__,
        },
    }
    for name in ("Idle", "Walk"):
        action = bpy.data.actions[name]
        rig.animation_data.action = action
        rig.animation_data.action_slot = action.slots[0]
        frames = []
        for frame in (1, 7, 13, 19, 25):
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            deps = bpy.context.evaluated_depsgraph_get()
            skin_error = socket_error = 0.0
            for identifier, obj in meshes.items():
                evaluated = obj.evaluated_get(deps)
                actual = evaluated.matrix_world @ evaluated.data.vertices[0].co
                expected = (
                    rig.matrix_world
                    @ rig.pose.bones[identifier].matrix
                    @ rest_bone[identifier].inverted()
                    @ rest_vertex[identifier]
                )
                skin_error = max(skin_error, (actual - expected).length)
            for obj in sockets:
                owner = obj.parent_bone
                expected = (
                    rig.matrix_world
                    @ rig.pose.bones[owner].matrix
                    @ rest_bone[owner].inverted()
                    @ rest_socket[obj.name]
                )
                socket_error = max(socket_error, (obj.matrix_world.translation - expected).length)
            frames.append(
                {
                    "frame": frame,
                    "angles": {b.name: float(b.rotation_euler.x) for b in rig.pose.bones},
                    "root_position": list(rig.matrix_world @ rig.pose.bones["root"].head),
                    "skin_error_m": skin_error,
                    "socket_error_m": socket_error,
                }
            )
        report["clips"][name] = {
            "slot_count": len(action.slots),
            "channelbag_count": len(action.layers[0].strips[0].channelbags),
            "duration_seconds": (action.frame_range[1] - action.frame_range[0]) / 24,
            "samples": frames,
        }
    (output / "motion.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    # Both actions are exported explicitly, using slots and matching the one supported armature.
    bpy.context.scene.frame_set(1)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in [rig, *meshes.values(), *sockets]:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.export_scene.fbx(
        filepath=str(output / "robot.fbx"),
        check_existing=False,
        use_selection=True,
        object_types={"ARMATURE", "MESH", "EMPTY"},
        add_leaf_bones=False,
        bake_anim=True,
        bake_anim_use_all_actions=True,
        bake_anim_use_nla_strips=False,
        bake_anim_simplify_factor=0,
        axis_forward="-Z",
        axis_up="Y",
        apply_unit_scale=True,
        use_custom_props=True,
    )
    # Four actual pose views, using the existing source-audit renderer.
    rig.animation_data.action = bpy.data.actions["Walk"]
    rig.animation_data.action_slot = rig.animation_data.action.slots[0]
    bpy.context.scene.frame_set(7)
    audit_path = worker_path.with_name("audit_worker.py")
    spec = importlib.util.spec_from_file_location("polyforge_rig_audit", audit_path)
    if spec is None or spec.loader is None:
        raise ValueError("Missing audit worker")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    audit.render_views(output, 256)
    completed = {
        "input_digest": job["input_digest"],
        "worker_sha256": job["worker_sha256"],
        "files": [
            {"name": p.name, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(output.iterdir())
            if p.is_file() and p.suffix != ".blend1"
        ],
    }
    temporary = output / ".worker-complete.tmp"
    temporary.write_text(json.dumps(completed, indent=2) + "\n", encoding="utf-8")
    temporary.replace(output / "worker-complete.json")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1 :]
    run(json.loads(Path(argv[0]).read_text("utf-8")), Path(argv[1]))
