"""Independent binding variants and corrupt evidence must override a worker PASS."""

import copy

import pytest
from test_audit_unity_gaps import complete_native

from polyforge.unity.evidence import reconcile_report


def assert_rejected(request, report, category):
    assert report["status"] == "PASS"
    result = reconcile_report(request, report)
    assert result["status"] == "FAIL", result
    assert any(issue["category"] == category for issue in result["issues"]), result


def mesh_native():
    request, report = complete_native()
    asset, actual = request["assets"][0], report["objects"][0]
    asset["collider"] = actual["collider"] = "mesh"
    asset["modules"].append({"id": "head"})
    actual["nodes"][1].update(mesh_guid="a" * 32, mesh_local_id=300)
    actual["nodes"].append(
        dict(
            id="head",
            kind="module",
            path="model/head",
            guid="a" * 32,
            local_id=125,
            component="MeshRenderer",
            mesh_guid="a" * 32,
            mesh_local_id=400,
        )
    )
    actual["transform_count"] = 5
    report["scene_object_count"] = 26
    actual["colliders"] = [
        dict(
            kind="MeshCollider",
            path=path,
            enabled=True,
            is_trigger=False,
            mesh_guid="a" * 32,
            mesh_local_id=local_id,
            convex=False,
        )
        for path, local_id in (("model/head", 400), ("model/body", 300))
    ]
    return request, report


def normal_native():
    request, report = complete_native()
    path = "Assets/PolyForgeGenerated/Textures/robot/blue/normal.png"
    request["assets"][0]["materials"][0]["textures"] = [
        dict(kind="normal", path=path, sha256="d" * 64)
    ]
    slots = report["objects"][0]["textures"]
    slots[0]["normal_keyword"] = True
    slots[1].update(
        path=path,
        sha256="d" * 64,
        srgb=False,
        texture_type="NormalMap",
        material_texture_path=path,
        has_texture=True,
        normal_keyword=True,
        convert_to_normal=False,
    )
    return request, report


def test_none_collider_accepts_an_empty_observation_but_rejects_a_hidden_solid():
    request, report = complete_native()
    solid = report["objects"][0]["colliders"][0]
    request["assets"][0]["collider"] = "none"
    report["objects"][0].update(collider="none", colliders=[])
    assert reconcile_report(request, report)["status"] == "PASS"
    report["objects"][0]["colliders"].append(solid)
    assert_rejected(request, report, "collider")


@pytest.mark.parametrize(
    "field,value",
    [("center_m", [0, 2, 0]), ("size_m", [4, 4, 4]), ("size_m", [2, 6, 2]), ("direction", True)],
)
def test_tall_capsule_requires_fitted_y_height_and_horizontal_diameter(field, value):
    request, report = complete_native()
    request["assets"][0].update(collider="capsule", bounds_m=[2, 6, 4])
    actual = report["objects"][0]
    actual.update(collider="capsule", bounds_m=[2, 6, 4])
    actual["colliders"][0].update(
        kind="CapsuleCollider", center_m=[0, 3, 0], size_m=[4, 6, 4], direction=1
    )
    assert reconcile_report(request, report)["status"] == "PASS"
    actual["colliders"][0][field] = value
    assert_rejected(request, report, "collider")


def test_each_mesh_module_accepts_its_own_reference_in_any_observation_order():
    request, report = mesh_native()
    assert reconcile_report(request, report)["status"] == "PASS"
    report["objects"][0]["colliders"].reverse()
    assert reconcile_report(request, report)["status"] == "PASS"


@pytest.mark.parametrize(
    "field,value",
    [
        ("path", "model/front"),
        ("path", "model/missing"),
        ("convex", True),
        ("kind", "BoxCollider"),
        ("enabled", False),
        ("is_trigger", True),
        ("mesh_guid", "b" * 32),
        ("mesh_local_id", 0),
        ("mesh_local_id", True),
    ],
)
def test_mesh_reference_must_be_enabled_solid_and_bound_to_its_module(field, value):
    request, report = mesh_native()
    assert reconcile_report(request, report)["status"] == "PASS"
    report["objects"][0]["colliders"][0][field] = value
    assert_rejected(request, report, "collider")


@pytest.mark.parametrize("damage", ["missing-module", "duplicate-module", "forged-source"])
def test_mesh_collider_coverage_cannot_be_faked_by_count_or_self_consistent_foreign_guid(damage):
    request, report = mesh_native()
    actual = report["objects"][0]
    if damage == "missing-module":
        actual["colliders"].pop()
    elif damage == "duplicate-module":
        actual["colliders"][1] = copy.deepcopy(actual["colliders"][0])
    else:
        actual["nodes"][-1]["mesh_guid"] = "c" * 32
        actual["colliders"][0]["mesh_guid"] = "c" * 32
    assert_rejected(request, report, "collider")


@pytest.mark.parametrize("bounds", [[2, 5, 6], [1.5, 5, 5]])
def test_ground_geometry_is_lowered_below_the_floor_in_both_scenes_without_moving_actors(bounds):
    request, report = complete_native()
    request["scene_bounds_m"] = bounds
    for instance in report["scene_instances"]:
        if instance["id"] == "asset:robot":
            instance["position_m"] = [0, -2, 0]
    assert reconcile_report(request, report)["status"] == "PASS"
    report["scene_instances"][2]["position_m"] = [0, 0, 0]
    assert_rejected(request, report, "scene_instance")


@pytest.mark.parametrize("bounds", [[2, 5, 6.1], [2.1, 5, 6]])
def test_a_single_wide_axis_does_not_make_an_asset_ground(bounds):
    request, report = complete_native()
    request["scene_bounds_m"] = bounds
    assert reconcile_report(request, report)["status"] == "PASS"
    report["scene_instances"][0]["position_m"] = [0, -2, 0]
    assert_rejected(request, report, "scene_instance")


def test_second_asset_is_spaced_in_opposite_directions_in_arena_and_training():
    request, report = complete_native()
    asset = copy.deepcopy(request["assets"][0])
    asset["id"] = "crate"
    request["assets"].append(asset)
    observed = copy.deepcopy(report["objects"][0])
    observed.update(id="crate", prefab_id="Assets/PolyForgeGenerated/Prefabs/crate.prefab")
    report["objects"].append(observed)
    report["scene_object_count"] = 30
    for scene, position in (("Arena", [2, 0, 0]), ("Training", [-2, 0, 0])):
        instance = copy.deepcopy(report["scene_instances"][0])
        instance.update(scene=scene, id="asset:crate", asset_id="crate", position_m=position)
        report["scene_instances"].append(instance)
    assert reconcile_report(request, report)["status"] == "PASS"
    report["scene_instances"][-1]["position_m"] = [2, 0, 0]
    assert_rejected(request, report, "scene_instance")


@pytest.mark.parametrize(
    "field,value",
    [
        ("srgb", True),
        ("texture_type", "Default"),
        ("convert_to_normal", True),
        ("normal_keyword", False),
        ("has_texture", False),
        ("sha256", "e" * 64),
        ("material_texture_path", "Assets/Unrelated.png"),
    ],
)
def test_normal_only_material_requires_native_normal_import_and_material_binding(field, value):
    request, report = normal_native()
    assert reconcile_report(request, report)["status"] == "PASS"
    report["objects"][0]["textures"][1][field] = value
    assert_rejected(request, report, "texture")


def test_material_normal_keyword_is_required_even_on_the_empty_base_color_slot():
    request, report = normal_native()
    assert reconcile_report(request, report)["status"] == "PASS"
    report["objects"][0]["textures"][0]["normal_keyword"] = False
    assert_rejected(request, report, "texture")


@pytest.mark.parametrize("damage", ["duplicate", "unknown-material", "unknown-role", "missing"])
def test_texture_evidence_requires_each_material_role_exactly_once(damage):
    request, report = normal_native()
    slots = report["objects"][0]["textures"]
    if damage == "duplicate":
        slots.append(copy.deepcopy(slots[1]))
    elif damage == "unknown-material":
        slots[1]["material_id"] = "unrelated"
    elif damage == "unknown-role":
        slots[1]["kind"] = "roughness"
    else:
        slots.pop()
    assert_rejected(request, report, "texture")


@pytest.mark.parametrize("damage", ["duplicate", "missing", "malformed-pose", "bad-quaternion"])
def test_scene_evidence_requires_unique_instances_and_well_formed_poses(damage):
    request, report = complete_native()
    instances = report["scene_instances"]
    if damage == "duplicate":
        instances.append(copy.deepcopy(instances[0]))
    elif damage == "missing":
        instances.pop()
    elif damage == "malformed-pose":
        instances[0]["position_m"] = [0, 0]
    else:
        instances[0]["rotation_xyzw"] = [0, 0, 0, 2]
    assert_rejected(request, report, "scene_instance")


@pytest.mark.parametrize("field", ["textures", "colliders", "scene_instances"])
def test_missing_native_binding_sections_fail_closed(field):
    request, report = complete_native()
    container = report if field == "scene_instances" else report["objects"][0]
    del container[field]
    assert_rejected(request, report, "texture" if field == "textures" else "contract")


@pytest.mark.parametrize("field", ["mesh_guid", "mesh_local_id", "convex"])
def test_missing_mesh_reference_details_fail_closed(field):
    request, report = mesh_native()
    del report["objects"][0]["colliders"][0][field]
    assert_rejected(request, report, "contract")


def test_duplicate_semantic_socket_observations_are_not_collapsed_into_a_valid_graph():
    request, report = complete_native()
    actual = report["objects"][0]
    actual["sockets"].append(copy.deepcopy(actual["sockets"][0]))
    assert_rejected(request, report, "socket")
