"""Explicit deliverable classification; never infer that a fixture name defines scope."""

from importlib.resources import files
from pathlib import Path
from typing import Any

from polyforge.capabilities.registry import lookup
from polyforge.contracts.validation import InputError, canonical_digest, validate_schema
from polyforge.workforce.models import job_context, validate_task


def engine_digest() -> str:
    import hashlib
    from importlib.resources.abc import Traversable

    identities = {}

    def visit(node: Traversable, prefix: str) -> None:
        for child in sorted(node.iterdir(), key=lambda item: item.name):
            name = prefix + child.name
            if child.is_dir() and child.name != "__pycache__":
                visit(child, name + "/")
            elif child.is_file() and Path(child.name).suffix in {
                ".py",
                ".json",
                ".cs",
                ".asmdef",
                ".meta",
                ".txt",
            }:
                identities[name] = hashlib.sha256(child.read_bytes()).hexdigest()

    for package in ("polyforge", "unity_package"):
        visit(files(package), package + ":")
    return canonical_digest(identities)


def plan_task(value: dict[str, Any], *, workspace: Path | None = None) -> dict[str, Any]:
    digest = validate_task(value)
    tool_digest = engine_digest()
    workspace_inputs = {}
    if workspace is not None:
        import hashlib

        from polyforge.doctor import discover_tool
        from polyforge.security.paths import WorkspacePolicy
        from polyforge.unity.bridge import configuration

        policy = WorkspacePolicy(workspace)
        names = ["polyforge.toml"]
        inputs = value.get("input", {})
        if value.get("capability_id") == "sprite.unity.strip.v1":
            names += [inputs["metadata_file"], inputs["atlas_file"], *inputs["frame_files"]]
        elif value.get("capability_id") == "sprite.robot.bake.v1":
            names.append(inputs["source_blend"])
        elif value.get("capability_id") == "asset.package.build.v1":
            names += [r["path"] for r in inputs["spec"]["references"]]
        elif value.get("capability_id") == "unity.game.platformer.v1":
            from polyforge.unity.platformer import compile_platformer_request

            compiled = compile_platformer_request(inputs, policy)
            names += list(compiled["source_hashes"])
            names.append(str(Path(inputs["sprite_receipt"]).parent / "artifacts.json"))

        if (
            value["task_class"] == "BUILD_GAME"
            and value.get("capability_id") == "unity.game.arena.v1"
        ) or (value["task_class"] == "ANIMATE" and "unity" in value["domain_tags"]):
            names += [
                "game_manifest.json",
                "UnityProject/Assets/PolyForgeGenerated/Game/PlayableArena.unity",
            ]
            names += [
                p.relative_to(policy.root).as_posix()
                for p in policy.path("recipes").rglob("*")
                if p.is_file()
            ]
        for name in names:
            path = policy.path(name)
            workspace_inputs[name] = (
                hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "MISSING"
            )
        config = configuration(policy)
        for name, explicit in [
            ("blender", config.blender_executable),
            ("unity", config.unity_executable),
        ]:
            if name not in value["domain_tags"]:
                continue
            tool_path = discover_tool(name, explicit)
            workspace_inputs[name + "_binary"] = (
                hashlib.sha256(tool_path.read_bytes()).hexdigest()
                if tool_path and tool_path.is_file()
                else "UNAVAILABLE"
            )
    tool_digest = canonical_digest({"engine": tool_digest, "workspace_inputs": workspace_inputs})
    capability = value.get("capability_id")
    task = value["task_class"]
    if task in {"CREATE_ASSET", "ANIMATE", "BUILD_GAME"} and (
        not capability or "input" not in value
    ):
        raise InputError("Producing tasks need a registered capability and typed input")
    if capability == "animation.robot.rig.v1":
        # Registration occurs only when its real native gates pass.
        validate_schema(value["input"], "recipe_request.schema.json")
    elif capability is not None:
        descriptor = lookup(capability)
        validate_schema(value["input"], descriptor["input_schema"].split("/")[-1])
    if task == "ANIMATE" and capability != "animation.robot.rig.v1":
        raise InputError("ANIMATE requires a supported animation capability")
    if capability == "asset.package.build.v1":
        from polyforge.assets.contracts import validate_spec

        validate_spec(value["input"]["spec"], workspace or Path.cwd())
        if value["brief"] != value["input"]["spec"]["brief"]:
            raise InputError("AssetSpec must preserve the exact original task brief")
    if task == "CREATE_ASSET" and (
        capability is None or not capability.startswith(("mesh.", "asset.package.", "sprite."))
    ):
        raise InputError("CREATE_ASSET requires a supported mesh capability")
    if task == "BUILD_GAME" and capability not in {
        "unity.game.arena.v1",
        "unity.game.platformer.v1",
    }:
        raise InputError("BUILD_GAME requires an implemented game capability")
    stages = ["S0", "S1"]
    jobs = []
    if task in {"CREATE_ASSET", "ANIMATE", "BUILD_GAME"}:
        stages += ["S2", "S3"] if task != "BUILD_GAME" else ["S2", "S3", "S4", "S5"]
        roles = [
            "intent_analyst",
            "rig_animation_artist"
            if task == "ANIMATE"
            else "unity_integration"
            if task == "BUILD_GAME"
            else "asset_producer",
            "animation_inspector" if task == "ANIMATE" else "asset_inspector",
        ]
        if task == "ANIMATE" and "unity" in value["domain_tags"]:
            roles.append("unity_integration")
            stages += ["S4", "S5"]
        for index, role in enumerate(roles):
            jobs.append(
                {
                    "schema_version": "1.0.0",
                    "job_id": "job_" + str(index),
                    "role_id": role,
                    "capability_id": capability
                    if index == 1
                    else "animation.robot.unity.v1"
                    if index == 3
                    else "artifact.candidate.inspect.v1"
                    if index == 2
                    else "intent.freeze.v1",
                    "depends_on": ["job_" + str(index - 1)] if index else [],
                    "stage": "S4"
                    if index == 3
                    else "S3"
                    if index == 2
                    else "S2"
                    if index == 1
                    else "S1",
                    "budget_seconds": value.get("budget_seconds", 3600),
                    "write_root": "runs/",
                    "feature_ids": value["feature_ids"],
                }
            )
            context = job_context(value, workspace_inputs, role, workspace=workspace)
            jobs[-1]["context"] = context
            jobs[-1]["context_digest"] = canonical_digest(context)
            validate_schema(jobs[-1], "job_ticket.schema.json")
    if capability == "unity.game.platformer.v1" and task == "BUILD_GAME":
        stages = ["S0", "S1", "S4", "S5"]
        jobs[1]["stage"] = "S4"
        jobs[2]["stage"] = "S5"
        jobs[2]["role_id"] = "gameplay_qa_inspector"
        context = job_context(value, workspace_inputs, "gameplay_qa_inspector", workspace=workspace)
        jobs[2]["context"] = context
        jobs[2]["context_digest"] = canonical_digest(context)
        validate_schema(jobs[2], "job_ticket.schema.json")
    if capability == "sprite.unity.strip.v1" and task == "CREATE_ASSET":
        stages = ["S0", "S1", "S4", "S5"]
        jobs[1]["role_id"] = "unity_integration"
        jobs[1]["stage"] = "S4"
        jobs[2]["stage"] = "S5"
        context = job_context(value, workspace_inputs, "unity_integration", workspace=workspace)
        jobs[1]["context"] = context
        jobs[1]["context_digest"] = canonical_digest(context)
    return {
        "schema_version": "1.0.0",
        "task_id": "task_" + digest[:16] + "_" + tool_digest[:8],
        "engine_digest": tool_digest,
        "workspace_inputs": workspace_inputs,
        "input_digest": digest,
        "original_request": value,
        "stages": stages,
        "jobs": jobs,
        "execution_status": "NOT_RUN",
        "support_state": "REFERENCE_ONLY"
        if task == "EXPLAIN"
        else "REVIEW"
        if not jobs
        else "SUPPORTED",
        "semantic_interpretation": "USER_OR_HOST_CLASSIFIED",
        "requirements_preserved": True,
    }
