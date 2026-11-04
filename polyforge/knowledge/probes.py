"""Fixed scratch API probes. Receipts attest local observations, never authority."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, load_json
from polyforge.doctor import discover_tool
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bridge import configuration

PINS = {
    "blender": ("5.2.2", "blender.mesh-context.v1", "blender-knowledge-probe.py.txt"),
    "unity": ("6000.6.3f1", "unity.typecache.v1", "unity-knowledge-probe.cs.txt"),
    "unity-ui": ("6000.6.3f1", "unity.editor-window.v1", "unity-ui-probe.cs.txt"),
    "blender-bvh": ("5.2.2", "blender.bvh-ray.v1", "blender-bvh-probe.py.txt"),
    "unity-pool": ("6000.6.3f1", "unity.object-pool.v1", "unity-pool-probe.cs.txt"),
}
CHECKS = {
    "blender": {
        "valid_mesh_unchanged": True,
        "degenerate_mesh_repaired": True,
        "context_poll_without_active_object": False,
        "context_poll_with_active_object": True,
    },
    "unity": {"known_record_found": True, "unrelated_type_excluded": True, "editor_assembly": True},
    "unity-ui": {"interactive_mode": True, "window_painted": True},
    "blender-bvh": {
        "ray_hits_triangle": True,
        "ray_misses_triangle": True,
        "distance_limit_enforced": True,
    },
    "unity-pool": {
        "released_instance_reused": True,
        "duplicate_release_rejected": True,
        "clear_destroys_inactive": True,
    },
}


def _pin(tool: str) -> tuple[str, str, str]:
    if not isinstance(tool, str) or tool not in PINS:
        raise InputError("Only registered Blender/Unity probes are available")
    return PINS[tool]


def _source(tool: str) -> bytes:
    return files("polyforge").joinpath("data/" + _pin(tool)[2]).read_bytes()


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    if path.stat().st_size > 1_073_741_824:
        raise InputError("Probe identity exceeds binary/evidence hash budget")
    with path.open("rb") as stream:
        while block := stream.read(1_048_576):
            digest.update(block)
    return digest.hexdigest()


def validate_observation(tool: str, value: Any) -> dict[str, Any]:
    version, identifier, _ = _pin(tool)
    if (
        not isinstance(value, dict)
        or set(value) != {"schema_version", "probe_id", "tool_version", "checks", "artifacts"}
        or value["schema_version"] != "1.0.0"
        or value["probe_id"] != identifier
        or value["tool_version"] != version
        or value["artifacts"] != []
        or not isinstance(value["checks"], dict)
        or set(value["checks"]) != set(CHECKS[tool])
        or any(
            type(value["checks"][k]) is not bool or value["checks"][k] is not expected
            for k, expected in CHECKS[tool].items()
        )
    ):
        raise InputError("Fixed native probe did not establish the pinned API checks")
    return {
        "knowledge_state": "VERSION_PROBED",
        "tool_version": version,
        "checks": value["checks"],
        "execution_support_promoted": False,
        "host_delegation": "UNKNOWN",
        "host_vision": "UNKNOWN",
        "unity_ui": "VERSION_PROBED" if tool == "unity-ui" else "UNKNOWN",
        "package_compatibility": "ONLY_FIXED_PROBE_CONTEXT",
    }


def _args(policy: WorkspacePolicy, executable: Path, tool: str, relative: str) -> list[str]:
    output = str(policy.path(relative + "/observation.json"))
    if tool.startswith("blender"):
        return [
            str(executable),
            "--background",
            "--factory-startup",
            "--threads",
            "1",
            "--python",
            str(policy.path(relative + "/probe.py")),
            "--",
            output,
        ]
    return [
        str(executable),
        *(["-batchmode", "-nographics"] if tool != "unity-ui" else []),
        "-job-worker-count",
        "2",
        "-projectPath",
        str(policy.path(relative + "/scratch/UnityProject")),
        "-logFile",
        "-",
        "-upmLogFile",
        str(policy.path(relative + "/upm.log")),
        "-executeMethod",
        "PolyForgeKnowledgeProbe.Run",
        "-polyforgeProbeOutput",
        output,
    ]


def probe_tool(workspace: Path, tool: str, *, dry_run: bool = False) -> Result:
    version, identifier, _ = _pin(tool)
    policy = WorkspacePolicy(workspace)
    config = configuration(policy)
    executable = discover_tool(
        "blender" if tool.startswith("blender") else "unity",
        config.blender_executable if tool.startswith("blender") else config.unity_executable,
    )
    if dry_run:
        return Result(
            data={
                "probe_id": identifier,
                "pinned_version": version,
                "execution_status": "NOT_RUN",
                "planned_writes": ["runs/<new-probe>/scratch"],
                "network": "DISABLED",
                "availability": "PRESENT"
                if executable is not None and executable.is_file()
                else "UNAVAILABLE",
            }
        )
    if executable is None or not executable.is_file():
        return failure(
            ErrorKind.MISSING_DEPENDENCY,
            "PF-KNOWLEDGE-TOOL",
            "Registered probe tool is unavailable",
        )
    run_id = "knowledge-" + uuid4().hex[:16]
    relative = "runs/" + run_id
    policy.mkdir(relative)
    source = _source(tool)
    path = policy.path(
        relative
        + (
            "/probe.py"
            if tool.startswith("blender")
            else "/scratch/UnityProject/Assets/Editor/PolyForgeKnowledgeProbe.cs"
        )
    )
    policy.mkdir(path.parent)
    path.write_bytes(source)
    if not tool.startswith("blender"):
        atomic_json(
            policy, relative + "/scratch/UnityProject/Packages/manifest.json", {"dependencies": {}}
        )
        setting = policy.path(relative + "/scratch/UnityProject/ProjectSettings/ProjectVersion.txt")
        policy.mkdir(setting.parent)
        setting.write_text("m_EditorVersion: " + version + "\n", encoding="utf-8")
    args = _args(policy, executable, tool, relative)
    outcome = run_process(
        args,
        policy,
        relative + "/process",
        ProcessPolicy(
            (executable,),
            min(
                180,
                config.blender_timeout_seconds
                if tool.startswith("blender")
                else config.unity_timeout_seconds,
            ),
            config.max_output_bytes,
            config.memory_limit_mb,
        ),
    )
    process_path = relative + "/process.json"
    atomic_json(policy, process_path, {"argv": args, **asdict(outcome)})
    if outcome.reason != "exit" or outcome.returncode != 0:
        return Result(
            status="FAIL",
            exit_code=5,
            error_code="PF-KNOWLEDGE-PROBE",
            run_id=run_id,
            data={
                "execution_status": "FAIL",
                "knowledge_state": "UNAVAILABLE",
                "reason": outcome.reason,
            },
            evidence_paths=[process_path],
        )
    observation = load_json(policy.path(relative + "/observation.json"))
    validated = validate_observation(tool, observation)
    receipt = {
        "schema_version": "1.0.0",
        "tool": tool,
        "probe_id": identifier,
        "run_id": run_id,
        "binary_path": str(executable),
        "binary_sha256": _sha(executable),
        "source_path": path.relative_to(policy.root).as_posix(),
        "source_sha256": hashlib.sha256(source).hexdigest(),
        "observation_path": relative + "/observation.json",
        "observation_sha256": _sha(policy.path(relative + "/observation.json")),
        "process_path": process_path,
        "process_sha256": _sha(policy.path(process_path)),
    }
    atomic_json(policy, ".polyforge/knowledge-" + tool + ".json", receipt)
    return Result(
        run_id=run_id,
        evaluated_test_status="PASS",
        data={
            "probe_id": identifier,
            **validated,
            "execution_status": "PASS",
            "isolation_verified": False,
            "probe_scope": "FIXED_TRUSTED_LOCAL_EMPTY_SCRATCH",
            "network": "DISABLED",
            "receipt": receipt,
        },
        evidence_paths=[receipt["observation_path"], process_path],
    )


def read_probe(policy: WorkspacePolicy, tool: str) -> dict[str, Any] | None:
    _, identifier, _ = _pin(tool)
    marker = policy.path(".polyforge/knowledge-" + tool + ".json")
    if not marker.is_file():
        return None
    receipt = load_json(marker)
    fields = {
        "schema_version",
        "tool",
        "probe_id",
        "run_id",
        "binary_path",
        "binary_sha256",
        "source_path",
        "source_sha256",
        "observation_path",
        "observation_sha256",
        "process_path",
        "process_sha256",
    }
    if (
        not isinstance(receipt, dict)
        or set(receipt) != fields
        or any(not isinstance(v, str) for v in receipt.values())
        or receipt["schema_version"] != "1.0.0"
        or receipt["tool"] != tool
        or receipt["probe_id"] != identifier
        or not re.fullmatch(r"knowledge-[a-f0-9]{16}", receipt["run_id"])
    ):
        raise InputError("Invalid registered knowledge probe receipt")
    config = configuration(policy)
    executable = discover_tool(
        "blender" if tool.startswith("blender") else "unity",
        config.blender_executable if tool.startswith("blender") else config.unity_executable,
    )
    if (
        executable is None
        or str(executable) != receipt["binary_path"]
        or _sha(executable) != receipt["binary_sha256"]
    ):
        raise InputError("Installed tool differs from the recorded probe")
    relative = "runs/" + receipt["run_id"]
    expected_source = relative + (
        "/probe.py"
        if tool.startswith("blender")
        else "/scratch/UnityProject/Assets/Editor/PolyForgeKnowledgeProbe.cs"
    )
    if (
        receipt["source_path"] != expected_source
        or receipt["source_sha256"] != hashlib.sha256(_source(tool)).hexdigest()
    ):
        raise InputError("Probe source is not the current registered engine probe")
    for key, path in [
        ("source", expected_source),
        ("observation", relative + "/observation.json"),
        ("process", relative + "/process.json"),
    ]:
        if receipt[key + "_path"] != path or _sha(policy.path(path)) != receipt[key + "_sha256"]:
            raise InputError("Knowledge probe evidence changed or escaped its run")
    process = load_json(policy.path(receipt["process_path"]))
    if (
        not isinstance(process, dict)
        or process.get("reason") != "exit"
        or process.get("returncode") != 0
        or process.get("argv") != _args(policy, executable, tool, relative)
    ):
        raise InputError("Probe receipt lacks a matching successful native invocation")
    return {
        "receipt": receipt,
        **validate_observation(tool, load_json(policy.path(receipt["observation_path"]))),
    }
