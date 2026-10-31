"""Real Unity gates; unavailable tools fail this explicit gate instead of skipping it."""

import hashlib
import json
from pathlib import Path

import pytest

from polyforge.blender.build import build_assets
from polyforge.contracts.validation import load_json
from polyforge.unity.evidence import EDITMODE_TESTS, verify_test_xml
from polyforge.workspace import init_workspace

pytestmark = pytest.mark.unity


@pytest.fixture(scope="module")
def arena(tmp_path_factory):
    root = tmp_path_factory.mktemp("polyforge_phase5") / "arena"
    init_workspace(root, "simple_arena")
    result = build_assets(root, through="S4", allow_package_downloads=True)
    (root / "first-result.json").write_text(json.dumps(result.to_dict(), indent=2))
    assert result.status == "PASS", result.to_dict()
    return root


def test_real_native_build_has_executed_editmode_and_two_scenes(arena: Path):
    first = load_json(arena / "first-result.json")
    run = arena / "runs" / first["run_id"]
    assert verify_test_xml(run / "editmode.xml", EDITMODE_TESTS)["executed"] == 23
    bindings = load_json(run / "bindings.json")
    assert len(bindings["objects"]) == 3
    assert bindings["issues"] == []
    assert len(bindings["scene_guids"]) == 2
    assert (arena / "UnityProject/Assets/PolyForgeGenerated/Scenes/Arena.unity").is_file()
    assert (arena / "UnityProject/Assets/PolyForgeGenerated/Scenes/Training.unity").is_file()


def test_material_only_rebuild_preserves_fbx_code_guids_and_object_counts(arena: Path):
    before = load_json(arena / "first-result.json")
    baseline = load_json(arena / "runs" / before["run_id"] / "bindings.json")

    def hashes(pattern):
        return {
            str(p.relative_to(arena)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in arena.glob(pattern)
        }

    fbx = hashes("UnityProject/Assets/PolyForgeGenerated/Models/*.fbx")
    code = hashes("UnityProject/Packages/com.polyforge.engine/**/*.cs")
    sources = set(arena.glob("runs/mesh-*"))
    path = arena / "game_manifest.json"
    manifest = load_json(path)
    manifest["materials"][0]["base_color_rgba"] = [0.8, 0.15, 0.05, 1]
    path.write_text(json.dumps(manifest, indent=2))
    result = build_assets(arena, through="S4")
    (arena / "second-result.json").write_text(json.dumps(result.to_dict(), indent=2))
    assert result.status == "PASS", result.to_dict()
    assert all(x["reused_geometry"] for x in result.data["source_bindings"])
    assert set(arena.glob("runs/mesh-*")) == sources
    assert hashes("UnityProject/Assets/PolyForgeGenerated/Models/*.fbx") == fbx
    assert hashes("UnityProject/Packages/com.polyforge.engine/**/*.cs") == code
    actual = load_json(arena / "runs" / result.run_id / "bindings.json")
    assert actual["scene_object_count"] == baseline["scene_object_count"]
    assert [(a["guid"], a["prefab_guid"]) for a in actual["objects"]] == [
        (a["guid"], a["prefab_guid"]) for a in baseline["objects"]
    ]


def test_real_scale_diagnosis_minimal_repair_and_snapshot_reimport_rollback(
    arena: Path, monkeypatch
):
    import shutil

    from polyforge.config import Config
    from polyforge.doctor import discover_tool
    from polyforge.runner.processes import ProcessPolicy, run_process
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity.bridge import launch
    from polyforge.unity.evidence import reconcile_report
    from polyforge.unity.repairs import (
        current_request,
        reconcile_workspace,
        repair_apply,
        repair_plan,
    )
    from polyforge.unity.transactions import ManagedTransaction

    policy = WorkspacePolicy(arena)
    executable = discover_tool("unity")
    assert executable is not None
    fixture = policy.path("UnityProject/Assets/PolyForgeFaultFixtures/Editor/Fault.cs")
    policy.mkdir(fixture.parent)
    shutil.copyfile(Path(__file__).with_name("unity_fault_probe.cs"), fixture)
    request = current_request(policy)
    baseline = reconcile_workspace(arena)
    assert baseline.status == "PASS", baseline.to_dict()
    latest = load_json(arena / "runs" / baseline.run_id / "bindings.json")
    tx = ManagedTransaction.create(policy, "acceptance_restore")
    outcome = run_process(
        [
            str(executable),
            "-batchmode",
            "-nographics",
            "-job-worker-count",
            "2",
            "-projectPath",
            str(policy.path("UnityProject")),
            "-executeMethod",
            "PolyForgeFaultProbe.DamageScaleAndMaterial",
            "-logFile",
            "-",
        ],
        policy,
        "fault-scale",
        ProcessPolicy((executable,), timeout_seconds=600),
    )
    assert outcome.returncode == 0, outcome
    failed = reconcile_workspace(arena)
    assert failed.exit_code == 6, failed.to_dict()
    issue = next(
        x for x in failed.data["issues"] if x["category"] == "scale" and x["asset_id"] == "robot_a"
    )
    preview = repair_plan(arena, issue["issue_id"])
    assert preview.data["dry_run"] is True
    path = policy.path("repair.json")
    path.write_text(json.dumps(preview.data["plan"], indent=2))
    repaired = repair_apply(arena, "repair.json")
    (arena / "repair-result.json").write_text(json.dumps(repaired.to_dict(), indent=2))
    assert repaired.status == "PASS", repaired.to_dict()
    assert repaired.data["repair_status"] == "COMMITTED"
    assert any(i["asset_id"] == "crate_a" for i in repaired.data["remaining_issues"])
    crate_issue = next(
        i
        for i in failed.data["issues"]
        if i["asset_id"] == "crate_a" and i["category"] == "material"
    )
    crate_plan = repair_plan(arena, crate_issue["issue_id"])
    path.write_text(json.dumps(crate_plan.data["plan"], indent=2), encoding="utf-8")
    from polyforge.contracts.validation import InputError
    from polyforge.unity import repairs

    native_launch = repairs.launch

    def reject_after_real_apply(*args, **kwargs):
        value = native_launch(*args, **kwargs)
        if args[4] == "build":
            raise InputError("Injected post-apply verification rejection")
        return value

    with monkeypatch.context() as injected:
        injected.setattr(repairs, "launch", reject_after_real_apply)
        rejected = repair_apply(arena, "repair.json")
    assert rejected.error_code == "PF-REPAIR-ROLLED-BACK", rejected.to_dict()
    journal = load_json(arena / "transactions" / rejected.rollback_id / "journal.json")
    assert journal["status"] == "ROLLED_BACK"
    assert journal["verification"]["status"] == "FAIL"  # faithfully restored faulty baseline
    (arena / "faulty-baseline-rollback.json").write_text(
        json.dumps(rejected.to_dict(), indent=2), encoding="utf-8"
    )
    # Deliberately change the managed manifest and model source, then restore the
    # baseline exactly; Library is retained to exercise real application reimport.
    manifest = load_json(arena / "game_manifest.json")
    manifest["project"]["seed"] = 43
    (arena / "game_manifest.json").write_text(json.dumps(manifest))
    model = policy.path("UnityProject/" + request["assets"][0]["fbx_path"])
    model.write_bytes(b"damaged managed source")
    tx.record("ACCEPTANCE_FAULT", changed=["game_manifest.json", str(model.relative_to(arena))])
    tx.restore()
    assert tx.verify_restored()
    output = policy.path("transactions/acceptance_restore/reimport.json")
    launch(
        policy,
        executable,
        Config(),
        "rollback-reimport",
        "restore",
        request=policy.path(".polyforge/unity-request.json"),
        output=output,
    )
    restored = load_json(output)
    assert reconcile_report(request, restored)["status"] == "PASS"
    assert restored["scene_object_count"] == latest["scene_object_count"]
    assert restored["scene_guids"] == latest["scene_guids"]
    assert [(x["guid"], x["prefab_guid"]) for x in restored["objects"]] == [
        (x["guid"], x["prefab_guid"]) for x in latest["objects"]
    ]
    tx.record(
        "ROLLED_BACK",
        verification="actual forced Unity reimport and semantic reconciliation",
        bytes_match=tx.verify_restored(),
    )
    (arena / "rollback-result.json").write_text(json.dumps(restored, indent=2))
