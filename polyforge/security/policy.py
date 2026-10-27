"""Explicit trust disclosure, minimal worker environments, and credential redaction."""

from __future__ import annotations

import os
import platform
import re
import shutil
from collections.abc import Mapping
from pathlib import Path
from typing import Any

SECRET_NAME = re.compile(r"token|secret|password|api.?key|credential|authorization", re.I)
ASSIGNMENT = re.compile(
    r"""(?i)((?:api[_-]?key|token|secret|password)["']?\s*[=:]\s*)(?:"[^"]*"|'[^']*'|[^\s,;"']+)"""
)
BEARER = re.compile(r"(?i)(bearer\s+)[a-z0-9._~+/=-]+")
URL_AUTH = re.compile(r"(?i)(https?://)[^/@\s]+@")


def redact(text: str, inherited: Mapping[str, str] | None = None) -> str:
    """Redact known inherited credentials as well as common log assignments."""
    source = os.environ if inherited is None else inherited
    secrets = sorted(
        {value for name, value in source.items() if SECRET_NAME.search(name) and value},
        key=len,
        reverse=True,
    )
    for value in secrets:
        text = text.replace(value, "[REDACTED]")
        # An output budget can cut a known credential before its complete value.
        for width in range(min(len(value) - 1, len(text)), 0, -1):
            if text.endswith(value[:width]):
                text = text[:-width] + "[REDACTED]"
                break
    return URL_AUTH.sub(
        r"\1[REDACTED]@", BEARER.sub(r"\1[REDACTED]", ASSIGNMENT.sub(r"\1[REDACTED]", text))
    )


def worker_environment(
    executable: Path, temporary: Path, inherited: Mapping[str, str] | None = None
) -> dict[str, str]:
    """Forward only essential OS values; credentials and home directories are absent."""
    source = os.environ if inherited is None else inherited
    allowed = {
        "SYSTEMROOT",
        "WINDIR",
        "LANG",
        "LC_ALL",
        "NUMBER_OF_PROCESSORS",
        "PROCESSOR_ARCHITECTURE",
    }
    env = {name: value for name, value in source.items() if name.upper() in allowed}
    system = source.get("SystemRoot", source.get("SYSTEMROOT", "C:/Windows"))
    env["PATH"] = (
        str(executable.parent)
        + os.pathsep
        + (str(Path(system) / "System32") if os.name == "nt" else "/usr/bin:/bin")
    )
    env.update(
        TEMP=str(temporary),
        TMP=str(temporary),
        TMPDIR=str(temporary),
        PYTHONIOENCODING="utf-8",
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
    )
    for suffix in ("CONFIG", "SCRIPTS", "DATAFILES", "EXTENSIONS"):
        env["BLENDER_USER_" + suffix] = str(temporary / "blender" / suffix.lower())
    return env


def isolation_profile(inherited: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Report feasibility only. Executable presence is never isolation proof."""
    source = os.environ if inherited is None else inherited
    return {
        "security_scope": "TRUSTED_LOCAL",
        "status": "UNSANDBOXED",
        "isolation_verified": False,
        "untrusted_execution_allowed": False,
        "os": platform.system(),
        "windows_sandbox_available": bool(shutil.which("WindowsSandbox.exe")),
        "container_cli_available": bool(shutil.which("docker") or shutil.which("podman")),
        "secret_variable_names": sorted(name for name in source if SECRET_NAME.search(name)),
        "network_policy": "no_requested_network; egress containment NOT_RUN",
        "os_denial_probes": "NOT_RUN",
    }
