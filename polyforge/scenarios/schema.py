"""Validate bounded development scenarios; no simulation or acceptance is implied."""

from __future__ import annotations

from typing import Any

from polyforge.contracts.validation import InputError, validate_schema


def validate_scenario(value: Any, *, scene_id: str, entity_ids: set[str]) -> dict[str, Any]:
    validate_schema(value, "scenario.schema.json")
    if value["setup"]["scene_id"] != scene_id:
        raise InputError("$.setup.scene_id: unknown scene")
    if not set(value["setup"]["entity_ids"]).issubset(entity_ids):
        raise InputError("$.setup.entity_ids: unknown entity")
    for index, step in enumerate(value["steps"]):
        if (
            step["action"] in {"move", "attack", "interact"}
            and step.get("actor_id") not in entity_ids
        ):
            raise InputError(f"$.steps[{index}].actor_id: known actor required")
        if step["action"] == "move" and "direction" not in step:
            raise InputError(f"$.steps[{index}].direction: movement vector required")
    duration = sum(step["ticks"] for step in value["steps"]) * value["fixed_delta_seconds"]
    if duration > value["timeout_s"]:
        raise InputError("$.steps: requested schedule exceeds timeout")
    result: dict[str, Any] = value
    return result
