"""Bounded native robot animation capability, with independent sample validation."""

import hashlib
from dataclasses import asdict
from importlib.resources import files
from typing import Any
from uuid import uuid4

from polyforge.animation.contract import inspect_motion
from polyforge.blender.recipes import expand_recipe
from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.doctor import discover_tool
from polyforge.runner.locks import FileLock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bridge import configuration


def animate_robot(inputs: dict[str, Any], context: RunContext) -> Result:
    recipe = expand_recipe("robot", inputs, seed=context.seed)
    digest = canonical_digest(
        {"recipe": recipe, "seed": context.seed, "rig_family": "robot.modular.rigid.v1"}
    )
    if context.dry_run:
        return Result(
            input_digest=digest,
            data={
                "dry_run": True,
                "family": "robot.modular.rigid.v1",
                "execution_status": "NOT_RUN",
            },
        )
    policy = WorkspacePolicy(context.workspace)
    config = configuration(policy)
    blender = discover_tool("blender", config.blender_executable)
    if blender is None:
        return failure(
            ErrorKind.MISSING_DEPENDENCY, "PF-ANIMATION-BLENDER", "Install Blender 5.2.2"
        )
    run_id = "rig-" + (context.run_id or uuid4().hex[:16])
    relative = "runs/" + run_id
    output = policy.mkdir(relative + "/asset")
    worker = files("polyforge.animation").joinpath("worker.py")
    request = atomic_json(
        policy,
        relative + "/input.json",
        {
            "recipe": recipe,
            "input_digest": digest,
            "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
            "blender_sha256": hashlib.sha256(blender.read_bytes()).hexdigest(),
        },
    )
    recovered = False
    complete = policy.path(output / "worker-complete.json")
    if complete.is_file():
        receipt = load_json(complete)
        if (
            receipt["input_digest"] != digest
            or receipt["worker_sha256"] != hashlib.sha256(worker.read_bytes()).hexdigest()
            or not all(
                hashlib.sha256(policy.path(output / item["name"]).read_bytes()).hexdigest()
                == item["sha256"]
                for item in receipt["files"]
            )
        ):
            raise InputError(
                "Interrupted animation output identity/hash mismatch",
                kind=ErrorKind.CONTRACT_FAILURE,
            )
        recovered = True
    if not recovered:
        with FileLock(policy, ".polyforge/locks/blender-worker.lock"):
            result = run_process(
                [
                    str(blender),
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
                    str(request),
                    str(output),
                ],
                policy,
                relative + "/log",
                ProcessPolicy(
                    (blender,),
                    config.blender_timeout_seconds,
                    config.max_output_bytes,
                    config.memory_limit_mb,
                ),
                cancel=context.cancel,
            )
        atomic_json(policy, relative + "/process.json", asdict(result))
    if not recovered and (result.reason != "exit" or result.returncode != 0):
        return Result(
            status="FAIL",
            exit_code=9 if result.reason == "cancelled" else 5,
            run_id=run_id,
            data={"log": result.stdout_path},
            evidence_paths=[relative + "/process.json"],
        )
    inspection = inspect_motion(load_json(output / "motion.json"))
    atomic_json(policy, relative + "/inspection.json", inspection)
    artifacts = []
    for path in sorted(output.iterdir()):
        if path.is_file() and path.suffix != ".blend1":
            artifacts.append(
                {
                    "relative_path": path.relative_to(policy.root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                    "input_digest": digest,
                }
            )
    atomic_json(policy, relative + "/artifacts.json", {"artifacts": artifacts})
    return Result(
        run_id=run_id,
        input_digest=digest,
        evaluated_test_status="PASS",
        data={
            "fbx_path": relative + "/asset/robot.fbx",
            "motion_path": relative + "/asset/motion.json",
            "source_blend": relative + "/asset/source.blend",
            "family": "robot.modular.rigid.v1",
            "visual_review": "REVIEW",
        },
        evidence_paths=[relative + "/inspection.json", relative + "/artifacts.json"],
    )
