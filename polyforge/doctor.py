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
from urllib.parse import urlsplit
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


def graphics_availability() -> dict[str, Any]:
    """Read OS display/device metadata without opening a display or testing rendering."""
    result: dict[str, Any] = {
        "display": {"status": "UNKNOWN", "count": None},
        "gpu": {"status": "UNKNOWN", "devices": []},
        "render": {"status": "NOT_RUN"},
        "headless_render": {"status": "UNKNOWN"},
        "qualification": "Metadata does not establish driver, render or headless support",
    }
    try:
        if sys.platform == "win32":
            from ctypes import wintypes

            class DisplayDevice(ct.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("DeviceName", wintypes.WCHAR * 32),
                    ("DeviceString", wintypes.WCHAR * 128),
                    ("StateFlags", wintypes.DWORD),
                    ("DeviceID", wintypes.WCHAR * 128),
                    ("DeviceKey", wintypes.WCHAR * 128),
                ]

            api = ct.WinDLL("user32", use_last_error=True)
            count = int(api.GetSystemMetrics(80))  # SM_CMONITORS, current desktop only.
            result["display"] = {
                "status": "OBSERVED" if count > 0 else "BLOCKED",
                "count": count,
                "source": "GetSystemMetrics(SM_CMONITORS)",
            }
            for index in range(32):
                device = DisplayDevice()
                device.cb = ct.sizeof(device)
                if not api.EnumDisplayDevicesW(None, index, ct.byref(device), 0):
                    break
                result["gpu"]["devices"].append(
                    {
                        "name": device.DeviceString,
                        "device": device.DeviceName,
                        "state_flags": int(device.StateFlags),
                    }
                )
            if result["gpu"]["devices"]:
                result["gpu"].update(status="OBSERVED", source="EnumDisplayDevicesW")
        elif sys.platform.startswith("linux"):
            # Read only fixed kernel metadata; environment display names are hints.
            for index in range(32):
                device = Path(f"/sys/class/drm/card{index}/device")
                if not device.is_dir():
                    continue
                metadata = {}
                for name in ("vendor", "device"):
                    path = device / name
                    if path.is_file():
                        with path.open("r", encoding="ascii") as stream:
                            value = stream.read(32).strip()
                        if re.fullmatch(r"0x[0-9a-fA-F]{4}", value):
                            metadata[name] = value
                if metadata:
                    result["gpu"]["devices"].append({"card": index, **metadata})
            if result["gpu"]["devices"]:
                result["gpu"].update(status="OBSERVED", source="linux_drm_sysfs")
            result["display"]["configured"] = bool(
                os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
            )
        elif sys.platform == "darwin":
            api = ct.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
            count = ct.c_uint32()
            if api.CGGetActiveDisplayList(0, None, ct.byref(count)) == 0:
                result["display"] = {
                    "status": "OBSERVED" if count.value else "BLOCKED",
                    "count": count.value,
                    "source": "CGGetActiveDisplayList",
                }
    except (OSError, AttributeError, ValueError):
        pass  # Partial metadata remains useful; missing observations never become PASS.
    return result


def integration_availability(
    tools: dict[str, Any], *, sessions: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    """Validate explicit host metadata; never scan private config or connect endpoints."""
    operations = {"plan", "blender_build", "unity_build", "interactive_scene_edit"}
    if sessions is not None and (not isinstance(sessions, list) or len(sessions) > 32):
        raise InputError("MCP session inventory must be a list of at most 32 descriptors")
    observed = []
    for session in sessions or []:
        if (
            not isinstance(session, dict)
            or set(session) - {"tool", "transport", "endpoint", "connected", "operations"}
            or not isinstance(session.get("tool"), str)
            or session.get("tool") not in {"blender", "unity"}
            or not isinstance(session.get("transport"), str)
            or session.get("transport") not in {"stdio", "http"}
            or type(session.get("connected")) is not bool
            or not isinstance(session.get("operations"), list)
            or len(session["operations"]) > len(operations)
            or any(not isinstance(op, str) or op not in operations for op in session["operations"])
        ):
            raise InputError("Invalid explicit MCP session descriptor")
        endpoint = session.get("endpoint")
        if session["transport"] == "http":
            if not isinstance(endpoint, str) or len(endpoint) > 2048:
                raise InputError("MCP endpoint must be an explicit localhost URL")
            try:
                url = urlsplit(endpoint)
                valid = (
                    url.scheme in {"http", "https"}
                    and url.hostname in {"localhost", "127.0.0.1", "::1"}
                    and url.port is not None
                    and url.port > 0
                    and not (url.username or url.password or url.query or url.fragment)
                    and not any(ord(char) < 32 for char in endpoint)
                )
            except ValueError:
                valid = False
            if not valid:
                raise InputError("MCP endpoint must be localhost without credentials or parameters")
        elif endpoint is not None:
            raise InputError("stdio descriptors cannot include endpoints or launch commands")
        observed.append(
            {
                "tool": session["tool"],
                "transport": session["transport"],
                "connected": session["connected"],
                "operations": list(session["operations"]),
                "status": "OBSERVED",
                "source": "CALLER_SUPPLIED",
            }
        )
    matrix = {
        operation: {
            "offline": (
                "OBSERVED"
                if operation == "plan"
                else "BLOCKED"
                if operation == "interactive_scene_edit"
                else "OBSERVED"
                if tools.get(operation.split("_")[0], {}).get("status") == "PASS"
                else "UNKNOWN"
            ),
            "assisted": "OBSERVED"
            if any(
                session["connected"] and operation in session["operations"] for session in observed
            )
            else "UNKNOWN",
        }
        for operation in sorted(operations)
    }
    return {
        "blender_mcp_cli": shutil.which("blender-mcp"),
        "unity_mcp_cli": shutil.which("unity-mcp"),
        "host_sessions": observed,
        "offline_core": True,
        "matrix": matrix,
        "operational_probe": "NOT_RUN",
        "execution_authority": "NONE",
    }


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
    graphics = graphics_availability()
    return {
        "os": platform.platform(),
        "cpu": platform.processor() or "NOT_RUN",
        "logical_cpus": os.cpu_count(),
        "physical_memory_bytes": memory,
        "gpu": graphics["gpu"],
        "graphics": graphics,
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
    from polyforge.runner.workspace_lock import binary_identity

    return {
        "status": "PASS" if success else "FAIL",
        "path": str(executable),
        "version": match.group(1) if match else None,
        "binary_identity": binary_identity(executable),
        "worker": asdict(outcome),
        "error_code": None if success else f"PF-{name.upper()}-VERSION-PROBE",
    }


def doctor(
    root: Path,
    *,
    config_path: Path | None = None,
    project: Path | None = None,
    dry_run: bool = False,
    mcp_sessions: list[dict[str, Any]] | None = None,
) -> Result:
    """Always save a valid precheck report, including missing-tool outcomes."""
    policy = WorkspacePolicy(root)
    if config_path is None and policy.path("polyforge.toml").is_file():
        config_path = policy.path("polyforge.toml")
    config = load_config(config_path)
    integration_availability({}, sessions=mcp_sessions)  # Validate before any writes.
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
            "integrations": integration_availability(tools, sessions=mcp_sessions),
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
