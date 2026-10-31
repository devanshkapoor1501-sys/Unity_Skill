"""Bounded headless Blender adapter with immutable inputs and owned run evidence."""

from __future__ import annotations

import copy
import hashlib
import re
import shutil
from dataclasses import asdict, replace
from importlib.resources import files
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.blender.audit import VIEWS, validate_audit, validate_exchange
from polyforge.blender.recipes import RECIPES, expand_recipe, validate_geometry, validate_recipe
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


def execute_recipe(
    recipe: dict[str, Any],
    context: RunContext,
    *,
    precheck_only: bool = False,
    audit_export: bool = False,
    source: Path | None = None,
) -> Result:
    validate_recipe(recipe)
    recipe = copy.deepcopy(recipe)
    recipe.setdefault("pivot", "base_center")
    recipe.setdefault("materials", [{"id": "base", "color_rgba": [0.3, 0.3, 0.3, 1]}])
    policy = WorkspacePolicy(context.workspace)
    config_path = policy.path("polyforge.toml")
    config = load_config(config_path if config_path.is_file() else None)
    if audit_export and config.preview_resolution > 1024:
        raise InputError("Audit previews are limited to 1024 pixels")
    source_digest = None
    if source is not None:
        source = policy.path(source)
        if not source.is_file():
            raise InputError("Audit source must be an existing managed Blender file")
        source_digest = hashlib.sha256(source.read_bytes()).hexdigest()
    input_digest = canonical_digest(
        {
            "recipe": recipe,
            "seed": context.seed,
            "source_sha256": source_digest,
            "audit_export": audit_export,
            "preview_resolution": config.preview_resolution if audit_export else None,
        }
    )
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
                    *(
                        [
                            "runs/<new-run>/asset/" + name
                            for name in (
                                "asset.fbx",
                                "material.json",
                                "audit_metadata.json",
                                "handoff.json",
                                "fbx_roundtrip.json",
                                "view_checks.json",
                                "review.html",
                                "front.png",
                                "side.png",
                                "top.png",
                                "iso.png",
                            )
                        ]
                        if audit_export
                        else []
                    ),
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
        "audit_worker_sha256": hashlib.sha256(
            files("polyforge.blender").joinpath("audit_worker.py").read_bytes()
        ).hexdigest(),
        "interchange_sha256": hashlib.sha256(
            files("polyforge.blender").joinpath("interchange.py").read_bytes()
        ).hexdigest(),
        "executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
        "executable": str(executable),
        "required_version": "5.2.2",
        "validator": "geometry.v1",
    }
    run_id = "mesh-" + (context.run_id or uuid4().hex[:16])
    if context.run_id and not audit_export:
        completed = policy.path("runs/" + run_id + "/asset/worker-complete.json")
        if completed.is_file():
            receipt = load_json(completed)
            folder = completed.parent
            if (
                receipt["input_digest"] != input_digest
                or receipt["toolchain"] != fingerprint
                or not all(
                    hashlib.sha256(policy.path(folder / item["name"]).read_bytes()).hexdigest()
                    == item["sha256"]
                    for item in receipt["files"]
                )
            ):
                raise InputError(
                    "Interrupted mesh output identity/hash mismatch",
                    kind=ErrorKind.CONTRACT_FAILURE,
                )
            metrics = load_json(folder / "metrics.json")
            validate_geometry(recipe, metrics)
            recovered_artifacts = [
                {
                    "artifact_id": run_id + ":" + item["name"],
                    "relative_path": (folder / item["name"]).relative_to(policy.root).as_posix(),
                    "sha256": item["sha256"],
                    "bytes": (folder / item["name"]).stat().st_size,
                    "input_digest": input_digest,
                    "toolchain": fingerprint,
                }
                for item in receipt["files"]
            ]
            recovered_artifacts = complete_records(
                policy, run_id, "S2", recovered_artifacts, input_digest=input_digest
            )
            atomic_json(
                policy, "runs/" + run_id + "/artifacts.json", {"artifacts": recovered_artifacts}
            )
            recovered_journal = RunJournal(policy, run_id)
            if recovered_journal.read()["stages"]["S2"]["status"] == "running":
                recovered_journal.transition(
                    "S2",
                    "passed",
                    evidence=["runs/" + run_id + "/artifacts.json"],
                    note="Recovered native worker completion receipt",
                )
            return Result(
                run_id=run_id,
                input_digest=input_digest,
                evaluated_test_status="PASS",
                metrics=metrics,
                data={
                    "source_blend": (folder / "source.blend").relative_to(policy.root).as_posix(),
                    "metrics_path": (folder / "metrics.json").relative_to(policy.root).as_posix(),
                    "recovered_native_output": True,
                },
                evidence_paths=["runs/" + run_id + "/artifacts.json"],
            )
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
            "audit_export": audit_export,
            "preview_resolution": config.preview_resolution,
            "source": str(source) if source is not None else None,
            "source_sha256": source_digest,
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
            cancel=context.cancel,
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
        if source is not None:
            shutil.copyfile(source, output / "source.blend")
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
                cancel=context.cancel,
            )
        atomic_json(policy, relative + "/process.json", asdict(process))
        if process.reason != "exit" or process.returncode != 0:
            if audit_export and policy.path(output / "metrics.json").is_file():
                partial = load_json(policy.path(output / "metrics.json"))
                validate_geometry(recipe, partial)
                journal.transition("S2", "passed", evidence=[relative + "/asset/metrics.json"])
                active_stage = "S3"
                journal.transition("S3", "running")
                diagnostic_path = policy.path(output / "diagnostics.json")
                if diagnostic_path.is_file():
                    raise InputError(
                        "Audit geometry diagnostics failed; see "
                        + str(diagnostic_path.relative_to(policy.root)),
                        kind=ErrorKind.CONTRACT_FAILURE,
                        code="PF-AUDIT-DIAGNOSTICS",
                    )
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
        s2_files = ("source.blend", "metrics.json", "logical-geometry.json")
        s3_files: tuple[str, ...] = (
            (
                "asset.fbx",
                "material.json",
                "audit_metadata.json",
                "fbx_roundtrip.json",
                "handoff.json",
                "front.png",
                "side.png",
                "top.png",
                "iso.png",
            )
            if audit_export
            else ()
        )
        if audit_export:
            active_stage = "S3"
            journal.transition("S2", "passed", evidence=[relative + "/asset/metrics.json"])
            journal.transition("S3", "running")
            metadata = load_json(policy.path(output / "audit_metadata.json"))
            validate_audit(metadata, metrics)
            validate_exchange(
                recipe,
                metrics,
                load_json(policy.path(output / "material.json")),
                load_json(policy.path(output / "handoff.json")),
                load_json(policy.path(output / "fbx_roundtrip.json")),
            )
            image_reports = {}
            for view in VIEWS:
                report = inspect_png(
                    policy.path(output / (view + ".png")).read_bytes(),
                    expected_size=config.preview_resolution,
                )
                if not report["nonblank"] or not report["framing_pass"]:
                    raise InputError(
                        "Blank/clipped audit view: " + view, kind=ErrorKind.CONTRACT_FAILURE
                    )
                image_reports[view] = report
            atomic_json(policy, relative + "/asset/view_checks.json", image_reports)
            s3_files += ("view_checks.json",)
            if not policy.path(output / "asset.fbx").read_bytes().startswith(b"Kaydara FBX Binary"):
                raise InputError("Invalid FBX output", kind=ErrorKind.CONTRACT_FAILURE)
            if (
                source is not None
                and hashlib.sha256(source.read_bytes()).hexdigest() != source_digest
            ):
                raise InputError(
                    "Original source changed during audit", kind=ErrorKind.CONTRACT_FAILURE
                )
            review = (
                '<!doctype html><meta charset="utf-8"><title>PolyForge asset review</title>'
                "<h1>Visual review required</h1><p>Geometry checks passed. "
                "Artistic quality: REVIEW. Unity import: NOT_RUN.</p>"
                + "".join(
                    '<figure><img width="256" src="'
                    + v
                    + '.png"><figcaption>'
                    + v
                    + "</figcaption></figure>"
                    for v in VIEWS
                )
            )
            policy.path(output / "review.html").write_text(review, encoding="utf-8")
            s3_files += ("review.html",)
        artifacts: list[dict[str, Any]] = []
        for filename in (*s2_files, *s3_files):
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
        artifacts = complete_records(
            policy, run_id, "S3" if audit_export else "S2", artifacts, input_digest=input_digest
        )
        registry = atomic_json(policy, relative + "/artifacts.json", {"artifacts": artifacts})
        if audit_export:
            binding = atomic_json(
                policy,
                relative + "/export_binding.json",
                {
                    "schema_version": "1.0.0",
                    "asset_id": recipe["asset_id"],
                    "input_digest": input_digest,
                    "source_geometry_digest": metrics["geometry_digest"],
                    "artifacts": [
                        {k: v for k, v in row.items() if k != "resolved_location"}
                        for row in artifacts
                    ],
                    "visual_review_status": "REVIEW",
                    "unity_import_status": "NOT_RUN",
                },
            )
            context.artifact_registry[run_id + ":export_binding.json"] = complete_records(
                policy,
                run_id,
                "S3",
                [
                    {
                        "artifact_id": run_id + ":export_binding.json",
                        "relative_path": binding.relative_to(policy.root).as_posix(),
                    }
                ],
                input_digest=input_digest,
            )[0]
        journal.transition(
            active_stage, "passed", evidence=[str(registry.relative_to(policy.root))]
        )
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
                "through": "S3" if audit_export else "S2",
                "visual_review_status": "REVIEW" if audit_export else "NOT_RUN",
                "unity_import_status": "NOT_RUN",
                "fbx_path": relative + "/asset/asset.fbx" if audit_export else None,
                "export_binding": relative + "/export_binding.json" if audit_export else None,
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
