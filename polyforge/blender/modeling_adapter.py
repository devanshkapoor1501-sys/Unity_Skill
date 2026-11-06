"""Bounded advanced modeling adapter with independent native inspection."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, replace
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.blender.modeling import compile_modeling
from polyforge.blender.modeling_inspection import validate_modeling_report
from polyforge.capabilities.protocol import RunContext
from polyforge.config import load_config
from polyforge.contracts.images import inspect_png
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.doctor import discover_tool
from polyforge.runner.artifacts import complete_records
from polyforge.runner.locks import FileLock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import RunJournal, atomic_json
from polyforge.security.paths import WorkspacePolicy

ARTIFACT_NAMES = (
    "source.blend",
    "asset.fbx",
    "lod.fbx",
    "inspection.json",
    "provenance.json",
    "front.png",
    "side.png",
    "top.png",
    "iso.png",
)


def _sha(path: Path, *, max_bytes: int = 67_108_864) -> str:
    if not path.is_file() or not 0 < path.stat().st_size <= max_bytes:
        raise InputError(f"Modeling file is absent, empty or exceeds its limit: {path.name}")
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _contract_error(message: str) -> InputError:
    return InputError(message, kind=ErrorKind.CONTRACT_FAILURE, code="PF-MODELING-EVIDENCE")


def _inspection(policy: WorkspacePolicy, output: Path, plan: dict[str, Any]) -> dict[str, Any]:
    report = load_json(policy.path(output / "inspection.json"))
    if not isinstance(report, dict):
        raise _contract_error("Modeling inspection must be an object")
    validate_modeling_report(plan, report)
    source_sha = _sha(policy.path(output / "source.blend"))
    provenance = load_json(policy.path(output / "provenance.json"))
    if report["source_sha256_before"] != source_sha or provenance != {
        "schema_version": "1.0.0",
        "asset_id": plan["asset_id"],
        "input_digest": plan["input_digest"],
        "tool_version": "5.2.2",
        "editable_source": "source.blend",
        "source_sha256": source_sha,
        "export_policy": "EVALUATED_COPIES_SOURCE_MODIFIERS_PRESERVED",
        "coordinate_basis": report["coordinate_basis"],
        "artistic_status": "REVIEW",
    }:
        raise _contract_error("Modeling source, provenance or independent inspection differs")
    return report


def _result(
    context: RunContext,
    run_id: str,
    identity: str,
    plan: dict[str, Any],
    report: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> Result:
    relative = "runs/" + run_id
    return Result(
        operation_id=context.operation_id,
        run_id=run_id,
        input_digest=identity,
        evaluated_test_status="PASS",
        data={
            "source_blend": relative + "/asset/source.blend",
            "inspection": report,
            "plan": plan,
            "artistic_status": "REVIEW",
            "editable_modifiers_preserved": True,
        },
        evidence_paths=[relative + "/artifacts.json", relative + "/asset/inspection.json"],
        artifact_ids=[row["artifact_id"] for row in artifacts],
    )


def _recover(
    journal: RunJournal,
    context: RunContext,
    identity: str,
    plan: dict[str, Any],
) -> Result:
    policy, relative = journal.policy, journal.relative
    saved = load_json(policy.path(relative + "/result.json"))
    rows = load_json(policy.path(relative + "/artifacts.json"))
    if saved != {"identity": identity, "inventory_digest": canonical_digest(rows)}:
        raise _contract_error("Modeling run identity or artifact receipt differs")
    if not isinstance(rows, dict) or not isinstance(artifacts := rows.get("artifacts"), list):
        raise _contract_error("Invalid modeling artifact receipt")
    if len(artifacts) != len(ARTIFACT_NAMES):
        raise _contract_error("Modeling artifact inventory is incomplete")
    stages = journal.read()["stages"]
    if any(stages[f"S{i}"]["status"] != "passed" for i in range(4)):
        raise _contract_error("Modeling journal has incomplete stages")
    for name, row in zip(ARTIFACT_NAMES, artifacts, strict=True):
        expected = relative + "/asset/" + name
        path = policy.path(expected)
        if (
            not isinstance(row, dict)
            or row.get("relative_path") != expected
            or row.get("artifact_id") != journal.run_id + ":" + expected
            or row.get("run_id") != journal.run_id
            or row.get("stage") != "S3"
            or row.get("input_digest") != identity
            or row.get("sha256") != _sha(path)
            or row.get("bytes") != path.stat().st_size
        ):
            raise _contract_error("Recovered modeling artifact changed or is misbound")
    report = _inspection(policy, policy.path(relative + "/asset"), plan)
    return _result(context, journal.run_id, identity, plan, report, artifacts)


def execute_modeling(kind: str, inputs: dict[str, Any], context: RunContext) -> Result:
    plan = compile_modeling(kind, inputs, seed=context.seed)
    policy = WorkspacePolicy(context.workspace)
    config_path = policy.path("polyforge.toml")
    config = load_config(config_path if config_path.is_file() else None)
    if context.cancel is not None and context.cancel.is_set():
        return failure(ErrorKind.INTERRUPTED, "PF-MODELING-CANCELLED", "Modeling cancelled")
    if context.dry_run:
        return Result(
            input_digest=plan["input_digest"],
            data={
                "plan": plan,
                "execution_status": "NOT_RUN",
                "dry_run": True,
                "planned_writes": [
                    "runs/<new-run>/asset/source.blend",
                    "runs/<new-run>/asset/asset.fbx",
                    "runs/<new-run>/asset/lod.fbx",
                    "runs/<new-run>/asset/inspection.json",
                ],
            },
        )
    executable = discover_tool("blender", config.blender_executable)
    if executable is None or not executable.is_file():
        return failure(
            ErrorKind.MISSING_DEPENDENCY,
            "PF-BLENDER-MISSING",
            "Advanced modeling requires Blender 5.2.2",
        )
    scripts = {
        name: Path(str(files("polyforge.blender").joinpath(name + ".py")))
        for name in ("modeling_worker", "modeling_inspector")
    }
    fingerprint = {name: _sha(path) for name, path in scripts.items()}
    fingerprint["executable"] = _sha(executable, max_bytes=536_870_912)
    identity = canonical_digest({"plan": plan, "toolchain": fingerprint})
    run_id = "model-" + (context.run_id or uuid4().hex[:16])
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise InputError("Invalid modeling run identity")
    relative = "runs/" + run_id
    result_path = policy.path(relative + "/result.json")
    if result_path.exists():
        return _recover(RunJournal(policy, run_id), context, identity, plan)
    # Refuse to overwrite partial outputs or preexisting files in a reused run.
    policy.mkdir("runs")
    try:
        policy.path(relative).mkdir(exist_ok=False)
    except FileExistsError as exc:
        raise _contract_error("Modeling run already exists without a completion receipt") from exc
    journal = RunJournal.create(policy, run_id, retry_limit=0)
    output = policy.mkdir(relative + "/asset")
    job = atomic_json(
        policy,
        relative + "/input.json",
        {
            "plan": plan,
            "output_dir": str(output),
            "source_blend": str(output / "source.blend"),
            "input_digest": identity,
        },
    )
    process_policy = ProcessPolicy(
        (executable,),
        min(context.timeout_seconds, config.blender_timeout_seconds),
        min(context.max_output_bytes, config.max_output_bytes),
        config.memory_limit_mb,
    )
    active = "S0"
    journal.transition(active, "running")
    try:
        probe = run_process(
            [str(executable), "--version"],
            policy,
            relative + "/precheck",
            process_policy,
            cancel=context.cancel,
        )
        text = policy.path(probe.stdout_path).read_text(encoding="utf-8")
        if (
            probe.returncode != 0
            or probe.reason != "exit"
            or re.search(r"^Blender 5\.2\.2(?:\s|$)", text, re.MULTILINE) is None
        ):
            raise InputError(
                "Pinned Blender 5.2.2 version check failed", kind=ErrorKind.MISSING_DEPENDENCY
            )
        journal.transition(active, "passed", evidence=[probe.stdout_path])
        journal.transition("S1", "running")
        journal.transition("S1", "passed", evidence=[relative + "/input.json"])
        active = "S2"
        journal.transition(active, "running")
        with FileLock(
            policy,
            ".polyforge/locks/blender-worker.lock",
            wait_seconds=process_policy.timeout_seconds,
            cancel=context.cancel,
        ):
            source_hash = None
            for name, script in scripts.items():
                snapshot = policy.path(relative + "/" + name + ".py")
                with snapshot.open("xb") as stream:
                    stream.write(script.read_bytes())
                if _sha(snapshot) != fingerprint[name]:
                    raise _contract_error("Fixed Blender script changed before execution")
                if name == "modeling_inspector":
                    source_hash = _sha(policy.path(output / "source.blend"))
                    journal.transition("S2", "passed", evidence=[relative + "/asset/source.blend"])
                    active = "S3"
                    journal.transition(active, "running")
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
                        str(snapshot),
                        "--",
                        str(job),
                    ],
                    policy,
                    relative + "/" + name,
                    process_policy,
                    cancel=context.cancel,
                )
                atomic_json(policy, relative + "/" + name + "/process.json", asdict(process))
                if process.reason != "exit" or process.returncode != 0:
                    raise InputError(
                        "Advanced modeling worker failed; inspect its owned logs",
                        kind=ErrorKind.INTERRUPTED
                        if process.reason == "cancelled"
                        else ErrorKind.PRODUCER_FAILURE,
                        code="PF-MODELING-NATIVE",
                    )
            if source_hash != _sha(policy.path(output / "source.blend")):
                raise InputError(
                    "Independent inspection changed editable source",
                    kind=ErrorKind.CONTRACT_FAILURE,
                )
        report = _inspection(policy, output, plan)
        rows = []
        for name in ARTIFACT_NAMES:
            path = policy.path(output / name)
            sha = _sha(path)
            if name.endswith(".png"):
                image = inspect_png(path.read_bytes(), expected_size=256)
                if not image["nonblank"] or not image["framing_pass"]:
                    raise InputError(
                        "Modeling audit image is blank or clipped", kind=ErrorKind.CONTRACT_FAILURE
                    )
            rows.append(
                {
                    "relative_path": path.relative_to(policy.root).as_posix(),
                    "sha256": sha,
                    "bytes": path.stat().st_size,
                    "input_digest": identity,
                    "toolchain": fingerprint,
                }
            )
        artifacts = complete_records(policy, run_id, "S3", rows, input_digest=identity)
        registry = {"artifacts": artifacts}
        atomic_json(policy, relative + "/artifacts.json", registry)
        journal.transition(active, "passed", evidence=[relative + "/asset/inspection.json"])
        atomic_json(
            policy,
            relative + "/result.json",
            {"identity": identity, "inventory_digest": canonical_digest(registry)},
        )
        return _result(context, run_id, identity, plan, report, artifacts)
    except (InputError, OSError) as exc:
        if journal.read()["stages"][active]["status"] == "running":
            journal.transition(active, "failed", note=str(exc))
        result = (
            failure(exc.kind, exc.code, str(exc))
            if isinstance(exc, InputError)
            else failure(ErrorKind.PRODUCER_FAILURE, "PF-MODELING-IO", str(exc))
        )
        return replace(
            result,
            run_id=run_id,
            operation_id=context.operation_id,
            evidence_paths=[relative + "/events.jsonl"],
        )
