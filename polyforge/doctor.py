"""Version probes, static project readiness and truthful environment diagnostics."""

from __future__ import annotations

import ctypes as ct
import os
import platform
import re
import shutil
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.config import Config, load_config
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.locks import FileLock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import RunJournal, atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.security.policy import isolation_profile, redact


def discover_tool(name: str, override: str = "") -> Path | None:
    """Honor explicit overrides, then search PATH and conventional installation roots."""
    if override:
        return Path(override).expanduser().resolve()
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    if sys.platform == "win32":
        candidates = (
            list((program_files / "Blender Foundation").glob("Blender */blender.exe"))
            if name == "blender"
            else list((program_files / "Unity/Hub/Editor").glob("*/Editor/Unity.exe"))
        )
    elif sys.platform == "darwin":
        candidates = (
            [Path("/Applications/Blender.app/Contents/MacOS/Blender")]
            if name == "blender"
            else list(
                Path("/Applications/Unity/Hub/Editor").glob("*/Unity.app/Contents/MacOS/Unity")
            )
        )
    else:
        candidates = (
            list(Path("/opt").glob("blender*/blender"))
            if name == "blender"
            else list((Path.home() / "Unity/Hub/Editor").glob("*/Editor/Unity"))
        )

    def version_key(path: Path) -> tuple[int, ...]:
        return tuple(int(value) for value in re.findall(r"\d+", str(path.parent)))

    installed = next(
        (
            path.resolve()
            for path in sorted(candidates, key=version_key, reverse=True)
            if path.is_file()
        ),
        None,
    )
    if installed is not None:
        return installed
    located = shutil.which("blender" if name == "blender" else "Unity")
    return Path(located).resolve() if located else None


def inspect_project(project: Path) -> dict[str, Any]:
    """Static known-file checks only. Never launch Unity on the original project."""
    policy = WorkspacePolicy(project)
    version_file = policy.path("ProjectSettings/ProjectVersion.txt")
    packages_file = policy.path("Packages/manifest.json")
    result: dict[str, Any] = {
        "status": "NOT_RUN",
        "packages": {},
        "version": None,
        "inspection_mode": "STATIC",
        "error_code": None,
    }
    if version_file.is_file():
        try:
            with version_file.open("rb") as stream:
                raw_version = stream.read(4097)
            if len(raw_version) > 4096:
                raise ValueError("ProjectVersion.txt exceeds 4 KiB")
            version = re.search(
                r"^m_EditorVersion:\s*(6000\.\d+\.\d+[a-z]\d+)\s*$",
                raw_version.decode("utf-8"),
                re.MULTILINE,
            )
            if version is None:
                raise ValueError("Expected a supported Unity 6 m_EditorVersion")
            result["version"] = version.group(1)
        except (OSError, ValueError) as exc:
            raise InputError(
                f"Invalid project version metadata: {exc}", code="PF-UNITY-PROJECT-VERSION"
            ) from exc
    if packages_file.is_file():
        value = load_json(packages_file)
        if not isinstance(value, dict) or not isinstance(value.get("dependencies"), dict):
            raise InputError("Unity package manifest must contain a dependencies object")
        if any(
            not isinstance(version, str) or not version.strip()
            for version in value["dependencies"].values()
        ):
            raise InputError("Unity dependency values must be nonempty version/path strings")
        result["packages"] = {
            name: redact(version) for name, version in value["dependencies"].items()
        }
    if policy.path("Temp/UnityLockfile").exists():
        result.update(status="BLOCKED", error_code="PF-UNITY-PROJECT-LOCKED")
    elif not version_file.is_file():
        result.update(status="BLOCKED", error_code="PF-UNITY-PROJECT-NOT-READY")
    elif any(
        name not in result["packages"]
        for name in ("com.unity.render-pipelines.universal", "com.unity.test-framework")
    ):
        result.update(status="BLOCKED", error_code="PF-UNITY-PACKAGES-MISSING")
    else:
        result["status"] = "PASS"
    return result


def hardware_fingerprint() -> dict[str, Any]:
    """Best-effort measurements; no GPU/performance result is inferred."""
    memory: int | None = None
    if sys.platform == "win32":

        class Memory(ct.Structure):
            _fields_ = [
                ("length", ct.c_ulong),
                ("load", ct.c_ulong),
                ("total", ct.c_ulonglong),
                ("available", ct.c_ulonglong),
                ("page_total", ct.c_ulonglong),
                ("page_available", ct.c_ulonglong),
                ("virtual_total", ct.c_ulonglong),
                ("virtual_available", ct.c_ulonglong),
                ("extended", ct.c_ulonglong),
            ]

        info = Memory()
        info.length = ct.sizeof(info)
        api = ct.WinDLL("kernel32", use_last_error=True)
        if api.GlobalMemoryStatusEx(ct.byref(info)):
            memory = info.total
    elif hasattr(os, "sysconf"):
        try:
            memory = int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
        except (ValueError, OSError):
            pass
    return {
        "os": platform.platform(),
        "cpu": platform.processor() or "NOT_RUN",
        "logical_cpus": os.cpu_count(),
        "physical_memory_bytes": memory,
        "gpu": "NOT_RUN",
        "graphics_render_probe": "NOT_RUN",
        "python": sys.version,
    }


def probe_tool(
    name: str, executable: Path | None, policy: WorkspacePolicy, run_id: str, config: Config
) -> dict[str, Any]:
    if executable is None or not executable.is_file():
        return {
            "status": "BLOCKED",
            "error_code": f"PF-DEPENDENCY-{name.upper()}",
            "path": str(executable) if executable else None,
            "version": None,
        }
    outcome = run_process(
        [str(executable), "--version" if name == "blender" else "-version"],
        policy,
        f"runs/{run_id}/log/{name}",
        ProcessPolicy(
            allowed_executables=(executable,),
            timeout_seconds=config.version_probe_timeout_seconds,
            max_output_bytes=config.max_output_bytes,
            memory_limit_mb=config.memory_limit_mb,
        ),
    )
    text = policy.path(outcome.stdout_path).read_text("utf-8") + policy.path(
        outcome.stderr_path
    ).read_text("utf-8")
    match = re.search(
        r"Blender (5\.\d+\.\d+)" if name == "blender" else r"(6000\.\d+\.\d+[a-z]\d+)", text
    )
    success = outcome.reason == "exit" and outcome.returncode == 0 and match is not None
    return {
        "status": "PASS" if success else "FAIL",
        "path": str(executable),
        "version": match.group(1) if match else None,
        "worker": asdict(outcome),
        "error_code": None if success else f"PF-{name.upper()}-VERSION-PROBE",
    }


def doctor(
    root: Path,
    *,
    config_path: Path | None = None,
    project: Path | None = None,
    dry_run: bool = False,
) -> Result:
    """Always save a valid precheck report, including missing-tool outcomes."""
    policy = WorkspacePolicy(root)
    if config_path is None and policy.path("polyforge.toml").is_file():
        config_path = policy.path("polyforge.toml")
    config = load_config(config_path)
    readiness = inspect_project(project) if project else {"status": "NOT_RUN", "packages": {}}
    if dry_run:
        return Result(
            data={
                "dry_run": True,
                "planned_writes": ["doctor.json", "runs/<new-id>"],
                "probes": "NOT_RUN",
                "isolation": isolation_profile(),
            }
        )
    run_id = "doctor-" + uuid4().hex[:16]
    with FileLock(policy, ".polyforge/locks/doctor.lock"):
        journal = RunJournal.create(policy, run_id, retry_limit=config.retry_limit)
        journal.transition("S0", "running")
        tools: dict[str, Any] = {}
        for name, override in (
            ("blender", config.blender_executable),
            ("unity", config.unity_executable),
        ):
            try:
                tools[name] = probe_tool(
                    name, discover_tool(name, override), policy, run_id, config
                )
            except InputError as exc:
                tools[name] = {
                    "status": "BLOCKED" if int(exc.kind) in {3, 4} else "FAIL",
                    "error_code": exc.code,
                    "message": str(exc),
                    "version": None,
                    "exit_code": int(exc.kind),
                }
        git_revision: str | None = None
        git = shutil.which("git")
        if git is not None:
            try:
                outcome = run_process(
                    [
                        git,
                        "-C",
                        str(Path(__file__).resolve().parents[1]),
                        "rev-parse",
                        "--verify",
                        "HEAD",
                    ],
                    policy,
                    f"runs/{run_id}/log/git",
                    ProcessPolicy(
                        allowed_executables=(Path(git),), timeout_seconds=5, max_output_bytes=8192
                    ),
                )
                candidate = policy.path(outcome.stdout_path).read_text("utf-8").strip()
                if outcome.returncode == 0 and re.fullmatch(r"[a-f0-9]{40,64}", candidate):
                    git_revision = candidate
            except InputError:
                pass  # Source archives/wheels may have no Git checkout; absence stays explicit.
        data: dict[str, Any] = {
            "tools": tools,
            "project": readiness,
            "hardware": hardware_fingerprint(),
            "isolation": isolation_profile(),
            "config_digest": canonical_digest(asdict(config)),
            "workspace_writable": True,
            "engine_git_revision": git_revision,
            "license": {"status": "NOT_RUN", "reason": "Version output does not verify activation"},
            "integrations": {
                "blender_mcp_cli": shutil.which("blender-mcp"),
                "unity_mcp_cli": shutil.which("unity-mcp"),
                "host_sessions": "NOT_RUN",
                "offline_core": True,
            },
            "execution_limits": {
                "timeout_seconds": config.version_probe_timeout_seconds,
                "max_output_bytes": config.max_output_bytes,
                "memory_limit_mb": config.memory_limit_mb,
            },
        }
        missing = any(value["status"] == "BLOCKED" for value in tools.values())
        failed = any(value["status"] == "FAIL" for value in tools.values())
        if readiness["status"] == "BLOCKED":
            result = failure(
                ErrorKind.POLICY_DENIED
                if readiness.get("error_code") == "PF-UNITY-PROJECT-LOCKED"
                else ErrorKind.MISSING_DEPENDENCY,
                readiness["error_code"],
                "Project readiness needs operator action",
            )
        elif missing:
            result = failure(
                ErrorKind.POLICY_DENIED
                if any(value.get("exit_code") == 4 for value in tools.values())
                else ErrorKind.MISSING_DEPENDENCY,
                "PF-DOCTOR-DEPENDENCY",
                "One or more configured tools are unavailable; inspect doctor.json",
            )
        elif failed:
            result = failure(
                ErrorKind.PRODUCER_FAILURE,
                "PF-DOCTOR-PROBE",
                "One or more version probes failed; inspect saved worker logs",
            )
        else:
            result = Result()
        from dataclasses import replace

        result = replace(
            result,
            run_id=run_id,
            data=data,
            evidence_paths=["doctor.json"],
            input_digest=data["config_digest"],
        )
        atomic_json(policy, "doctor.json", result.to_dict())
        atomic_json(policy, f"runs/{run_id}/doctor.json", result.to_dict())
        journal.transition(
            "S0",
            "passed" if result.status == "PASS" else "failed",
            evidence=[f"runs/{run_id}/doctor.json"],
            note=result.error_code or "version precheck",
        )
        return result
