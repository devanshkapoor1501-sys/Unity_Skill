"""Phase 2 command orchestration; validate everything before publishing derived state."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from polyforge.compiler.contract_compiler import compile_contract
from polyforge.contracts.manifest import Manifest, load_manifest
from polyforge.contracts.results import Result
from polyforge.contracts.validation import InputError, load_json
from polyforge.planner.cache import cache_hit
from polyforge.planner.plans import build_plan, changed_tasks
from polyforge.runner.artifacts import complete_records
from polyforge.runner.locks import FileLock
from polyforge.runner.state import atomic_json
from polyforge.runner.workspace_lock import build_workspace_lock
from polyforge.security.paths import WorkspacePolicy


def _check_frozen(model: Manifest, policy: WorkspacePolicy) -> None:
    frozen = policy.path(".polyforge/original_prompt.txt")
    if frozen.exists():
        with frozen.open("rb") as stream:
            content = stream.read(262145)
        if hashlib.sha256(content).hexdigest() != model.brief_sha256:
            raise InputError(
                "$.intent.brief_path: brief differs from frozen original; use a new "
                "workspace or a separately approved amendment workflow"
            )


def _preflight(model: Manifest, outputs: dict[str, Any], source: Path) -> None:
    """Reject collisions with immutable inputs before even taking a writing lock."""
    policy = WorkspacePolicy(model.workspace)
    inputs = [
        source.absolute(),
        *[policy.path(a["recipe"]) for a in model.data["assets"]],
        *[policy.path(name) for name in model.input_digests],
        policy.path("polyforge.toml"),
        policy.path("doctor.json"),
        policy.path("UnityProject/ProjectSettings/ProjectVersion.txt"),
        policy.path("UnityProject/Packages/manifest.json"),
        policy.path("UnityProject/Packages/packages-lock.json"),
    ]
    if model.brief is not None:
        inputs.append(policy.path(model.data.get("intent", {}).get("brief_path", "brief.md")))
    for name in [
        *outputs,
        ".polyforge/planning-state.json",
        ".polyforge/brief-lock.json",
        ".polyforge/original_prompt.txt",
        ".polyforge/locks/planning.lock",
    ]:
        path = policy.path(name)
        if any(
            str(path).casefold() == str(value).casefold()
            or (path.exists() and value.exists() and path.samefile(value))
            for value in inputs
        ):
            raise InputError(f"$.outputs[{name}]: destination overlaps immutable input")
        if path.exists() and not path.is_file():
            raise InputError(f"$.outputs[{name}]: expected a file destination")
        for parent in path.parents:
            if parent == policy.root:
                break
            if parent.exists() and not parent.is_dir():
                raise InputError(f"$.outputs[{name}]: destination parent must be a directory")
        if name == "polyforge.lock.json" and path.is_file():
            state_path = policy.path(".polyforge/planning-state.json")
            state = load_json(state_path) if state_path.is_file() else {}
            records = state.get("artifacts", []) if isinstance(state, dict) else []
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            prior_owned = isinstance(records, list) and any(
                isinstance(record, dict)
                and record.get("relative_path") == name
                and record.get("sha256") == digest
                for record in records
            )
            pending_owned = (
                isinstance(state, dict)
                and state.get("status") == "PREPARING"
                and state.get("project_id") == model.data["project"]["id"]
                and digest in (state.get("pending_lock_sha256"), state.get("previous_lock_sha256"))
            )
            if not (prior_owned or pending_owned):
                raise InputError("Existing workspace lock is not an unchanged owned artifact")


def _publish(model: Manifest, outputs: dict[str, Any], source: Path) -> None:
    policy = WorkspacePolicy(model.workspace)
    _check_frozen(model, policy)
    _preflight(model, outputs, source)
    with FileLock(policy, ".polyforge/locks/planning.lock"):
        _check_frozen(model, policy)
        _preflight(model, outputs, source)
        if model.brief is not None:
            frozen = policy.path(".polyforge/original_prompt.txt")
            policy.mkdir(frozen.parent)
            if not frozen.exists():
                with frozen.open("xb") as stream:
                    stream.write(model.brief.encode("utf-8"))
            atomic_json(
                policy,
                ".polyforge/brief-lock.json",
                {
                    "schema_version": "1.0.0",
                    "original_brief_sha256": model.brief_sha256,
                    "task_id": model.data["project"]["id"],
                    "acceptance_rubric_version": None,
                    "acceptance_status": "NOT_RUN",
                    "owner": "DEVELOPMENT_FREEZE",
                },
            )
        state_path = policy.path(".polyforge/planning-state.json")
        previous = load_json(state_path) if state_path.is_file() else {}
        lock_path = policy.path("polyforge.lock.json")
        # _preflight established ownership of these exact current bytes above.
        previous_lock_sha256 = (
            hashlib.sha256(lock_path.read_bytes()).hexdigest() if lock_path.is_file() else None
        )
        pending_lock = (
            json.dumps(outputs["polyforge.lock.json"], indent=2, ensure_ascii=True, allow_nan=False)
            + "\n"
        ).encode()
        atomic_json(
            policy,
            ".polyforge/planning-state.json",
            {
                "status": "PREPARING",
                "project_id": model.data["project"]["id"],
                "artifacts": previous.get("artifacts", []) if isinstance(previous, dict) else [],
                "pending_lock_sha256": hashlib.sha256(pending_lock).hexdigest(),
                "previous_lock_sha256": previous_lock_sha256,
                "manifest_digest": model.digest,
                "input_digest": model.input_digest,
            },
        )
        inventory = []
        for name, value in outputs.items():
            path = atomic_json(policy, name, value)
            content = path.read_bytes()
            inventory.append(
                {
                    "artifact_id": name,
                    "kind": "planning_json",
                    "relative_path": name,
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "bytes": len(content),
                    "upstream_input_digest": model.input_digest,
                    "validation_status": "PASS",
                    "validator": "polyforge.contract_compiler.v1",
                }
            )
        inventory = complete_records(
            policy,
            "planning_" + model.input_digest[:16],
            "S1",
            inventory,
            input_digest=model.input_digest,
            project_id=model.data["project"]["id"],
        )
        atomic_json(
            policy,
            ".polyforge/planning-state.json",
            {
                "status": "COMMITTED",
                "manifest_digest": model.digest,
                "input_digest": model.input_digest,
                "artifacts": inventory,
            },
        )


def manifest_command(path: Path, operation: str, *, dry_run: bool = False) -> Result:
    model = load_manifest(path)
    policy = WorkspacePolicy(model.workspace)
    _check_frozen(model, policy)
    compiled = compile_contract(model)
    if operation == "validate":
        return Result(
            input_digest=model.input_digest,
            data={
                "schema_version": model.data["schema_version"],
                "asset_order": list(model.asset_order),
                "requirement_coverage": compiled["requirement_coverage"],
            },
        )
    outputs = compiled.copy()
    if operation == "plan":
        plan = build_plan(model)
        previous_path = policy.path("plan.json")
        previous = load_json(previous_path) if previous_path.is_file() else None
        plan["affected_tasks"] = (
            changed_tasks(previous, plan)
            if previous is not None
            else [task["id"] for task in plan["tasks"]]
        )
        cache_path = policy.path(".polyforge/build-cache.json")
        cache = load_json(cache_path) if cache_path.is_file() else {}
        if not isinstance(cache, dict):
            raise InputError("$.build_cache: expected an object")
        for task in plan["tasks"]:
            hit = cache_hit(task, cache.get(task["id"]), policy)
            task["cache_status"] = "HIT" if hit else "NOT_BUILT"
            task["reason"] = (
                "validated output hashes match" if hit else "execution evidence required"
            )
        outputs["plan"] = plan
    named = {name + ".json": value for name, value in outputs.items()}
    named["polyforge.lock.json"] = build_workspace_lock(model)
    _preflight(model, named, path)
    if not dry_run:
        _publish(model, named, path)
    return Result(
        input_digest=model.input_digest,
        data={**outputs, "dry_run": dry_run, "planned_writes": list(named)},
        evidence_paths=[] if dry_run else list(named),
    )
