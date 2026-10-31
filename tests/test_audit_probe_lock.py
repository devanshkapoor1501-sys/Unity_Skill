"""Regression checks for conservative inventory and workspace provenance publication."""

from __future__ import annotations

import importlib
import json
from dataclasses import asdict

import pytest
from test_foundation import snapshot
from test_phase2_contracts import arena

from polyforge.compiler.commands import manifest_command
from polyforge.config import load_config
from polyforge.contracts.manifest import load_manifest
from polyforge.contracts.validation import InputError, canonical_digest


def test_graphics_inventory_observes_windows_metadata_without_render_claim(monkeypatch):
    doctor = importlib.import_module("polyforge.doctor")

    class User32:
        def GetSystemMetrics(self, index):
            return 2

        def EnumDisplayDevicesW(self, unused, index, output, flags):
            if index:
                return 0
            output._obj.DeviceString = "Fixture GPU"
            output._obj.DeviceName = "DISPLAY1"
            output._obj.StateFlags = 1
            return 1

    monkeypatch.setattr(doctor.sys, "platform", "win32")
    monkeypatch.setattr(doctor.ct, "WinDLL", lambda *a, **k: User32(), raising=False)
    detector = getattr(doctor, "graphics_availability", None)
    assert callable(detector), "doctor needs an actual read-only graphics detector"
    observed = detector()
    assert observed["display"]["status"] == "OBSERVED"
    assert observed["display"]["count"] == 2
    assert observed["gpu"]["devices"][0]["name"] == "Fixture GPU"
    assert observed["render"]["status"] == "NOT_RUN"
    assert observed["headless_render"]["status"] == "UNKNOWN"


def test_graphics_unavailable_api_remains_unknown(monkeypatch):
    doctor = importlib.import_module("polyforge.doctor")
    monkeypatch.setattr(doctor.sys, "platform", "win32")

    def unavailable(*args, **kwargs):
        raise OSError("no API")

    monkeypatch.setattr(doctor.ct, "WinDLL", unavailable, raising=False)
    detector = getattr(doctor, "graphics_availability", None)
    assert callable(detector), "missing metadata must remain an explicit unknown"
    observed = detector()
    assert observed["display"]["status"] == "UNKNOWN"
    assert observed["gpu"]["status"] == "UNKNOWN"


def test_explicit_mcp_inventory_is_metadata_and_rejects_remote_or_secret_endpoints():
    doctor = importlib.import_module("polyforge.doctor")
    inventory = getattr(doctor, "integration_availability", None)
    assert callable(inventory), "interactive inventory must accept explicit caller observations"
    unknown = inventory({})
    assert unknown["matrix"]["interactive_scene_edit"]["assisted"] == "UNKNOWN"
    assert unknown["matrix"]["plan"]["offline"] == "OBSERVED"
    sessions = [
        {
            "tool": "blender",
            "transport": "http",
            "endpoint": "http://127.0.0.1:8080/mcp",
            "connected": True,
            "operations": ["interactive_scene_edit"],
        }
    ]
    observed = inventory({}, sessions=sessions)
    assert observed["matrix"]["interactive_scene_edit"]["assisted"] == "OBSERVED"
    assert observed["execution_authority"] == "NONE"
    assert observed["operational_probe"] == "NOT_RUN"
    assert "endpoint" not in observed["host_sessions"][0]
    for endpoint in [
        "https://example.com/mcp",
        "http://user:secret@localhost:80/mcp",
        "http://localhost:80/mcp?token=secret",
        "http://127.0.0.2:80/mcp",
    ]:
        with pytest.raises(InputError):
            inventory({}, sessions=[{**sessions[0], "endpoint": endpoint}])


@pytest.mark.parametrize("field", ["tool", "transport"])
def test_malformed_mcp_field_types_are_recoverable_without_writes(tmp_path, field):
    doctor = importlib.import_module("polyforge.doctor")
    session = {"tool": "blender", "transport": "stdio", "connected": False, "operations": []}
    session[field] = []
    before = snapshot(tmp_path)
    with pytest.raises(InputError):
        doctor.doctor(tmp_path, mcp_sessions=[session])
    assert snapshot(tmp_path) == before


def test_plan_publishes_canonical_lock_without_running_tools(tmp_path, monkeypatch):
    arena(tmp_path)
    doctor = importlib.import_module("polyforge.doctor")
    monkeypatch.setattr(doctor, "discover_tool", lambda *args: None)
    before = snapshot(tmp_path)
    result = manifest_command(tmp_path / "game_manifest.json", "plan", dry_run=True)
    assert "polyforge.lock.json" in result.data["planned_writes"]
    assert snapshot(tmp_path) == before
    manifest_command(tmp_path / "game_manifest.json", "plan")
    lock = json.loads((tmp_path / "polyforge.lock.json").read_text())
    assert lock["manifest_digest"] == load_manifest(tmp_path / "game_manifest.json").digest
    assert lock["seed"] == 42
    assert lock["tools"]["blender"]["version_status"] == "UNPROBED"
    assert lock["packages"]["status"] == "UNPROBED"
    assert len(lock["engine"]["source_sha256"]) == 64
    assert lock["execution_authority"] == "NONE"
    manifest_command(tmp_path / "game_manifest.json", "compile")
    manifest_command(tmp_path / "game_manifest.json", "plan")


def test_lock_only_uses_version_report_for_matching_config_and_binary(tmp_path, monkeypatch):
    from polyforge.runner.workspace_lock import binary_identity, build_workspace_lock

    arena(tmp_path)
    executable = tmp_path / "blender.exe"
    executable.write_bytes(b"fixture binary; never executed")
    doctor = importlib.import_module("polyforge.doctor")
    monkeypatch.setattr(doctor, "discover_tool", lambda name, override: executable)
    config = load_config()
    report = {
        "data": {
            "config_digest": canonical_digest(asdict(config)),
            "tools": {
                "blender": {
                    "status": "PASS",
                    "path": str(executable),
                    "version": "5.0.0",
                    "binary_identity": binary_identity(executable),
                }
            },
        }
    }
    (tmp_path / "doctor.json").write_text(json.dumps(report))
    before = snapshot(tmp_path)
    model = load_manifest(tmp_path / "game_manifest.json")
    lock = build_workspace_lock(model)
    assert lock["tools"]["blender"]["version"] == "5.0.0"
    assert lock["tools"]["blender"]["version_status"] == "OBSERVED_REPORT"
    assert lock["tools"]["unity"]["version_status"] == "UNPROBED"
    assert snapshot(tmp_path) == before
    executable.write_bytes(b"changed binary")
    assert build_workspace_lock(model)["tools"]["blender"]["version_status"] == "UNPROBED"
    report["data"]["config_digest"] = "0" * 64
    (tmp_path / "doctor.json").write_text(json.dumps(report))
    assert build_workspace_lock(model)["tools"]["blender"]["version"] is None
    report["data"]["config_digest"] = canonical_digest(asdict(config))
    report["data"]["tools"]["blender"]["binary_identity"] = binary_identity(executable)
    report["data"]["tools"]["blender"]["version"] = "arbitrary secret data"
    (tmp_path / "doctor.json").write_text(json.dumps(report))
    assert build_workspace_lock(model)["tools"]["blender"]["version_status"] == "UNPROBED"


def test_lock_static_packages_distinguish_requested_from_installed_evidence(tmp_path, monkeypatch):
    from polyforge.runner.workspace_lock import build_workspace_lock

    arena(tmp_path)
    doctor = importlib.import_module("polyforge.doctor")
    monkeypatch.setattr(doctor, "discover_tool", lambda *args: None)
    project = tmp_path / "UnityProject"
    (project / "ProjectSettings").mkdir(parents=True)
    (project / "Packages").mkdir()
    (project / "ProjectSettings/ProjectVersion.txt").write_text("m_EditorVersion: 6000.6.3f1\n")
    (project / "Packages/manifest.json").write_text(
        json.dumps(
            {
                "dependencies": {
                    "com.unity.render-pipelines.universal": "17.6.0",
                    "com.unity.test-framework": "1.8.0",
                }
            }
        )
    )
    before = snapshot(tmp_path)
    lock = build_workspace_lock(load_manifest(tmp_path / "game_manifest.json"))
    assert lock["unity_project"]["version"] == "6000.6.3f1"
    assert lock["packages"]["status"] == "OBSERVED"
    assert lock["packages"]["packages"]["com.unity.test-framework"]["status"] == "UNKNOWN"
    assert lock["packages"]["api_compatibility"] == "UNKNOWN"
    assert snapshot(tmp_path) == before


def test_modified_lock_and_invalid_config_do_not_partially_publish(tmp_path, monkeypatch):
    arena(tmp_path)
    doctor = importlib.import_module("polyforge.doctor")
    monkeypatch.setattr(doctor, "discover_tool", lambda *args: None)
    path = tmp_path / "game_manifest.json"
    manifest_command(path, "plan")
    lock = tmp_path / "polyforge.lock.json"
    lock.write_text("user edit")
    before = snapshot(tmp_path)
    with pytest.raises(InputError):
        manifest_command(path, "plan")
    assert snapshot(tmp_path) == before
    lock.unlink()
    (tmp_path / "polyforge.toml").write_text("[tools]\nunknown=true\n")
    before = snapshot(tmp_path)
    with pytest.raises(InputError):
        manifest_command(path, "plan", dry_run=True)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("collision", ["user_lock", "parent_file", "manifest_input"])
def test_new_lock_destination_preflight_preserves_all_inputs(tmp_path, collision):
    arena(tmp_path)
    if collision == "user_lock":
        (tmp_path / "polyforge.lock.json").write_text("user content")
    elif collision == "parent_file":
        (tmp_path / ".polyforge").write_text("user content")
    else:
        (tmp_path / "game_manifest.json").rename(tmp_path / "polyforge.lock.json")
    before = snapshot(tmp_path)
    path = tmp_path / (
        "polyforge.lock.json" if collision == "manifest_input" else "game_manifest.json"
    )
    with pytest.raises(InputError):
        manifest_command(path, "plan")
    assert snapshot(tmp_path) == before
