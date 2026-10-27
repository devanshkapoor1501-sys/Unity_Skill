"""Compile validated design intent without fabricating produced or accepted artifacts."""

from __future__ import annotations

import copy
from typing import Any

from polyforge.composition.grammar import FEATURES, compose
from polyforge.contracts.manifest import Manifest


def compile_contract(manifest: Manifest) -> dict[str, Any]:
    """Produce development scene/feature/coverage contracts from one validated source."""
    data = manifest.data
    requirements = data.get("intent", {}).get("requirements", [])
    composition = compose(requirements)
    objects: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    for material in sorted(data["materials"], key=lambda value: value["id"]):
        objects.append(
            {
                "id": "material:" + material["id"],
                "kind": "material",
                "parameters": copy.deepcopy(material),
                "binding_status": "NOT_RUN",
            }
        )
    for asset in sorted(data["assets"], key=lambda value: value["id"]):
        recipe = manifest.recipes[asset["id"]]
        identifier = "asset:" + asset["id"]
        objects.append(
            {
                "id": identifier,
                "kind": "asset",
                "source_id": asset["id"],
                "asset_capability": recipe["capability_id"],
                "bounds_m": asset["target_size_m"],
                "material_ids": asset["material_ids"],
                "socket_ids": [socket["id"] for socket in recipe["sockets"]],
                "animations": asset["animation_ids"],
                "collider": asset["collider"],
                "binding_status": "NOT_RUN",
            }
        )
        for material_id in asset["material_ids"]:
            links.append(
                {
                    "source_id": identifier,
                    "target_id": "material:" + material_id,
                    "relation": "uses_material",
                    "required": True,
                    "invariant_id": "material_exists",
                }
            )
        for socket in recipe["sockets"]:
            socket_id = f"socket:{asset['id']}:{socket['id']}"
            objects.append(
                {
                    "id": socket_id,
                    "kind": "socket",
                    "position_m": socket["position"],
                    "position_space": "MODULE_LOCAL_UNITY",
                    "module_id": socket["module_id"],
                    "binding_status": "NOT_RUN",
                }
            )
            links.append(
                {
                    "source_id": identifier,
                    "target_id": socket_id,
                    "relation": "has_socket",
                    "required": True,
                    "invariant_id": "socket_binding",
                }
            )
    for actor in sorted(data["actors"], key=lambda value: value["id"]):
        identifier = "actor:" + actor["id"]
        objects.append(
            {
                "id": identifier,
                "kind": "actor",
                "source_id": actor["id"],
                "pose": {"position_m": actor["spawn_xyz"]},
                "controller": actor["controller"],
                "binding_status": "NOT_RUN",
            }
        )
        links.append(
            {
                "source_id": identifier,
                "target_id": "asset:" + actor["asset_id"],
                "relation": "instance_of",
                "required": True,
                "invariant_id": "prefab_binding",
            }
        )
    for animation in sorted(data.get("animations", []), key=lambda value: value["id"]):
        identifier = "animation:" + animation["id"]
        objects.append(
            {
                "id": identifier,
                "kind": "animation",
                "source_id": animation["id"],
                "animation_contract": copy.deepcopy(animation),
                "binding_status": "NOT_RUN",
            }
        )
        links.append(
            {
                "source_id": "asset:" + animation["asset_id"],
                "target_id": identifier,
                "relation": "animates",
                "required": True,
                "invariant_id": "animation_binding",
            }
        )
    features = []
    for requirement in requirements:
        template = FEATURES.get(requirement["feature_id"])
        span = requirement["source_span"]
        features.append(
            {
                **copy.deepcopy(requirement),
                "source_text": manifest.brief[span["start"] : span["end"]]
                if manifest.brief
                else "",
                "capability_id": requirement["feature_id"] if template else None,
                "capability_version": "1.0.0" if template else None,
                "support_state": "BLOCKED" if template else "UNSUPPORTED",
                "reason": "Blender generation available; scene-level Unity bindings await Phase 5"
                if requirement["feature_id"] == "geometry.static_assets.v1"
                else f"Execution worker scheduled for Phase {template['phase']}"
                if template
                else "No declared capability template",
                "expected_component": template["component"] if template else None,
                "implementation_status": "NOT_RUN",
                "independent_oracle_status": "NOT_RUN",
                "acceptance_authority": "GENERATOR_DEVELOPMENT_INTENT",
            }
        )
    unresolved = []
    if not requirements:
        unresolved.append("unannotated_brief")
    # Source ranges are traceability, not semantic completeness or evaluator approval.
    if manifest.brief:
        covered = bytearray(len(manifest.brief))
        for requirement in requirements:
            span = requirement["source_span"]
            covered[span["start"] : span["end"]] = b"\x01" * (span["end"] - span["start"])
        if any(
            character.isalnum() and not covered[index]
            for index, character in enumerate(manifest.brief)
        ):
            unresolved.append("unreviewed_brief_text")
    blocked = [
        feature["id"]
        for feature in features
        if feature["required"] and feature["support_state"] == "BLOCKED"
    ]
    unsupported = [
        feature["id"]
        for feature in features
        if feature["required"] and feature["support_state"] == "UNSUPPORTED"
    ]
    unresolved.extend(unsupported)
    unresolved.extend(sorted({item["requirement_id"] for item in composition["unconnected_ports"]}))
    coverage = {
        "requested_features_total": len(features),
        "supported_features_total": 0,
        "implemented_features_total": 0,
        "independently_verified_features_total": 0,
        "blocked_requirements": blocked,
        "unsupported_requirements": unsupported,
        "unresolved_requirements": sorted(set(unresolved)),
        "game_status": "PARTIAL",
        "annotation_status": "REVIEW" if unresolved else "PASS",
        "authority": "DEVELOPMENT_ONLY",
        "original_brief_sha256": manifest.brief_sha256,
    }
    scene = {
        "schema_version": "1.0.0",
        "id": f"{data['project']['id']}:{data['scene']['id']}",
        "manifest_digest": manifest.digest,
        "input_digest": manifest.input_digest,
        "input_fingerprints": manifest.input_fingerprints,
        "coordinate_basis": {"up": "Y", "forward": "Z"},
        "source_basis": {"up": "Z", "forward": "-Y"},
        "meters_per_unit": 1,
        "objects": objects,
        "links": links,
        "scenarios": [],
        "spritesheets": copy.deepcopy(data.get("spritesheets", [])),
        "game_status": "PARTIAL",
    }
    feature_contract = {
        "schema_version": "1.0.0",
        "authority": "DEVELOPMENT_ONLY",
        "original_brief_sha256": manifest.brief_sha256,
        "requirements": features,
        "composition": composition,
    }
    return {
        "scene_contract": scene,
        "feature_contract": feature_contract,
        "requirement_coverage": coverage,
    }
