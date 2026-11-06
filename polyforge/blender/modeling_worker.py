"""Fixed Blender modeling operations. Requests contain data, never executable code."""

from __future__ import annotations

import copy
import hashlib
import importlib
import json
import math
import sys
from pathlib import Path
from typing import Any


def native(values: list[float]) -> tuple[float, float, float]:
    return values[0], -values[2], values[1]


def grid_nodes(bpy: Any, obj: Any, spec: dict[str, Any]) -> None:
    group = bpy.data.node_groups.new(obj.name + "_geometry", "GeometryNodeTree")
    group.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    cube = group.nodes.new("GeometryNodeMeshCube")
    cube.inputs["Size"].default_value = (spec["size_m"][0], spec["size_m"][2], spec["size_m"][1])
    for key in ("Vertices X", "Vertices Y", "Vertices Z"):
        cube.inputs[key].default_value = spec.get("detail", 1) + 1
    uv = group.nodes.new("GeometryNodeStoreNamedAttribute")
    uv.domain = "CORNER"
    uv.data_type = "FLOAT2"
    uv.inputs["Name"].default_value = "UVMap"
    group.links.new(cube.outputs["Mesh"], uv.inputs["Geometry"])
    group.links.new(cube.outputs["UV Map"], uv.inputs["Value"])
    output = group.nodes.new("NodeGroupOutput")
    group.links.new(uv.outputs["Geometry"], output.inputs["Geometry"])
    modifier = obj.modifiers.new("polyforge_grid", "NODES")
    modifier.node_group = group


def primitive(bpy: Any, spec: dict[str, Any], *, lod: bool = False) -> Any:
    kind = spec["primitive"]
    if kind == "curve":
        curve = bpy.data.curves.new(spec["id"] + "_curve", "CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 1
        curve.bevel_depth = spec["bevel_m"]
        curve.bevel_resolution = 0 if lod else 1
        curve.use_fill_caps = True
        spline = curve.splines.new("POLY")
        spline.points.add(len(spec["points"]) - 1)
        for point, coordinates in zip(spline.points, spec["points"], strict=True):
            point.co = (*native(coordinates), 1)
        obj = bpy.data.objects.new(spec["id"], curve)
        bpy.context.collection.objects.link(obj)
        weld = obj.modifiers.new("polyforge_curve_weld", "WELD")
        weld.merge_threshold = 0.000001
        return obj
    if kind == "box":
        bpy.ops.mesh.primitive_cube_add(size=1, calc_uvs=True)
    elif kind == "sphere":
        bpy.ops.mesh.primitive_uv_sphere_add(
            segments=16 if lod else 32, ring_count=8 if lod else 16, radius=0.5, calc_uvs=True
        )
    elif kind == "cylinder":
        bpy.ops.mesh.primitive_cylinder_add(
            vertices=16 if lod else 32, radius=0.5, depth=1, calc_uvs=True
        )
    elif kind == "grid":
        mesh = bpy.data.meshes.new(spec["id"] + "_base")
        obj = bpy.data.objects.new(spec["id"], mesh)
        bpy.context.collection.objects.link(obj)
        grid_nodes(bpy, obj, spec)
        return obj
    else:
        raise ValueError("Unknown fixed modeling primitive")
    obj = bpy.context.object
    obj.scale = (spec["size_m"][0], spec["size_m"][2], spec["size_m"][1])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


def add_modifiers(obj: Any, spec: dict[str, Any], objects: dict[str, Any]) -> None:
    for index, operation in enumerate(spec["modifiers"]):
        kind = operation["type"]
        modifier = obj.modifiers.new(
            f"polyforge_{index}_{kind}",
            {
                "bevel": "BEVEL",
                "subdivision": "SUBSURF",
                "mirror": "MIRROR",
                "solidify": "SOLIDIFY",
                "boolean": "BOOLEAN",
            }[kind],
        )
        if kind == "bevel":
            modifier.width = operation["width_m"]
            modifier.segments = operation["segments"]
        elif kind == "subdivision":
            modifier.levels = modifier.render_levels = operation["levels"]
        elif kind == "mirror":
            axis = {0: 0, 1: 2, 2: 1}[operation["axis"]]
            modifier.use_axis = tuple(i == axis for i in range(3))
            modifier.use_bisect_axis = tuple(i == axis for i in range(3))
            modifier.use_clip = modifier.use_mirror_merge = True
        elif kind == "solidify":
            modifier.thickness = operation["thickness_m"]
        else:
            modifier.operation = operation["operation"]
            modifier.solver = "EXACT"
            modifier.object = objects[operation["target"]]


def mesh_copy(bpy: Any, obj: Any, graph: Any) -> Any:
    mesh = bpy.data.meshes.new_from_object(
        obj.evaluated_get(graph), preserve_all_data_layers=True, depsgraph=graph
    )
    duplicate = bpy.data.objects.new(obj.name + "_evaluated", mesh)
    bpy.context.collection.objects.link(duplicate)
    duplicate.matrix_world = obj.matrix_world.copy()
    for key in ("semantic_id", "polyforge_kind"):
        duplicate[key] = obj.get(key, "")
    return duplicate


def create_lod(bpy: Any, objects: dict[str, Any], root: Any, plan: dict[str, Any]) -> Any:
    vertices: list[Any] = []
    faces: list[Any] = []
    material_indices: list[int] = []
    materials: list[Any] = []
    proxies = []
    try:
        for original in plan["objects"]:
            if not original["export"]:
                continue
            spec = copy.deepcopy(original)
            if spec["primitive"] == "grid":
                spec["detail"] = 1
            modifiers = []
            for operation in spec["modifiers"]:
                if operation["type"] == "bevel":
                    continue
                if operation["type"] == "subdivision":
                    if operation["levels"] <= 1:
                        continue
                    operation["levels"] -= 1
                modifiers.append(operation)
            spec["modifiers"] = modifiers
            proxy = primitive(bpy, spec, lod=True)
            proxy.matrix_world = objects[spec["id"]].matrix_world.copy()
            proxy.data.materials.append(objects[spec["id"]].data.materials[0])
            add_modifiers(proxy, spec, objects)
            proxies.append(proxy)
        bpy.context.view_layer.update()
        graph = bpy.context.evaluated_depsgraph_get()
        for obj in proxies:
            evaluated = obj.evaluated_get(graph)
            mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=graph)
            try:
                offset = len(vertices)
                vertices.extend(tuple(obj.matrix_world @ vertex.co) for vertex in mesh.vertices)
                faces.extend([offset + i for i in face.vertices] for face in mesh.polygons)
                for face in mesh.polygons:
                    material = obj.data.materials[face.material_index]
                    if material not in materials:
                        materials.append(material)
                    material_indices.append(materials.index(material))
            finally:
                evaluated.to_mesh_clear()
    finally:
        for obj in proxies:
            bpy.data.objects.remove(obj, do_unlink=True)
    mesh = bpy.data.meshes.new("polyforge_lod_geometry")
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    lod = bpy.data.objects.new(plan["asset_id"] + "_LOD1", mesh)
    bpy.context.collection.objects.link(lod)
    lod.parent = root
    lod["polyforge_kind"] = "lod"
    lod["semantic_id"] = plan["asset_id"] + "_LOD1"
    lod["polyforge_lod_strategy"] = "LOWER_RESOLUTION_PRIMITIVES"
    for material in materials:
        mesh.materials.append(material)
    for face, index in zip(mesh.polygons, material_indices, strict=True):
        face.material_index = index
    bpy.ops.object.select_all(action="DESELECT")
    lod.select_set(True)
    bpy.context.view_layer.objects.active = lod
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.cube_project(cube_size=1)
    bpy.ops.object.mode_set(mode="OBJECT")
    lod.hide_render = True
    return lod


def export_copies(bpy: Any, selected: list[Any], path: Path, root: Any) -> None:
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    duplicates = [mesh_copy(bpy, obj, graph) for obj in selected]
    try:
        bpy.ops.object.select_all(action="DESELECT")
        root.select_set(True)
        for child in root.children:
            if child.get("polyforge_kind") == "socket":
                child.select_set(True)
        for obj in duplicates:
            obj.parent = root
            obj.select_set(True)
        bpy.context.view_layer.objects.active = duplicates[0]
        bpy.ops.export_scene.fbx(
            filepath=str(path),
            check_existing=False,
            use_selection=True,
            object_types={"MESH", "EMPTY"},
            use_mesh_modifiers=False,
            use_custom_props=True,
            add_leaf_bones=False,
            path_mode="STRIP",
            axis_forward="-Z",
            axis_up="Y",
            apply_unit_scale=True,
            global_scale=1.0,
            bake_anim=False,
        )
    finally:
        for obj in duplicates:
            mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            bpy.data.meshes.remove(mesh)


def render_views(bpy: Any, output: Path, plan: dict[str, Any], objects: dict[str, Any]) -> None:
    mathutils = importlib.import_module("mathutils")
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = scene.render.resolution_y = 256
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = True
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_shadows = True
    for spec in plan["objects"]:
        if not spec["export"]:
            objects[spec["id"]].hide_render = True
    camera_data = bpy.data.cameras.new("polyforge_audit_camera")
    camera = bpy.data.objects.new("polyforge_audit_camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(plan["size_m"]) * 1.9
    center = mathutils.Vector((0, 0, plan["size_m"][1] / 2))
    distance = max(plan["size_m"]) * 3
    for name, direction in {
        "front": (0, -1, 0),
        "side": (1, 0, 0),
        "top": (0, 0, 1),
        "iso": (1, -1, 0.8),
    }.items():
        camera.location = center + mathutils.Vector(direction).normalized() * distance
        camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(output / (name + ".png"))
        bpy.ops.render.render(write_still=True)


def run(job: dict[str, Any]) -> None:
    bpy: Any = importlib.import_module("bpy")
    mathutils: Any = importlib.import_module("mathutils")
    if tuple(bpy.app.version[:3]) != (5, 2, 2):
        raise ValueError("Modeling worker requires Blender 5.2.2")
    plan = job["plan"]
    output = Path(job["output_dir"])
    if not output.is_dir():
        raise ValueError("Owned output directory must already exist")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.unit_settings.system = "METRIC"
    bpy.context.scene.unit_settings.scale_length = 1
    bpy.context.scene["polyforge_plan_digest"] = plan["input_digest"]
    root = bpy.data.objects.new(plan["asset_id"], None)
    bpy.context.collection.objects.link(root)
    root["semantic_id"] = plan["asset_id"]
    root["polyforge_kind"] = "root"
    materials = {}
    for spec in plan["materials"]:
        material = bpy.data.materials.new(spec["id"])
        material.diffuse_color = spec["color_rgba"]
        material["semantic_id"] = spec["id"]
        material.use_fake_user = True
        materials[spec["id"]] = material
    basis = mathutils.Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
    objects = {}
    for spec in plan["objects"]:
        obj = primitive(bpy, spec)
        obj.name = plan["asset_id"] + ":module:" + spec["id"]
        obj["semantic_id"] = spec["id"]
        obj["polyforge_kind"] = "module"
        obj["polyforge_primitive"] = spec["primitive"]
        obj["polyforge_export"] = spec["export"]
        obj.parent = root
        obj.location = native(spec["location"])
        rotation = mathutils.Euler([math.radians(v) for v in spec["rotation_deg"]], "XYZ")
        obj.rotation_euler = (basis @ rotation.to_matrix() @ basis.inverted()).to_euler("XYZ")
        obj.data.materials.append(materials[spec["material_id"]])
        objects[spec["id"]] = obj
    for spec in plan["objects"]:
        add_modifiers(objects[spec["id"]], spec, objects)
    for spec in plan["sockets"]:
        socket = bpy.data.objects.new(plan["asset_id"] + ":socket:" + spec["id"], None)
        bpy.context.collection.objects.link(socket)
        socket.parent = root
        socket.location = native(spec["position"])
        socket["semantic_id"] = spec["id"]
        socket["polyforge_kind"] = "socket"
    bpy.context.view_layer.update()
    exported = [objects[s["id"]] for s in plan["objects"] if s["export"]]
    lod = create_lod(bpy, objects, root, plan)
    export_copies(bpy, exported, output / "asset.fbx", root)
    export_copies(bpy, [lod], output / "lod.fbx", root)
    render_views(bpy, output, plan, objects)
    bpy.context.scene.render.filepath = "//audit.png"
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "source.blend"), check_existing=False)
    provenance = {
        "schema_version": "1.0.0",
        "asset_id": plan["asset_id"],
        "input_digest": plan["input_digest"],
        "tool_version": ".".join(str(number) for number in bpy.app.version[:3]),
        "editable_source": "source.blend",
        "source_sha256": hashlib.sha256((output / "source.blend").read_bytes()).hexdigest(),
        "export_policy": "EVALUATED_COPIES_SOURCE_MODIFIERS_PRESERVED",
        "coordinate_basis": {"up": "Z", "forward": "-Y", "meters_per_unit": 1},
        "artistic_status": "REVIEW",
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")


if __name__ == "__main__":
    supplied = sys.argv[sys.argv.index("--") + 1 :]
    if len(supplied) != 1:
        raise ValueError("Expected one engine-owned modeling job")
    run(json.loads(Path(supplied[0]).read_text(encoding="utf-8")))
