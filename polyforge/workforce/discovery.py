"""Read-only discovery: binary presence is never a version compatibility claim."""

import os
import shutil
import sys
from importlib import import_module
from pathlib import Path
from typing import Any

from polyforge.capabilities.registry import catalog
from polyforge.contracts.validation import InputError
from polyforge.doctor import discover_tool, hardware_fingerprint
from polyforge.knowledge.availability import availability_snapshot
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bridge import configuration


def resource_usage(policy: WorkspacePolicy) -> dict[str, Any]:
    """Fast local availability checks, without tool hashing or GPU enumeration."""
    available_ram = None
    try:
        if sys.platform == "win32":
            import ctypes as ct

            class MemoryStatus(ct.Structure):
                _fields_ = [("length", ct.c_uint32), ("load", ct.c_uint32)] + [
                    (name, ct.c_uint64)
                    for name in (
                        "total",
                        "available",
                        "page",
                        "free_page",
                        "virtual",
                        "free_virtual",
                        "extended",
                    )
                ]

            status = MemoryStatus()
            status.length = ct.sizeof(status)
            if ct.windll.kernel32.GlobalMemoryStatusEx(ct.byref(status)):
                available_ram = status.available
        elif sys.platform.startswith("linux"):
            for line in Path("/proc/meminfo").read_text().splitlines():
                if line.startswith("MemAvailable:"):
                    available_ram = int(line.split()[1]) * 1024
    except (OSError, ValueError, AttributeError):
        pass
    try:
        disk_free = shutil.disk_usage(policy.root).free
    except OSError:
        disk_free = None
    return {
        "cpu_count": os.cpu_count(),
        "disk_free_bytes": disk_free,
        "available_ram_bytes": available_ram,
    }


def gpu_metadata(
    *, platform: str | None = None, drm_root: Path = Path("/sys/class/drm")
) -> dict[str, Any]:
    """Read bounded OS adapter metadata; capacity never proves GPU execution support.

    Registry adapters may be inactive. VRAM is the largest reported adapter capacity,
    not currently free memory, and missing/ambiguous values remain unknown.
    """
    platform = platform or sys.platform
    adapters: list[dict[str, Any]] = []
    if platform == "win32":
        winreg = import_module("winreg")

        display_class = (
            r"SYSTEM\CurrentControlSet\Control\Class"
            r"\{4d36e968-e325-11ce-bfc1-08002be10318}"
        )
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, display_class) as root:
                for index in range(32):
                    try:
                        name = winreg.EnumKey(root, index)
                    except OSError:
                        break
                    if len(name) != 4 or not name.isdecimal():
                        continue
                    try:
                        with winreg.OpenKey(root, name) as key:
                            description = str(winreg.QueryValueEx(key, "DriverDesc")[0])[:512]
                            vram = None
                            for field in (
                                "HardwareInformation.qwMemorySize",
                                "HardwareInformation.MemorySize",
                                "HardwareInformation.AdapterRam",
                            ):
                                try:
                                    raw = winreg.QueryValueEx(key, field)[0]
                                except OSError:
                                    continue
                                if isinstance(raw, bytes) and len(raw) in {4, 8}:
                                    raw = int.from_bytes(raw, "little")
                                if type(raw) is int and 0 < raw < 2**63 and raw != 0xFFFFFFFF:
                                    vram = raw
                                    break
                            adapters.append(
                                {
                                    "name": description,
                                    "vram_bytes": vram,
                                    "source": "WINDOWS_DISPLAY_CLASS_REGISTRY",
                                }
                            )
                    except OSError:
                        continue
        except OSError:
            pass
    elif platform.startswith("linux"):
        # Fixed numeric card names bound the reads even on an unexpected sysfs mount.
        for index in range(32):
            device = drm_root / f"card{index}" / "device"
            try:
                with (device / "vendor").open() as stream:
                    vendor = stream.read(64).strip()
                with (device / "device").open() as stream:
                    identifier = stream.read(64).strip()
            except (OSError, UnicodeError):
                continue
            vram = None
            try:
                with (device / "mem_info_vram_total").open() as stream:
                    reported = int(stream.read(64).strip())
                if 0 < reported < 2**63:
                    vram = reported
            except (OSError, ValueError):
                pass
            adapters.append(
                {"name": vendor + ":" + identifier, "vram_bytes": vram, "source": "LINUX_DRM_SYSFS"}
            )
    capacities = [adapter["vram_bytes"] for adapter in adapters if adapter["vram_bytes"]]
    return {
        "gpu_observation": "METADATA_ONLY" if adapters else "UNKNOWN",
        "gpu_execution": "UNVERIFIED",
        "vram_bytes": max(capacities) if capacities else None,
        "adapters": adapters,
    }


def resource_snapshot(policy: WorkspacePolicy) -> dict[str, Any]:
    """Full read-only admission observation; GPU metadata is never qualification."""
    return {**resource_usage(policy), "hardware": hardware_fingerprint(), **gpu_metadata()}


def check_resource_floors(observed: dict[str, Any], requirements: dict[str, Any]) -> None:
    """Fail closed whenever an explicitly required observation is unavailable."""
    from polyforge.contracts.results import ErrorKind
    from polyforge.contracts.validation import InputError

    for wanted, measured in (
        (requirements.get("min_cpu_count", 1), observed["cpu_count"]),
        (requirements.get("min_free_disk_bytes", 1_048_576), observed["disk_free_bytes"]),
        (requirements.get("min_available_ram_bytes", 0), observed["available_ram_bytes"]),
    ):
        if wanted and (measured is None or measured < wanted):
            raise InputError(
                "Insufficient or unknown requested hardware budget", kind=ErrorKind.POLICY_DENIED
            )
    if requirements.get("gpu_required", False):
        raise InputError(
            "GPU execution/VRAM is unverified; required GPU work blocked",
            kind=ErrorKind.POLICY_DENIED,
        )


def admit_resources(policy: WorkspacePolicy, requirements: dict[str, Any]) -> dict[str, Any]:
    observed = resource_snapshot(policy)
    check_resource_floors(observed, requirements)
    observed.update(
        {
            "mode": "LOCAL_SEQUENTIAL",
            "admitted_parallel_workers": 1,
            "worker_limits": {"blender": 1, "unity": 1, "model": 0, "blender_cpu_threads": 1},
            "render_policy": "REGISTERED_FIXED_CPU",
            "degradation_reason": "Measured admission permits one sequential worker; parallel/GPU "
            "execution and adaptive render quality are unqualified. "
            "Registered CPU quality retained.",
        }
    )
    return observed


def discover(policy: WorkspacePolicy) -> dict[str, Any]:
    config = configuration(policy)
    tools = {}
    for name, explicit in [
        ("blender", config.blender_executable),
        ("unity", config.unity_executable),
    ]:
        path = discover_tool(name, explicit)
        tools[name] = {
            "path": str(path) if path else None,
            "availability": "PRESENT" if path else "UNAVAILABLE",
            "version_status": "UNPROBED",
            "execution_authorized": "TRUSTED_REGISTERED_ONLY",
        }
    resources = resource_snapshot(policy)
    try:
        check_resource_floors(resources, {})
        admitted = 1
    except InputError:
        admitted = 0
    return {
        "tools": tools,
        "capability_ids": [c["id"] for c in catalog()],
        "network": "DISABLED",
        "knowledge_state": "REFERENCE_ONLY",
        **resources,
        "native_subagents": "UNAVAILABLE",
        "host_delegation_probe": "AVAILABLE_ON_REQUEST",
        "experimental_execution": "BLOCKED",
        "host_affordances": availability_snapshot(policy),
        "max_parallel_unity": admitted,
        "max_parallel_blender": admitted,
        "max_parallel_model": 0,
        "resource_mode": "LOCAL_SEQUENTIAL" if admitted else "BLOCKED",
    }
