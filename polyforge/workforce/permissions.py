"""Roles propose bounded work; registered engine capabilities retain execution authority."""

from typing import Any

from polyforge.blender.modeling import MODELING_CAPABILITIES
from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError
from polyforge.security.paths import WorkspacePolicy

ROLES: dict[str, dict[str, list[str]]] = {
    "intent_analyst": {"tools": [], "writes": ["workforce/"]},
    "rig_animation_artist": {"tools": ["animation.robot.rig.v1"], "writes": ["runs/"]},
    "asset_producer": {
        "tools": [
            "asset.package.build.v1",
            "sprite.robot.bake.v1",
            "mesh.props.crate.v1",
            "mesh.robot.modular.v1",
            "mesh.architecture.wall.v1",
            "mesh.architecture.doorway.v1",
            "mesh.environment.tile.v1",
        ],
        "writes": ["runs/"],
    },
    "animation_inspector": {"tools": ["artifact.candidate.inspect.v1"], "writes": []},
    "asset_inspector": {"tools": ["artifact.candidate.inspect.v1"], "writes": []},
    "unity_integration": {
        "tools": [
            "animation.robot.unity.v1",
            "unity.game.arena.v1",
            "unity.game.platformer.v1",
            "sprite.unity.strip.v1",
        ],
        "writes": ["UnityProject/"],
    },
}

ROLES.update(
    {
        "asset_architect": {"tools": [], "writes": ["workforce/"]},
        "modeler": {"tools": list(ROLES["asset_producer"]["tools"]), "writes": ["runs/"]},
        "uv_material_artist": {"tools": [], "writes": ["runs/"]},
        "asset_refiner": {"tools": list(ROLES["asset_producer"]["tools"]), "writes": ["runs/"]},
        "asset_quality_inspector": {"tools": [], "writes": []},
    }
)

MODELING_ROLES = {
    "room_kit": "modeler_architecture",
    "vehicle": "modeler_hard_surface",
    "mechanical_prop": "modeler_hard_surface",
    "organic": "modeler_organic_retopo",
    "compose": "modeler_procedural",
}
for _kind, _role in MODELING_ROLES.items():
    ROLES.setdefault(_role, {"tools": [], "writes": ["runs/"]})["tools"].append(
        MODELING_CAPABILITIES[_kind]
    )


def assert_public_path(policy: WorkspacePolicy, target: str) -> None:
    relative = policy.path(target).relative_to(policy.root)
    if {p.casefold() for p in relative.parts} & {"evaluator", "holdouts", "protected_evaluator"}:
        raise InputError(
            "Evaluator-owned namespaces cannot enter worker/review evidence",
            kind=ErrorKind.POLICY_DENIED,
        )


for _inspector in (
    "brief_compliance_inspector",
    "asset_animation_inspector",
    "unity_import_inspector",
    "gameplay_qa_inspector",
    "performance_inspector",
    "release_supervisor",
):
    ROLES[_inspector] = {"tools": ["artifact.candidate.inspect.v1"], "writes": []}


def execution_profile(mode: str) -> dict[str, Any]:
    if mode not in {"sequential", "single"}:
        raise InputError(
            "No verified host delegation adapter; use sequential or single mode",
            kind=ErrorKind.POLICY_DENIED,
        )
    return {
        "execution_mode": "LOCAL_MULTIROLE_SEQUENTIAL"
        if mode == "sequential"
        else "LOCAL_SINGLE_ROLE",
        "native_subagents": "UNAVAILABLE",
        "host_delegation_probe": "NOT_IMPLEMENTED",
        "independence": "DIFFERENT_ROLE_SAME_HOST",
        "evaluator_owner": "EXTERNAL_NOT_SUPPLIED",
    }


def authorize(policy: WorkspacePolicy, role: str, action: str, target: str) -> bool:
    rule = ROLES.get(role)
    if rule is None:
        raise InputError("Unknown worker role")
    if action == "tool":
        allowed = target in rule["tools"]
    else:
        assert_public_path(policy, target)
        path = policy.path(target)
        relative = path.relative_to(policy.root).as_posix()
        allowed = action == "read" and relative.startswith(("runs/", "workforce/", "recipes/"))
        if action == "write":
            allowed = any(relative.startswith(prefix) for prefix in rule["writes"])
    if not allowed:
        raise InputError(
            "Role lacks authorization for " + action + ": " + target, kind=ErrorKind.POLICY_DENIED
        )
    return True
