"""S4 orchestration over owned Unity invocations and independently checked evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import threading
import zipfile
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.blender.adapter import execute_recipe
from polyforge.blender.worker import name_for
from polyforge.capabilities.protocol import RunContext
from polyforge.compiler.commands import manifest_command
from polyforge.config import Config, load_config
from polyforge.contracts.manifest import Manifest
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.doctor import discover_tool
from polyforge.runner.locks import FileLock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.runner.state import RunJournal, atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bootstrap import check_project_idle, installed_template, prepare_project
from polyforge.unity.evidence import EDITMODE_TESTS, reconcile_report, verify_test_xml


def configuration(policy: WorkspacePolicy) -> Config:
    path = policy.path("polyforge.toml")
    return load_config(path if path.is_file() else None)


def unity_tool(config: Config) -> Path:
    executable = discover_tool("unity", config.unity_executable)
    if executable is None or not executable.is_file():
        raise InputError(
            "Install Unity 6000.6.3f1 with its URP template",
            kind=ErrorKind.MISSING_DEPENDENCY,
            code="PF-UNITY-MISSING",
        )
    return executable


def launch(
    policy: WorkspacePolicy,
    executable: Path,
    config: Config,
    relative: str,
    mode: str,
    *,
    request: Path | None = None,
    output: Path | None = None,
    allow_contract_failure: bool = False,
    test_platform: str = "EditMode",
    test_filter: str = "PolyForge.Editor.Tests",
    game_input: Path | None = None,
    scenario_input: Path | None = None,
    telemetry_directory: Path | None = None,
    cancel: threading.Event | None = None,
) -> dict[str, Any]:
    if test_platform not in {"EditMode", "PlayMode"} or test_filter not in {
        "PolyForge.Editor.Tests",
        "PolyForge.Game.Editor.Tests",
        "PolyForge.Game.Tests",
        "PolyForge.Animation.Editor.Tests",
        "PolyForge.Animation.Tests",
    }:
        raise InputError("Unknown owned Unity test platform/filter")
    policy.mkdir(relative)
    args = [
        str(executable),
        "-batchmode",
        "-nographics",
        "-job-worker-count",
        "2",
        "-projectPath",
        str(policy.path("UnityProject")),
        "-logFile",
        "-",
        "-upmLogFile",
        str(policy.path(relative + "/upm.log")),
    ]
    if request is not None:
        args += ["-polyforgeInput", str(policy.path(request))]
    for key, path_value in (
        ("-polyforgeGameInput", game_input),
        ("-polyforgeScenarioInput", scenario_input),
        ("-polyforgeTelemetry", telemetry_directory),
    ):
        if path_value is not None:
            args += [key, str(policy.path(path_value))]
    if mode == "compile":
        args += ["-quit"]
    elif mode == "tests":
        assert output is not None
        args += [
            "-runTests",
            "-testPlatform",
            test_platform,
            "-testFilter",
            test_filter,
            "-testResults",
            str(policy.path(output)),
        ]
    elif mode == "animation":
        args += ["-executeMethod", "PolyForge.Animation.Editor.AnimationBuilder.BuildBatch"]
        if output is not None:
            args += ["-polyforgeOutput", str(policy.path(output))]
    elif mode in {"game", "player"}:
        method = "BuildBatch" if mode == "game" else "BuildPlayerBatch"
        args += ["-executeMethod", "PolyForge.Game.Editor.GameBuilder." + method]
        if output is not None:
            args += ["-polyforgeOutput", str(policy.path(output))]
    else:
        assert mode in {"build", "reconcile", "restore"} and output is not None
        method = {"build": "BuildBatch", "reconcile": "ReconcileBatch", "restore": "ReimportBatch"}[
            mode
        ]
        args += [
            "-executeMethod",
            "PolyForge.Editor.PolyForgeBuilder." + method,
            "-polyforgeOutput",
            str(policy.path(output)),
        ]
    outcome = run_process(
        args,
        policy,
        relative,
        ProcessPolicy(
            (executable,),
            config.unity_timeout_seconds,
            config.max_output_bytes,
            config.memory_limit_mb,
        ),
        cancel=cancel,
    )
    value = {"argv": args, **asdict(outcome)}
    atomic_json(policy, relative + "/process.json", value)
    if (
        allow_contract_failure
        and mode in {"build", "reconcile", "restore"}
        and outcome.reason == "exit"
        and outcome.returncode == 6
    ):
        return value
    if outcome.reason != "exit" or outcome.returncode != 0:
        log = policy.path(outcome.stdout_path).read_text("utf-8") if outcome.stdout_path else ""
        kind = (
            ErrorKind.INTERRUPTED
            if outcome.reason == "cancelled"
            else ErrorKind.TEST_FAILURE
            if mode == "tests" and outcome.returncode == 2
            else ErrorKind.MISSING_DEPENDENCY
            if "No valid Unity Editor license" in log
            else (
                ErrorKind.CONTRACT_FAILURE
                if outcome.returncode == 6
                else ErrorKind.PRODUCER_FAILURE
            )
        )
        raise InputError(
            f"Unity {mode} failed: {outcome.reason}, exit {outcome.returncode}; "
            f"see {relative}/stdout.txt",
            kind=kind,
            code="PF-UNITY-WORKER",
        )
    return value


def geometry_identity(recipe: dict[str, Any]) -> str:
    value = copy.deepcopy(recipe)
    value["materials"] = [{"id": m["id"]} for m in value["materials"]]
    return canonical_digest(value)


def reusable_export(policy: WorkspacePolicy, recipe: dict[str, Any], seed: int) -> Path | None:
    candidates = []
    for folder in policy.path("runs").glob("mesh-*"):
        folder = policy.path(folder)
        if not policy.path(folder / "export_binding.json").is_file():
            continue
        job = load_json(policy.path(folder / "input.json"))
        if (
            job["recipe"]["asset_id"] != recipe["asset_id"]
            or job["seed"] != seed
            or geometry_identity(job["recipe"]) != geometry_identity(recipe)
        ):
            continue
        state = load_json(policy.path(folder / "state.json"))
        if state["stages"]["S3"]["status"] == "passed":
            candidates.append((state["updated_utc"], folder))
    if not candidates:
        return None
    folder = max(candidates)[1]
    registry = load_json(policy.path(folder / "artifacts.json"))
    required = {
        str((folder / "asset" / name).relative_to(policy.root))
        for name in ("asset.fbx", "source.blend", "metrics.json", "material.json", "handoff.json")
    }
    entries = registry.get("artifacts") if isinstance(registry, dict) else None
    if not isinstance(entries, list) or not entries:
        raise InputError("S3 export has no artifact inventory", kind=ErrorKind.CONTRACT_FAILURE)
    registered: set[str] = set()
    for item in entries:
        if not isinstance(item, dict) or not isinstance(item.get("relative_path"), str):
            raise InputError("Malformed S3 artifact inventory", kind=ErrorKind.CONTRACT_FAILURE)
        path = policy.path(item["relative_path"])
        if not path.is_relative_to(folder) or str(path.relative_to(policy.root)) in registered:
            raise InputError("S3 artifact path/identity mismatch", kind=ErrorKind.CONTRACT_FAILURE)
        registered.add(str(path.relative_to(policy.root)))
        if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            raise InputError("Registered S3 artifact changed", kind=ErrorKind.CONTRACT_FAILURE)
    if not required.issubset(registered):
        raise InputError(
            "Missing registered source/export evidence", kind=ErrorKind.CONTRACT_FAILURE
        )
    return policy.path(folder / "asset")


def asset_spec(recipe: dict[str, Any], folder: Path, collider: str) -> dict[str, Any]:
    metrics = load_json(folder / "metrics.json")
    identifier = recipe["asset_id"]
    return {
        "id": identifier,
        "fbx_path": f"Assets/PolyForgeGenerated/Models/{identifier}.fbx",
        "sha256": hashlib.sha256((folder / "asset.fbx").read_bytes()).hexdigest(),
        "bounds_m": metrics["bounds_unity_m"],
        "collider": collider,
        "materials": [
            {
                "id": m["id"],
                "base_color_rgba": m["color_rgba"],
                "metallic": m.get("metallic", 0),
                "roughness": m.get("roughness", 0.65),
            }
            for m in recipe["materials"]
        ],
        "modules": [
            {
                "id": m["id"],
                "name": name_for(identifier + ":module:" + m["id"]),
                "material_ids": [m["material_id"]],
            }
            for m in recipe["modules"]
        ],
        "sockets": [
            {
                "id": s["id"],
                "name": name_for(identifier + ":socket:" + s["id"]),
                "position_m": metrics["socket_positions_unity_m"][s["id"]],
            }
            for s in recipe["sockets"]
        ],
    }


def build_unity(
    model: Manifest,
    recipes: dict[str, Any],
    *,
    dry_run: bool = False,
    allow_package_downloads: bool = False,
    cancel: threading.Event | None = None,
) -> Result:
    if cancel is not None and cancel.is_set():
        return failure(
            ErrorKind.INTERRUPTED, "PF-UNITY-CANCELLED", "Build cancelled before mutation"
        )
    policy = WorkspacePolicy(model.workspace)
    config = configuration(policy)
    if dry_run:
        project = policy.path("UnityProject")
        if project.exists() and not policy.path(project / ".polyforge-project.json").is_file():
            raise InputError("Refusing an unmanaged Unity project")
        return Result(
            input_digest=model.input_digest,
            data={
                "through": "S4",
                "dry_run": True,
                "project": str(project),
                "execution_status": "NOT_RUN",
            },
        )
    marker = policy.path(".polyforge/unity-network-approval.json")
    authorized = marker.is_file() and load_json(marker).get("package_downloads_authorized") is True
    if not authorized and not allow_package_downloads:
        return failure(
            ErrorKind.POLICY_DENIED,
            "PF-UNITY-DOWNLOAD-OPT-IN",
            "Unity may resolve packages over the network; pass --allow-package-downloads",
        )
    executable = unity_tool(config)
    template = installed_template(executable)
    check_project_idle(policy)
    project = prepare_project(policy, template, dry_run=True)
    compiled = manifest_command(policy.path("game_manifest.json"), "plan")
    run_id = "unity-" + uuid4().hex[:16]
    relative = "runs/" + run_id
    journal = RunJournal.create(policy, run_id, retry_limit=0)
    journal.transition("S4", "running")
    try:
        with FileLock(policy, ".polyforge/locks/unity-project.lock"):
            prepare_project(policy, template)
            from polyforge.unity.upgrade import sync_package

            sync_package(policy)
            atomic_json(
                policy,
                marker,
                {
                    "package_downloads_authorized": True,
                    "scope": "managed Unity project package resolution",
                    "trust": "TRUSTED_LOCAL",
                },
            )
            assets = {a["id"]: a for a in model.data["assets"]}
            specs = []
            source_bindings = []
            for identifier in model.asset_order:
                recipe = recipes[identifier]
                folder = reusable_export(policy, recipe, model.data["project"]["seed"])
                reused = folder is not None
                if folder is None:
                    result = execute_recipe(
                        recipe,
                        RunContext(policy.root, seed=model.data["project"]["seed"], cancel=cancel),
                        audit_export=True,
                    )
                    if result.status != "PASS":
                        journal.transition("S4", "failed", note="S3 prerequisite failed")
                        return result
                    folder = policy.path(result.data["source_blend"]).parent
                spec = asset_spec(recipe, folder, assets[identifier]["collider"])
                target = policy.path(project / spec["fbx_path"])
                policy.mkdir(target.parent)
                if (
                    not target.is_file()
                    or hashlib.sha256(target.read_bytes()).hexdigest() != spec["sha256"]
                ):
                    shutil.copyfile(folder / "asset.fbx", target)
                specs.append(spec)
                source_bindings.append(
                    {
                        "asset_id": identifier,
                        "source": str(folder.relative_to(policy.root)),
                        "reused_geometry": reused,
                        "fbx_sha256": spec["sha256"],
                    }
                )
            request = {
                "schema_version": "1.0.0",
                "input_digest": model.input_digest,
                "assets": specs,
                "actors": model.data["actors"],
                "scene_bounds_m": model.data["scene"]["bounds_m"],
            }
            request_path = atomic_json(policy, relative + "/request.json", request)
            atomic_json(
                policy,
                relative + "/inputs.json",
                {
                    "manifest_digest": model.digest,
                    "input_fingerprints": model.input_fingerprints,
                    "sources": source_bindings,
                    "unity_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                    "package_downloads_authorized": True,
                    "security_scope": "TRUSTED_LOCAL",
                    "isolation_verified": False,
                    "package_manifest": load_json(project / "Packages/manifest.json"),
                },
            )
            launch(policy, executable, config, relative + "/compile", "compile", cancel=cancel)
            output = policy.path(relative + "/bindings.json")
            launch(
                policy,
                executable,
                config,
                relative + "/build",
                "build",
                request=request_path,
                output=output,
                cancel=cancel,
            )
            reconciled = reconcile_report(request, load_json(output))
            if reconciled["status"] != "PASS":
                raise InputError(
                    "Native bindings differ from source: " + json.dumps(reconciled["issues"]),
                    kind=ErrorKind.CONTRACT_FAILURE,
                )
            tests_path = policy.path(relative + "/editmode.xml")
            launch(
                policy,
                executable,
                config,
                relative + "/editmode",
                "tests",
                request=request_path,
                output=tests_path,
                cancel=cancel,
            )
            tests = verify_test_xml(tests_path, EDITMODE_TESTS)
            atomic_json(policy, relative + "/reconcile.json", reconciled)
            atomic_json(policy, relative + "/tests.json", tests)
            archive_path = policy.path(relative + "/native-output.zip")
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for scope in ("Assets", "Packages", "ProjectSettings"):
                    for path in sorted(policy.path(project / scope).rglob("*")):
                        path = policy.path(path)
                        if path.is_file():
                            archive.write(path, path.relative_to(project).as_posix())
            outputs = (
                "request.json",
                "inputs.json",
                "bindings.json",
                "reconcile.json",
                "editmode.xml",
                "tests.json",
                "native-output.zip",
            )
            artifacts: list[dict[str, Any]] = []
            for name in outputs:
                path = policy.path(relative + "/" + name)
                artifacts.append(
                    {
                        "artifact_id": run_id + ":" + name,
                        "relative_path": relative + "/" + name,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "bytes": path.stat().st_size,
                        "input_digest": model.input_digest,
                    }
                )
            atomic_json(policy, relative + "/artifacts.json", {"artifacts": artifacts})
            atomic_json(policy, ".polyforge/unity-request.json", request)
            atomic_json(
                policy,
                ".polyforge/unity-latest.json",
                {
                    "run_id": run_id,
                    "request": relative + "/request.json",
                    "bindings": relative + "/bindings.json",
                },
            )
            evidence = [
                relative + "/bindings.json",
                relative + "/reconcile.json",
                relative + "/editmode.xml",
                relative + "/inputs.json",
            ]
            journal.transition("S4", "passed", evidence=evidence)
            return Result(
                run_id=run_id,
                input_digest=model.input_digest,
                evaluated_test_status="PASS",
                artifact_ids=[a["artifact_id"] for a in artifacts],
                data={
                    "through": "S4",
                    "project": str(project.relative_to(policy.root)),
                    "source_bindings": source_bindings,
                    "static_import_status": "PASS",
                    "playmode_status": "NOT_RUN",
                    "visual_review_status": "REVIEW",
                    "security_scope": "TRUSTED_LOCAL",
                    "isolation_verified": False,
                    "network_policy": "explicit Unity package resolution authorization",
                },
                evidence_paths=[*evidence, *compiled.evidence_paths],
            )
    except (InputError, OSError, KeyboardInterrupt) as exc:
        journal.transition("S4", "failed", note=str(exc) or "interrupted")
        kind = (
            exc.kind
            if isinstance(exc, InputError)
            else (
                ErrorKind.INTERRUPTED
                if isinstance(exc, KeyboardInterrupt)
                else ErrorKind.PRODUCER_FAILURE
            )
        )
        return replace(
            failure(kind, "PF-UNITY-S4", str(exc) or "interrupted"),
            run_id=run_id,
            evidence_paths=[relative + "/events.jsonl"],
        )
