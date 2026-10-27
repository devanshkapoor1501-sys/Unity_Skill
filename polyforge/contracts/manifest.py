"""Validated v1 manifests and recipe inputs, independent of application adapters."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from polyforge.blender.recipes import validate_recipe
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.planner.dag import topological_order
from polyforge.security.paths import WorkspacePolicy


@dataclass(frozen=True)
class Manifest:
    """Owned validated JSON and resolved input fingerprints; no transient run state."""

    data: dict[str, Any]
    workspace: Path
    asset_order: tuple[str, ...]
    recipes: dict[str, dict[str, Any]]
    recipe_digests: dict[str, str]
    brief: str | None
    brief_sha256: str | None
    input_digests: dict[str, str]

    @property
    def digest(self) -> str:
        return canonical_digest(self.data)

    @property
    def input_fingerprints(self) -> dict[str, Any]:
        return {
            "manifest": self.digest,
            "recipes": dict(self.recipe_digests),
            "files": dict(self.input_digests),
            "original_brief": self.brief_sha256,
        }

    @property
    def input_digest(self) -> str:
        return canonical_digest(self.input_fingerprints)

    def canonical_json(self) -> str:
        return json.dumps(
            self.data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        )


def relative_file(policy: WorkspacePolicy, supplied: str, location: str) -> Path:
    """Manifest paths use one unambiguous relative POSIX spelling on every OS."""
    if (
        not supplied
        or "\\" in supplied
        or ":" in supplied
        or "\x00" in supplied
        or supplied.startswith("/")
        or any(part in {"", ".", ".."} for part in supplied.split("/"))
    ):
        raise InputError(f"{location}: expected a safe relative POSIX path")
    try:
        path = policy.path(PurePosixPath(supplied).as_posix())
    except InputError as exc:
        raise InputError(f"{location}: {exc}") from exc
    if not path.is_file():
        raise InputError(f"{location}: required input file does not exist: {supplied}")
    return path


def parse_manifest(data: Any, workspace: Path) -> Manifest:
    """Validate all shape/references/paths before compilation can mutate anything."""
    if isinstance(data, dict) and isinstance(data.get("schema_version"), str):
        if data["schema_version"].split(".")[0] != "1":
            raise InputError("$.schema_version: unsupported major; explicit migration required")
    validate_schema(data, "game_manifest.schema.json")
    policy = WorkspacePolicy(workspace)
    ids: dict[str, str] = {}
    for group in (
        "project",
        "scene",
        "materials",
        "assets",
        "actors",
        "animations",
        "spritesheets",
    ):
        entries = data.get(group, [])
        if isinstance(entries, dict):
            entries = [entries]
        for index, entry in enumerate(entries):
            identifier = entry["id"]
            location = f"$.{group}[{index}].id"
            if identifier in ids:
                raise InputError(
                    f"{location}: duplicate ID {identifier}; first at {ids[identifier]}"
                )
            ids[identifier] = location
    materials = {item["id"] for item in data["materials"]}
    assets = {item["id"]: item for item in data["assets"]}
    animations = {item["id"]: item for item in data.get("animations", [])}
    sprites = {item["id"]: item for item in data.get("spritesheets", [])}
    input_digests: dict[str, str] = {}
    path_spellings: dict[str, str] = {}

    def file_digest(supplied: str, location: str) -> None:
        key = supplied.casefold()
        if key in path_spellings and path_spellings[key] != supplied:
            raise InputError(f"{location}: case-insensitive path collision")
        path_spellings[key] = supplied
        path = relative_file(policy, supplied, location)
        with path.open("rb") as stream:
            content = stream.read(33_554_433)
        if len(content) > 33_554_432:
            raise InputError(f"{location}: input exceeds 32 MiB budget")
        input_digests[supplied] = hashlib.sha256(content).hexdigest()

    for index, material in enumerate(data["materials"]):
        textures = material.get("textures", [])
        if len({texture["kind"] for texture in textures}) != len(textures):
            raise InputError(f"$.materials[{index}].textures: duplicate texture role")
        for texture in textures:
            file_digest(texture["path"], f"$.materials[{index}].textures.path")
    asset_order = topological_order({key: item["dependencies"] for key, item in assets.items()})
    recipes: dict[str, dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    spellings: dict[str, str] = {}
    for index, item in enumerate(data["assets"]):
        location = f"$.assets[{index}]"
        for reference in item["material_ids"]:
            if reference not in materials:
                raise InputError(f"{location}.material_ids: dangling reference {reference}")
        for reference in item["animation_ids"]:
            if reference not in animations or animations[reference]["asset_id"] != item["id"]:
                raise InputError(
                    f"{location}.animation_ids: missing or wrong-asset animation {reference}"
                )
        key = item["recipe"].casefold()
        if key in spellings:
            raise InputError(f"{location}.recipe: case-insensitive input path collision")
        spellings[key] = item["recipe"]
        path = relative_file(policy, item["recipe"], location + ".recipe")
        recipe = load_json(path)
        validate_recipe(recipe)
        if recipe["asset_id"] != item["id"]:
            raise InputError(f"{location}.recipe.asset_id: must match owning asset")
        recipes[item["id"]], hashes[item["id"]] = recipe, canonical_digest(recipe)
    bounds = data["scene"]["bounds_m"]
    for index, actor in enumerate(data["actors"]):
        if actor["asset_id"] not in assets:
            raise InputError(f"$.actors[{index}].asset_id: dangling asset reference")
        x, y, z = actor["spawn_xyz"]
        if abs(x) > bounds[0] / 2 or not 0 <= y <= bounds[1] or abs(z) > bounds[2] / 2:
            raise InputError(f"$.actors[{index}].spawn_xyz: outside scene bounds")
    for index, animation in enumerate(data.get("animations", [])):
        if animation["asset_id"] not in assets:
            raise InputError(f"$.animations[{index}].asset_id: dangling asset reference")
        if animation["kind"] == "rig" and animation["frames"][0] >= animation["frames"][1]:
            raise InputError(f"$.animations[{index}].frames: expected increasing frame range")
        if animation["kind"] == "sprite" and (
            animation["spritesheet_id"] not in sprites
            or sprites[animation["spritesheet_id"]]["asset_id"] != animation["asset_id"]
        ):
            raise InputError(f"$.animations[{index}].spritesheet_id: missing/wrong asset binding")
    for index, sprite in enumerate(data.get("spritesheets", [])):
        if sprite["asset_id"] not in assets:
            raise InputError(f"$.spritesheets[{index}].asset_id: dangling asset reference")
        if sprite["kind"] == "atlas":
            file_digest(sprite["path"], f"$.spritesheets[{index}].path")
    brief: str | None = None
    brief_hash: str | None = None
    brief_path = data.get("intent", {}).get("brief_path", "brief.md")
    if "intent" in data or policy.path(brief_path).is_file():
        path = relative_file(policy, brief_path, "$.intent.brief_path")
        try:
            with path.open("rb") as stream:
                content = stream.read(262145)
            if len(content) > 262144:
                raise ValueError("brief exceeds 256 KiB")
            brief, brief_hash = content.decode("utf-8"), hashlib.sha256(content).hexdigest()
        except (OSError, ValueError) as exc:
            raise InputError(f"$.intent.brief_path: {exc}") from exc
    requirements = data.get("intent", {}).get("requirements", [])
    seen: set[str] = set()
    for index, requirement in enumerate(requirements):
        location = f"$.intent.requirements[{index}]"
        if requirement["id"] in seen:
            raise InputError(f"{location}.id: duplicate requirement")
        seen.add(requirement["id"])
        start, end = requirement["source_span"]["start"], requirement["source_span"]["end"]
        if brief is None or not 0 <= start < end <= len(brief):
            raise InputError(f"{location}.source_span: outside original brief")
        if any(reference not in ids for reference in requirement["binding_ids"]):
            raise InputError(f"{location}.binding_ids: dangling semantic binding")
    return Manifest(
        data, policy.root, asset_order, recipes, hashes, brief, brief_hash, input_digests
    )


def load_manifest(path: Path) -> Manifest:
    policy = WorkspacePolicy(path.absolute().parent)
    source = policy.path(path.absolute())
    return parse_manifest(load_json(source), policy.root)
