"""Fixed Blender tool for the public Phase 13 comparison and source inspection."""

from __future__ import annotations

import json
import math
import sys
from importlib import import_module
from pathlib import Path
from typing import Any


def build(bpy: Any, job: dict[str, Any]) -> None:
    output = Path.cwd()
    asset = job["asset_id"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1
    root = bpy.data.objects.new(asset, None)
    scene.collection.objects.link(root)
    materials = {}
    for name, color in (
        ("base", (0.34, 0.46, 0.58, 1)),
        ("trim", (0.18, 0.24, 0.30, 1)),
        ("accent", (0.90, 0.39, 0.13, 1)),
    ):
        material = bpy.data.materials.new(name)
        material.diffuse_color = color
        materials[name] = material

    def meshes(lod: bool) -> list[Any]:
        result = []
        for spec in job["modules"]:
            if spec["primitive"] == "box":
                bpy.ops.mesh.primitive_cube_add(size=1, calc_uvs=True)
            else:
                bpy.ops.mesh.primitive_cylinder_add(
                    vertices=16 if lod else 32, radius=0.5, depth=1, calc_uvs=True
                )
            obj = bpy.context.object
            obj.scale = spec["size"]
            bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
            obj.name = f"{asset}:module:{spec['id']}" if not lod else "lod_" + spec["id"]
            obj.location = spec["position"]
            obj.rotation_euler.z = math.radians(spec["rotation_z"])
            obj.parent = root
            obj.data.materials.append(materials[spec["material"]])
            result.append(obj)
        return result

    main = meshes(lod=False)
    lod_meshes = meshes(lod=True)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in lod_meshes:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = lod_meshes[0]
    bpy.ops.object.join()
    lod = bpy.context.object
    lod.name = asset + "_LOD1"
    sockets = []
    for spec in job["sockets"]:
        socket = bpy.data.objects.new(f"{asset}:socket:{spec['id']}", None)
        scene.collection.objects.link(socket)
        socket.parent = root
        socket.location = spec["position"]
        sockets.append(socket)

    def export(name: str, objects: list[Any]) -> None:
        bpy.ops.object.select_all(action="DESELECT")
        for obj in [root, *objects, *sockets]:
            obj.select_set(True)
        try:
            root.scale.x = -1 if job["reflect_export_x"] else 1
            bpy.context.view_layer.update()
            bpy.ops.export_scene.fbx(
                filepath=str(output / name),
                check_existing=False,
                use_selection=True,
                object_types={"MESH", "EMPTY"},
                add_leaf_bones=False,
                path_mode="STRIP",
                axis_forward="-Z",
                axis_up="Y",
                apply_unit_scale=True,
                global_scale=1,
                bake_anim=False,
            )
        finally:
            root.scale.x = 1
            bpy.context.view_layer.update()

    export("asset.fbx", main)
    export("lod.fbx", [lod])
    lod.hide_render = True
    lod.hide_set(True)
    vector = import_module("mathutils").Vector
    camera_data = bpy.data.cameras.new("technical_preview")
    camera = bpy.data.objects.new("technical_preview", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    center = sum((obj.location for obj in main), vector((0, 0, 0))) / len(main)
    span = max((obj.location - center).length + max(obj.dimensions) for obj in main)
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(2, span * 2.2)
    camera.location = center + vector((1, -1, 0.8)).normalized() * span * 3
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.color_type = "MATERIAL"
    scene.render.filepath = str(output / "preview.png")
    bpy.ops.render.render(write_still=True)
    scene.render.filepath = "//preview.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "source.blend"), check_existing=False)


def inspect(bpy: Any, rubric: dict[str, Any], source: Path) -> dict[str, Any]:
    bpy.ops.wm.open_mainfile(filepath=str(source))
    bmesh = import_module("bmesh")
    identifier = rubric["id"]
    failures = []
    modules = []
    sockets = []
    if bpy.context.scene.unit_settings.scale_length != 1:
        failures.append("Source meter scale differs")

    def unity(v: Any) -> tuple[float, float, float]:
        return v.x, v.z, -v.y

    for spec in rubric["modules"]:
        obj = bpy.data.objects.get(f"{identifier}:module:{spec['id']}")
        if obj is None or obj.type != "MESH":
            failures.append(f"Missing editable mesh {spec['id']}")
            continue
        vertices = [unity(obj.matrix_world @ v.co) for v in obj.data.vertices]
        if not vertices or not all(math.isfinite(x) for point in vertices for x in point):
            failures.append(f"No finite mesh vertices {spec['id']}")
            continue
        lo = [min(point[axis] for point in vertices) for axis in range(3)]
        hi = [max(point[axis] for point in vertices) for axis in range(3)]
        if any(
            abs(x - y) > 0.015
            for x, y in zip(lo + hi, spec["bounds_min"] + spec["bounds_max"], strict=True)
        ):
            failures.append(f"Source bounds differ for {spec['id']}")
        editable = bmesh.new()
        try:
            editable.from_mesh(obj.data)
            if not editable.faces or any(not edge.is_manifold for edge in editable.edges):
                failures.append(f"Source mesh is not closed for {spec['id']}")
        finally:
            editable.free()
        if not obj.data.uv_layers or not any(
            slot.name == spec["material"] for slot in obj.material_slots
        ):
            failures.append(f"Source UV or material differs for {spec['id']}")
        modules.append({"id": spec["id"], "bounds_min": lo, "bounds_max": hi})
    for spec in rubric["sockets"]:
        obj = bpy.data.objects.get(f"{identifier}:socket:{spec['id']}")
        if obj is None or obj.type != "EMPTY":
            failures.append(f"Missing editable socket {spec['id']}")
            continue
        position = unity(obj.matrix_world.translation)
        if math.dist(position, spec["position"]) > 0.005:
            failures.append(f"Source socket position differs for {spec['id']}")
        sockets.append({"id": spec["id"], "position": position})
    lod = bpy.data.objects.get(identifier + "_LOD1")
    if lod is None or lod.type != "MESH" or not lod.data.polygons:
        failures.append("Missing editable LOD1")
    return {
        "passed": not failures,
        "failures": failures,
        "modules": modules,
        "sockets": sockets,
        "blender_version": bpy.app.version_string,
    }


if __name__ == "__main__":
    native = import_module("bpy")
    mode, input_file, *extra = sys.argv[sys.argv.index("--") + 1 :]
    data = json.loads(Path(input_file).read_text(encoding="utf-8"))
    if mode == "build":
        build(native, data)
    elif mode == "inspect" and len(extra) == 1:
        Path("blender-inspection.json").write_text(
            json.dumps(inspect(native, data, Path(extra[0])), indent=2), encoding="utf-8"
        )
    else:
        raise ValueError("Expected a fixed build or inspect operation")
