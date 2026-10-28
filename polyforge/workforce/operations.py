"""Durable operation receipts bridge native completion and coordinator publication."""

import hashlib
import re
import threading
from pathlib import Path
from typing import Any

from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import ErrorKind, Result
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


def operation_context(
    workspace: Path, task: str, job: str, seed: int, cancel: threading.Event | None
) -> RunContext:
    identity = "op_" + hashlib.sha256((task + ":" + job).encode()).hexdigest()[:32]
    return RunContext(workspace, seed=seed, cancel=cancel, operation_id=identity, run_id=identity)


def receipt_path(context: RunContext) -> str:
    if context.operation_id is None or not re.fullmatch(r"op_[a-f0-9]{32}", context.operation_id):
        raise InputError("Invalid durable operation identity")
    return ".polyforge/operations/" + context.operation_id + ".json"


def recover(identifier: str, inputs: dict[str, Any], context: RunContext) -> Result | None:
    if context.operation_id is None:
        return None
    policy = WorkspacePolicy(context.workspace)
    path = policy.path(receipt_path(context))
    if not path.is_file():
        return None
    receipt = load_json(path, max_bytes=33_554_432)
    if receipt["request_digest"] != canonical_digest(
        {"capability": identifier, "inputs": inputs, "seed": context.seed}
    ):
        raise InputError(
            "Operation identity reused for a different request", kind=ErrorKind.CONTRACT_FAILURE
        )
    for item in receipt["files"]:
        source = policy.path(item["path"])
        if (
            not source.is_file()
            or hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise InputError(
                "Completed operation output changed; dependent jobs invalidated",
                kind=ErrorKind.CONTRACT_FAILURE,
            )
    value = receipt["result"]
    validate_schema(value, "result.schema.json")
    return Result(**{k: v for k, v in value.items() if k != "operation_status"})


def complete(
    identifier: str, inputs: dict[str, Any], context: RunContext, result: Result
) -> Result:
    if context.operation_id is None or result.status != "PASS":
        return result
    policy = WorkspacePolicy(context.workspace)
    paths = set()
    if result.run_id:
        paths.add("runs/" + result.run_id)
    paths.update(result.evidence_paths)
    if identifier in {"animation.robot.unity.v1", "unity.game.arena.v1", "unity.scene.static.v1"}:
        paths.update(
            "UnityProject/" + p
            for p in (
                "Assets/PolyForgeGenerated",
                "Packages/com.polyforge.engine",
                "ProjectSettings",
            )
        )
    inventory = []
    for relative in sorted(paths):
        path = policy.path(relative)
        for source in [path] if path.is_file() else sorted(path.rglob("*")):
            if not source.is_file() or "tmp" in source.relative_to(policy.root).parts:
                continue
            source = policy.path(source)
            inventory.append(
                {
                    "path": source.relative_to(policy.root).as_posix(),
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                }
            )
    atomic_json(
        policy,
        receipt_path(context),
        {
            "request_digest": canonical_digest(
                {"capability": identifier, "inputs": inputs, "seed": context.seed}
            ),
            "files": inventory,
            "result": result.to_dict(),
        },
    )
    return result
