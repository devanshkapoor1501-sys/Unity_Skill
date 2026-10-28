"""Reviewed Blender S3 diagnostics, fixed camera audit and static FBX interchange."""

from __future__ import annotations

import importlib
import json
import math
from pathlib import Path
from typing import Any

VIEWS = ("front", "side", "top", "iso")
EXPORT_OPTIONS: dict[str, Any] = {
    "axis_forward": "-Z",
    "axis_up": "Y",
    "global_scale": 1.0,
    "apply_unit_scale": True,
    "apply_scale_options": "FBX_SCALE_UNITS",
    "bake_space_transform": False,
    "bake_anim": False,
    "use_selection": True,
    "use_custom_props": True,
    "object_types": ["EMPTY", "MESH"],
}


def diagnostics(recipe: dict[str, Any]) -> dict[str, Any]:
    bpy: Any = importlib.import_module("bpy")
    Vector: Any = importlib.import_module("mathutils").Vector
    bpy.context.view_layer.update()
    objects = {
        o.get("semantic_id"): o
        for o in bpy.context.scene.objects
        if o.get("polyforge_kind") == "module"
    }
    sockets = {
        o.get("semantic_id"): o
        for o in bpy.context.scene.objects
        if o.get("polyforge_kind") == "socket"
    }
    roots = [o for o in bpy.context.scene.objects if o.get("polyforge_kind") == "asset"]
    issues = []

    def issue(category: str, identifier: str, detail: str) -> None:
        issues.append(
            {
                "category": category,
                "module_id": identifier,
                "detail": detail,
                "origin": "recipe.modules" if identifier in objects else "recipe.sockets_or_export",
            }
        )

    for obj in [*objects.values(), *roots]:
        matrix = obj.matrix_world
        scale = matrix.to_scale()
        if any(not math.isfinite(n) or abs(n - 1) > 1e-5 for n in scale):
            issue(
                "nonuniform_scale",
                obj.get("semantic_id", "root"),
                "expected applied positive unit scale",
            )
        if any(
            abs(matrix.to_3x3()[i][j] - (1 if i == j else 0)) > 1e-5
            for i in range(3)
            for j in range(3)
        ):
            issue(
                "orientation",
                obj.get("semantic_id", "root"),
                "unexpected static rotation/scale matrix",
            )
        if obj.type == "ARMATURE" or any(mod.type == "ARMATURE" for mod in obj.modifiers):
            issue(
                "unsupported_rig",
                obj.get("semantic_id", "root"),
                "armatures excluded from static export",
            )
    for identifier, obj in objects.items():
        if obj.type != "MESH":
            issue("geometry", identifier, "semantic module is not a mesh")
            continue
        mesh = obj.data
        if not mesh.materials or any(material is None for material in mesh.materials):
            issue("material", identifier, "missing material assignment")
        if not mesh.uv_layers.active:
            issue("missing_uv", identifier, "UV layer absent")
        center = sum((v.co for v in mesh.vertices), Vector()) / max(1, len(mesh.vertices))
        if any(p.normal.dot(p.center - center) < -1e-7 for p in mesh.polygons):
            issue("reversed_normals", identifier, "inward face on supported convex primitive")
        if any(p.area <= 1e-12 for p in mesh.polygons):
            issue("degenerate_geometry", identifier, "collapsed face")
        module = next((m for m in recipe["modules"] if m["id"] == identifier), None)
        expected_parent = module.get("parent", recipe["asset_id"]) if module else None
        if obj.parent is None or obj.parent.get("semantic_id") != expected_parent:
            issue("binding", identifier, "module parent differs from recipe")
    for socket in recipe["sockets"]:
        obj = sockets.get(socket["id"])
        if (
            obj is None
            or obj.parent is None
            or obj.parent.get("semantic_id") != socket["module_id"]
        ):
            issue("absent_socket", socket["id"], "socket or parent binding absent")
    for obj in bpy.context.scene.objects:
        if obj.type == "ARMATURE" and obj not in objects.values():
            issue("unsupported_rig", obj.name, "static export refuses armatures")
    return {"status": "FAIL" if issues else "PASS", "issues": issues}


def render_views(output: Path, resolution: int) -> dict[str, Any]:
    bpy: Any = importlib.import_module("bpy")
    Vector: Any = importlib.import_module("mathutils").Vector
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 8
    scene.cycles.use_denoising = False
    scene.cycles.seed = 42
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.view_settings.view_transform = "Standard"
    scene.world = bpy.data.worlds.new("audit_world")
    scene.world.use_nodes = True
    scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.15, 0.15, 0.15, 1)
    scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.5
    meshes = [o for o in scene.objects if o.type == "MESH" and o.get("polyforge_kind") == "module"]
    points = [obj.matrix_world @ vertex.co for obj in meshes for vertex in obj.data.vertices]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    center = (low + high) / 2
    radius = (high - low).length
    for material in bpy.data.materials:
        if "semantic_id" not in material:
            continue
        color = list(material.diffuse_color)
        material.use_nodes = True
        node = material.node_tree.nodes.get("Principled BSDF")
        node.inputs["Base Color"].default_value = color
        node.inputs["Roughness"].default_value = material.roughness
        node.inputs["Metallic"].default_value = material.metallic
    for index, position in enumerate(((2, -3, 4), (-3, -1, 2), (1, 3, 3))):
        data = bpy.data.lights.new("audit_light_" + str(index), "AREA")
        data.energy = 150 * max(1, radius**2)
        data.shape = "DISK"
        data.size = max(1, radius)
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        obj.location = center + Vector(position) * radius
        obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()
    cameras = {}
    for name, direction in zip(VIEWS, ((0, -1, 0), (1, 0, 0), (0, 0, 1), (1, -1, 1)), strict=True):
        data = bpy.data.cameras.new("audit_" + name)
        data.type = "ORTHO"
        obj = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(obj)
        obj.location = center + Vector(direction).normalized() * radius * 3
        obj.rotation_euler = (center - obj.location).to_track_quat("-Z", "Y").to_euler()
        bpy.context.view_layer.update()
        inverse = obj.matrix_world.inverted()
        projected = [inverse @ p for p in points]
        extent = max(max(p[i] for p in projected) - min(p[i] for p in projected) for i in (0, 1))
        data.ortho_scale = extent * 1.2
        data.clip_start = max(0.0001, radius / 10000)
        data.clip_end = max(100, radius * 10)
        scene.camera = obj
        scene.render.filepath = str(output / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        cameras[name] = {
            "position_native_m": [round(n, 6) for n in obj.location],
            "target_native_m": [round(n, 6) for n in center],
            "ortho_scale": round(data.ortho_scale, 6),
            "resolution": resolution,
        }
    return cameras


def run(
    recipe: dict[str, Any], metrics: dict[str, Any], output: Path, resolution: int, measure: Any
) -> None:
    bpy: Any = importlib.import_module("bpy")
    result = diagnostics(recipe)
    if result["status"] != "PASS":
        (output / "diagnostics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
        raise RuntimeError("Static export preflight failed; see diagnostics.json")
    bpy.ops.object.select_all(action="DESELECT")
    selected = [
        o
        for o in bpy.context.scene.objects
        if o.get("polyforge_kind") in {"asset", "module", "socket"}
    ]
    for obj in selected:
        obj.select_set(True)
    options = dict(EXPORT_OPTIONS)
    options["object_types"] = set(options["object_types"])
    bpy.ops.export_scene.fbx(
        filepath=str(output / "asset.fbx"),
        check_existing=False,
        add_leaf_bones=False,
        path_mode="STRIP",
        **options,
    )
    materials = {
        "schema_version": "1.0.0",
        "asset_id": recipe["asset_id"],
        "shader_intent": "URP_LIT",
        "color_space": "LINEAR_RGBA",
        "materials": [
            {
                "id": m["id"],
                "base_color_rgba": list(bpy.data.materials[m["id"]].diffuse_color),
                "metallic": bpy.data.materials[m["id"]].metallic,
                "roughness": bpy.data.materials[m["id"]].roughness,
            }
            for m in recipe["materials"]
        ],
        "module_materials": {
            o["semantic_id"]: [m["semantic_id"] for m in o.data.materials]
            for o in selected
            if o.type == "MESH"
        },
    }
    (output / "material.json").write_text(json.dumps(materials, indent=2), encoding="utf-8")
    # Roundtrip is Blender evidence only. Unity importer axis handling remains Phase 5.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(
        filepath=str(output / "asset.fbx"), use_custom_props=True, use_anim=False
    )
    imported = measure(recipe)
    roundtrip = {
        "schema_version": "1.0.0",
        "status": "PASS",
        "verification_scope": "BLENDER_FBX_ROUNDTRIP",
        "unity_import_status": "NOT_RUN",
        "collider_validation_status": "NOT_RUN",
        "bounds_unity_m": imported["bounds_unity_m"],
        "socket_positions_unity_m": imported["socket_positions_unity_m"],
        "module_ids": imported["module_ids"],
        "material_ids": imported["material_ids"],
    }
    spec = importlib.util.spec_from_file_location(
        "polyforge_interchange", Path(__file__).with_name("interchange.py")
    )
    assert spec is not None and spec.loader is not None
    numeric = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(numeric)
    if imported["module_ids"] != metrics["module_ids"]:
        roundtrip["status"] = "FAIL"
    for key in ("bounds_unity_m", "socket_positions_unity_m"):
        if not numeric.coordinates_match(metrics[key], imported[key]):
            roundtrip["status"] = "FAIL"
    (output / "fbx_roundtrip.json").write_text(json.dumps(roundtrip, indent=2), encoding="utf-8")
    if roundtrip["status"] != "PASS":
        raise RuntimeError("FBX Blender roundtrip failed")
    bpy.ops.wm.open_mainfile(
        filepath=str(output / "source.blend"), load_ui=False, use_scripts=False
    )
    cameras = render_views(output, resolution)
    metadata = {
        "schema_version": "1.0.0",
        "asset_id": recipe["asset_id"],
        "geometry_digest": metrics["geometry_digest"],
        "diagnostics": result,
        "view_ids": list(VIEWS),
        "cameras": cameras,
        "export": EXPORT_OPTIONS,
        "material_ids": metrics["material_ids"],
        "socket_ids": metrics["socket_ids"],
        "visual_review_status": "REVIEW",
        "unity_import_status": "NOT_RUN",
        "source_basis": metrics["coordinate_basis"],
        "canonical_basis": {"up": "Y", "forward": "Z"},
        "meters_per_unit": metrics["meters_per_unit"],
        "unity_import_intent": {
            "global_scale": 1.0,
            "use_file_scale": True,
            "bake_axis_conversion": False,
        },
        "renderer": {"engine": "CYCLES", "device": "CPU", "samples": 8, "seed": 42},
    }
    (output / "audit_metadata.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8"
    )
    (output / "handoff.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "coordinate_basis": metrics["coordinate_basis"],
                "meters_per_unit": metrics["meters_per_unit"],
                "producer": "BLENDER_EXPORT",
                "objects": [
                    {
                        "id": "asset:" + recipe["asset_id"],
                        "bounds_m": metrics["bounds_m"],
                        "material_ids": metrics["material_ids"],
                        "socket_ids": metrics["socket_ids"],
                        "geometry_digest": metrics["geometry_digest"],
                        "socket_positions_unity_m": metrics["socket_positions_unity_m"],
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
