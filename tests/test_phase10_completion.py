"""Regression cases for omissions found by the blueprint completeness audit."""

import copy

import pytest

from polyforge.contracts.validation import InputError
from polyforge.knowledge.catalog import catalog_cards, validate_cards
from polyforge.knowledge.router import route_reference
from polyforge.security.paths import WorkspacePolicy


@pytest.mark.parametrize(
    "query",
    [
        "Explain ScriptableObject architecture patterns",
        "Explain Unity assembly definition architecture",
        "Explain URP package compatibility",
    ],
)
def test_missing_specialties_route_to_reference_only_without_execution(tmp_path, query):
    result = route_reference(
        WorkspacePolicy(tmp_path), {"schema_version": "1.0.0", "query": query, "output": "EXPLAIN"}
    )
    assert result["status"] == "PASS"
    assert result["cards"] and not result["capability_ids"]
    assert all(c["support_state"] == "REFERENCE_ONLY" for c in result["cards"])
    assert not list(tmp_path.iterdir())


def test_package_applicability_has_exact_pins_and_rejects_unbounded_names():
    cards = catalog_cards()
    package = next((c for c in cards if c["knowledge_id"] == "unity.packages"), None)
    assert package is not None
    assert package["package_versions"]["com.unity.render-pipelines.universal"]
    invalid = copy.deepcopy(cards)
    invalid[-1]["package_versions"] = {"../shell": ["*"]}
    with pytest.raises(InputError):
        validate_cards(invalid)


def test_new_sprite_art_does_not_route_to_import_based_on_count(tmp_path):
    result = route_reference(
        WorkspacePolicy(tmp_path),
        {"schema_version": "1.0.0", "query": "Draw six new dragon sprites", "output": "SPRITE"},
    )
    assert result["status"] == "REVIEW"
    assert result["capability_ids"] == []


def test_package_probe_distinguishes_requested_resolved_and_cached_versions(tmp_path):
    import json

    from polyforge.knowledge.availability import probe_packages

    project = tmp_path / "Project"
    for relative, value in {
        "Packages/manifest.json": {
            "dependencies": {"com.unity.render-pipelines.universal": "17.6.0"}
        },
        "Packages/packages-lock.json": {
            "dependencies": {"com.unity.render-pipelines.universal": {"version": "17.6.0"}}
        },
        "Library/PackageCache/com.unity.render-pipelines.universal@abc/package.json": {
            "name": "com.unity.render-pipelines.universal",
            "version": "17.3.0",
        },
    }.items():
        path = project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
    before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    result = probe_packages(WorkspacePolicy(tmp_path), "Project")
    urp = result["packages"]["com.unity.render-pipelines.universal"]
    assert urp["requested"] == "17.6.0" and urp["resolved"] == "17.6.0"
    assert urp["cached"] == ["17.3.0"] and urp["status"] == "MISMATCH"
    assert result["api_compatibility"] == "UNKNOWN"
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == before
    with pytest.raises(InputError):
        probe_packages(WorkspacePolicy(tmp_path), "../escape")


def test_package_probe_missing_cache_does_not_claim_installed(tmp_path):
    from polyforge.knowledge.availability import probe_packages

    result = probe_packages(WorkspacePolicy(tmp_path), ".")
    assert result["status"] == "UNKNOWN" and result["packages"] == {}
    assert not list(tmp_path.iterdir())


def test_package_cache_mismatch_is_reported_without_lockfile(tmp_path):
    import json

    from polyforge.knowledge.availability import probe_packages

    for relative, value in {
        "Packages/manifest.json": {"dependencies": {"com.unity.test-framework": "1.8.0"}},
        "Library/PackageCache/test/package.json": {
            "name": "com.unity.test-framework",
            "version": "1.7.0",
        },
    }.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")
    result = probe_packages(WorkspacePolicy(tmp_path), ".")
    assert result["packages"]["com.unity.test-framework"]["status"] == "MISMATCH"


def test_package_inspection_handles_posix_file_parent_errors(tmp_path, monkeypatch):
    from pathlib import Path

    from polyforge.knowledge.availability import probe_packages

    packages = tmp_path / "Packages"
    packages.mkdir()
    (packages / "manifest.json").write_text('{"dependencies":{}}', encoding="utf-8")
    original = Path.lstat

    # POSIX raises ENOTDIR for a/file.json/package.json; Windows may return ENOENT.
    def posix_lstat(path, *args, **kwargs):
        if path.name == "package.json" and path.parent.is_file():
            raise NotADirectoryError(str(path))
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", posix_lstat)
    assert probe_packages(WorkspacePolicy(tmp_path), ".")["status"] == "OBSERVED"


def test_host_probe_missing_binary_is_explicitly_blocked(tmp_path, monkeypatch):
    from polyforge.knowledge import availability

    monkeypatch.setattr(availability, "host_binary", lambda name: None)
    result = availability.probe_host(WorkspacePolicy(tmp_path), "codex")
    assert result["status"] == "BLOCKED"
    assert result["role_delegation"] == "UNKNOWN"
    assert not list(tmp_path.iterdir())


def test_host_feature_observation_never_promotes_actual_delegation():
    from polyforge.knowledge.availability import host_observation

    result = host_observation("codex", "multi_agent experimental true\nshell_tool stable true\n", 0)
    assert result["delegation_feature"] == "ENABLED"
    assert result["role_delegation"] == "UNKNOWN"
    assert (
        host_observation("codex", "multi_agent experimental false\n", 0)["delegation_feature"]
        == "DISABLED"
    )
    assert host_observation("codex", "", 1)["status"] == "BLOCKED"


@pytest.mark.parametrize(
    "metadata", [[], {"dependencies": []}, {"dependencies": {str(i): "1.0.0" for i in range(513)}}]
)
def test_invalid_or_oversized_package_metadata_is_denied(tmp_path, metadata):
    import json

    from polyforge.knowledge.availability import probe_packages

    packages = tmp_path / "Packages"
    packages.mkdir()
    (packages / "manifest.json").write_text(json.dumps(metadata), encoding="utf-8")
    with pytest.raises(InputError):
        probe_packages(WorkspacePolicy(tmp_path), ".")


def test_failed_native_host_probe_retains_evidence_without_claiming_delegation(
    tmp_path, monkeypatch
):
    import sys
    from pathlib import Path

    from polyforge.contracts.validation import load_json
    from polyforge.knowledge import availability

    # An installed process that rejects the fixed query is an external tool failure.
    monkeypatch.setattr(availability, "host_binary", lambda name: Path(sys.executable))
    result = availability.probe_host(WorkspacePolicy(tmp_path), "codex")
    assert result["status"] == "BLOCKED" and result["role_delegation"] == "UNKNOWN"
    record = load_json(tmp_path / result["evidence_path"])
    assert record["outcome"]["returncode"] != 0
    assert record["argv"][1:] == ["features", "list"]
    with pytest.raises(InputError):
        availability.host_observation("shell", "enabled", 0)


def test_unity_ui_probe_is_a_separate_fixed_probe_and_dry_run_is_pure(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    from polyforge.knowledge import probes

    monkeypatch.setattr(probes, "discover_tool", lambda *a: Path(sys.executable))
    value = probes.probe_tool(tmp_path, "unity-ui", dry_run=True)
    assert value.data["probe_id"] == "unity.editor-window.v1"
    assert value.data["execution_status"] == "NOT_RUN"
    args = probes._args(WorkspacePolicy(tmp_path), Path(sys.executable), "unity-ui", "runs/test")
    assert "-batchmode" not in args and "-nographics" not in args
    with pytest.raises(InputError):
        probes.validate_observation("unity-ui", {"checks": {"window_painted": True}})
    assert not list(tmp_path.iterdir())
