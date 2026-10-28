"""Boundary regressions from the one fresh Phase 8 review."""

import copy
import hashlib
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from test_assets import spec
from test_sprites import sample

from polyforge.assets.contracts import inspect_bundle, seal_bundle
from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import Result
from polyforge.contracts.validation import InputError, canonical_digest
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.sprites.images import atlas
from polyforge.sprites.integration import EDIT_TESTS, PLAY_TESTS, import_strip
from polyforge.workforce.workers import inspect_candidate, seal_candidate


def asset_fixture(tmp_path, value=None):
    value = spec() if value is None else value
    folder = tmp_path / "runs/asset_native/asset"
    folder.mkdir(parents=True)
    for name in ("metrics.json", "logical-geometry.json", "material.json"):
        shutil.copyfile(Path(__file__).parent / "fixtures/phase8" / name, folder / name)
    (folder / "source.blend").write_bytes(b"unit-fixture-source")
    (folder / "asset.fbx").write_bytes(b"unit-fixture-export")
    slots = {
        key: (folder / name).relative_to(tmp_path).as_posix()
        for key, name in {
            "geometry_source": "source.blend",
            "export": "asset.fbx",
            "uv_source": "logical-geometry.json",
            "geometry_metrics": "metrics.json",
            "material_source": "material.json",
        }.items()
    }
    return value, seal_bundle(tmp_path, value, slots, revision=1, producer="modeler")


def rehash(bundle):
    bundle["revision_digest"] = canonical_digest(
        {k: v for k, v in bundle.items() if k != "revision_digest"}
    )
    return bundle


@pytest.mark.parametrize("change", ["omit", "license", "authority", "substitute"])
def test_approved_bundle_cannot_drop_or_substitute_reference_provenance(tmp_path, change):
    reference = tmp_path / "concept.txt"
    reference.write_text("A visual style reference is data only.")
    value = spec()
    value["references"] = [
        {
            "kind": "STYLE",
            "path": "concept.txt",
            "sha256": hashlib.sha256(reference.read_bytes()).hexdigest(),
            "license": "CC0-1.0",
            "authority": "DATA_ONLY",
        }
    ]
    value, bundle = asset_fixture(tmp_path, value)
    assert inspect_bundle(tmp_path, bundle, value)["technical_verdict"] == "APPROVED"
    bundle = copy.deepcopy(bundle)
    if change == "omit":
        bundle["dependencies"] = []
    elif change == "substitute":
        bundle["dependencies"][0]["path"] = "different.txt"
    elif change == "license":
        bundle["dependencies"][0]["license"] = "MISSING"
    else:
        bundle["dependencies"][0]["authority"] = "EXECUTE"
    with pytest.raises(InputError):
        inspect_bundle(tmp_path, rehash(bundle), value)


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown", "mapping"])
def test_material_bindings_require_complete_unique_expected_ids(tmp_path, change):
    value, bundle = asset_fixture(tmp_path)
    source = tmp_path / bundle["slots"]["material_source"]["path"]
    material = json.loads(source.read_text("utf-8"))
    if change == "missing":
        material["materials"] = material["materials"][:1]
    elif change == "duplicate":
        material["materials"].append(copy.deepcopy(material["materials"][0]))
    elif change == "unknown":
        material["materials"][0]["id"] = "unknown"
    else:
        material["module_materials"] = {"wrong_module": ["base"]}
    source.write_text(json.dumps(material), encoding="utf-8")
    bundle["slots"]["material_source"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(InputError):
        inspect_bundle(tmp_path, rehash(bundle), value)


@pytest.mark.parametrize(
    "tolerance,delta,accepted", [(0.000001, 0.000005, False), (0.001, 0.0005, True)]
)
def test_declared_dimension_tolerance_is_an_actual_acceptance_boundary(
    tmp_path, tolerance, delta, accepted
):
    value = spec()
    value["rubric"]["dimension_tolerance_m"] = tolerance
    value, bundle = asset_fixture(tmp_path, value)
    source = tmp_path / bundle["slots"]["geometry_metrics"]["path"]
    metrics = json.loads(source.read_text("utf-8"))
    metrics["bounds_unity_m"][0] += delta
    source.write_text(json.dumps(metrics), encoding="utf-8")
    bundle["slots"]["geometry_metrics"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    if accepted:
        assert inspect_bundle(tmp_path, rehash(bundle), value)["technical_verdict"] == "APPROVED"
    else:
        with pytest.raises(InputError):
            inspect_bundle(tmp_path, rehash(bundle), value)


def sprite_fixture(tmp_path, prefix=""):
    policy = WorkspacePolicy(tmp_path)
    folder = policy.mkdir(prefix) if prefix else tmp_path
    frames = [sample(i) for i in range(6)]
    metadata = {
        "schema_version": "1.0.0",
        "asset_id": "robot_a",
        "frame_size": 32,
        "frame_count": 6,
        "pixels_per_unit": 64,
        "fps": 6,
        "pivot": [0.5, 0.1],
        "trim": "NONE",
        "order": list(range(6)),
        "frame_sha256": [hashlib.sha256(f).hexdigest() for f in frames],
        "source_sha256": "a" * 64,
        "framing": "FIXED_ORTHOGRAPHIC",
        "source_license": "CC0-1.0",
    }
    for i, frame in enumerate(frames):
        (folder / f"frame-{i}.png").write_bytes(frame)
    (folder / "atlas.png").write_bytes(atlas(frames))
    (folder / "atlas.json").write_text(json.dumps(metadata), encoding="utf-8")

    def relative(name):
        return (folder / name).relative_to(tmp_path).as_posix()

    request = {
        "schema_version": "1.0.0",
        "asset_id": "robot_a",
        "source_kind": "DIRECT_SPRITES",
        "atlas_file": relative("atlas.png"),
        "metadata_file": relative("atlas.json"),
        "frame_files": [relative(f"frame-{i}.png") for i in range(6)],
    }
    return policy, request, metadata


@pytest.mark.parametrize("prefix", ["", "inputs/sprites"])
def test_direct_sprite_input_paths_do_not_define_the_production_run(tmp_path, prefix):
    policy, inputs, metadata = sprite_fixture(tmp_path, prefix)
    run = "sprite-unity-native"
    folder = policy.mkdir("runs/" + run)
    for name, expected in [("editmode.xml", EDIT_TESTS), ("playmode.xml", PLAY_TESTS)]:
        root = ET.Element("test-run", result="Passed")
        for test in sorted(expected):
            ET.SubElement(root, "test-case", fullname=test, result="Passed")
        (folder / name).write_bytes(ET.tostring(root))
    (folder / "bindings.json").write_text(
        json.dumps({"metadata_digest": canonical_digest(metadata)}), encoding="utf-8"
    )
    paths = [
        inputs["metadata_file"],
        inputs["atlas_file"],
        *inputs["frame_files"],
        *[f"runs/{run}/{n}" for n in ("bindings.json", "editmode.xml", "playmode.xml")],
    ]
    atomic_json(
        policy,
        "runs/" + run + "/artifacts.json",
        {
            "artifacts": [
                {
                    "relative_path": p,
                    "sha256": hashlib.sha256(policy.path(p).read_bytes()).hexdigest(),
                }
                for p in paths
            ]
        },
    )
    task = {
        "schema_version": "1.0.0",
        "brief": "Use existing sprites directly in Unity.",
        "task_class": "CREATE_ASSET",
        "domain_tags": ["unity", "2d"],
        "feature_ids": [],
        "capability_id": "sprite.unity.strip.v1",
        "input": inputs,
    }
    candidate = seal_candidate(policy, Result(run_id=run), canonical_digest(task["brief"]))
    assert inspect_candidate(policy, candidate, task)["verdict"] == "APPROVED"


def test_existing_project_without_package_authorization_cannot_launch_unity(tmp_path, monkeypatch):
    import polyforge.sprites.integration as module

    policy, inputs, metadata = sprite_fixture(tmp_path)
    # Reach policy admission without spending a native process on this unit fixture.
    metadata["frame_size"] = 128
    (tmp_path / "atlas.json").write_text(json.dumps(metadata), encoding="utf-8")
    monkeypatch.setattr(module, "inspect_strip", lambda *args: {"status": "PASS"})
    monkeypatch.setattr(module, "unity_tool", lambda config: Path("Unity.exe"))
    monkeypatch.setattr(module, "installed_template", lambda tool: Path("template.tgz"))
    project = policy.mkdir("UnityProject")
    monkeypatch.setattr(module, "prepare_project", lambda *args, **kwargs: project)
    monkeypatch.setattr(module, "check_project_idle", lambda *args: None)

    def forbidden(*args, **kwargs):
        raise AssertionError("Unauthorized project reached native synchronization")

    monkeypatch.setattr(module, "sync_package", forbidden)
    with pytest.raises(InputError) as failure:
        import_strip(inputs, RunContext(tmp_path))
    assert int(failure.value.kind) == 4


def test_sprite_operation_cache_rejects_changed_input_files(tmp_path):
    from polyforge.workforce.operations import complete, operation_context, recover

    policy, inputs, _ = sprite_fixture(tmp_path)
    folder = policy.mkdir("runs/sprite_cache")
    (folder / "output.json").write_text("{}")
    context = operation_context(tmp_path, "sprite_task", "produce", 42, None)
    complete("sprite.unity.strip.v1", inputs, context, Result(run_id="sprite_cache"))
    assert recover("sprite.unity.strip.v1", inputs, context).status == "PASS"
    (tmp_path / inputs["metadata_file"]).write_text('{"changed":true}')
    with pytest.raises(InputError):
        recover("sprite.unity.strip.v1", inputs, context)


def test_unchanged_fresh_package_records_baseline_before_later_upgrade(tmp_path):
    from polyforge.unity.upgrade import sync_package

    policy = WorkspacePolicy(tmp_path)
    package = policy.mkdir("UnityProject/Packages/com.polyforge.engine")
    (package / "Runtime.cs").write_bytes(b"fresh trusted engine code")
    sync_package(policy, {"Runtime.cs": b"fresh trusted engine code"})
    assert sync_package(policy, {"Runtime.cs": b"upgraded trusted engine code"}) is not None
    assert (package / "Runtime.cs").read_bytes() == b"upgraded trusted engine code"
    (package / "Runtime.cs").write_bytes(b"unrecorded local change")
    with pytest.raises(InputError):
        sync_package(policy, {"Runtime.cs": b"another engine version"})
