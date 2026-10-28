"""Reviewed six-frame Blender bake; fixed camera and root-projected pivot."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from pathlib import Path
from typing import Any


def run(job: dict[str, Any], output: Path) -> None:
    bpy: Any = importlib.import_module("bpy")
    Vector: Any = importlib.import_module("mathutils").Vector
    project: Any = importlib.import_module("bpy_extras.object_utils").world_to_camera_view
    source = Path(job["source"])
    if (
        bpy.app.version[:3] != (5, 2, 2)
        or hashlib.sha256(source.read_bytes()).hexdigest() != job["source_sha256"]
    ):
        raise ValueError("Pinned source/version changed")
    bpy.ops.wm.open_mainfile(filepath=str(source), load_ui=False, use_scripts=False)
    scene = bpy.context.scene
    rig = next(o for o in scene.objects if o.type == "ARMATURE")
    if rig.get("semantic_id") != job["asset_id"]:
        raise ValueError("Wrong rig identity")
    action = bpy.data.actions["Walk"]
    rig.animation_data.action = action
    rig.animation_data.action_slot = action.slots[0]
    frames = [1, 5, 9, 13, 17, 21]
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.cycles.seed = 42
    scene.cycles.use_denoising = False
    scene.render.resolution_x = scene.render.resolution_y = 128
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "Standard"
    height = 0.0
    for frame in frames:
        scene.frame_set(frame)
        deps = bpy.context.evaluated_depsgraph_get()
        for obj in scene.objects:
            if obj.type == "MESH":
                evaluated = obj.evaluated_get(deps)
                height = max(
                    height,
                    *(float((evaluated.matrix_world @ v.co).z) for v in evaluated.data.vertices),
                )
    scale = height / 0.75
    target = Vector((0, 0, 0.4 * scale))
    data = bpy.data.cameras.new("sprite_camera")
    data.type = "ORTHO"
    data.ortho_scale = scale
    camera = bpy.data.objects.new("sprite_camera", data)
    scene.collection.objects.link(camera)
    camera.location = target + Vector((1, -3, 0)) * scale * 2
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.world = bpy.data.worlds.new("sprite_world")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.4
    for material in bpy.data.materials:
        if "semantic_id" in material:
            color = list(material.diffuse_color)
            material.use_nodes = True
            node = material.node_tree.nodes.get("Principled BSDF")
            node.inputs["Base Color"].default_value = color
            node.inputs["Metallic"].default_value = material.metallic
            node.inputs["Roughness"].default_value = material.roughness
    for index, position in enumerate(((2, -3, 4), (-3, -1, 2))):
        light = bpy.data.lights.new("sprite_light_" + str(index), "AREA")
        light.energy = 150 * scale**2
        light.size = scale
        obj = bpy.data.objects.new(light.name, light)
        scene.collection.objects.link(obj)
        obj.location = target + Vector(position) * scale
        obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()
    samples = []
    for index, frame in enumerate(frames):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        pivot = project(scene, camera, Vector((0, 0, 0)))
        if abs(pivot.x - 0.5) > 0.0001 or abs(pivot.y - 0.1) > 0.0001:
            raise ValueError("Projected root pivot drift")
        path = output / f"frame-{index}.png"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        samples.append(
            {
                "index": index,
                "source_frame": frame,
                "pivot": [float(pivot.x), float(pivot.y)],
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "source.blend"), check_existing=False)
    (output / "bake.json").write_text(
        json.dumps(
            {
                "blender_version": bpy.app.version_string,
                "asset_id": job["asset_id"],
                "source_sha256": job["source_sha256"],
                "camera": {
                    "orthographic_scale": scale,
                    "position": list(camera.location),
                    "target": list(target),
                },
                "samples": samples,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1 :]
    run(json.loads(Path(args[0]).read_text("utf-8")), Path(args[1]))
