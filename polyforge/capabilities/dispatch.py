"""One bounded capability dispatcher shared by CLI and worker coordinator."""

from typing import Any

from polyforge.capabilities.protocol import RunContext
from polyforge.capabilities.registry import ManifestCapability, RegistryValidator, lookup
from polyforge.contracts.results import Result


def execute(identifier: str, inputs: dict[str, Any], context: RunContext) -> Result:
    lookup(identifier)
    if identifier == "sprite.unity.strip.v1":
        from polyforge.review.sprite_source import review_sprite_source
        from polyforge.security.paths import WorkspacePolicy

        source_review = review_sprite_source(
            WorkspacePolicy(context.workspace), inputs, remember_requirement=not context.dry_run
        )
        if source_review["promotion"] != "APPROVED":
            return Result(status="REVIEW", exit_code=4, data={"source_review": source_review})
    from polyforge.workforce.operations import complete, recover

    previous = recover(identifier, inputs, context)
    if previous is not None:
        return previous
    result = _execute(identifier, inputs, context)
    return complete(identifier, inputs, context, result)


def _execute(identifier: str, inputs: dict[str, Any], context: RunContext) -> Result:
    if identifier == "unity.game.platformer.v1":
        from polyforge.contracts.validation import validate_schema
        from polyforge.unity.platformer import build_platformer

        validate_schema(inputs, "platformer.schema.json")
        return build_platformer(
            context.workspace,
            inputs,
            dry_run=context.dry_run,
            standalone=inputs.get("standalone", False),
            cancel=context.cancel,
        )
    if identifier == "asset.package.build.v1":
        from polyforge.assets.pipeline import build_asset

        return build_asset(inputs, context)
    if identifier == "sprite.robot.bake.v1":
        from polyforge.sprites.bake import bake_robot

        return bake_robot(inputs, context)
    if identifier == "sprite.unity.strip.v1":
        from polyforge.sprites.integration import import_strip

        return import_strip(inputs, context)
    if identifier in {"artifact.candidate.inspect.v1", "animation.robot.unity.v1"}:
        from polyforge.contracts.validation import load_json, validate_schema
        from polyforge.security.paths import WorkspacePolicy
        from polyforge.workforce.workers import inspect_candidate, require_approval

        validate_schema(
            inputs,
            "candidate_review.schema.json"
            if identifier.startswith("artifact.")
            else "animation_import.schema.json",
        )
        policy = WorkspacePolicy(context.workspace)
        candidate = load_json(policy.path(inputs["candidate_file"]))
        if identifier.startswith("artifact."):
            from polyforge.review.board import review_candidate
            from polyforge.workforce.router import plan_task

            plan = load_json(policy.path(inputs["task_file"]))
            plan_task(plan["original_request"])
            return Result(
                data={
                    "review": inspect_candidate(
                        policy, candidate, plan["original_request"], technical_only=True
                    ),
                    "board": review_candidate(policy, candidate, plan["original_request"]),
                }
            )
        review = load_json(policy.path(inputs["review_file"]))
        production = load_json(policy.path(inputs["production_file"]))
        require_approval(policy, candidate, review)
        if production.get("candidate") != candidate:
            from polyforge.contracts.validation import InputError

            raise InputError("Production receipt belongs to a different candidate")
        if context.dry_run:
            return Result(data={"dry_run": True, "execution_status": "NOT_RUN"})
        from polyforge.animation.integration import integrate_animation

        return integrate_animation(
            policy.root,
            candidate,
            production["result"],
            cancel=context.cancel,
            operation_id=context.operation_id,
        )
    if identifier == "animation.robot.rig.v1":
        from polyforge.animation.adapter import animate_robot

        return animate_robot(inputs, context)
    if identifier == "unity.game.arena.v1":
        from polyforge.blender.build import build_assets
        from polyforge.contracts.validation import validate_schema

        validate_schema(inputs, "game_build.schema.json")
        return build_assets(
            context.workspace,
            through="S5",
            dry_run=context.dry_run,
            allow_package_downloads=inputs.get("allow_package_downloads", False),
            standalone=inputs.get("standalone", False),
            cancel=context.cancel,
        )
    if identifier == "unity.scene.static.v1":
        from polyforge.blender.build import build_assets
        from polyforge.contracts.validation import validate_schema

        validate_schema(inputs, "unity_build.schema.json")
        return build_assets(
            context.workspace,
            through="S4",
            dry_run=context.dry_run,
            allow_package_downloads=inputs.get("allow_package_downloads", False),
        )
    if identifier == "audit.static.multiview.v1":
        from polyforge.blender.audit import audit_asset
        from polyforge.contracts.validation import validate_schema

        validate_schema(inputs, "audit_request.schema.json")
        return audit_asset(context.workspace, inputs["asset_id"], dry_run=context.dry_run)
    if identifier == "contract.capability.validate.v1":
        return RegistryValidator().execute(inputs, context)
    from polyforge.blender.adapter import BlenderCapability
    from polyforge.blender.recipes import RECIPES

    if identifier in RECIPES.values():
        kind = next(key for key, value in RECIPES.items() if value == identifier)
        return BlenderCapability(kind).execute(inputs, context)
    operation = {
        "contract.manifest.validate.v1": "validate",
        "contract.scene.compile.v1": "compile",
        "plan.scene.v1": "plan",
    }[identifier]
    return ManifestCapability(operation).execute(inputs, context)
