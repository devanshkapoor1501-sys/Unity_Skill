"""Phase 5 bootstrap boundaries and independent observed-report contracts."""

import io
import json
import tarfile
from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError
from polyforge.security.paths import WorkspacePolicy


def archive(path: Path, entries: dict[str, bytes]) -> Path:
    with tarfile.open(path, "w:gz") as t:
        for name, data in entries.items():
            m = tarfile.TarInfo(name)
            m.size = len(data)
            t.addfile(m, io.BytesIO(data))
    return path


def test_template_preflight_rejects_traversal_and_existing_project_without_writes(tmp_path: Path):
    from polyforge.unity.bootstrap import prepare_project

    policy = WorkspacePolicy(tmp_path)
    template = archive(tmp_path / "bad.tgz", {"package/ProjectData~/../escape": b"bad"})
    with pytest.raises(InputError):
        prepare_project(policy, template)
    assert not (tmp_path / "UnityProject").exists()
    template = archive(
        tmp_path / "good.tgz",
        {
            "package/ProjectData~/Packages/manifest.json": b'{"dependencies":{}}',
            "package/ProjectData~/Assets/keep.txt": b"original",
        },
    )
    (tmp_path / "UnityProject").mkdir()
    (tmp_path / "UnityProject/user.txt").write_text("never overwrite")
    with pytest.raises(InputError):
        prepare_project(policy, template)
    assert (tmp_path / "UnityProject/user.txt").read_text() == "never overwrite"


def test_template_bootstrap_preserves_native_assets_and_records_exact_inputs(tmp_path: Path):
    from polyforge.unity.bootstrap import prepare_project

    template = archive(
        tmp_path / "template.tgz",
        {
            "package/ProjectData~/Packages/manifest.json": (
                b'{"dependencies":{"com.unity.test-framework":"1.8.0"}}'
            ),
            "package/ProjectData~/Assets/keep.asset": b"opaque Unity bytes\n",
            "package/ProjectData~/Library/stale": b"do not copy caches",
        },
    )
    policy = WorkspacePolicy(tmp_path)
    project = prepare_project(policy, template)
    assert (project / "Assets/keep.asset").read_bytes() == b"opaque Unity bytes\n"
    assert not (project / "Library").exists()
    assert (
        json.loads((project / "Packages/manifest.json").read_text())["dependencies"][
            "com.polyforge.engine"
        ]
        == "file:com.polyforge.engine"
    )
    assert (project / "Packages/com.polyforge.engine/Editor/PolyForgeBuilder.cs").is_file()
    before = (project / "Assets/keep.asset").read_bytes()
    assert prepare_project(policy, template) == project
    assert (project / "Assets/keep.asset").read_bytes() == before
    (project / "Packages/manifest.json").write_text("{}")
    with pytest.raises(InputError):
        prepare_project(policy, template)


def test_unity_environment_supplies_owned_profile_without_inherited_secrets(tmp_path: Path):
    from polyforge.security.policy import worker_environment

    env = worker_environment(
        Path("C:/Unity/Unity.exe"),
        tmp_path / "tmp",
        {"LOCALAPPDATA": "C:/private", "TOKEN": "canary"},
        unity_profile=tmp_path / "profile",
    )
    assert env["LOCALAPPDATA"] == "C:/private"
    assert env["APPDATA"] == str(tmp_path / "profile" / "AppData" / "Roaming")
    assert env["USERPROFILE"] == str(tmp_path / "profile")
    assert "TOKEN" not in env


def test_test_xml_rejects_empty_skipped_duplicate_and_wrong_test_runs(tmp_path: Path):
    from polyforge.unity.evidence import verify_test_xml

    names = {"A.One", "A.Two"}
    p = tmp_path / "tests.xml"
    p.write_text(
        '<test-run result="Passed"><test-case fullname="A.One" result="Passed"/>'
        '<test-case fullname="A.Two" result="Passed"/></test-run>'
    )
    assert verify_test_xml(p, names)["executed"] == 2
    for cases in [
        "",
        '<test-case fullname="A.One" result="Skipped"/>',
        '<test-case fullname="B.Other" result="Passed"/>',
        '<test-case fullname="A.One" result="Passed"/>'
        '<test-case fullname="A.One" result="Passed"/>',
    ]:
        p.write_text('<test-run result="Passed">' + cases + "</test-run>")
        with pytest.raises(InputError):
            verify_test_xml(p, names)


def test_observed_report_rejects_stale_identity_missing_guid_and_socket_position(tmp_path: Path):
    import copy

    from polyforge.unity.evidence import reconcile_report

    request = {
        "schema_version": "1.0.0",
        "input_digest": "f" * 64,
        "assets": [
            {
                "id": "robot",
                "bounds_m": [1, 2, 3],
                "sockets": [{"id": "front", "position_m": [0, 1, 1.5]}],
                "materials": [{"id": "blue"}],
            }
        ],
    }
    raw = {
        "schema_version": "1.0.0",
        "input_digest": "f" * 64,
        "unity_version": "6000.6.3f1",
        "verification_scope": "UNITY_EDITOR_STATIC",
        "status": "PASS",
        "issues": [],
        "scene_guids": ["a" * 32, "b" * 32],
        "scene_object_count": 12,
        "objects": [
            {
                "id": "robot",
                "guid": "a" * 32,
                "prefab_guid": "b" * 32,
                "prefab_id": "Assets/PolyForgeGenerated/Prefabs/robot.prefab",
                "bounds_m": [1, 2, 3],
                "socket_ids": ["front"],
                "sockets": [{"id": "front", "position_m": [0, 1, 1.5]}],
                "material_ids": ["blue"],
                "transform_count": 3,
                "nodes": [
                    {
                        "id": "front",
                        "kind": "socket",
                        "path": "robot/front",
                        "guid": "a" * 32,
                        "local_id": 123,
                        "component": "Transform",
                    }
                ],
            }
        ],
    }
    request["scene_bounds_m"] = [20, 5, 20]
    request["assets"][0]["collider"] = "none"
    raw["objects"][0].update(collider="none", colliders=[])
    raw.update(
        camera_count=2,
        light_count=2,
        scene_instances=[
            {
                "scene": scene,
                "id": "asset:robot",
                "asset_id": "robot",
                "prefab_guid": "b" * 32,
                "source_guid": "a" * 32,
                "position_m": [0, 0, 0],
                "scale": [1, 1, 1],
                "rotation_xyzw": [0, 0, 0, 1],
            }
            for scene in ("Arena", "Training")
        ],
    )
    raw["objects"][0]["textures"] = empty_texture_slots("blue")
    assert reconcile_report(request, raw)["status"] == "PASS"
    for mutate in [
        lambda x: x.update(input_digest="0" * 64),
        lambda x: x["objects"][0].update(guid=""),
        lambda x: x["objects"][0]["sockets"][0].update(position_m=[0, 1, -1.5]),
        lambda x: x.update(objects=[]),
    ]:
        value = copy.deepcopy(raw)
        mutate(value)
        assert reconcile_report(request, value)["status"] == "FAIL"


def test_unity_retains_only_os_local_license_root_and_redirects_upm_state(tmp_path: Path):
    from polyforge.security.policy import worker_environment

    env = worker_environment(
        Path("C:/Unity/Unity.exe"),
        tmp_path / "tmp",
        {"LOCALAPPDATA": "C:/actual-license-root", "TOKEN": "canary"},
        unity_profile=tmp_path / "profile",
    )
    assert env["LOCALAPPDATA"] == "C:/actual-license-root"
    assert env["ALLUSERSPROFILE"] == str(tmp_path / "profile" / "ProgramData")
    assert env["UPM_CACHE_ROOT"] == str(tmp_path / "profile" / "upm-cache")
    assert "TOKEN" not in env


def test_unity_keeps_native_activation_profile_but_never_forwards_credentials(tmp_path: Path):
    from polyforge.security.policy import worker_environment

    values = {
        "USERPROFILE": "C:/activated",
        "APPDATA": "C:/activated/roaming",
        "LOCALAPPDATA": "C:/activated/local",
        "PROGRAMDATA": "C:/ProgramData",
        "ALLUSERSPROFILE": "C:/ProgramData",
        "PASSWORD": "do-not-copy",
    }
    env = worker_environment(
        Path("C:/Unity/Unity.exe"), tmp_path / "tmp", values, unity_profile=tmp_path / "profile"
    )
    for key, value in values.items():
        if key != "PASSWORD":
            assert env[key] == value
    assert "PASSWORD" not in env


def test_unity_compiler_parallelism_is_bounded_within_owned_process_budget(tmp_path: Path):
    from polyforge.security.policy import worker_environment

    env = worker_environment(Path("Unity.exe"), tmp_path, {}, unity_profile=tmp_path / "profile")
    assert env["BEE_BUILD_THREADS"] == "2"


def test_managed_snapshot_restores_exact_bytes_and_removes_new_owned_files(tmp_path: Path):
    from polyforge.unity.transactions import ManagedTransaction

    policy = WorkspacePolicy(tmp_path)
    target = tmp_path / "UnityProject/Assets/PolyForgeGenerated"
    target.mkdir(parents=True)
    source = target / "robot.prefab"
    source.write_bytes(b"original-native-bytes")
    (tmp_path / "game_manifest.json").write_text('{"seed":42}')
    tx = ManagedTransaction.create(policy, "test_tx")
    source.write_bytes(b"broken")
    (target / "new.mat").write_bytes(b"new")
    (tmp_path / "game_manifest.json").write_text('{"seed":43}')
    tx.restore()
    assert source.read_bytes() == b"original-native-bytes"
    assert not (target / "new.mat").exists()
    assert (tmp_path / "game_manifest.json").read_text() == '{"seed":42}'
    assert tx.verify_restored()
    with pytest.raises(InputError):
        ManagedTransaction.create(policy, "../escape")
    snapshot = next((tmp_path / "transactions/test_tx/snapshot").rglob("robot.prefab"))
    snapshot.write_bytes(b"corrupted snapshot")
    with pytest.raises(InputError):
        tx.restore()


def test_s4_dry_run_and_unapproved_downloads_never_publish_files(tmp_path: Path):
    from test_foundation import snapshot

    from polyforge.blender.build import build_assets
    from polyforge.workspace import init_workspace

    root = tmp_path / "arena"
    init_workspace(root, "simple_arena")
    before = snapshot(root)
    result = build_assets(root, through="S4", dry_run=True)
    assert result.status == "PASS", result.to_dict()
    assert result.data["through"] == "S4"
    assert snapshot(root) == before
    result = build_assets(root, through="S4")
    assert result.exit_code in {3, 4}, result.to_dict()
    assert snapshot(root) == before


def test_material_edits_keep_geometry_identity_but_shape_edits_invalidate():
    import copy

    from polyforge.blender.recipes import expand_recipe
    from polyforge.unity.bridge import geometry_identity

    recipe = expand_recipe(
        "crate",
        {"schema_version": "1.0.0", "asset_id": "crate", "parameters": {"size_m": [1, 1, 1]}},
        seed=42,
    )
    original = geometry_identity(recipe)
    color = copy.deepcopy(recipe)
    color["materials"][0]["color_rgba"] = [1, 0, 0, 1]
    assert geometry_identity(color) == original
    shape = copy.deepcopy(recipe)
    shape["parameters"]["size_m"] = [2, 1, 1]
    assert geometry_identity(shape) != original


def test_repair_plan_rejects_wrong_manifest_unknown_assets_and_unbounded_paths():
    import copy

    from polyforge.unity.repairs import validate_plan

    request = {"input_digest": "a" * 64, "assets": [{"id": "robot"}]}
    plan = {
        "schema_version": "1.0.0",
        "input_digest": "a" * 64,
        "issue_id": "ISSUE-123",
        "category": "scale",
        "asset_id": "robot",
        "operation": "rebuild_native_binding",
    }
    validate_plan(plan, request)
    for patch in [
        {"input_digest": "b" * 64},
        {"asset_id": "other"},
        {"operation": "run_shell"},
        {"path": "../../outside"},
    ]:
        value = copy.deepcopy(plan)
        value.update(patch)
        with pytest.raises(InputError):
            validate_plan(value, request)


def test_unity_xml_cdata_is_allowed_but_entity_declarations_are_denied(tmp_path: Path):
    from polyforge.unity.evidence import verify_test_xml

    p = tmp_path / "test.xml"
    p.write_text(
        '<test-run result="Passed"><test-case fullname="A.One" result="Passed">'
        "<output><![CDATA[native output]]></output></test-case></test-run>"
    )
    assert verify_test_xml(p, {"A.One"})["executed"] == 1
    p.write_text('<!DOCTYPE x [<!ENTITY sample "unsafe">]><test-run result="Passed"/>')
    with pytest.raises(InputError):
        verify_test_xml(p, set())


def test_project_preflight_denies_busy_editor_and_hardlinked_generated_output(tmp_path: Path):
    from polyforge.unity.bootstrap import check_project_idle

    p = WorkspacePolicy(tmp_path)
    busy = tmp_path / "UnityProject/Temp/UnityLockfile"
    busy.parent.mkdir(parents=True)
    busy.write_text("busy")
    with pytest.raises(InputError):
        check_project_idle(p)
    busy.unlink()
    original = tmp_path / "original"
    original.write_text("untouched")
    target = tmp_path / "UnityProject/Assets/PolyForgeGenerated/outside.fbx"
    target.parent.mkdir(parents=True)
    target.hardlink_to(original)
    with pytest.raises(InputError):
        check_project_idle(p)
    assert original.read_text() == "untouched"


def test_fbx_coordinate_comparison_accepts_micrometres_but_rejects_real_scale_errors():
    from polyforge.blender.interchange import coordinates_match

    assert coordinates_match([20, 0.2, 20], [20, 0.200003, 20])
    assert coordinates_match({"front": [0, 0.1, 10]}, {"front": [0, 0.100002, 10]})
    assert not coordinates_match([20, 0.2, 20], [20, 0.201, 20])
    assert not coordinates_match({"left": [1, 0, 0]}, {"right": [1, 0, 0]})
    assert not coordinates_match([1, 2, 3], [1, 2])
    assert not coordinates_match([1, 2, 3], [1, float("nan"), 3])


def test_reuse_requires_registered_fbx_metrics_and_source_bytes(tmp_path: Path):
    from polyforge.runner.state import atomic_json
    from polyforge.unity.bridge import reusable_export

    p = WorkspacePolicy(tmp_path)
    recipe = {"asset_id": "crate", "materials": [{"id": "base"}]}
    atomic_json(p, "runs/mesh-fake/input.json", {"recipe": recipe, "seed": 42})
    atomic_json(
        p, "runs/mesh-fake/state.json", {"stages": {"S3": {"status": "passed"}}, "updated_utc": "1"}
    )
    atomic_json(p, "runs/mesh-fake/export_binding.json", {})
    atomic_json(p, "runs/mesh-fake/artifacts.json", {"artifacts": []})
    with pytest.raises(InputError):
        reusable_export(p, recipe, 42)


def test_unity_failed_test_process_maps_to_test_exit_seven(tmp_path: Path, monkeypatch):
    from polyforge.config import Config
    from polyforge.contracts.results import ErrorKind
    from polyforge.runner.processes import ProcessOutcome
    from polyforge.unity import bridge

    monkeypatch.setattr(
        bridge,
        "run_process",
        lambda *args, **kwargs: ProcessOutcome(2, "exit", 123, "WINDOWS_JOB", 1, "", "", True),
    )
    with pytest.raises(InputError) as exc:
        bridge.launch(
            WorkspacePolicy(tmp_path),
            Path("Unity.exe"),
            Config(),
            "run",
            "tests",
            output=tmp_path / "tests.xml",
        )
    assert exc.value.kind == ErrorKind.TEST_FAILURE


@pytest.mark.parametrize(
    "field,value,category",
    [
        ("prefab_id", "Assets/User.prefab", "binding"),
        ("bounds_m", [1, 0.02, 3], "scale"),
        ("bounds_m", [1, 2], "scale"),
        ("socket_ids", [], "socket"),
        ("sockets", [], "socket"),
        ("material_ids", [], "material"),
        ("transform_count", 1, "binding"),
        ("nodes", [], "binding"),
    ],
)
def test_native_report_mutations_fail_independent_contract(field, value, category):
    import copy

    from polyforge.unity.evidence import reconcile_report

    request, raw = native_contract_fixture()
    changed = copy.deepcopy(raw)
    changed["objects"][0][field] = value
    result = reconcile_report(request, changed)
    assert result["status"] == "FAIL"
    assert any(x["category"] == category for x in result["issues"])


def native_contract_fixture():
    request = {
        "input_digest": "f" * 64,
        "assets": [
            {
                "id": "robot",
                "bounds_m": [1, 2, 3],
                "modules": [{"id": "body"}],
                "sockets": [{"id": "front", "position_m": [0, 1, 1.5]}],
                "materials": [{"id": "blue"}],
            }
        ],
        "actors": [{"asset_id": "robot"}],
    }
    raw = {
        "schema_version": "1.0.0",
        "input_digest": "f" * 64,
        "unity_version": "6000.6.3f1",
        "verification_scope": "UNITY_EDITOR_STATIC",
        "status": "PASS",
        "issues": [],
        "scene_guids": ["a" * 32, "b" * 32],
        "scene_object_count": 22,
        "objects": [
            {
                "id": "robot",
                "guid": "a" * 32,
                "prefab_guid": "b" * 32,
                "prefab_id": "Assets/PolyForgeGenerated/Prefabs/robot.prefab",
                "bounds_m": [1, 2, 3],
                "socket_ids": ["front"],
                "sockets": [{"id": "front", "position_m": [0, 1, 1.5]}],
                "material_ids": ["blue"],
                "transform_count": 4,
                "nodes": [
                    {
                        "id": "front",
                        "kind": "socket",
                        "path": "model/front",
                        "guid": "a" * 32,
                        "local_id": 123,
                        "component": "Transform",
                    },
                    {
                        "id": "body",
                        "kind": "module",
                        "path": "model/body",
                        "guid": "a" * 32,
                        "local_id": 124,
                        "component": "MeshRenderer",
                    },
                ],
            }
        ],
    }
    request["scene_bounds_m"] = [20, 5, 20]
    request["assets"][0]["collider"] = "box"
    request["actors"] = [{"id": "enemy", "asset_id": "robot", "spawn_xyz": [3, 0, 2]}]
    raw["objects"][0].update(
        collider="box",
        colliders=[
            {
                "kind": "BoxCollider",
                "path": "",
                "enabled": True,
                "is_trigger": False,
                "center_m": [0, 1, 0],
                "size_m": [1, 2, 3],
            }
        ],
    )
    raw.update(
        camera_count=2,
        light_count=2,
        scene_instances=[
            {
                "scene": scene,
                "id": identifier,
                "asset_id": "robot",
                "prefab_guid": "b" * 32,
                "source_guid": "a" * 32,
                "position_m": pose,
                "scale": [1, 1, 1],
                "rotation_xyzw": [0, 0, 0, 1],
            }
            for scene in ("Arena", "Training")
            for identifier, pose in (("asset:robot", [0, 0, 0]), ("actor:enemy", [3, 0, 2]))
        ],
    )
    raw["objects"][0]["textures"] = empty_texture_slots("blue")
    return request, raw


@pytest.mark.parametrize(
    "change,category",
    [
        ({"scene_guids": []}, "scene"),
        ({"scene_guids": ["a" * 32, "a" * 32]}, "scene"),
        ({"scene_object_count": 0}, "scene"),
        ({"scene_object_count": 23}, "scene"),
        ({"status": "FAIL"}, "worker"),
        ({"objects": None}, "contract"),
        (
            {
                "issues": [
                    {
                        "category": "collider",
                        "asset_id": "robot",
                        "expected": "box",
                        "actual": "none",
                    }
                ]
            },
            "collider",
        ),
    ],
)
def test_native_scene_counts_faults_and_incomplete_payloads_fail(change, category):
    from polyforge.unity.evidence import reconcile_report

    request, raw = native_contract_fixture()
    raw.update(change)
    result = reconcile_report(request, raw)
    assert result["status"] == "FAIL"
    assert any(x["category"] == category for x in result["issues"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("guid", "c" * 32),
        ("local_id", 0),
        ("local_id", "123"),
        ("path", ""),
        ("component", "MissingRenderer"),
    ],
)
def test_semantic_node_reference_mutations_are_detected(field, value):
    from polyforge.unity.evidence import reconcile_report

    request, raw = native_contract_fixture()
    assert reconcile_report(request, raw)["status"] == "PASS"
    raw["objects"][0]["nodes"][0][field] = value
    assert reconcile_report(request, raw)["status"] == "FAIL"


def test_native_duplicate_asset_nonobject_report_and_invalid_xml_are_rejected(tmp_path: Path):
    from polyforge.unity.evidence import reconcile_report, verify_test_xml

    request, raw = native_contract_fixture()
    raw["objects"].append(raw["objects"][0])
    assert reconcile_report(request, raw)["status"] == "FAIL"
    assert reconcile_report(request, [])["status"] == "FAIL"
    p = tmp_path / "malformed.xml"
    p.write_text("not XML")
    with pytest.raises(InputError):
        verify_test_xml(p, {"case"})


def test_recorded_repair_evidence_binds_issue_asset_and_attempt_key(tmp_path: Path):
    from polyforge.runner.state import atomic_json
    from polyforge.unity.repairs import resolve_plan

    request = {"input_digest": "a" * 64, "assets": [{"id": "robot"}, {"id": "crate"}]}
    issue = {
        "issue_id": "ISSUE-real",
        "category": "scale",
        "asset_id": "robot",
        "expected": [1, 2, 3],
        "actual": [100, 200, 300],
    }
    policy = WorkspacePolicy(tmp_path)
    atomic_json(
        policy, ".polyforge/unity-issues.json", {"input_digest": "a" * 64, "issues": [issue]}
    )
    plan = {
        "schema_version": "1.0.0",
        "input_digest": "a" * 64,
        "issue_id": "ISSUE-real",
        "category": "scale",
        "asset_id": "robot",
        "operation": "rebuild_native_binding",
    }
    key = resolve_plan(policy, plan, request)
    assert len(key) == 64
    for field, value in [
        ("issue_id", "ISSUE-forged"),
        ("asset_id", "crate"),
        ("category", "material"),
    ]:
        changed = {**plan, field: value}
        with pytest.raises(InputError):
            resolve_plan(policy, changed, request)


def test_scoped_repair_and_rollback_compare_faulty_baseline():
    from polyforge.unity.repairs import equivalent_bindings, scoped_verification

    baseline = {
        "status": "FAIL",
        "issues": [
            {"category": "scale", "asset_id": "robot", "expected": "1", "actual": "100"},
            {"category": "material", "asset_id": "crate", "expected": "blue", "actual": "missing"},
        ],
    }
    after = {"status": "FAIL", "issues": [baseline["issues"][1]]}
    assert scoped_verification(baseline, after, "robot")
    assert not scoped_verification(baseline, baseline, "robot")
    assert not scoped_verification(
        baseline,
        {"issues": [{"category": "socket", "asset_id": "crate", "expected": "a", "actual": "b"}]},
        "robot",
    )
    assert equivalent_bindings(
        {"bounds": [1, 2, 3], "guid": "same"}, {"bounds": [1.00001, 2, 3], "guid": "same"}
    )
    assert not equivalent_bindings({"guid": "same"}, {"guid": "other"})


def test_reconciliation_requires_frozen_source_hash_before_native_launch(tmp_path: Path):
    from polyforge.contracts.results import ErrorKind
    from polyforge.unity.repairs import verify_source_hashes

    p = WorkspacePolicy(tmp_path)
    target = p.mkdir("UnityProject/Assets/PolyForgeGenerated/Models") / "robot.fbx"
    target.write_bytes(b"changed geometry same bounds")
    with pytest.raises(InputError) as exc:
        verify_source_hashes(
            p,
            {
                "assets": [
                    {
                        "id": "robot",
                        "fbx_path": "Assets/PolyForgeGenerated/Models/robot.fbx",
                        "sha256": "0" * 64,
                    }
                ]
            },
        )
    assert exc.value.kind == ErrorKind.CONTRACT_FAILURE
    assert exc.value.code == "PF-UNITY-SOURCE-IDENTITY"


def test_unapproved_s4_remains_model_free_on_hosts_without_unity(tmp_path: Path, monkeypatch):
    from polyforge.blender.build import build_assets
    from polyforge.unity import bridge
    from polyforge.workspace import init_workspace

    root = tmp_path / "arena"
    init_workspace(root, "simple_arena")
    monkeypatch.setattr(bridge, "discover_tool", lambda *args: None)
    assert build_assets(root, through="S4").exit_code == 4


def empty_texture_slots(material):
    return [
        dict(
            material_id=material,
            kind=role,
            path="",
            sha256="",
            srgb=False,
            texture_type="missing",
            material_texture_path="",
            has_texture=False,
            normal_keyword=False,
            convert_to_normal=False,
        )
        for role in ("base_color", "normal")
    ]
