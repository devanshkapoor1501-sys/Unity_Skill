"""Local availability observations; neither configuration nor caches prove execution."""

from __future__ import annotations

import re
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.knowledge.probes import read_probe
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy

VERSION = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?")
PACKAGE = re.compile(r"com\.[a-z0-9]+(?:[.-][a-z0-9]+)+")


def probe_packages(policy: WorkspacePolicy, project: str) -> dict[str, Any]:
    root = policy.path(project)
    requested: dict[str, Any] = {}
    resolved: dict[str, Any] = {}
    cached: dict[str, set[str]] = {}
    evidence = []
    for relative, target in [
        ("Packages/manifest.json", requested),
        ("Packages/packages-lock.json", resolved),
    ]:
        path = policy.path(root / relative)
        if path.is_file():
            value = load_json(path)
            if not isinstance(value, dict) or not isinstance(value.get("dependencies"), dict):
                raise InputError("Package metadata requires a dependencies object")
            if len(value["dependencies"]) > 512:
                raise InputError("Package inspection exceeds 512 dependencies")
            target.update(value["dependencies"])
            evidence.append(
                {
                    "path": path.relative_to(policy.root).as_posix(),
                    "digest": canonical_digest(value),
                }
            )
    for relative in ["Library/PackageCache", "Packages"]:
        directory = policy.path(root / relative)
        if not directory.is_dir():
            continue
        for index, child in enumerate(directory.iterdir()):
            if index >= 512:
                raise InputError("Package inspection exceeds 512 cache entries")
            child = policy.path(child)
            if not child.is_dir():
                continue
            path = policy.path(child / "package.json")
            if not path.is_file():
                continue
            value = load_json(path)
            if not isinstance(value, dict):
                raise InputError("Cached package metadata must be an object")
            name, version = value.get("name"), value.get("version")
            if (
                isinstance(name, str)
                and PACKAGE.fullmatch(name)
                and isinstance(version, str)
                and VERSION.fullmatch(version)
            ):
                cached.setdefault(name, set()).add(version)
                evidence.append(
                    {
                        "path": path.relative_to(policy.root).as_posix(),
                        "digest": canonical_digest(value),
                    }
                )
    packages = {}
    for name in sorted(requested.keys() | resolved.keys() | cached.keys()):
        if not PACKAGE.fullmatch(name):
            continue
        requested_version = requested.get(name)
        lock = resolved.get(name, {})
        resolved_version = lock.get("version") if isinstance(lock, dict) else None
        requested_version = (
            requested_version
            if isinstance(requested_version, str) and VERSION.fullmatch(requested_version)
            else None
        )
        resolved_version = (
            resolved_version
            if isinstance(resolved_version, str) and VERSION.fullmatch(resolved_version)
            else None
        )
        versions = sorted(cached.get(name, set()))
        expected = resolved_version or requested_version
        mismatch = bool(
            requested_version and resolved_version and requested_version != resolved_version
        ) or bool(versions and expected and versions != [expected])
        packages[name] = {
            "requested": requested_version,
            "resolved": resolved_version,
            "cached": versions,
            "status": "MISMATCH" if mismatch else "CACHE_OBSERVED" if versions else "UNKNOWN",
        }
    return {
        "status": "OBSERVED" if evidence else "UNKNOWN",
        "packages": packages,
        "api_compatibility": "UNKNOWN",
        "network": "DISABLED",
        "evidence": evidence,
    }


def host_binary(host: str) -> Path | None:
    if host not in {"codex", "claude"}:
        raise InputError("Only fixed Codex/Claude availability probes are registered")
    located = shutil.which(host)
    if not located:
        return None
    path = Path(located).resolve()
    if path.suffix.lower() in {".cmd", ".bat"}:
        if host == "codex":
            candidates = sorted(
                path.parent.glob(
                    "node_modules/@openai/codex/node_modules/@openai/codex-*/vendor/*/bin/codex.exe"
                )
            )
            return candidates[0].resolve() if len(candidates) == 1 else None
        return None
    return path


def host_observation(host: str, text: str, returncode: int | None) -> dict[str, Any]:
    if host not in {"codex", "claude"}:
        raise InputError("Unknown host availability probe")
    flag = re.search(r"^multi_agent\s+[^\n]+?\s+(true|false)\s*$", text, re.M)
    feature = (
        ("ENABLED" if flag[1] == "true" else "DISABLED")
        if host == "codex" and flag
        else "CLI_DECLARED"
        if host == "claude" and "--agents" in text
        else "UNKNOWN"
    )
    return {
        "status": "OBSERVED" if returncode == 0 else "BLOCKED",
        "delegation_feature": feature if returncode == 0 else "UNKNOWN",
        "role_delegation": "UNKNOWN",
        "skill_execution": "UNKNOWN",
        "reason": "Local feature/help observation; model, permissions and actual delegation "
        "require a separate host smoke",
    }


def probe_host(policy: WorkspacePolicy, host: str) -> dict[str, Any]:
    executable = host_binary(host)
    if executable is None or not executable.is_file():
        return {
            **host_observation(host, "", None),
            "reason": "Native host binary missing or launcher unsupported; no shell fallback",
        }
    relative = "runs/host-probe-" + uuid4().hex[:16]
    args = [str(executable), *(["features", "list"] if host == "codex" else ["--help"])]
    outcome = run_process(args, policy, relative, ProcessPolicy((executable,), 15, 65536, 1024))
    text = policy.path(outcome.stdout_path).read_text("utf-8")
    result = host_observation(host, text, outcome.returncode if outcome.reason == "exit" else None)
    atomic_json(
        policy,
        relative + "/probe.json",
        {"argv": args, "outcome": asdict(outcome), "observation": result},
    )
    return {**result, "evidence_path": relative + "/probe.json"}


def availability_snapshot(policy: WorkspacePolicy, project: str | None = None) -> dict[str, Any]:
    observations = {tool: read_probe(policy, tool) for tool in ["blender", "unity", "unity-ui"]}
    return {
        "hosts": {
            host: {
                "path": str(path) if (path := host_binary(host)) else None,
                "role_delegation": "UNKNOWN",
                "skill_execution": "UNKNOWN",
                "probe_command": "polyforge knowledge availability --workspace ROOT --host " + host,
            }
            for host in ["codex", "claude"]
        },
        "unity_headless": "VERSION_PROBED" if observations["unity"] else "UNKNOWN",
        "unity_ui": "VERSION_PROBED" if observations["unity-ui"] else "UNKNOWN",
        "blender_operator_context": "VERSION_PROBED" if observations["blender"] else "UNKNOWN",
        "native_observations": observations,
        "installation_packages": probe_packages(policy, project)
        if project
        else {
            "status": "UNKNOWN",
            "reason": "Supply --project for read-only manifest, lock and local cache inspection",
        },
        "network": "DISABLED",
        "vision": "UNKNOWN",
    }
