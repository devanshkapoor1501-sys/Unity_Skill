"""Managed S0–S2 static asset builds. Later integration stages stay unavailable."""

from __future__ import annotations

import copy
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
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


def build_assets(
    workspace: Path, *, through: str | None = None, only: str | None = None, dry_run: bool = False
) -> Result:
    through = through or "S2"
    if through not in {"S0", "S1", "S2"}:
        return failure(
            ErrorKind.PRODUCER_FAILURE,
            "PF-STAGE-NOT-IMPLEMENTED",
            "Only S0–S2 static asset generation is implemented; audit/export begins in Phase 4",
            status="NOT_RUN",
        )
    policy = WorkspacePolicy(workspace)
    config_path = policy.path("polyforge.toml")
    load_config(config_path if config_path.is_file() else None)
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
                {"id": key, "color_rgba": materials[key]["base_color_rgba"]} for key in wanted
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
    context = RunContext(policy.root, seed=model.data["project"]["seed"])
    if through in {"S0", "S1"}:
        probe = execute_recipe(model.recipes[identifiers[0]], context, precheck_only=True)
        if probe.status != "PASS" or through == "S0":
            return probe
        compiled = manifest_command(path, "plan")
        return replace(compiled, run_id=probe.run_id, data={**compiled.data, "through": "S1"})
    compiled = manifest_command(path, "plan")
    results: dict[str, Any] = {}
    for identifier in identifiers:
        result = execute_recipe(prepared[identifier], context)
        results[identifier] = result.to_dict()
        if result.status != "PASS":
            return replace(result, data={**result.data, "assets": results, "through": "S2"})
    run_id = "build-" + uuid4().hex[:16]
    summary = atomic_json(
        policy,
        f"runs/{run_id}/summary.json",
        {
            "input_digest": model.input_digest,
            "input_fingerprints": model.input_fingerprints,
            "through": "S2",
            "assets": results,
            "game_status": "PARTIAL",
        },
    )
    return Result(
        run_id=run_id,
        input_digest=model.input_digest,
        data={"through": "S2", "assets": results, "later_stages": "NOT_RUN"},
        artifact_ids=list(context.artifact_registry),
        evidence_paths=[str(summary.relative_to(policy.root)), *compiled.evidence_paths],
    )
