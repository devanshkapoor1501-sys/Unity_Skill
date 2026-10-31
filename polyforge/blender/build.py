"""Managed S0–S2 static asset builds. Later integration stages stay unavailable."""

from __future__ import annotations

import copy
import hashlib
import threading
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.blender.adapter import execute_recipe
from polyforge.blender.recipes import validate_recipe
from polyforge.capabilities.protocol import RunContext
from polyforge.compiler.commands import manifest_command
from polyforge.config import load_config
from polyforge.contracts.manifest import load_manifest
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError
from polyforge.runner.artifacts import complete_records
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


def build_assets(
    workspace: Path,
    *,
    through: str | None = None,
    only: str | None = None,
    dry_run: bool = False,
    allow_package_downloads: bool = False,
    standalone: bool = False,
    cancel: threading.Event | None = None,
) -> Result:
    if cancel is not None and cancel.is_set():
        return failure(
            ErrorKind.INTERRUPTED, "PF-BUILD-CANCELLED", "Build cancelled before mutation"
        )
    through = through or "S2"
    if through not in {"S0", "S1", "S2", "S3", "S4", "S5"}:
        return failure(
            ErrorKind.PRODUCER_FAILURE,
            "PF-STAGE-NOT-IMPLEMENTED",
            "Only S0–S4 static generation/import is implemented; gameplay begins in Phase 6",
            status="NOT_RUN",
        )
    policy = WorkspacePolicy(workspace)
    config_path = policy.path("polyforge.toml")
    config = load_config(config_path if config_path.is_file() else None)
    if standalone and through != "S5":
        raise InputError("Standalone builds require --through S5")
    if through in {"S3", "S4", "S5"} and config.preview_resolution > 1024:
        raise InputError("Audit previews are limited to 1024 pixels")
    path = policy.path("game_manifest.json")
    model = load_manifest(path)
    # Include publication destination validation before any execution side effects.
    planned = manifest_command(path, "plan", dry_run=True)
    for recipe in model.recipes.values():
        validate_recipe(recipe)
    selected = {only} if only is not None else set(model.asset_order)
    if not selected.issubset(model.recipes):
        raise InputError("$.only: unknown asset ID")
    assets = {a["id"]: a for a in model.data["assets"]}
    materials = {m["id"]: m for m in model.data["materials"]}
    prepared = {}
    for identifier, source in model.recipes.items():
        recipe = copy.deepcopy(source)
        recipe["parameters"]["size_m"] = assets[identifier]["target_size_m"]
        wanted = assets[identifier]["material_ids"]
        if wanted:
            old = [m["id"] for m in recipe.get("materials", [])]
            recipe["materials"] = [
                {
                    "id": key,
                    "color_rgba": materials[key]["base_color_rgba"],
                    "metallic": materials[key]["metallic"],
                    "roughness": materials[key]["roughness"],
                }
                for key in wanted
            ]
            for module in recipe["modules"]:
                index = old.index(module["material_id"]) if module.get("material_id") in old else 0
                module["material_id"] = wanted[index % len(wanted)]
        prepared[identifier] = validate_recipe(recipe)
    pending = list(selected)
    while pending:
        for dependency in assets[pending.pop()]["dependencies"]:
            if dependency not in selected:
                selected.add(dependency)
                pending.append(dependency)
    identifiers = [key for key in model.asset_order if key in selected]
    texture_specs: list[dict[str, Any]] = [
        {"id": key, "materials": [{"id": m} for m in assets[key]["material_ids"]]}
        for key in identifiers
    ]
    if through in {"S3", "S4", "S5"}:
        from polyforge.unity.bridge import copy_material_textures

        copy_material_textures(
            policy, policy.path(".polyforge/texture-preflight"), model, texture_specs, dry_run=True
        )
    if through == "S5":
        from polyforge.unity.game import build_game

        if only is not None:
            raise InputError("S5 builds a complete arena; --only is supported through S3")
        return build_game(
            model,
            prepared,
            dry_run=dry_run,
            allow_package_downloads=allow_package_downloads,
            standalone=standalone,
            cancel=cancel,
        )
    if through == "S4":
        from polyforge.unity.bridge import build_unity

        if only is not None:
            raise InputError("S4 builds complete static scenes; --only is supported through S3")
        return build_unity(
            model,
            prepared,
            dry_run=dry_run,
            allow_package_downloads=allow_package_downloads,
            cancel=cancel,
        )
    if dry_run:
        return Result(
            input_digest=model.input_digest,
            data={
                "dry_run": True,
                "through": through,
                "asset_ids": identifiers,
                "plan": planned.data["plan"],
                "execution_status": "NOT_RUN",
            },
        )
    context = RunContext(policy.root, seed=model.data["project"]["seed"], cancel=cancel)
    if through in {"S0", "S1"}:
        probe = execute_recipe(model.recipes[identifiers[0]], context, precheck_only=True)
        if probe.status != "PASS" or through == "S0":
            return probe
        compiled = manifest_command(path, "plan")
        return replace(compiled, run_id=probe.run_id, data={**compiled.data, "through": "S1"})
    compiled = manifest_command(path, "plan")
    results: dict[str, Any] = {}
    for identifier in identifiers:
        result = execute_recipe(prepared[identifier], context, audit_export=through == "S3")
        results[identifier] = result.to_dict()
        if result.status != "PASS":
            return replace(result, data={**result.data, "assets": results, "through": through})
    run_id = "build-" + uuid4().hex[:16]
    if through == "S3":
        from polyforge.unity.bridge import copy_material_textures

        copy_material_textures(
            policy, policy.path(f"runs/{run_id}/supplied-textures"), model, texture_specs
        )
    summary = atomic_json(
        policy,
        f"runs/{run_id}/summary.json",
        {
            "input_digest": model.input_digest,
            "input_fingerprints": model.input_fingerprints,
            "through": through,
            "supplied_textures": texture_specs if through == "S3" else [],
            "assets": results,
            "asset_bindings": {
                identifier: {
                    "source_blend": value["data"]["source_blend"],
                    "fbx_path": value["data"].get("fbx_path"),
                    "material_ids": assets[identifier]["material_ids"],
                    "collider_intent": assets[identifier]["collider"],
                    "collider_validation_status": "NOT_RUN",
                }
                for identifier, value in results.items()
            },
            "game_status": "PARTIAL",
        },
    )
    texture_artifacts = []
    if through == "S3":
        for asset in texture_specs:
            for material in asset["materials"]:
                for texture in material["textures"]:
                    relative = f"runs/{run_id}/supplied-textures/{texture['path']}"
                    target = policy.path(relative)
                    texture_artifacts.append(
                        {
                            "artifact_id": run_id + ":" + relative,
                            "relative_path": relative,
                            "sha256": texture["sha256"],
                            "bytes": target.stat().st_size,
                            "input_digest": model.input_digest,
                            "source_path": texture["source_path"],
                            "source_sha256": texture["sha256"],
                        }
                    )
        if texture_artifacts:
            summary_relative = summary.relative_to(policy.root).as_posix()
            texture_artifacts.append(
                {
                    "artifact_id": run_id + ":summary.json",
                    "relative_path": summary_relative,
                    "sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
                    "bytes": summary.stat().st_size,
                    "input_digest": model.input_digest,
                }
            )
            texture_artifacts = complete_records(
                policy, run_id, "S3", texture_artifacts, input_digest=model.input_digest
            )
            atomic_json(policy, f"runs/{run_id}/artifacts.json", {"artifacts": texture_artifacts})
    return Result(
        run_id=run_id,
        input_digest=model.input_digest,
        data={"through": through, "assets": results, "later_stages": "NOT_RUN"},
        artifact_ids=[*context.artifact_registry, *[a["artifact_id"] for a in texture_artifacts]],
        evidence_paths=[str(summary.relative_to(policy.root)), *compiled.evidence_paths],
    )
