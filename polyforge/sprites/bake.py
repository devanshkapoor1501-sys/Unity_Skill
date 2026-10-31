"""Registered source-only Blender bake with independent pixel inspection."""

import hashlib
from dataclasses import asdict
from importlib.resources import files
from typing import Any
from uuid import uuid4

from polyforge.animation.contract import inspect_motion
from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.doctor import discover_tool
from polyforge.runner.artifacts import complete_records
from polyforge.runner.locks import FileLock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.sprites.images import atlas, inspect_strip
from polyforge.unity.bridge import configuration


def bake_robot(inputs: dict[str, Any], context: RunContext) -> Result:
    validate_schema(inputs, "sprite_bake.schema.json")
    policy = WorkspacePolicy(context.workspace)
    source = policy.path(inputs["source_blend"])
    if (
        not source.is_file()
        or not source.is_relative_to(policy.path("runs"))
        or source.parent.name != "asset"
    ):
        raise InputError("Sprite bake requires a registered run-scoped animation source")
    registry = load_json(policy.path(source.parent.parent / "artifacts.json"))["artifacts"]
    if (
        not any(
            a["relative_path"] == inputs["source_blend"] and a["sha256"] == inputs["source_sha256"]
            for a in registry
        )
        or hashlib.sha256(source.read_bytes()).hexdigest() != inputs["source_sha256"]
    ):
        raise InputError("Registered sprite source hash mismatch")
    motion = load_json(policy.path(source.parent / "motion.json"))
    inspect_motion(motion)
    if motion["asset_id"] != inputs["asset_id"]:
        raise InputError("Source semantic asset ID mismatch")
    digest = canonical_digest(inputs)
    if context.dry_run:
        return Result(
            input_digest=digest, data={"dry_run": True, "execution_status": "NOT_RUN", "frames": 6}
        )
    config = configuration(policy)
    executable = discover_tool("blender", config.blender_executable)
    if executable is None:
        return failure(ErrorKind.MISSING_DEPENDENCY, "PF-SPRITE-BLENDER", "Install Blender 5.2.2")
    run_id = "sprites-" + (context.run_id or uuid4().hex[:16])
    relative = "runs/" + run_id
    output = policy.mkdir(relative + "/asset")
    worker = files("polyforge.sprites").joinpath("worker.py")
    request = atomic_json(
        policy,
        relative + "/input.json",
        {
            **inputs,
            "source": str(source),
            "input_digest": digest,
            "worker_sha256": hashlib.sha256(worker.read_bytes()).hexdigest(),
        },
    )
    with FileLock(
        policy,
        ".polyforge/locks/blender-worker.lock",
        wait_seconds=min(context.timeout_seconds, config.blender_timeout_seconds),
        cancel=context.cancel,
    ):
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
                str(request),
                str(output),
            ],
            policy,
            relative + "/log",
            ProcessPolicy(
                (executable,),
                config.blender_timeout_seconds,
                config.max_output_bytes,
                config.memory_limit_mb,
            ),
            cancel=context.cancel,
        )
    atomic_json(policy, relative + "/process.json", asdict(process))
    if process.reason != "exit" or process.returncode != 0:
        return Result(
            status="FAIL",
            exit_code=9 if process.reason == "cancelled" else 5,
            run_id=run_id,
            evidence_paths=[relative + "/process.json"],
        )
    frames = [policy.path(output / f"frame-{i}.png").read_bytes() for i in range(6)]
    metadata = {
        "schema_version": "1.0.0",
        "asset_id": inputs["asset_id"],
        "frame_size": 128,
        "frame_count": 6,
        "pixels_per_unit": 64,
        "fps": 6,
        "pivot": [0.5, 0.1],
        "trim": "NONE",
        "order": list(range(6)),
        "frame_sha256": [hashlib.sha256(f).hexdigest() for f in frames],
        "source_sha256": inputs["source_sha256"],
        "framing": "FIXED_ORTHOGRAPHIC",
        "source_license": "Apache-2.0",
        "units": "pixels",
        "duration_seconds": 1,
        "route": "BAKED_ROBOT",
    }
    baked = load_json(output / "bake.json")
    if [s["source_frame"] for s in baked["samples"]] != [1, 5, 9, 13, 17, 21] or any(
        abs(s["pivot"][0] - 0.5) > 0.0001 or abs(s["pivot"][1] - 0.1) > 0.0001
        for s in baked["samples"]
    ):
        raise InputError(
            "Native frame order/root-projected pivot drift", kind=ErrorKind.CONTRACT_FAILURE
        )
    sheet = atlas(frames)
    policy.path(output / "atlas.png").write_bytes(sheet)
    inspection = inspect_strip(frames, sheet, metadata)
    atomic_json(policy, relative + "/asset/atlas.json", metadata)
    atomic_json(policy, relative + "/inspection.json", inspection)
    records = [
        {
            "relative_path": p.relative_to(policy.root).as_posix(),
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "bytes": p.stat().st_size,
            "input_digest": digest,
        }
        for p in sorted(output.iterdir())
        if p.is_file() and p.suffix != ".blend1"
    ]
    records = complete_records(policy, run_id, "S3", records, input_digest=digest)
    atomic_json(policy, relative + "/artifacts.json", {"artifacts": records})
    return Result(
        run_id=run_id,
        input_digest=digest,
        evaluated_test_status="PASS",
        data={
            "atlas": relative + "/asset/atlas.png",
            "metadata": relative + "/asset/atlas.json",
            "source_blend": relative + "/asset/source.blend",
            "visual_review": "REVIEW",
        },
        evidence_paths=[relative + "/artifacts.json", relative + "/inspection.json"],
    )
