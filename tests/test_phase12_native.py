"""Qualification against actual pinned Blender and Unity binaries."""

import json
import shutil
from collections import Counter
from hashlib import file_digest
from pathlib import Path

import pytest

from polyforge.blender.modeling import MODELING_CAPABILITIES
from polyforge.capabilities.dispatch import execute
from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.validation import InputError

FAMILIES = {
    "room_kit": [4, 3, 5],
    "vehicle": [3, 2, 6],
    "mechanical_prop": [2, 1, 3],
    "organic": [2, 3, 1],
}


def family_input(kind):
    return {
        "schema_version": "1.0.0",
        "asset_id": kind,
        "parameters": {"size_m": FAMILIES[kind], "detail": 2},
    }


def part(id_, primitive, size, location, material_id="base", **extra):
    return {
        "id": id_,
        "primitive": primitive,
        "size_m": size,
        "location": location,
        "rotation_deg": [0, 0, 0],
        "material_id": material_id,
        "export": True,
        "modifiers": [],
    } | extra


def transfer_input():
    # A coolant valve with a bored housing, procedural mounting base and pipe.
    return {
        "schema_version": "1.0.0",
        "asset_id": "coolant_valve",
        "parameters": {"size_m": [3, 2, 2]},
        "objects": [
            part("foot", "grid", [3, 0.2, 2], [0, 0.1, 0], "trim", detail=3),
            part(
                "housing",
                "cylinder",
                [1.2, 0.8, 1],
                [0, 0.6, 0],
                modifiers=[
                    {"type": "boolean", "target": "bore", "operation": "DIFFERENCE"},
                ],
            ),
            part("bore", "cylinder", [0.4, 1, 0.35], [0, 0.6, 0], export=False),
            part(
                "pipe",
                "curve",
                [0.6, 0.6, 0.6],
                [0.7, 0.55, 0.15],
                "accent",
                points=[[-0.22, -0.15, 0], [0, 0.1, 0.1], [0.2, 0.22, 0.2]],
                bevel_m=0.04,
            ),
            part(
                "handle",
                "sphere",
                [0.65, 0.5, 0.5],
                [0, 1.2, 0],
                "accent",
                modifiers=[
                    {"type": "subdivision", "levels": 1},
                ],
            ),
        ],
        "sockets": [{"id": "outlet", "position": [0.9, 0.77, 0.35]}],
    }


def gantry_input():
    # A walkway inspection station with an angled crossbeam and overhead conduit.
    return {
        "schema_version": "1.0.0",
        "asset_id": "inspection_gantry",
        "parameters": {"size_m": [5.5, 4, 4], "lod_ratio": 0.65},
        "objects": [
            part("deck", "grid", [4.8, 0.24, 3.2], [0, 0.12, 0], "trim", detail=2),
            part("post_left", "box", [0.4, 2.64, 0.4], [-1.48, 1.56, 0.31]),
            part("post_right", "box", [0.4, 2.64, 0.4], [1.48, 1.56, -0.31]),
            part(
                "crossbeam",
                "box",
                [3.72, 0.32, 0.46],
                [0, 3.04, 0],
                rotation_deg=[0, 12, 0],
                modifiers=[{"type": "bevel", "width_m": 0.04, "segments": 2}],
            ),
            part(
                "conduit",
                "curve",
                [2.6, 0.75, 0.5],
                [0, 3.39, 0.12],
                "accent",
                points=[
                    [-1.2, -0.22, 0.12],
                    [-0.8, 0.2, 0.1],
                    [0.8, 0.2, -0.1],
                    [1.2, -0.22, -0.12],
                ],
                bevel_m=0.035,
            ),
            part(
                "inspection_head",
                "box",
                [0.46, 0.38, 0.42],
                [0.32, 2.71, 0.02],
                "accent",
                rotation_deg=[0, 0, -15],
            ),
        ],
        "sockets": [
            {"id": "sensor_mount", "position": [0.32, 2.52, 0.02]},
            {"id": "walkway_entry", "position": [-1.9, 0.24, 1.25]},
        ],
        "overlap_policy": "ASSEMBLY_CONTACTS",
        "expected_bounds": False,
    }


@pytest.fixture(scope="module")
def native_models(tmp_path_factory):
    root = tmp_path_factory.mktemp("phase12-blender")
    results = {}
    requests = {kind: (kind, family_input(kind)) for kind in FAMILIES}
    requests.update(
        compose=("compose", transfer_input()), inspection_gantry=("compose", gantry_input())
    )
    for name, (kind, request) in requests.items():
        context = RunContext(root, run_id=name)
        result = execute(MODELING_CAPABILITIES[kind], request, context)
        assert result.status == "PASS", result.to_dict()
        assert result.data["artistic_status"] == "REVIEW"
        assert result.data["inspection"]["source_unchanged"]
        assert len(result.artifact_ids) == 9
        assert execute(MODELING_CAPABILITIES[kind], request, context) == result
        results[name] = result.to_dict()
    (root / "native-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    trace_model_frames(root, results)
    return root, results


def trace_model_frames(root, results):
    from polyforge.doctor import discover_tool
    from polyforge.runner.processes import ProcessPolicy, run_process
    from polyforge.security.paths import WorkspacePolicy

    blender = discover_tool("blender")
    assert blender is not None
    inputs = root / "frame-inputs.json"
    inputs.write_text(
        json.dumps(
            [
                {
                    "source": str(root / r["data"]["source_blend"]),
                    "worker": str(
                        Path(__file__).resolve().parents[1] / "polyforge/blender/modeling_worker.py"
                    ),
                }
                for r in results.values()
            ]
        ),
        encoding="utf-8",
    )
    output = root / "frame-trace.json"
    process = run_process(
        [
            str(blender),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--threads",
            "1",
            "--python-exit-code",
            "5",
            "--python",
            str(Path(__file__).resolve().parent / "fixtures/modeling/export_trace.py"),
            "--",
            str(inputs),
            str(output),
        ],
        WorkspacePolicy(root),
        "frame-trace-process",
        ProcessPolicy((blender,), 180),
    )
    assert process.returncode == 0 and process.reason == "exit", process
    trace = json.loads(output.read_text(encoding="utf-8"))
    assert len(trace["models"]) == len(results)
    assert all(row["sha256_before"] == row["sha256_after"] for row in trace["models"])
    assert all(row["export_failure_rolled_back"] for row in trace["models"])


@pytest.mark.blender
def test_native_inspection_gantry_preserves_distinct_composed_features(native_models):
    _, results = native_models
    inspected = results["inspection_gantry"]["data"]["inspection"]
    objects = {row["id"]: row for row in inspected["objects"]}
    assert objects["deck"]["modifiers"][0] == {"type": "geometry_nodes", "detail": 2}
    assert objects["crossbeam"]["rotation_deg"] == pytest.approx([0, 12, 0], abs=0.001)
    assert objects["inspection_head"]["rotation_deg"] == pytest.approx([0, 0, -15], abs=0.001)
    assert objects["conduit"]["source_geometry"]["spline_type"] == "POLY"
    assert objects["conduit"]["source_geometry"]["closed_caps"] is True
    assert {row["id"]: row["position_unity"] for row in inspected["sockets"]} == {
        "sensor_mount": pytest.approx([0.32, 2.52, 0.02], abs=0.0001),
        "walkway_entry": pytest.approx([-1.9, 0.24, 1.25], abs=0.0001),
    }
    assert {obj["material_ids"][0] for obj in objects.values()} == {"base", "trim", "accent"}


@pytest.mark.blender
def test_native_exports_recover_only_while_artifacts_match(native_models):
    root, results = native_models
    source = root / results["compose"]["data"]["source_blend"]
    export = source.with_name("asset.fbx")
    payload = export.read_bytes()
    assert payload.startswith(b"Kaydara FBX Binary")
    try:
        export.write_bytes(payload + b"changed")
        with pytest.raises(InputError, match="artifact changed"):
            execute(
                MODELING_CAPABILITIES["compose"],
                transfer_input(),
                RunContext(root, run_id="compose"),
            )
    finally:
        export.write_bytes(payload)


@pytest.mark.blender
def test_native_inspection_detects_pivot_socket_and_topology_faults(native_models, tmp_path):
    from polyforge.blender.modeling_inspection import validate_modeling_report
    from polyforge.doctor import discover_tool
    from polyforge.runner.processes import ProcessPolicy, run_process
    from polyforge.security.paths import WorkspacePolicy

    root, results = native_models
    data = results["room_kit"]["data"]
    source = root / data["source_blend"]
    with source.open("rb") as stream:
        original = file_digest(stream, "sha256").hexdigest()
    run = source.parent.parent
    fault_script = Path(__file__).parent / "fixtures/modeling/modeling_faults.py"
    blender = discover_tool("blender")
    assert blender is not None
    process = run_process(
        [
            str(blender),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--threads",
            "1",
            "--python-exit-code",
            "5",
            "--python",
            str(fault_script),
            "--",
            str(source),
            str(run / "input.json"),
            str(run / "modeling_inspector.py"),
            str(tmp_path),
        ],
        WorkspacePolicy(tmp_path),
        "fault-process",
        ProcessPolicy((blender,), 180),
    )
    assert process.returncode == 0 and process.reason == "exit", process
    for name in ("pivot", "socket", "open_mesh", "reversed_mesh"):
        report = json.loads((tmp_path / (name + ".json")).read_text(encoding="utf-8"))
        if name == "reversed_mesh":
            assert "floor: normal_inconsistencies=1" in report["issues"]
        with pytest.raises(InputError):
            validate_modeling_report(data["plan"], report)
    with source.open("rb") as stream:
        assert file_digest(stream, "sha256").hexdigest() == original


@pytest.mark.blender
@pytest.mark.parametrize(
    "primitive,modifiers",
    [
        ("sphere", [{"type": "mirror", "axis": 0}]),
        (
            "box",
            [
                {"type": "bevel", "width_m": 0.08, "segments": 2},
                {"type": "solidify", "thickness_m": 0.04},
            ],
        ),
    ],
)
def test_editable_mirror_and_hollow_shell_with_one_material(tmp_path, primitive, modifiers):
    value = {
        "schema_version": "1.0.0",
        "asset_id": "single_material",
        "parameters": {"size_m": [4, 4, 4]},
        "objects": [
            {
                "id": "part",
                "primitive": primitive,
                "size_m": [2, 2, 2],
                "location": [0, 2, 0],
                "rotation_deg": [0, 0, 0],
                "material_id": "base",
                "export": True,
                "modifiers": modifiers,
            },
        ],
    }
    result = execute(MODELING_CAPABILITIES["compose"], value, RunContext(tmp_path))
    assert result.status == "PASS", result.to_dict()
    inspected = result.data["inspection"]
    assert len(inspected["materials"]) == 3
    assert inspected["objects"][0]["normal_inconsistencies"] == 0
    assert inspected["lod"]["normal_inconsistencies"] == 0


@pytest.mark.blender
def test_workforce_delivers_candidate_and_holds_artistic_promotion(tmp_path):
    from polyforge.contracts.validation import load_json
    from polyforge.workforce.orchestrator import run_task

    task = {
        "schema_version": "1.0.0",
        "task_class": "CREATE_ASSET",
        "brief": "Model an editable 4 by 3 by 5 meter modular room kit with a doorway socket.",
        "domain_tags": ["blender"],
        "feature_ids": ["editable_source", "doorway_socket"],
        "capability_id": MODELING_CAPABILITIES["room_kit"],
        "input": family_input("room_kit"),
    }
    with pytest.raises(InputError, match="required approval"):
        run_task(tmp_path, task)
    (board_path,) = (tmp_path / "workforce").glob("*/board.json")
    board = load_json(board_path)
    assert board["technical"] == "APPROVED"
    assert board["subjective"] == board["promotion"] == "REVIEW"
    lineage = load_json(board_path.with_name("lineage.json"))
    assert [step["role_id"] for step in lineage] == [
        "asset_architect",
        "modeler_architecture",
        "asset_inspector",
    ]


@pytest.mark.unity
def test_unity_imports_modeling_families_and_lods(native_models, tmp_path):
    from polyforge.runner.locks import unity_project_lock
    from polyforge.runner.processes import ProcessPolicy, run_process
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity.bootstrap import installed_template, prepare_project
    from polyforge.unity.bridge import configuration, unity_tool

    root, results = native_models
    policy = WorkspacePolicy(tmp_path)
    editor = unity_tool(configuration(policy))
    project = policy.path("UnityProject")
    with unity_project_lock(policy, project):
        prepare_project(policy, installed_template(editor))
        files = policy.mkdir(project / "Assets/Phase12Models")
        scripts = policy.mkdir(project / "Assets/Editor")
        fixture = Path(__file__).parent / "fixtures/modeling/ModelingImportProbe.cs"
        shutil.copyfile(fixture, scripts / fixture.name)
        expected = []
        source_hashes = {}
        for kind, result in results.items():
            data = result["data"]
            folder = (root / data["source_blend"]).parent
            with (folder / "source.blend").open("rb") as stream:
                source_hashes[folder / "source.blend"] = file_digest(stream, "sha256").hexdigest()
            for name in ("asset", "lod"):
                filename = f"{kind}_{name}.fbx"
                shutil.copyfile(folder / (name + ".fbx"), files / filename)
                inspected = data["inspection"]["aggregate" if name == "asset" else "lod"]
                material_triangles = Counter()
                if name == "asset":
                    for obj in data["inspection"]["objects"]:
                        if obj["export"]:
                            material_triangles.update(obj["material_triangle_counts"])
                else:
                    material_triangles.update(inspected["material_triangle_counts"])
                expected.append(
                    {
                        "path": f"Assets/Phase12Models/{filename}",
                        "lo": inspected["bounds_min_unity"],
                        "hi": inspected["bounds_max_unity"],
                        "meshCount": sum(o["export"] for o in data["plan"]["objects"])
                        if name == "asset"
                        else 1,
                        "materialIds": sorted(
                            {
                                material
                                for obj in data["inspection"]["objects"]
                                if obj["export"]
                                for material in obj["material_ids"]
                            }
                        ),
                        "materialTriangles": [
                            {"id": material, "triangles": count}
                            for material, count in sorted(material_triangles.items())
                        ],
                        "sockets": [
                            {"id": s["id"], "position": s["position"]}
                            for s in data["plan"]["sockets"]
                        ],
                        "modules": [
                            {
                                "id": obj["id"],
                                "lo": obj["bounds_min_unity"],
                                "hi": obj["bounds_max_unity"],
                                "materialIds": obj["material_ids"],
                            }
                            for obj in data["inspection"]["objects"]
                            if obj["export"]
                        ]
                        if name == "asset"
                        else [],
                    }
                )
        inputs = tmp_path / "unity-input.json"
        inputs.write_text(json.dumps({"models": expected}), encoding="utf-8")
        receipt = tmp_path / "unity-result.json"
        process = run_process(
            [
                str(editor),
                "-batchmode",
                "-nographics",
                "-quit",
                "-job-worker-count",
                "2",
                "-projectPath",
                str(project),
                "-logFile",
                "-",
                "-executeMethod",
                "ModelingImportProbe.Run",
                "-modelingInput",
                str(inputs),
                "-modelingResult",
                str(receipt),
            ],
            policy,
            "editor-process",
            ProcessPolicy((editor,), 900),
        )
    assert process.returncode == 0 and process.reason == "exit", process
    observed = json.loads(receipt.read_text(encoding="utf-8"))
    assert observed["models"] == 12 and observed["passed"]
    assert len(observed["observations"]) == 12
    by_path = {row["path"]: row for row in observed["observations"]}
    for kind in ("compose", "inspection_gantry"):
        for export in ("asset", "lod"):
            row = by_path[f"Assets/Phase12Models/{kind}_{export}.fbx"]
            assert row["passed"]
            mutants = {m["id"]: m for m in row["mutants"]}
            assert mutants["whole_root_x_reflection"]["detected"]
            if kind == "compose":
                assert mutants["outlet_x_reflection"]["detected"]
                (outlet,) = row["sockets"]
                assert outlet["expected"] == pytest.approx([0.9, 0.77, 0.35], abs=0.000001)
                assert outlet["observed"] == pytest.approx([0.9, 0.77, 0.35], abs=0.005)
    for row in observed["observations"]:
        assert row["guidBeforeReimport"] == row["guidAfterReimport"]
        assert row["metaSha256Before"] == row["metaSha256After"]
        assert all(m["cleanedUp"] for m in row["mutants"])
        assert len(row["parentCases"]) == 2
        assert all(p["restored"] and p["cleanedUp"] for p in row["parentCases"])
    for source, before in source_hashes.items():
        with source.open("rb") as stream:
            assert file_digest(stream, "sha256").hexdigest() == before
