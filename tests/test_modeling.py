"""Typed modeling plans preserve geometry intent before native execution."""

import copy

import pytest

from polyforge.contracts.validation import InputError, canonical_digest


def request(size=None, **controls):
    return {
        "schema_version": "1.0.0",
        "asset_id": "example_asset",
        "parameters": {"size_m": size or [4.0, 3.0, 5.0], **controls},
    }


@pytest.mark.parametrize("kind", ["room_kit", "vehicle", "mechanical_prop", "organic"])
def test_family_plans_are_deterministic_parameterized_and_preserve_input(kind):
    from polyforge.blender.modeling import MODELING_CAPABILITIES, compile_modeling

    value = request(detail=2)
    unchanged = copy.deepcopy(value)
    plan = compile_modeling(kind, value, seed=42)
    assert len(MODELING_CAPABILITIES) == 5 and kind in MODELING_CAPABILITIES
    assert plan == compile_modeling(kind, value, seed=42)
    assert value == unchanged
    assert plan["workflow"] == kind and plan["asset_id"] == value["asset_id"]
    assert plan["size_m"] == value["parameters"]["size_m"]
    assert plan["expected_bounds"] is True
    assert plan["objects"] and plan["materials"] and plan["sockets"]
    assert len({o["id"] for o in plan["objects"]}) == len(plan["objects"])
    required = {
        "id",
        "primitive",
        "size_m",
        "location",
        "rotation_deg",
        "material_id",
        "export",
        "modifiers",
    }
    assert all(required <= obj.keys() for obj in plan["objects"])
    changed = compile_modeling(kind, request([6.0, 4.0, 8.0], detail=3))
    assert plan["objects"] != changed["objects"]
    assert plan["input_digest"] != changed["input_digest"]
    assert canonical_digest(plan) == canonical_digest(compile_modeling(kind, value))


def object_spec(identifier="main", primitive="box", **changes):
    return {
        "id": identifier,
        "primitive": primitive,
        "size_m": [2.0, 1.0, 2.0],
        "location": [0.0, 0.5, 0.0],
        "rotation_deg": [0.0, 0.0, 0.0],
        "material_id": "base",
        "export": True,
        "modifiers": [],
        **changes,
    }


def composition(*objects, **changes):
    return {**request(), "objects": list(objects) or [object_spec()], **changes}


@pytest.mark.parametrize("kind", ["room_kit", "vehicle", "mechanical_prop", "organic"])
def test_family_size_envelopes_budget_and_parameter_effects(kind):
    from polyforge.blender.modeling import compile_modeling

    small = compile_modeling(kind, request(detail=1))
    detailed = compile_modeling(kind, request(detail=3, max_polygons=100000, lod_ratio=0.4))
    assert detailed["lod_ratio"] == 0.4 and detailed["max_polygons"] == 100000
    assert 0 < small["estimated_polygons"] < detailed["estimated_polygons"] <= 100000
    assert len(detailed["objects"]) > len(small["objects"])
    assert all(socket["position"][1] >= 0 for socket in detailed["sockets"])


def test_composition_combines_unfamiliar_operations_with_editable_modifiers():
    from polyforge.blender.modeling import compile_modeling

    objects = [
        object_spec(
            "shell",
            modifiers=[
                {"type": "mirror", "axis": 0},
                {"type": "bevel", "width_m": 0.03, "segments": 2},
            ],
        ),
        object_spec("procedural", "grid", size_m=[0.5, 0.5, 0.5], location=[1.5, 0.3, 0], detail=3),
        object_spec(
            "wire",
            "curve",
            size_m=[1, 1, 1],
            location=[0, 1.4, 0],
            points=[[-0.4, 0, 0], [0, 0.4, 0.2], [0.4, 0, 0]],
            bevel_m=0.02,
        ),
    ]
    value = composition(
        *objects,
        sockets=[{"id": "grip", "position": [0, 1.5, 0]}],
        expected_bounds=False,
        overlap_policy="DISALLOW",
    )
    before = copy.deepcopy(value)
    plan = compile_modeling("compose", value)
    assert plan["objects"] == objects and plan["sockets"] == value["sockets"]
    assert plan["expected_bounds"] is False and plan["overlap_policy"] == "DISALLOW"
    assert plan["estimated_polygons"] < plan["max_polygons"]
    plan["objects"][0]["modifiers"].clear()
    assert value == before


@pytest.mark.parametrize(
    "edit",
    [
        lambda r: r.update(python="exec('arbitrary')"),
        lambda r: r.update(schema_version="1.1.0"),
        lambda r: r.update(asset_id="../outside"),
        lambda r: r.update(asset_id="asset_" + "a" * 49),
        lambda r: r["parameters"].update(unknown=True),
        lambda r: r["parameters"].update(size_m=[1, 1]),
        lambda r: r["parameters"].update(size_m=[True, 2, 3]),
        lambda r: r["parameters"].update(size_m=[1, float("nan"), 3]),
        lambda r: r["parameters"].update(size_m=[1, float("inf"), 3]),
        lambda r: r["parameters"].update(size_m=[0.049, 2, 3]),
        lambda r: r["parameters"].update(detail=True),
        lambda r: r["parameters"].update(detail=1.0),
        lambda r: r["parameters"].update(max_polygons=500.0),
        lambda r: r["parameters"].update(max_polygons=499),
        lambda r: r["parameters"].update(max_polygons=100001),
        lambda r: r["parameters"].update(lod_ratio=0.9),
        lambda r: r["parameters"].update(lod_ratio=True),
        lambda r: r["parameters"].update(wall_thickness_m=2),
    ],
)
def test_invalid_family_requests_fail_before_any_native_execution(edit):
    from polyforge.blender.modeling import compile_modeling

    value = request()
    edit(value)
    with pytest.raises(InputError):
        compile_modeling("room_kit", value)


@pytest.mark.parametrize(
    "kind,seed",
    [
        ("unknown", 42),
        ([], 42),
        ("vehicle", True),
        ("vehicle", -1),
        ("organic", 2**32),
        ("room_kit", 1.0),
    ],
)
def test_invalid_workflow_or_seed_is_structured_input_error(kind, seed):
    from polyforge.blender.modeling import compile_modeling

    with pytest.raises(InputError):
        compile_modeling(kind, request(), seed=seed)


@pytest.mark.parametrize(
    "edit",
    [
        lambda r: r["objects"].append(copy.deepcopy(r["objects"][0])),
        lambda r: r["objects"][0].update(material_id="missing"),
        lambda r: r["objects"][0].update(export=False),
        lambda r: r["objects"][0].update(size_m=[0, 1, 1]),
        lambda r: r["objects"][0].update(location=[0, -0.1, 0]),
        lambda r: r["objects"][0].update(rotation_deg=[0, 0, float("nan")]),
        lambda r: r["objects"][0].update(points=[[0, 0, 0], [1, 0, 0]]),
        lambda r: r["objects"][0].update(detail=2),
        lambda r: r.update(sockets=[{"id": "same", "position": [0, 0, 0]}] * 2),
        lambda r: r.update(sockets=[{"id": "outside", "position": [0, 4, 0]}]),
        lambda r: r["objects"][0]["modifiers"].append(
            {"type": "boolean", "target": "missing", "operation": "UNION"}
        ),
        lambda r: r["objects"][0]["modifiers"].append(
            {"type": "boolean", "target": "main", "operation": "DIFFERENCE"}
        ),
        lambda r: r["objects"][0]["modifiers"].append(
            {"type": "bevel", "width_m": 0.6, "segments": 2}
        ),
        lambda r: r["objects"][0]["modifiers"].append({"type": "subdivision", "levels": 2.0}),
        lambda r: r.update(objects=r["objects"] * 33),
        lambda r: r.update(overlap_policy="WHATEVER"),
    ],
)
def test_composition_invalid_geometry_links_and_resource_bombs_rejected(edit):
    from polyforge.blender.modeling import compile_modeling

    value = composition()
    edit(value)
    with pytest.raises(InputError):
        compile_modeling("compose", value)


def test_boolean_dependencies_cannot_form_cycle_and_budget_includes_hidden_targets():
    from polyforge.blender.modeling import compile_modeling

    first = object_spec(
        "first", modifiers=[{"type": "boolean", "target": "second", "operation": "UNION"}]
    )
    second = object_spec(
        "second",
        location=[0, 1.5, 0],
        modifiers=[{"type": "boolean", "target": "first", "operation": "UNION"}],
    )
    with pytest.raises(InputError):
        compile_modeling("compose", composition(first, second))
    huge = object_spec(
        "sphere", "sphere", location=[0, 1, 0], modifiers=[{"type": "subdivision", "levels": 2}] * 4
    )
    with pytest.raises(InputError, match="budget"):
        compile_modeling("compose", composition(huge))


@pytest.mark.parametrize(
    "points",
    [
        [[0, 0, 0], [0, 0, 0]],
        [[0, 0, 0], [5, 0, 0]],
        [[0, 0, 0], [1, 0, 0], [0, 0, 0]],
    ],
)
def test_curve_degeneracy_and_declared_local_bounds_rejected(points):
    from polyforge.blender.modeling import compile_modeling

    curve = object_spec(
        "curve", "curve", size_m=[1, 1, 1], location=[0, 1, 0], points=points, bevel_m=0.02
    )
    with pytest.raises(InputError):
        compile_modeling("compose", composition(curve))


def test_family_specific_controls_and_composition_admission_are_strict():
    from polyforge.blender.modeling import compile_modeling

    for kind in ("vehicle", "mechanical_prop", "organic", "compose"):
        with pytest.raises(InputError):
            compile_modeling(kind, request(wall_thickness_m=0.1))
    with pytest.raises(InputError):
        compile_modeling("compose", request())
    with pytest.raises(InputError):
        compile_modeling("vehicle", composition())
    with pytest.raises(InputError):
        compile_modeling(
            "compose", {**composition(), "parameters": {"size_m": [4, 3, 5], "detail": 2}}
        )


def test_composition_declared_full_bounds_must_be_reached_by_exported_geometry():
    from polyforge.blender.modeling import compile_modeling

    with pytest.raises(InputError, match="bounds"):
        compile_modeling("compose", composition(expected_bounds=True))
    plan = compile_modeling(
        "compose",
        composition(object_spec(size_m=[4, 3, 5], location=[0, 1.5, 0]), expected_bounds=True),
    )
    assert plan["expected_bounds"] is True


def test_curve_must_stay_within_envelope_after_evaluated_mirror_and_radius():
    from polyforge.blender.modeling import compile_modeling

    curve = object_spec(
        "curved",
        "curve",
        size_m=[0.6, 0.6, 0.6],
        location=[0, 1, 0],
        points=[[-0.2, 0, 0], [0.2, 0.2, 0]],
        bevel_m=0.03,
        modifiers=[{"type": "mirror", "axis": 0}],
    )
    assert compile_modeling("compose", composition(curve))["objects"][0] == curve
    curve["modifiers"].append({"type": "solidify", "thickness_m": 0.02})
    with pytest.raises(InputError, match="unsupported source conversion"):
        compile_modeling("compose", composition(curve))


def test_subdivision_solidify_and_boolean_composition_have_explicit_budget():
    from polyforge.blender.modeling import compile_modeling

    shell = object_spec(
        "shell",
        size_m=[0.5, 0.5, 0.5],
        location=[0, 1, 0],
        modifiers=[{"type": "solidify", "thickness_m": 0.01}, {"type": "subdivision", "levels": 1}],
    )
    assert compile_modeling("compose", composition(shell))["estimated_polygons"] == 144
    difference = object_spec(
        "solid", modifiers=[{"type": "boolean", "target": "cutter", "operation": "DIFFERENCE"}]
    )
    cutter = object_spec(
        "cutter", "cylinder", size_m=[0.25, 1.2, 0.25], location=[0, 0.6, 0], export=False
    )
    assert (
        compile_modeling("compose", composition(difference, cutter))["estimated_polygons"] == 1666
    )
    cutter["primitive"] = "curve"
    cutter.update(points=[[-0.05, 0, 0], [0.05, 0, 0]], bevel_m=0.01)
    with pytest.raises(InputError, match="mesh primitive"):
        compile_modeling("compose", composition(difference, cutter))


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_rotation_envelope_uses_all_three_axes_and_rejects_overflow(axis):
    from polyforge.blender.modeling import compile_modeling

    angles = [0, 0, 0]
    angles[axis] = 45
    obj = object_spec("rotated", size_m=[1, 1, 1], location=[0, 1, 0], rotation_deg=angles)
    assert compile_modeling("compose", composition(obj))["objects"][0]["rotation_deg"] == angles
    obj["size_m"] = [4, 3, 5]
    obj["location"] = [0, 1.5, 0]
    with pytest.raises(InputError, match="envelope"):
        compile_modeling("compose", composition(obj))


def test_total_resource_budget_includes_all_unmodified_objects():
    from polyforge.blender.modeling import compile_modeling

    spheres = [
        object_spec(f"sphere_{i}", "sphere", size_m=[0.1, 0.1, 0.1], location=[0, 1, 0])
        for i in range(2)
    ]
    value = composition(*spheres)
    value["parameters"]["max_polygons"] = 1000
    with pytest.raises(InputError, match="including cutters"):
        compile_modeling("compose", value)


@pytest.mark.parametrize("kind", ["room_kit", "vehicle", "mechanical_prop", "organic"])
@pytest.mark.parametrize("size", [[0.05, 0.05, 0.05], [50, 50, 50], [0.05, 10, 0.08]])
def test_family_dimension_boundaries_remain_finite_and_in_declared_envelope(kind, size):
    from polyforge.blender.modeling import compile_modeling

    plan = compile_modeling(kind, request(size, detail=3))
    assert plan["size_m"] == size and plan["estimated_polygons"] <= plan["max_polygons"]
    canonical_digest(plan)


def test_seed_and_room_thickness_are_preserved_as_separate_geometry_controls():
    from polyforge.blender.modeling import compile_modeling

    thin = compile_modeling("room_kit", request(wall_thickness_m=0.1), seed=0)
    thick = compile_modeling("room_kit", request(wall_thickness_m=0.2), seed=2**32 - 1)
    assert thin["seed"] == 0 and thick["seed"] == 2**32 - 1
    assert thin["objects"][0]["size_m"][1] == 0.1
    assert thick["objects"][0]["size_m"][1] == 0.2
    assert thin["input_digest"] != thick["input_digest"]


def test_curve_segments_that_collapse_at_native_precision_are_rejected():
    from polyforge.blender.modeling import compile_modeling

    curve = object_spec(
        "curve",
        "curve",
        size_m=[1, 1, 1],
        location=[0, 1, 0],
        points=[[0, 0, 0], [1e-12, 0, 0]],
        bevel_m=0.02,
    )
    with pytest.raises(InputError, match="segment"):
        compile_modeling("compose", composition(curve))


@pytest.mark.parametrize("kind", ["room_kit", "vehicle", "mechanical_prop", "organic"])
def test_generated_family_operations_can_be_reused_in_explicit_composition(kind):
    from polyforge.blender.modeling import compile_modeling

    family = compile_modeling(kind, request(detail=2))
    value = composition(*family["objects"], sockets=family["sockets"], expected_bounds=True)
    transfer = compile_modeling("compose", value)
    assert transfer["objects"] == family["objects"]
    assert transfer["estimated_polygons"] == family["estimated_polygons"]
    assert transfer["workflow"] == "compose" and transfer["input_digest"] != family["input_digest"]


def test_schema_itself_is_valid_and_accepts_declared_simple_input():
    from jsonschema import Draft202012Validator

    from polyforge.contracts.validation import schema_document

    schema = schema_document("modeling_request.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(request())
