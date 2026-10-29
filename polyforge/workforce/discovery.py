"""Read-only discovery: binary presence is never a version compatibility claim."""

import os
import shutil
from typing import Any

from polyforge.capabilities.registry import catalog
from polyforge.doctor import discover_tool
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
        "host_delegation_probe": "NOT_IMPLEMENTED",
        "experimental_execution": "BLOCKED",
        "host_affordances": {
            "codex": {
                "path": shutil.which("codex"),
                "skill_execution": "UNKNOWN",
                "role_delegation": "UNKNOWN",
            },
            "claude": {
                "path": shutil.which("claude"),
                "skill_execution": "UNKNOWN",
                "role_delegation": "UNKNOWN",
            },
            "vision": "UNKNOWN",
            "unity_ui": "UNKNOWN",
            "unity_headless": "UNKNOWN_UNTIL_FIXED_PROBE",
            "blender_operator_context": "UNKNOWN_UNTIL_FIXED_PROBE",
            "installation_packages": "UNKNOWN_EXCEPT_OBSERVED_PROJECT_MANIFEST",
        },
        "max_parallel_unity": 1,
        "max_parallel_blender": min(2, config.max_parallel_blender),
    }
