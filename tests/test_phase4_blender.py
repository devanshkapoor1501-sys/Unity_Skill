"""Actual separate Phase 4 rendering/export and source diagnostics gate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from polyforge.capabilities.protocol import RunContext

pytestmark = pytest.mark.blender


def test_three_real_fixtures_have_four_views_and_repeatable_export_metadata(tmp_path: Path) -> None:
    from polyforge.blender.adapter import execute_recipe
    from polyforge.blender.recipes import expand_recipe
    from polyforge.contracts.images import inspect_png

    results = []
    for kind, size in (("robot", [1, 1.8, 0.8]), ("crate", [1, 1, 1]), ("orientation", [1, 2, 3])):
        recipe = (
            json.loads((Path(__file__).parent / "fixtures/recipes/asymmetric.json").read_text())
            if kind == "orientation"
            else expand_recipe(
                kind,
                {"schema_version": "1.0.0", "asset_id": kind, "parameters": {"size_m": size}},
                seed=42,
            )
        )
        first = execute_recipe(recipe, RunContext(tmp_path), audit_export=True)
        assert first.status == "PASS", first.to_dict()
        assert first.data["visual_review_status"] == "REVIEW"
        assert first.data["unity_import_status"] == "NOT_RUN"
        source = tmp_path / first.data["source_blend"]
        folder = source.parent
        for view in ("front", "side", "top", "iso"):
            report = inspect_png((folder / (view + ".png")).read_bytes(), expected_size=512)
            assert report["nonblank"] and report["framing_pass"], report
        assert (folder / "asset.fbx").read_bytes().startswith(b"Kaydara FBX Binary")
        assert json.loads((folder / "material.json").read_text())["asset_id"] == recipe["asset_id"]
        second = execute_recipe(recipe, RunContext(tmp_path), audit_export=True)
        assert second.status == "PASS", second.to_dict()
        assert first.metrics["geometry_digest"] == second.metrics["geometry_digest"]
        a = json.loads((folder / "audit_metadata.json").read_text())
        b = json.loads(
            (tmp_path / second.data["source_blend"]).with_name("audit_metadata.json").read_text()
        )
        assert a == b
        results.append(first.to_dict())
    (tmp_path / "audit-results.json").write_text(json.dumps(results, indent=2), encoding="utf-8")


def test_fbx_reimport_preserves_asymmetric_front_height_and_semantic_names(tmp_path: Path) -> None:
    from polyforge.blender.adapter import execute_recipe

    recipe = json.loads((Path(__file__).parent / "fixtures/recipes/asymmetric.json").read_text())
    result = execute_recipe(recipe, RunContext(tmp_path), audit_export=True)
    assert result.status == "PASS", result.to_dict()
    report = json.loads(
        (tmp_path / result.data["source_blend"]).with_name("fbx_roundtrip.json").read_text()
    )
    assert report["status"] == "PASS"
    assert report["verification_scope"] == "BLENDER_FBX_ROUNDTRIP"
    assert report["unity_import_status"] == "NOT_RUN"
    assert report["bounds_unity_m"] == [1, 2, 3]
    assert report["socket_positions_unity_m"]["front"][2] > 0


def test_managed_saved_source_audit_is_nonmutating_and_dry_run_is_pure(tmp_path: Path) -> None:
    import hashlib

    from polyforge.blender.adapter import BlenderCapability
    from polyforge.blender.audit import audit_asset

    (tmp_path / "polyforge.toml").write_text("[visual_audit]\npreview_resolution = 64\n")
    source = BlenderCapability("crate").execute(
        {"schema_version": "1.0.0", "asset_id": "crate", "parameters": {"size_m": [1, 1, 1]}},
        RunContext(tmp_path),
    )
    assert source.status == "PASS", source.to_dict()
    original = tmp_path / source.data["source_blend"]
    before = hashlib.sha256(original.read_bytes()).hexdigest()
    inventory = {
        str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }
    dry = audit_asset(tmp_path, "crate", dry_run=True)
    assert dry.status == "PASS"
    assert {
        str(p.relative_to(tmp_path)): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    } == inventory
    audited = audit_asset(tmp_path, "crate")
    assert audited.status == "PASS", audited.to_dict()
    assert hashlib.sha256(original.read_bytes()).hexdigest() == before
    assert (tmp_path / audited.data["source_blend"]).read_bytes() == original.read_bytes()
    assert source.metrics["geometry_digest"] == audited.metrics["geometry_digest"]


def test_long_semantic_material_ids_survive_export_without_datablock_lookup_errors(
    tmp_path: Path,
) -> None:
    from polyforge.blender.adapter import execute_recipe
    from polyforge.blender.recipes import expand_recipe

    (tmp_path / "polyforge.toml").write_text("[visual_audit]\npreview_resolution = 32\n")
    recipe = expand_recipe(
        "crate",
        {"schema_version": "1.0.0", "asset_id": "crate", "parameters": {"size_m": [1, 1, 1]}},
        seed=42,
    )
    identifier = "m" * 64
    recipe["materials"] = [{"id": identifier, "color_rgba": [0.2, 0.4, 0.6, 1]}]
    for module in recipe["modules"]:
        module["material_id"] = identifier
    result = execute_recipe(recipe, RunContext(tmp_path), audit_export=True)
    assert result.status == "PASS", result.to_dict()


def test_real_fault_taxonomy_identifies_originating_modules(tmp_path: Path) -> None:
    from polyforge.blender.adapter import execute_recipe
    from polyforge.blender.recipes import expand_recipe
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
    assert result.status == "PASS"
    root = Path(__file__).resolve().parents[1]
    policy = WorkspacePolicy(tmp_path)
    source = tmp_path / result.data["source_blend"]
    job = atomic_json(
        policy,
        "fault-input.json",
        {
            "source": str(source),
            "recipe": recipe,
            "worker": str(root / "polyforge/blender/audit_worker.py"),
        },
    )
    executable = discover_tool("blender")
    assert executable is not None
    outcome = run_process(
        [
            str(executable),
            "--background",
            "--factory-startup",
            "--disable-autoexec",
            "--python-exit-code",
            "5",
            "--python",
            str(root / "tests/blender_audit_fault_probe.py"),
            "--",
            str(job),
            str(tmp_path / "audit-faults.json"),
        ],
        policy,
        "fault-log",
        ProcessPolicy((executable,), 120),
    )
    assert outcome.returncode == 0, (tmp_path / outcome.stderr_path).read_text()
    reports = json.loads((tmp_path / "audit-faults.json").read_text())
    for category, report in reports.items():
        assert report["status"] == "FAIL", report
        assert any(
            issue["category"] == category and issue["module_id"] for issue in report["issues"]
        ), report
