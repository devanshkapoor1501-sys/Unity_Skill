"""Bounded headless Blender adapter with immutable inputs and owned run evidence."""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import asdict, replace
from importlib.resources import files
from typing import Any
from uuid import uuid4

from polyforge.blender.recipes import RECIPES, expand_recipe, validate_geometry, validate_recipe
from polyforge.capabilities.protocol import RunContext
from polyforge.config import load_config
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.doctor import discover_tool
from polyforge.runner.locks import FileLock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import RunJournal, atomic_json
from polyforge.security.paths import WorkspacePolicy


def execute_recipe(
    recipe: dict[str, Any], context: RunContext, *, precheck_only: bool = False
) -> Result:
    validate_recipe(recipe)
    recipe = copy.deepcopy(recipe)
    recipe.setdefault("pivot", "base_center")
    recipe.setdefault("materials", [{"id": "base", "color_rgba": [0.3, 0.3, 0.3, 1]}])
    policy = WorkspacePolicy(context.workspace)
    config_path = policy.path("polyforge.toml")
    config = load_config(config_path if config_path.is_file() else None)
    input_digest = canonical_digest({"recipe": recipe, "seed": context.seed})
    if context.dry_run:
        return Result(
            input_digest=input_digest,
            data={
                "dry_run": True,
                "recipe": recipe,
                "planned_writes": [
                    "runs/<new-run>/asset/source.blend",
                    "runs/<new-run>/asset/metrics.json",
                    "runs/<new-run>/asset/logical-geometry.json",
                ],
                "execution_status": "NOT_RUN",
            },
        )
    executable = discover_tool("blender", config.blender_executable)
    if executable is None or not executable.is_file():
        return failure(
            ErrorKind.MISSING_DEPENDENCY,
            "PF-BLENDER-MISSING",
            "Install Blender 5.2.2 or set tools.blender_executable in polyforge.toml",
        )
    worker = files("polyforge.blender").joinpath("worker.py")
    fingerprint = {
        "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "executable": str(executable),
        "required_version": "5.2.2",
        "validator": "geometry.v1",
    }
    run_id = "mesh-" + uuid4().hex[:16]
    journal = RunJournal.create(policy, run_id, retry_limit=0)
    relative = f"runs/{run_id}"
    job = atomic_json(
        policy,
        relative + "/input.json",
        {
            "recipe": recipe,
            "seed": context.seed,
            "input_digest": input_digest,
            "toolchain": fingerprint,
        },
    )
    active_stage = "S0"
    journal.transition(active_stage, "running")
    try:
        probe = run_process(
            [str(executable), "--version"],
            policy,
            relative + "/precheck",
            ProcessPolicy(
                (executable,),
                min(context.timeout_seconds, config.version_probe_timeout_seconds),
                min(context.max_output_bytes, config.max_output_bytes),
                config.memory_limit_mb,
            ),
        )
        atomic_json(policy, relative + "/precheck-process.json", asdict(probe))
        text = policy.path(probe.stdout_path).read_text("utf-8")
        if (
            probe.reason != "exit"
            or probe.returncode != 0
            or re.search(r"^Blender 5\.2\.2(?:\s|$)", text, re.MULTILINE) is None
        ):
            raise InputError(
                "Blender 5.2.2 precheck failed; inspect version-probe logs",
                kind=ErrorKind.MISSING_DEPENDENCY,
                code="PF-BLENDER-VERSION",
            )
        journal.transition(active_stage, "passed", evidence=[probe.stdout_path])
        if precheck_only:
            return Result(
                run_id=run_id,
                input_digest=input_digest,
                data={"blender_version": "5.2.2", "through": "S0"},
                evidence_paths=[probe.stdout_path],
            )
        active_stage = "S1"
        journal.transition(active_stage, "running")
        journal.transition(active_stage, "passed", evidence=[str(job.relative_to(policy.root))])
        active_stage = "S2"
        journal.transition(active_stage, "running")
        output = policy.mkdir(relative + "/asset")
        with FileLock(policy, ".polyforge/locks/blender-worker.lock"):
            process = run_process(
                [
                    str(executable),
                    "--background",
                    "--factory-startup",
                    "--disable-autoexec",
                    "--threads",
                    "1",
                    "--python-exit-code",
                    "5",
                    "--python",
                    str(worker),
                    "--",
                    str(job),
                    str(output),
                ],
                policy,
                relative + "/log",
                ProcessPolicy(
                    (executable,),
                    min(context.timeout_seconds, config.blender_timeout_seconds),
                    min(context.max_output_bytes, config.max_output_bytes),
                    config.memory_limit_mb,
                ),
            )
        atomic_json(policy, relative + "/process.json", asdict(process))
        if process.reason != "exit" or process.returncode != 0:
            kind = (
                ErrorKind.INTERRUPTED
                if process.reason == "cancelled"
                else ErrorKind.PRODUCER_FAILURE
            )
            raise InputError(
                f"Blender worker {process.reason}, exit {process.returncode}; inspect run logs",
                kind=kind,
                code="PF-BLENDER-WORKER",
            )
        try:
            metrics = load_json(policy.path(relative + "/asset/metrics.json"))
            logical = load_json(policy.path(output / "logical-geometry.json"), max_bytes=33_554_432)
        except InputError as exc:
            raise InputError(
                "Invalid Blender output: " + str(exc),
                kind=ErrorKind.CONTRACT_FAILURE,
                code="PF-BLENDER-OUTPUT",
            ) from exc
        validate_geometry(recipe, metrics)
        if canonical_digest(logical) != metrics["geometry_digest"]:
            raise InputError(
                "Logical geometry artifact digest mismatch", kind=ErrorKind.CONTRACT_FAILURE
            )
        if (
            metrics.get("saved_roundtrip_verified") is not True
            or metrics.get("blender_version") != "5.2.2"
        ):
            raise InputError(
                "Blender version/source roundtrip verification missing",
                kind=ErrorKind.CONTRACT_FAILURE,
            )
        artifacts: list[dict[str, Any]] = []
        for filename in ("source.blend", "metrics.json", "logical-geometry.json"):
            path = policy.path(output / filename)
            content = path.read_bytes()
            if not content or (filename == "source.blend" and not content.startswith(b"BLENDER")):
                raise InputError(
                    "Missing/invalid Blender source artifact", kind=ErrorKind.CONTRACT_FAILURE
                )
            artifacts.append(
                {
                    "artifact_id": run_id + ":" + filename,
                    "relative_path": str(path.relative_to(policy.root)),
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "bytes": len(content),
                    "input_digest": input_digest,
                    "validation_status": "PASS",
                    "toolchain": fingerprint,
                }
            )
        registry = atomic_json(policy, relative + "/artifacts.json", {"artifacts": artifacts})
        journal.transition("S2", "passed", evidence=[str(registry.relative_to(policy.root))])
        context.artifact_registry.update({a["artifact_id"]: a for a in artifacts})
        return Result(
            run_id=run_id,
            operation_id=context.operation_id,
            input_digest=input_digest,
            metrics=metrics,
            artifact_ids=[a["artifact_id"] for a in artifacts],
            evidence_paths=[
                str(registry.relative_to(policy.root)),
                process.stdout_path,
                process.stderr_path,
            ],
            data={
                "source_blend": artifacts[0]["relative_path"],
                "metrics_path": artifacts[1]["relative_path"],
                "toolchain": fingerprint,
                "security_scope": "TRUSTED_LOCAL",
                "isolation_verified": False,
            },
        )
    except (InputError, OSError, KeyboardInterrupt) as exc:
        journal.transition(active_stage, "failed", note=str(exc) or "interrupted")
        if isinstance(exc, KeyboardInterrupt):
            result = failure(
                ErrorKind.INTERRUPTED, "PF-RUN-INTERRUPTED", "Blender operation interrupted"
            )
        elif isinstance(exc, InputError):
            result = failure(exc.kind, exc.code, str(exc))
        else:
            result = failure(ErrorKind.PRODUCER_FAILURE, "PF-BLENDER-IO", str(exc))
        return replace(result, run_id=run_id, input_digest=input_digest, evidence_paths=[relative])


class BlenderCapability:
    def __init__(self, kind: str) -> None:
        if kind not in RECIPES:
            raise InputError("Unknown Blender recipe")
        self.kind = kind

    def execute(self, inputs: dict[str, Any], context: RunContext) -> Result:
        return execute_recipe(expand_recipe(self.kind, inputs, seed=context.seed), context)
