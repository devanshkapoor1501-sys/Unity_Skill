"""Typed ports and incompatibilities for development gameplay composition."""

from __future__ import annotations

from typing import Any

from polyforge.contracts.validation import InputError

# These are declared interfaces for later workers, not implementations in the runtime catalog.
FEATURES: dict[str, dict[str, Any]] = {
    "movement.character_controller.v1": {
        "phase": 6,
        "inputs": ["input", "physics"],
        "outputs": ["movement"],
        "component": "PlayerController",
    },
    "movement.rigidbody.v1": {
        "phase": 6,
        "inputs": ["input", "physics"],
        "outputs": ["movement"],
        "component": "RigidbodyMovement",
    },
    "physics.collision.v1": {
        "phase": 6,
        "inputs": ["physics"],
        "outputs": ["collision"],
        "component": "Collider",
    },
    "ai.patrol.v1": {
        "phase": 6,
        "inputs": ["clock", "scene"],
        "outputs": ["patrol"],
        "component": "PatrolEnemy",
    },
    "combat.damage.v1": {
        "phase": 6,
        "inputs": ["collision", "health"],
        "outputs": ["damage"],
        "component": "ContactDamage",
    },
    "combat.health.v1": {"phase": 6, "inputs": [], "outputs": ["health"], "component": "Health"},
    "objective.survival.v1": {
        "phase": 6,
        "inputs": ["clock", "health"],
        "outputs": ["win_state"],
        "component": "SurvivalObjective",
    },
    "objective.failure.v1": {
        "phase": 6,
        "inputs": ["health"],
        "outputs": ["failure_state"],
        "component": "GameState",
    },
    "game.restart.v1": {
        "phase": 6,
        "inputs": ["input", "scene"],
        "outputs": ["restart"],
        "component": "RestartController",
    },
    "geometry.static_assets.v1": {
        "phase": 3,
        "inputs": [],
        "outputs": ["assets"],
        "component": "MeshFilter",
    },
    "audit.multiview.v1": {
        "phase": 4,
        "inputs": ["assets"],
        "outputs": ["visual_evidence"],
        "component": None,
    },
    "artifact.editable_sources.v1": {
        "phase": 5,
        "inputs": ["assets"],
        "outputs": ["editable_sources"],
        "component": None,
    },
    "animation.robot.v1": {
        "phase": 7,
        "inputs": ["assets"],
        "outputs": ["animation"],
        "component": "Animator",
    },
    "sprite.bake.v1": {
        "phase": 8,
        "inputs": ["assets"],
        "outputs": ["sprites"],
        "component": "SpriteRenderer",
    },
}


def compose(requirements: list[dict[str, Any]]) -> dict[str, Any]:
    """Check port compatibility and report unconnected requirements without substitution."""
    first, second = "movement.character_controller.v1", "movement.rigidbody.v1"
    for left in requirements:
        for right in requirements:
            if (
                left["feature_id"] == first
                and right["feature_id"] == second
                and set(left["binding_ids"]) & set(right["binding_ids"])
            ):
                raise InputError(
                    "$.intent.requirements: incompatible movement modes on one binding"
                )
    providers: dict[str, list[str]] = {}
    for requirement in requirements:
        for port in FEATURES.get(requirement["feature_id"], {}).get("outputs", []):
            providers.setdefault(port, []).append(requirement["id"])
    connections, missing = [], []
    intrinsic = {"input", "clock", "scene", "physics"}
    for requirement in requirements:
        for port in FEATURES.get(requirement["feature_id"], {}).get("inputs", []):
            if port in intrinsic:
                continue
            if not providers.get(port):
                missing.append({"requirement_id": requirement["id"], "port": port})
            for provider in providers.get(port, []):
                connections.append({"source": provider, "target": requirement["id"], "port": port})
    return {
        "grammar_version": "1.0.0",
        "connections": connections,
        "unconnected_ports": missing,
        "authority": "DEVELOPMENT_ONLY",
    }
