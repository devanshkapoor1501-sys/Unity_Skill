"""Read-only observations for the canonical workspace provenance snapshot."""

from __future__ import annotations

import hashlib
import platform
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

import polyforge
from polyforge.config import load_config
from polyforge.contracts.manifest import Manifest
from polyforge.contracts.validation import canonical_digest, load_json
from polyforge.security.paths import WorkspacePolicy


def binary_identity(path: Path) -> dict[str, Any]:
    """Hash a present bounded binary without executing it or loading its libraries."""
    try:
        info = path.stat()
        if not path.is_file() or info.st_size > 536_870_912:
            return {"status": "UNPROBED"}
        digest = hashlib.sha256()
        consumed = 0
        with path.open("rb") as stream:
            while block := stream.read(1_048_576):
                consumed += len(block)
                if consumed > 536_870_912:
                    return {"status": "UNPROBED"}
                digest.update(block)
        after = path.stat()
        if (info.st_size, info.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            return {"status": "UNPROBED"}
        return {"status": "OBSERVED", "sha256": digest.hexdigest(), "bytes": info.st_size}
    except OSError:
        return {"status": "UNPROBED"}


def build_workspace_lock(model: Manifest) -> dict[str, Any]:
    """Snapshot local metadata; version/report observations are never execution approval."""
    from polyforge.doctor import discover_tool, inspect_project
    from polyforge.knowledge.availability import probe_packages

    policy = WorkspacePolicy(model.workspace)
    config_path = policy.path("polyforge.toml")
    config = load_config(config_path if config_path.is_file() else None)
    config_digest = canonical_digest(asdict(config))
    report_path = policy.path("doctor.json")
    report = load_json(report_path) if report_path.is_file() else {}
    report_data = report.get("data", {}) if isinstance(report, dict) else {}
    if not isinstance(report_data, dict) or report_data.get("config_digest") != config_digest:
        report_data = {}
    reported_tools = report_data.get("tools", {})
    if not isinstance(reported_tools, dict):
        reported_tools = {}
    tools = {}
    for name, override in (
        ("blender", config.blender_executable),
        ("unity", config.unity_executable),
    ):
        path = discover_tool(name, override)
        identity = binary_identity(path) if path is not None else {"status": "UNPROBED"}
        prior = reported_tools.get(name, {})
        observed = (
            isinstance(prior, dict)
            and prior.get("status") == "PASS"
            and prior.get("path") == str(path)
            and identity["status"] == "OBSERVED"
            and prior.get("binary_identity") == identity
            and isinstance(prior.get("version"), str)
            and re.fullmatch(
                r"5\.\d+\.\d+" if name == "blender" else r"6000\.\d+\.\d+[a-z]\d+",
                prior["version"],
            )
            is not None
        )
        tools[name] = {
            "path": str(path) if path is not None else None,
            "binary_identity": identity,
            "version": prior["version"] if observed else None,
            "version_status": "OBSERVED_REPORT" if observed else "UNPROBED",
            "version_evidence": "doctor.json" if observed else None,
        }
    project_path = policy.path("UnityProject")
    project = inspect_project(project_path) if project_path.is_dir() else {"status": "UNPROBED"}
    packages = (
        probe_packages(policy, "UnityProject")
        if project_path.is_dir()
        else {"status": "UNPROBED", "packages": {}}
    )
    source = Path(polyforge.__file__)
    return {
        "schema_version": "1.0.0",
        "owner": "polyforge.workspace_lock.v1",
        "project_id": model.data["project"]["id"],
        "manifest_digest": model.digest,
        "input_digest": model.input_digest,
        "inputs": model.input_fingerprints,
        "seed": model.data["project"]["seed"],
        "config_digest": config_digest,
        "engine": {
            "version": polyforge.__version__,
            "python_version": platform.python_version(),
            "source_component": "polyforge/__init__.py",
            "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        },
        "tools": tools,
        "unity_project": project,
        "packages": packages,
        "execution_authority": "NONE",
        "qualification": "Local metadata snapshot; no tool launch, package resolution or network",
    }
