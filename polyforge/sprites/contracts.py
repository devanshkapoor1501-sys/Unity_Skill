"""Native 2D routing does not require unrelated 3D authoring."""

from polyforge.contracts.validation import InputError


def route_2d(request: dict[str, str]) -> list[str]:
    if set(request) != {"output", "source"} or request["output"] != "UNITY_2D":
        raise InputError("Unknown 2D deliverable route")
    if request["source"] == "DIRECT_SPRITES":
        return ["sprite.inspect", "unity.2d"]
    if request["source"] == "BAKED_ROBOT":
        return ["blender.bake", "sprite.inspect", "unity.2d"]
    raise InputError("Unknown sprite source; no implicit Blender work")
