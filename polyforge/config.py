"""Bounded TOML configuration with safe defaults and explicit tool overrides."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, fields
from pathlib import Path

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError


@dataclass(frozen=True)
class Config:
    blender_executable: str = ""
    unity_executable: str = ""
    max_parallel_blender: int = 2
    max_parallel_unity: int = 1
    blender_timeout_seconds: int = 600
    unity_timeout_seconds: int = 1800
    version_probe_timeout_seconds: int = 30
    max_output_bytes: int = 10_485_760
    memory_limit_mb: int = 8192
    retry_limit: int = 2
    allow_network: bool = False
    allow_outside_workspace: bool = False
    require_approval_for_download: bool = True
    mode: str = "TRUSTED_LOCAL"
    preview_resolution: int = 512
    visual_review_mode: str = "manual_or_host_vision"


SECTIONS = {
    "tools": {"blender_executable", "unity_executable"},
    "execution": {
        "max_parallel_blender",
        "max_parallel_unity",
        "blender_timeout_seconds",
        "unity_timeout_seconds",
        "version_probe_timeout_seconds",
        "max_output_bytes",
        "memory_limit_mb",
        "retry_limit",
    },
    "security": {
        "allow_network",
        "allow_outside_workspace",
        "require_approval_for_download",
        "mode",
    },
    "visual_audit": {"mode", "preview_resolution"},
}


def load_config(path: Path | None = None) -> Config:
    """Reject unknown/type-invalid settings before any writes or tool launch."""
    if path is None:
        return Config()
    try:
        with path.open("rb") as stream:
            content = stream.read(65537)
        if len(content) > 65536:
            raise InputError("Configuration exceeds 64 KiB")
        data = tomllib.loads(content.decode("utf-8"))
    except (OSError, ValueError, RecursionError) as exc:
        raise InputError(f"Cannot load configuration: {exc}", code="PF-INPUT-CONFIG") from exc
    defaults = Config()
    values = {field.name: getattr(defaults, field.name) for field in fields(defaults)}
    for section, settings in data.items():
        if section not in SECTIONS or not isinstance(settings, dict):
            raise InputError(f"Unknown or invalid configuration section: {section}")
        for key, value in settings.items():
            if key not in SECTIONS[section]:
                raise InputError(f"Unknown configuration key: {section}.{key}")
            attribute = "visual_review_mode" if (section, key) == ("visual_audit", "mode") else key
            if type(value) is not type(values[attribute]):
                raise InputError(f"Invalid type for configuration key: {section}.{key}")
            values[attribute] = value
    config = Config(**values)
    if (
        config.allow_network
        or config.allow_outside_workspace
        or not config.require_approval_for_download
        or config.mode != "TRUSTED_LOCAL"
    ):
        raise InputError(
            "Network/outside-root/untrusted execution is unavailable in this profile",
            kind=ErrorKind.POLICY_DENIED,
            code="PF-POLICY-CONFIG",
        )
    numbers = [getattr(config, key) for key in SECTIONS["execution"] if key != "retry_limit"]
    if any(number <= 0 for number in numbers) or not 0 <= config.retry_limit <= 2:
        raise InputError("Execution budgets must be positive; retry_limit must be 0..2")
    if config.max_parallel_unity != 1:
        raise InputError("Only one Unity worker per project is supported")
    if not 32 <= config.preview_resolution <= 4096:
        raise InputError("preview_resolution must be 32..4096")
    if config.visual_review_mode not in {"manual_or_host_vision", "manual"}:
        raise InputError("Unknown visual review mode")
    return config
