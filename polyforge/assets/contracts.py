"""Immutable asset slots, reference-as-data policy and independent technical rubric."""

import hashlib
import math
from pathlib import Path
from typing import Any

from polyforge.blender.recipes import expand_recipe, validate_geometry
from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.security.paths import WorkspacePolicy

SLOTS = {"geometry_source", "uv_source", "material_source", "export", "geometry_metrics"}


def validate_spec(value: dict[str, Any], workspace: Path) -> dict[str, Any]:
    canonical_digest(value)
    validate_schema(value, "asset_spec.schema.json")
    if not value["brief"].strip() or not value["silhouette"].strip():
        raise InputError("AssetSpec must preserve a nonempty brief and silhouette")
    # Validate the registered family's stricter semantic IDs before any ownership/state writes.
    expand_recipe(
        value["kind"],
        {
            "schema_version": "1.0.0",
            "asset_id": value["asset_id"],
            "parameters": {"size_m": value["dimensions_m"]},
        },
        seed=42,
    )
    policy = WorkspacePolicy(workspace)
    for reference in value["references"]:
        source = policy.path(reference["path"])
        if (
            not source.is_file()
            or source.stat().st_size > 33_554_432
            or hashlib.sha256(source.read_bytes()).hexdigest() != reference["sha256"]
        ):
            raise InputError("Reference unavailable or changed; references grant no permissions")
    return value


def seal_bundle(
    workspace: Path,
    spec: dict[str, Any],
    slots: dict[str, str],
    *,
    revision: int,
    producer: str,
) -> dict[str, Any]:
    validate_spec(spec, workspace)
    if not SLOTS <= slots.keys() or set(slots) - SLOTS or revision not in {1, 2}:
        raise InputError("Missing/unknown required asset source slot or invalid revision")
    if producer not in {"modeler", "asset_refiner"}:
        raise InputError("Unknown asset producer")
    policy = WorkspacePolicy(workspace)
    inventory = {}
    for name, relative in slots.items():
        source = policy.path(relative)
        if not source.is_file() or not source.is_relative_to(policy.path("runs")):
            raise InputError("Asset slots must identify existing run-scoped sources")
        inventory[name] = {
            "path": source.relative_to(policy.root).as_posix(),
            "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        }
    value = {
        "schema_version": "1.0.0",
        "asset_id": spec["asset_id"],
        "brief_digest": canonical_digest(spec["brief"]),
        "spec_digest": canonical_digest(spec),
        "source_license": spec["source_license"],
        "coordinates": spec["integration"],
        "pivot": spec["pivot"],
        "producer_id": producer,
        "revision": revision,
        "dependencies": spec["references"],
        "slots": inventory,
    }
    bundle = {**value, "revision_digest": canonical_digest(value)}
    validate_schema(bundle, "asset_bundle.schema.json")
    return bundle


def inspect_bundle(workspace: Path, bundle: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    validate_spec(spec, workspace)
    validate_schema(bundle, "asset_bundle.schema.json")
    policy = WorkspacePolicy(workspace)
    identity = {k: v for k, v in bundle.items() if k != "revision_digest"}
    if (
        set(bundle.get("slots", {})) != SLOTS
        or bundle.get("revision_digest") != canonical_digest(identity)
        or bundle.get("source_license") != spec["source_license"]
        or bundle.get("coordinates") != spec["integration"]
        or bundle.get("pivot") != spec["pivot"]
        or bundle.get("asset_id") != spec["asset_id"]
        or bundle.get("brief_digest") != canonical_digest(spec["brief"])
        or bundle.get("spec_digest") != canonical_digest(spec)
        or bundle.get("producer_id") not in {"modeler", "asset_refiner"}
        or bundle.get("dependencies") != spec["references"]
    ):
        raise InputError("Asset bundle identity/source/license/coordinates mismatch")
    for item in bundle["slots"].values():
        source = policy.path(item["path"])
        if (
            not source.is_file()
            or hashlib.sha256(source.read_bytes()).hexdigest() != item["sha256"]
        ):
            raise InputError("Asset source slot changed", kind=ErrorKind.CONTRACT_FAILURE)
    recipe = expand_recipe(
        spec["kind"],
        {
            "schema_version": "1.0.0",
            "asset_id": spec["asset_id"],
            "parameters": {"size_m": spec["dimensions_m"]},
        },
        seed=42,
    )
    metrics = load_json(policy.path(bundle["slots"]["geometry_metrics"]["path"]))
    validate_geometry(
        recipe, metrics, dimension_tolerance_m=spec["rubric"]["dimension_tolerance_m"]
    )
    logical = load_json(policy.path(bundle["slots"]["uv_source"]["path"]), max_bytes=16_777_216)
    if canonical_digest(logical) != metrics["geometry_digest"]:
        raise InputError(
            "UV/geometry source differs from the measured geometry digest",
            kind=ErrorKind.CONTRACT_FAILURE,
        )
    triangles = sum(len(face) - 2 for module in logical["modules"] for face in module["faces"])
    materials = load_json(policy.path(bundle["slots"]["material_source"]["path"]))
    if not isinstance(materials, dict):
        raise InputError("Invalid material source structure")
    entries = materials.get("materials")
    expected_ids = {m["id"] for m in recipe["materials"]}
    if (
        not isinstance(entries, list)
        or len(entries) != len(expected_ids)
        or any(
            not isinstance(m, dict)
            or not {"id", "base_color_rgba", "metallic", "roughness"} <= m.keys()
            or not isinstance(m["id"], str)
            for m in entries
        )
        or {m["id"] for m in entries} != expected_ids
        or len({m["id"] for m in entries}) != len(entries)
    ):
        raise InputError("Material source must retain every unique semantic material binding")
    if materials.get("module_materials") != {
        m["id"]: [m.get("material_id", recipe["materials"][0]["id"])] for m in recipe["modules"]
    }:
        raise InputError("Material assignment differs from semantic module bindings")
    issues = []
    if triangles > spec["poly_budget"]:
        issues.append("poly_budget")
    for material in materials["materials"]:
        for key, expected in spec["material"].items():
            actual = material.get(key)
            actual_values = actual if isinstance(actual, list) else [actual]
            expected_values = expected if isinstance(expected, list) else [expected]
            if len(actual_values) != len(expected_values) or any(
                type(a) not in {int, float}
                or not math.isclose(a, b, abs_tol=spec["rubric"]["color_tolerance"])
                for a, b in zip(actual_values, expected_values, strict=True)
            ):
                issues.append("material." + key)
    if not materials.get("materials") or materials.get("asset_id") != spec["asset_id"]:
        raise InputError("Missing/wrong material source")
    return {
        "schema_version": "1.0.0",
        "revision_digest": bundle["revision_digest"],
        "producer_id": bundle["producer_id"],
        "reviewer_id": "asset_quality_inspector",
        "independence": "DIFFERENT_ROLE_SAME_HOST",
        "technical_verdict": "REJECTED" if issues else "APPROVED",
        "issues": sorted(set(issues)),
        "triangles": triangles,
        "visual_review": "REVIEW",
        "visual_confidence": None,
        "visual_approval_required": spec["visual_approval_required"],
        "source_license": spec["source_license"],
    }


def require_bundle_approval(
    workspace: Path, bundle: dict[str, Any], review: dict[str, Any], spec: dict[str, Any]
) -> None:
    observed = inspect_bundle(workspace, bundle, spec)
    if (
        observed != review
        or observed["technical_verdict"] != "APPROVED"
        or spec["visual_approval_required"]
    ):
        raise InputError(
            "Bundle promotion requires exact technical and required visual approval",
            kind=ErrorKind.POLICY_DENIED,
        )
