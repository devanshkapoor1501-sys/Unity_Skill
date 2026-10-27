"""Real application gate, invoked separately with -m blender."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polyforge.capabilities.protocol import RunContext

pytestmark = pytest.mark.blender


def test_real_golden_fixtures_and_repeatability(tmp_path: Path) -> None:
    from polyforge.blender.adapter import execute_recipe
    from polyforge.blender.recipes import expand_recipe

    results = []
    for kind, size in (("robot", [1, 1.8, 0.8]), ("crate", [1, 1, 1])):
        recipe = expand_recipe(
            kind,
            {"schema_version": "1.0.0", "asset_id": kind, "parameters": {"size_m": size}},
            seed=42,
        )
        first = execute_recipe(recipe, RunContext(tmp_path))
        assert first.status == "PASS", first.to_dict()
        repeated = execute_recipe(recipe, RunContext(tmp_path))
        assert repeated.status == "PASS", repeated.to_dict()
        assert first.metrics["geometry_digest"] == repeated.metrics["geometry_digest"]
        assert first.metrics["logical_metrics"] == repeated.metrics["logical_metrics"]
        for result in (first, repeated):
            source = tmp_path / result.data["source_blend"]
            assert source.read_bytes().startswith(b"BLENDER")
            assert result.metrics["saved_roundtrip_verified"] is True
            assert result.metrics["blender_version"] == "5.2.2"
            logical = json.loads((source.parent / "logical-geometry.json").read_text())
            assert {m["id"]: m["parent"] for m in logical["modules"]} == {
                m["id"]: m.get("parent", recipe["asset_id"]) for m in recipe["modules"]
            }
        results.append(first.to_dict())
    recipe = json.loads((Path(__file__).parent / "fixtures/recipes/asymmetric.json").read_text())
    result = execute_recipe(recipe, RunContext(tmp_path))
    assert result.status == "PASS", result.to_dict()
    assert result.metrics["bounds_unity_m"] == [1, 2, 3]
    assert result.metrics["socket_positions_unity_m"]["front"][2] > 0
    repeat = execute_recipe(recipe, RunContext(tmp_path))
    assert repeat.status == "PASS", repeat.to_dict()
    assert result.metrics["logical_metrics"] == repeat.metrics["logical_metrics"]
    results.append(result.to_dict())
    (tmp_path / "integration-results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )


def test_five_registered_families_and_two_briefs_produce_distinct_parameterized_geometry(
    tmp_path: Path,
) -> None:
    from polyforge.blender.adapter import BlenderCapability
    from polyforge.blender.recipes import RECIPES

    hashes = []
    family_metrics = {}
    for kind in RECIPES:
        request = {
            "schema_version": "1.0.0",
            "asset_id": kind,
            "parameters": {"size_m": [2, 3, 0.4]},
        }
        result = BlenderCapability(kind).execute(request, RunContext(tmp_path))
        assert result.status == "PASS", result.to_dict()
        family_metrics[kind] = result.metrics
    for side in ("left", "right"):
        assert (
            family_metrics["wall"]["socket_positions_unity_m"]["join_" + side]
            == family_metrics["doorway"]["socket_positions_unity_m"]["join_" + side]
        )
    for brief, size in (("arena", [1, 1.8, 0.8]), ("warehouse", [2, 3, 1])):
        workspace = tmp_path / brief
        workspace.mkdir()
        (workspace / "brief.md").write_text(f"{brief}: use a modular robot sized {size} meters.")
        result = BlenderCapability("robot").execute(
            {"schema_version": "1.0.0", "asset_id": "robot_a", "parameters": {"size_m": size}},
            RunContext(workspace),
        )
        assert result.status == "PASS", result.to_dict()
        assert result.metrics["bounds_unity_m"] == size
        hashes.append(result.metrics["geometry_digest"])
    assert len(set(hashes)) == 2


def test_real_saved_geometry_faults_are_rejected(tmp_path: Path) -> None:
    import copy

    from polyforge.blender.adapter import execute_recipe
    from polyforge.blender.recipes import expand_recipe, validate_geometry
    from polyforge.contracts.validation import InputError
    from polyforge.doctor import discover_tool
    from polyforge.runner.processes import ProcessPolicy, run_process
    from polyforge.runner.state import atomic_json
    from polyforge.security.paths import WorkspacePolicy

    recipe = expand_recipe(
        "robot",
        {"schema_version": "1.0.0", "asset_id": "robot", "parameters": {"size_m": [1, 1.8, 0.8]}},
        seed=42,
    )
    result = execute_recipe(recipe, RunContext(tmp_path))
    assert result.status == "PASS", result.to_dict()
    root = Path(__file__).resolve().parents[1]
    policy = WorkspacePolicy(tmp_path)
    job = atomic_json(
        policy,
        "fault-input.json",
        {
            "recipe": recipe,
            "worker": str(root / "polyforge/blender/worker.py"),
            "source": str(tmp_path / result.data["source_blend"]),
        },
    )
    executable = discover_tool("blender")
    assert executable is not None
    output = tmp_path / "fault-reports.json"
    outcome = run_process(
        [
            str(executable),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "5",
            "--python",
            str(root / "tests/blender_fault_probe.py"),
            "--",
            str(job),
            str(output),
        ],
        policy,
        "fault-logs",
        ProcessPolicy((executable,), 120),
    )
    assert outcome.returncode == 0, (tmp_path / outcome.stderr_path).read_text()
    reports = json.loads(output.read_text())
    for name, report in reports.items():
        requested = copy.deepcopy(recipe)
        if name == "budget":
            requested["max_polygons"] = 4
        with pytest.raises(InputError) as error:
            validate_geometry(requested, report)
        assert int(error.value.kind) == 6


def test_large_valid_geometry_payload_exceeds_input_json_limit(tmp_path: Path) -> None:
    from polyforge.blender.adapter import execute_recipe

    recipe = {
        "schema_version": "1.0.0",
        "asset_id": "sphere_grid",
        "kind": "ground",
        "capability_id": "mesh.environment.tile.v1",
        "parameters": {"size_m": [2, 2, 2]},
        "modules": [
            {
                "id": f"sphere_{i}",
                "primitive": "sphere",
                "size_m": [0.15, 0.15, 0.15],
                "location": [(i % 8) * 0.25, ((i // 8) % 4) * 0.25, (i // 32) * 0.25],
            }
            for i in range(128)
        ],
        "sockets": [],
        "max_polygons": 25000,
    }
    result = execute_recipe(recipe, RunContext(tmp_path))
    assert result.status == "PASS", result.to_dict()
    path = (tmp_path / result.data["source_blend"]).parent / "logical-geometry.json"
    assert path.stat().st_size > 1_048_576
    assert result.metrics["polygon_count"] == 16384
