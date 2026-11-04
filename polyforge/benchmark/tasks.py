"""Bounded public benchmark inputs and immutable execution identities."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path
from typing import Any

from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.security.paths import WorkspacePolicy

TASK_TYPES = (
    "ASSET",
    "ANIMATION_IMPORT",
    "GAME_MECHANIC",
    "CROSS_ENGINE_REPAIR",
    "COMPLETE_GAME_2D",
    "COMPLETE_GAME_3D",
)
ARMS = ("A", "B", "C", "D")
METADATA_FIELDS = frozenset(
    {
        "model",
        "thinking_effort",
        "hardware",
        "os",
        "tool_versions",
        "generic_tools",
        "permissions",
        "default_tool_inventory",
        "external_assets",
        "licensing",
        "manual_intervention_policy",
        "git_commit",
        "prompt_sha256",
        "worker_mode",
        "worker_configuration",
        "stop_conditions",
    }
)
REQUIRED_METADATA = METADATA_FIELDS - {"worker_configuration", "stop_conditions"}
PARITY_FIELDS = REQUIRED_METADATA - {"prompt_sha256", "worker_mode"}
_SUITE_FIELDS = {
    "schema_version",
    "status",
    "tasks",
    "runs_per_task_arm",
    "arms",
    "c_d_general_mcp_parity",
    "hidden_evaluator_tasks",
    "note",
    "execution_metadata",
}


def _bounded_bytes(policy: WorkspacePolicy, path: Path, limit: int) -> bytes:
    path = policy.path(path)
    try:
        with path.open("rb") as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode):
                raise InputError("Benchmark inputs must be regular files")
            content = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        current = policy.path(path).stat()

        def identity(info: os.stat_result) -> tuple[int, int, int, int]:
            return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns

        if identity(opened) != identity(after) or identity(after) != identity(current):
            raise InputError("Benchmark input changed during its bounded read")
        if len(content) > limit:
            raise InputError("Benchmark input exceeds its finite byte limit")
        return content
    except OSError as exc:
        raise InputError(f"Cannot read benchmark input: {exc}") from exc


def read_brief(suite_path: Path, task: dict[str, Any]) -> str:
    """Bound and hash the public brief again at the adapter handoff boundary."""
    policy = WorkspacePolicy(suite_path.absolute().parent)
    content = _bounded_bytes(policy, policy.path("briefs/" + task["task_id"] + ".md"), 262144)
    if not content or hashlib.sha256(content).hexdigest() != task["original_brief_sha256"]:
        raise InputError(f"Public brief hash mismatch: {task['task_id']}")
    try:
        return content.decode("utf-8")
    except UnicodeError as exc:
        raise InputError("Public brief is not UTF-8") from exc


def _bounded_json(value: Any, depth: int = 0) -> None:
    if depth > 6:
        raise InputError("Benchmark metadata exceeds its nesting limit")
    if isinstance(value, dict):
        if len(value) > 128:
            raise InputError("Benchmark metadata has too many fields")
        for key, child in value.items():
            if not isinstance(key, str) or not 1 <= len(key) <= 256:
                raise InputError("Invalid benchmark metadata key")
            _bounded_json(child, depth + 1)
    elif isinstance(value, list):
        if len(value) > 256:
            raise InputError("Benchmark metadata has too many entries")
        for child in value:
            _bounded_json(child, depth + 1)
    elif isinstance(value, str) and len(value) > 4096:
        raise InputError("Benchmark metadata text is too long")


def validate_metadata(value: Any) -> None:
    """Validate declared metadata without executing tools or resolving references."""
    if not isinstance(value, dict) or set(value) - METADATA_FIELDS:
        raise InputError("Unknown benchmark execution metadata")
    canonical_digest(value)
    _bounded_json(value)
    for field in (
        "model",
        "thinking_effort",
        "os",
        "git_commit",
        "prompt_sha256",
        "worker_mode",
        "manual_intervention_policy",
    ):
        if field in value and (not isinstance(value[field], str) or not value[field].strip()):
            raise InputError(f"Execution metadata {field} requires nonempty text")
    for field in (
        "hardware",
        "tool_versions",
        "generic_tools",
        "licensing",
        "worker_configuration",
        "stop_conditions",
    ):
        if field in value and not isinstance(value[field], dict):
            raise InputError(f"Execution metadata {field} requires an object")
    for field in ("permissions", "default_tool_inventory", "external_assets"):
        if field in value and not isinstance(value[field], list):
            raise InputError(f"Execution metadata {field} requires a list")


def _validate_suite(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - _SUITE_FIELDS:
        raise InputError("Unknown public benchmark suite fields")
    if value.get("schema_version") != "1.0.0":
        raise InputError("Unsupported benchmark suite version")
    tasks = value.get("tasks")
    if not isinstance(tasks, list) or not 1 <= len(tasks) <= 128:
        raise InputError("Suite must declare 1..128 public tasks")
    seen = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise InputError("Each benchmark task must be an object")
        dimensions = {key: task[key] for key in ("genre", "platform", "complexity") if key in task}
        validate_schema(
            {key: child for key, child in task.items() if key not in dimensions},
            "benchmark_task.schema.json",
        )
        if task["task_id"] in seen or task["ownership"] != "DEV_FIXTURE":
            raise InputError(
                "Task IDs must be unique; only public development fixtures are allowed"
            )
        seen.add(task["task_id"])
        if len(task["task_success_schema"]) > 4096:
            raise InputError("Acceptance metadata exceeds its text limit")
        for dimension in dimensions.values():
            if not isinstance(dimension, str) or not 1 <= len(dimension) <= 128:
                raise InputError("Task strata require bounded nonempty text")
        for key, maximum in (
            ("wall_seconds", 86400),
            ("tool_calls", 100000),
            ("tokens", 10000000),
            ("retries", 2),
        ):
            budget = task["budgets"][key]
            if key == "tokens" and budget is None:
                continue  # An unconfigured token limit blocks execution, never implies infinity.
            if type(budget) is not int or not (0 if key == "retries" else 1) <= budget <= maximum:
                raise InputError(f"Task {key} budget is outside its finite bounds")
    arms = value.get("arms", list(ARMS))
    if (
        not isinstance(arms, list)
        or not arms
        or any(not isinstance(arm, str) for arm in arms)
        or len(set(arms)) != len(arms)
    ):
        raise InputError("Suite arms must be unique")
    if any(arm not in ARMS for arm in arms):
        raise InputError("Unknown benchmark arm")
    count = value.get("runs_per_task_arm", 5)
    if type(count) is not int or not 1 <= count <= 100:
        raise InputError("Declared runs per task must be 1..100")
    metadata = value.get("execution_metadata", {})
    if not isinstance(metadata, dict) or set(metadata) - set(ARMS):
        raise InputError("Execution metadata must use known arm identities")
    for arm_metadata in metadata.values():
        validate_metadata(arm_metadata)
    _bounded_json(value)
    return value


def load_suite(path: Path) -> dict[str, Any]:
    """Verify public briefs and return a frozen, JSON-safe suite reference."""
    policy = WorkspacePolicy(path.absolute().parent)
    source = policy.path(path.absolute())
    value = _validate_suite(load_json(source))
    before = _bounded_bytes(policy, source, 1048576)
    for task in value["tasks"]:
        read_brief(source, task)
    if before != _bounded_bytes(policy, source, 1048576) or load_json(source) != value:
        raise InputError("Benchmark suite changed while it was being frozen")
    return {
        **value,
        "suite_path": str(source),
        "suite_digest": hashlib.sha256(before).hexdigest(),
        "definition_digest": canonical_digest(value),
    }


def verify_frozen(suite: dict[str, Any]) -> dict[str, Any]:
    """Recheck original bytes and metadata immediately before execution."""
    if not isinstance(suite, dict) or not isinstance(suite.get("suite_path"), str):
        raise InputError("Execution requires a suite returned by load_suite")
    fresh = load_suite(Path(suite["suite_path"]))
    if canonical_digest(suite) != canonical_digest(fresh):
        raise InputError("Frozen benchmark suite or execution metadata changed")
    return fresh


def metadata_ready(metadata: dict[str, Any], arm: str) -> bool:
    """Absent inventory/hardware evidence is unavailable, even when both arms omit it."""
    if not REQUIRED_METADATA <= metadata.keys():
        return False
    fields = ["hardware", "tool_versions", "licensing", "permissions", "default_tool_inventory"]
    if arm in {"C", "D"}:
        fields.append("generic_tools")
    return all(bool(metadata[field]) for field in fields)


def comparison_status(suite: dict[str, Any]) -> str:
    """C/D attribution requires complete identical generic execution conditions."""
    metadata = suite.get("execution_metadata", {})
    c, d = metadata.get("C", {}), metadata.get("D", {})
    if not metadata_ready(c, "C") or not metadata_ready(d, "D"):
        return "NON_ATTRIBUTABLE"
    if any(c[field] != d[field] for field in PARITY_FIELDS):
        return "NON_ATTRIBUTABLE"
    return "DECLARED_MATCH_ONLY"
