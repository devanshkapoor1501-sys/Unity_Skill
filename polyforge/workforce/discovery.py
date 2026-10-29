"""Read-only discovery: binary presence is never a version compatibility claim."""

import os
import shutil
from typing import Any

from polyforge.capabilities.registry import catalog
from polyforge.doctor import discover_tool
from polyforge.knowledge.availability import availability_snapshot
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bridge import configuration


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
    return {
        "tools": tools,
        "capability_ids": [c["id"] for c in catalog()],
        "network": "DISABLED",
        "knowledge_state": "REFERENCE_ONLY",
        "cpu_count": os.cpu_count(),
        "disk_free_bytes": shutil.disk_usage(policy.root).free,
        "native_subagents": "UNAVAILABLE",
        "host_delegation_probe": "AVAILABLE_ON_REQUEST",
        "experimental_execution": "BLOCKED",
        "host_affordances": availability_snapshot(policy),
        "max_parallel_unity": 1,
        "max_parallel_blender": min(2, config.max_parallel_blender),
    }
