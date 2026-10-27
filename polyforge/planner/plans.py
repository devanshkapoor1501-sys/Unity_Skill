"""Content-addressed stage DAGs distinguish unchanged inputs from completed work."""

from __future__ import annotations

import re
from typing import Any

from polyforge.compiler.contract_compiler import compile_contract
from polyforge.contracts.manifest import Manifest
from polyforge.contracts.validation import InputError, canonical_digest
from polyforge.planner.dag import topological_order


def build_plan(manifest: Manifest) -> dict[str, Any]:
    compiled = compile_contract(manifest)
    tasks: dict[str, dict[str, Any]] = {}

    def add(
        identifier: str, stage: str, inputs: Any, dependencies: list[str], work: int = 1
    ) -> None:
        tasks[identifier] = {
            "id": identifier,
            "stage": stage,
            "local_input_digest": canonical_digest(inputs),
            "dependencies": sorted(dependencies),
            "execution_status": "NOT_RUN",
            "cache_status": "NOT_BUILT",
            "estimated_work_units": work,
            "estimate_seconds": None,
            "estimate_status": "NOT_MEASURED",
        }

    add("precheck:environment", "S0", {"schema": 1, "target": manifest.data["target"]}, [])
    add("contract:scene", "S1", compiled, ["precheck:environment"])
    for asset in manifest.data["assets"]:
        identifier = asset["id"]
        add(
            "geometry_contract:" + identifier,
            "S1",
            {
                "recipe": manifest.recipe_digests[identifier],
                "target_size_m": asset["target_size_m"],
            },
            ["precheck:environment"],
        )
        add(
            "mesh:" + identifier,
            "S2",
            {
                "recipe": manifest.recipe_digests[identifier],
                "target_size_m": asset["target_size_m"],
                "seed": manifest.data["project"]["seed"],
                "recipe_contract_version": "1.0.0",
            },
            ["geometry_contract:" + identifier, *["mesh:" + key for key in asset["dependencies"]]],
        )
        add(
            "export:" + identifier,
            "S3",
            {"basis": {"up": "Y", "forward": "Z"}, "format": "fbx"},
            ["mesh:" + identifier, *["animation:" + key for key in asset["animation_ids"]]],
        )
        add(
            "import:" + identifier,
            "S4",
            {
                "asset_id": identifier,
                "collider": asset["collider"],
                "materials": asset["material_ids"],
                "animations": asset["animation_ids"],
            },
            ["export:" + identifier, *["material:" + key for key in asset["material_ids"]]],
        )
        add(
            "audit:" + identifier,
            "S3",
            {"views": manifest.data["audit"]["required_views"]},
            ["mesh:" + identifier, *["appearance:" + key for key in asset["material_ids"]]],
            4,
        )
    for material in manifest.data["materials"]:
        add(
            "appearance:" + material["id"],
            "S2",
            {
                "material": material,
                "textures": {
                    t["path"]: manifest.input_digests[t["path"]]
                    for t in material.get("textures", [])
                },
            },
            ["precheck:environment"],
        )
        add(
            "material:" + material["id"],
            "S4",
            {"adapter": "urp_lit.v1"},
            ["appearance:" + material["id"]],
        )
    add(
        "runtime:gameplay",
        "S4",
        {
            "gameplay": manifest.data["gameplay"],
            "actors": manifest.data["actors"],
            "features": [
                {"feature_id": r["feature_id"], "binding_ids": r["binding_ids"]}
                for r in manifest.data.get("intent", {}).get("requirements", [])
            ],
        },
        ["precheck:environment"],
    )
    for animation in manifest.data.get("animations", []):
        dependency = (
            "mesh:" + animation["asset_id"]
            if animation["kind"] == "rig"
            else "sprite:" + animation["spritesheet_id"]
        )
        add("animation:" + animation["id"], "S3", animation, [dependency])
    for sprite in manifest.data.get("spritesheets", []):
        inputs = {
            "sprite": sprite,
            "source_digest": manifest.input_digests.get(sprite.get("path", "")),
        }
        add(
            "sprite:" + sprite["id"],
            "S3",
            inputs,
            [
                "mesh:" + sprite["asset_id"],
                *[
                    "appearance:" + key
                    for asset in manifest.data["assets"]
                    if sprite["kind"] == "bake" and asset["id"] == sprite["asset_id"]
                    for key in asset["material_ids"]
                ],
                *[
                    "animation:" + animation["id"]
                    for animation in manifest.data.get("animations", [])
                    if sprite["kind"] == "bake"
                    and animation["kind"] == "rig"
                    and animation["asset_id"] == sprite["asset_id"]
                ],
            ],
            len(sprite["frame_indices"]) if sprite["kind"] == "bake" else sprite["frame_count"],
        )
    add(
        "scene:assemble",
        "S4",
        {"scene": manifest.data["scene"], "actors": manifest.data["actors"]},
        [
            "contract:scene",
            "runtime:gameplay",
            *["import:" + a["id"] for a in manifest.data["assets"]],
            *["material:" + m["id"] for m in manifest.data["materials"]],
            *["sprite:" + s["id"] for s in manifest.data.get("spritesheets", [])],
            *["animation:" + a["id"] for a in manifest.data.get("animations", [])],
        ],
    )
    add(
        "verify:scene",
        "S5",
        {"oracle": "INDEPENDENT_ACCEPTANCE_REQUIRED"},
        ["scene:assemble", *["audit:" + a["id"] for a in manifest.data["assets"]]],
    )
    order = topological_order({key: value["dependencies"] for key, value in tasks.items()})
    indices = {key: index for index, key in enumerate(order)}
    order = tuple(sorted(order, key=lambda key: (tasks[key]["stage"], indices[key])))
    for identifier in order:
        task = tasks[identifier]
        task["input_digest"] = canonical_digest(
            {
                "local": task["local_input_digest"],
                "upstream": {key: tasks[key]["input_digest"] for key in task["dependencies"]},
            }
        )
    return {
        "schema_version": "1.0.0",
        "manifest_digest": manifest.digest,
        "input_digest": manifest.input_digest,
        "tasks": [tasks[key] for key in order],
        "game_status": "PARTIAL",
        "requirement_coverage": compiled["requirement_coverage"],
        "work_estimate": {
            "assets": len(manifest.data["assets"]),
            "render_views": 4 * len(manifest.data["assets"]),
        },
        "execution_status": "NOT_RUN",
    }


def changed_tasks(previous: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Compare transitive input digests; unchanged input is not an artifact cache hit."""

    def digests(value: dict[str, Any]) -> dict[str, str]:
        if not isinstance(value, dict) or not isinstance(value.get("tasks"), list):
            raise InputError("$.previous_plan.tasks: expected task list")
        result = {}
        for task in value["tasks"]:
            if (
                not isinstance(task, dict)
                or not isinstance(task.get("id"), str)
                or task["id"] in result
                or not isinstance(task.get("input_digest"), str)
                or not re.fullmatch(r"[a-f0-9]{64}", task["input_digest"])
            ):
                raise InputError("$.previous_plan.tasks: invalid/duplicate task digest")
            result[task["id"]] = task["input_digest"]
        return result

    before = digests(previous)
    after = digests(current)
    return sorted(
        identifier
        for identifier in before.keys() | after.keys()
        if before.get(identifier) != after.get(identifier)
    )
