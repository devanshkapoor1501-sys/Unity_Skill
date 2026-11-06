"""Independent report validation rejects geometry and source contract violations."""

from copy import deepcopy

import pytest

from polyforge.blender.modeling_inspection import validate_modeling_report
from polyforge.contracts.validation import InputError


def fixture():
    plan = {
        "schema_version": "1.0.0",
        "asset_id": "part",
        "input_digest": "a" * 64,
        "size_m": [2, 2, 2],
        "max_polygons": 500,
        "expected_bounds": True,
        "lod_ratio": 0.5,
        "overlap_policy": "DISALLOW",
        "materials": [{"id": "base", "color_rgba": [1, 0, 0, 1]}],
        "objects": [
            {
                "id": "body",
                "primitive": "box",
                "size_m": [2, 2, 2],
                "location": [0, 1, 0],
                "rotation_deg": [0, 0, 0],
                "material_id": "base",
                "export": True,
                "modifiers": [],
            }
        ],
        "sockets": [{"id": "top", "position": [0, 2, 0]}],
    }
    report = {
        "schema_version": "1.0.0",
        "asset_id": "part",
        "input_digest": "a" * 64,
        "technical_status": "PASS",
        "artistic_status": "REVIEW",
        "source_unchanged": True,
        "source_sha256_before": "b" * 64,
        "source_sha256_after": "b" * 64,
        "coordinate_basis": {"up": "Z", "forward": "-Y", "meters_per_unit": 1.0},
        "root": {
            "semantic_id": "part",
            "location_unity": [0, 0, 0],
            "rotation_deg": [0, 0, 0],
            "scale": [1, 1, 1],
        },
        "materials": [{"id": "base", "color_rgba": [1, 0, 0, 1]}],
        "objects": [
            {
                "id": "body",
                "parent_id": "part",
                "primitive": "box",
                "export": True,
                "material_ids": ["base"],
                "location_unity": [0, 1, 0],
                "rotation_deg": [0, 0, 0],
                "scale": [1, 1, 1],
                "modifiers": [],
                "modifiers_enabled": True,
                "source_geometry": {"size_m": [2, 2, 2]},
                "invalid_material_faces": 0,
                "vertices": 8,
                "polygons": 6,
                "triangles": 12,
                "nonmanifold_edges": 0,
                "degenerate_faces": 0,
                "nonfinite_values": 0,
                "normal_inconsistencies": 0,
                "signed_volume": 8.0,
                "uv_layers": 1,
                "uv_nonfinite_values": 0,
                "bounds_min_unity": [-1, 0, -1],
                "bounds_max_unity": [1, 2, 1],
            }
        ],
        "sockets": [{"id": "top", "parent_id": "part", "position_unity": [0, 2, 0]}],
        "aggregate": {
            "vertices": 8,
            "polygons": 6,
            "triangles": 12,
            "bounds_min_unity": [-1, 0, -1],
            "bounds_max_unity": [1, 2, 1],
        },
        "issues": [],
        "lod": {
            "polygons": 3,
            "source_polygons": 6,
            "ratio": 0.5,
            "nonmanifold_edges": 0,
            "degenerate_faces": 0,
            "nonfinite_values": 0,
            "normal_inconsistencies": 0,
            "signed_volume": 4.0,
        },
    }
    return plan, report


def test_valid_independently_observed_report_preserves_pending_artistic_review():
    plan, report = fixture()
    before = deepcopy(report)
    assert validate_modeling_report(plan, report) is None
    assert report == before


@pytest.mark.parametrize(
    "path,value",
    [
        (("schema_version",), "2.0.0"),
        (("asset_id",), "other"),
        (("input_digest",), "c" * 64),
        (("technical_status",), "FAIL"),
        (("artistic_status",), "PASS"),
        (("source_unchanged",), False),
        (("source_sha256_before",), "invalid"),
        (("source_sha256_after",), "c" * 64),
        (("issues",), ["observed failure"]),
        (("coordinate_basis", "forward"), "Y"),
        (("coordinate_basis", "meters_per_unit"), True),
        (("root", "semantic_id"), "wrong"),
        (("root", "location_unity"), [0, 1, 0]),
        (("root", "rotation_deg"), [0, 0, 90]),
        (("root", "scale"), [1, -1, 1]),
        (("objects", 0, "parent_id"), "wrong"),
        (("objects", 0, "primitive"), "sphere"),
        (("objects", 0, "export"), 1),
        (("objects", 0, "material_ids"), ["other"]),
        (("objects", 0, "location_unity"), [0, 1.5, 0]),
        (("objects", 0, "rotation_deg"), [0, 180, 0]),
        (("objects", 0, "scale"), [2, 1, 1]),
        (("objects", 0, "modifiers_enabled"), False),
        (("objects", 0, "nonmanifold_edges"), 1),
        (("objects", 0, "degenerate_faces"), 1),
        (("objects", 0, "nonfinite_values"), 1),
        (("objects", 0, "normal_inconsistencies"), 1),
        (("objects", 0, "invalid_material_faces"), 1),
        (("objects", 0, "uv_nonfinite_values"), 1),
        (("objects", 0, "signed_volume"), -8),
        (("objects", 0, "uv_layers"), 0),
        (("objects", 0, "vertices"), True),
        (("objects", 0, "polygons"), -1),
        (("objects", 0, "triangles"), 10_000_001),
        (("objects", 0, "bounds_min_unity"), [1, 0, -1]),
        (("aggregate", "polygons"), 7),
        (("aggregate", "bounds_min_unity"), [-2, 0, -1]),
        (("sockets", 0, "position_unity"), [0, 1, 0]),
        (("sockets", 0, "parent_id"), "wrong"),
        (("materials", 0, "color_rgba"), [0, 0, 0, 1]),
        (("lod", "polygons"), 6),
        (("lod", "source_polygons"), 12),
        (("lod", "ratio"), 0.1),
    ],
)
def test_corrupt_geometry_bindings_and_source_evidence_are_rejected(path, value):
    plan, report = fixture()
    target = report
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(InputError):
        validate_modeling_report(plan, report)


@pytest.mark.parametrize("value", [None, [], "PASS", 3, {}])
def test_missing_or_nonobject_report_never_passes(value):
    plan, _ = fixture()
    with pytest.raises(InputError):
        validate_modeling_report(plan, value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf"), True, "1", 1e20])
def test_nonfinite_untyped_and_unbounded_measurements_are_rejected(value):
    plan, report = fixture()
    report["objects"][0]["signed_volume"] = value
    with pytest.raises(InputError):
        validate_modeling_report(plan, report)


@pytest.mark.parametrize("inventory", ["objects", "materials", "sockets"])
def test_duplicate_or_missing_semantic_inventory_is_rejected(inventory):
    plan, report = fixture()
    report[inventory].append(deepcopy(report[inventory][0]))
    with pytest.raises(InputError):
        validate_modeling_report(plan, report)
    report[inventory] = []
    with pytest.raises(InputError):
        validate_modeling_report(plan, report)


@pytest.mark.parametrize(
    "modifier",
    [
        {"type": "bevel", "width_m": 0.1, "segments": 2},
        {"type": "subdivision", "levels": 1},
        {"type": "mirror", "axis": 0},
        {"type": "solidify", "thickness_m": 0.1},
        {"type": "boolean", "target": "cut", "operation": "DIFFERENCE"},
    ],
)
def test_editable_modifier_chain_is_compared_to_requested_operations(modifier):
    plan, report = fixture()
    plan["objects"][0]["modifiers"] = [modifier]
    report["objects"][0]["modifiers"] = [deepcopy(modifier)]
    validate_modeling_report(plan, report)
    report["objects"][0]["modifiers"] = []
    with pytest.raises(InputError, match="modifier"):
        validate_modeling_report(plan, report)


def test_altered_modifier_parameter_and_boolean_target_fail_independent_validation():
    plan, report = fixture()
    plan["objects"][0]["modifiers"] = [{"type": "bevel", "width_m": 0.1, "segments": 2}]
    report["objects"][0]["modifiers"] = [{"type": "bevel", "width_m": 0.2, "segments": 2}]
    with pytest.raises(InputError, match="parameters"):
        validate_modeling_report(plan, report)
    plan["objects"][0]["modifiers"] = [
        {"type": "boolean", "target": "cut", "operation": "DIFFERENCE"}
    ]
    report["objects"][0]["modifiers"] = [
        {"type": "boolean", "target": "wrong", "operation": "DIFFERENCE"}
    ]
    with pytest.raises(InputError, match="binding"):
        validate_modeling_report(plan, report)


def test_polygon_budget_and_declared_envelope_are_enforced():
    plan, report = fixture()
    plan["max_polygons"] = 5
    with pytest.raises(InputError, match="budget"):
        validate_modeling_report(plan, report)
    plan["max_polygons"] = 500
    report["objects"][0]["bounds_max_unity"][1] = 3
    report["aggregate"]["bounds_max_unity"][1] = 3
    with pytest.raises(InputError, match="envelope"):
        validate_modeling_report(plan, report)


def test_composition_may_underfill_its_envelope_when_requested():
    plan, report = fixture()
    plan["expected_bounds"] = False
    plan["size_m"] = [3, 3, 3]
    validate_modeling_report(plan, report)
    plan["expected_bounds"] = True
    with pytest.raises(InputError):
        validate_modeling_report(plan, report)


@pytest.mark.parametrize(
    "primitive,implicit",
    [
        ("grid", {"type": "geometry_nodes", "detail": 2}),
        ("curve", {"type": "weld", "merge_threshold_m": 0.000001}),
    ],
)
def test_procedural_native_operations_remain_observed_and_editable(primitive, implicit):
    plan, report = fixture()
    plan["objects"][0].update(primitive=primitive, detail=2)
    report["objects"][0].update(primitive=primitive, modifiers=[implicit])
    if primitive == "curve":
        plan["objects"][0].update(points=[[-1, 0, 0], [1, 0, 0]], bevel_m=0.1)
        report["objects"][0]["source_geometry"] = {
            "points": [[-1, 0, 0], [1, 0, 0]],
            "bevel_m": 0.1,
            "closed_caps": True,
            "spline_type": "POLY",
        }
    validate_modeling_report(plan, report)
    report["objects"][0]["modifiers"] = []
    with pytest.raises(InputError):
        validate_modeling_report(plan, report)


def test_disallowed_object_intersections_fail_but_declared_assembly_contacts_are_scoped():
    plan, report = fixture()
    part, observed = deepcopy(plan["objects"][0]), deepcopy(report["objects"][0])
    part["id"] = observed["id"] = "overlap"
    plan["objects"].append(part)
    report["objects"].append(observed)
    report["aggregate"].update(vertices=16, polygons=12, triangles=24)
    report["lod"].update(source_polygons=12, polygons=6)
    with pytest.raises(InputError, match="overlap"):
        validate_modeling_report(plan, report)
    plan["overlap_policy"] = "ASSEMBLY_CONTACTS"
    validate_modeling_report(plan, report)


@pytest.mark.parametrize(
    "key,value",
    [
        ("nonmanifold_edges", 1),
        ("nonfinite_values", 1),
        ("normal_inconsistencies", 1),
        ("signed_volume", -1),
    ],
)
def test_reduced_lod_must_preserve_valid_geometry(key, value):
    plan, report = fixture()
    report["lod"][key] = value
    with pytest.raises(InputError):
        validate_modeling_report(plan, report)


def test_native_observations_do_not_accept_missing_or_untyped_modifier_descriptors():
    plan, report = fixture()
    plan["objects"][0]["modifiers"] = [{"type": "bevel", "width_m": 0.1, "segments": 2}]
    report["objects"][0]["modifiers"] = [{"type": "bevel", "width_m": 0.1, "segments": 2.0}]
    with pytest.raises(InputError):
        validate_modeling_report(plan, report)


def test_interior_component_source_dimensions_cannot_hide_behind_aggregate_bounds():
    plan, report = fixture()
    report["objects"][0]["source_geometry"]["size_m"] = [1, 2, 2]
    with pytest.raises(InputError):
        validate_modeling_report(plan, report)
