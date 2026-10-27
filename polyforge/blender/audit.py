"""Audit evidence contracts and validated lookup of managed editable sources."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import ErrorKind, Result
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.security.paths import WorkspacePolicy

VIEWS = ("front", "side", "top", "iso")
EXPORT_OPTIONS = {
    "axis_forward": "-Z",
    "axis_up": "Y",
    "global_scale": 1.0,
    "apply_unit_scale": True,
    "apply_scale_options": "FBX_SCALE_UNITS",
    "bake_space_transform": False,
    "bake_anim": False,
    "use_selection": True,
    "use_custom_props": True,
    "object_types": ["EMPTY", "MESH"],
}


def validate_audit(value: Any, metrics: dict[str, Any]) -> None:
    try:
        canonical_digest(value)
    except InputError as exc:
        raise InputError("Invalid audit JSON", kind=ErrorKind.CONTRACT_FAILURE) from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version") != "1.0.0"
        or value.get("asset_id") != metrics["asset_id"]
        or value.get("geometry_digest") != metrics["geometry_digest"]
        or value.get("view_ids") != list(VIEWS)
        or value.get("export") != EXPORT_OPTIONS
        or value.get("diagnostics") != {"status": "PASS", "issues": []}
        or value.get("visual_review_status") != "REVIEW"
        or value.get("unity_import_status") != "NOT_RUN"
        or value.get("material_ids") != metrics["material_ids"]
        or value.get("socket_ids") != metrics["socket_ids"]
    ):
        raise InputError(
            "$.audit: export/diagnostic/evidence contract mismatch",
            kind=ErrorKind.CONTRACT_FAILURE,
            code="PF-AUDIT-CONTRACT",
        )


def validate_exchange(
    recipe: dict[str, Any], metrics: dict[str, Any], material: Any, handoff: Any, roundtrip: Any
) -> None:
    def reject() -> None:
        raise InputError(
            "$.export: material/handoff/roundtrip evidence mismatch",
            kind=ErrorKind.CONTRACT_FAILURE,
            code="PF-EXPORT-CONTRACT",
        )

    try:
        canonical_digest([material, handoff, roundtrip])
        if not isinstance(material, dict) or material.get("asset_id") != recipe["asset_id"]:
            reject()
        actual = material.get("materials")
        if not isinstance(actual, list) or len(actual) != len(recipe["materials"]):
            reject()
        entries = {m["id"]: m for m in actual}
        if set(entries) != {m["id"] for m in recipe["materials"]}:
            reject()
        for expected in recipe["materials"]:
            found = entries[expected["id"]]
            if len(found["base_color_rgba"]) != 4 or any(
                type(n) not in {int, float} or not math.isclose(n, want, abs_tol=1e-6)
                for n, want in zip(found["base_color_rgba"], expected["color_rgba"], strict=True)
            ):
                reject()
            for key, default in (("metallic", 0.0), ("roughness", 0.65)):
                if type(found.get(key)) not in {int, float} or not math.isclose(
                    found[key], expected.get(key, default), abs_tol=1e-6
                ):
                    reject()
        if material.get("module_materials") != {
            m["id"]: [m.get("material_id", recipe["materials"][0]["id"])] for m in recipe["modules"]
        }:
            reject()
        if (
            not isinstance(roundtrip, dict)
            or roundtrip.get("status") != "PASS"
            or roundtrip.get("verification_scope") != "BLENDER_FBX_ROUNDTRIP"
            or roundtrip.get("unity_import_status") != "NOT_RUN"
        ):
            reject()
        used = sorted(
            {m.get("material_id", recipe["materials"][0]["id"]) for m in recipe["modules"]}
        )
        if roundtrip.get("material_ids") != used:
            reject()
        for key in ("bounds_unity_m", "module_ids", "socket_positions_unity_m"):
            if roundtrip.get(key) != metrics[key]:
                reject()
        if (
            not isinstance(handoff, dict)
            or handoff.get("coordinate_basis") != metrics["coordinate_basis"]
            or handoff.get("meters_per_unit") != metrics["meters_per_unit"]
        ):
            reject()
        expected_object = {
            "id": "asset:" + recipe["asset_id"],
            **{
                key: metrics[key]
                for key in (
                    "bounds_m",
                    "material_ids",
                    "socket_ids",
                    "geometry_digest",
                    "socket_positions_unity_m",
                )
            },
        }
        if handoff.get("objects") != [expected_object]:
            reject()
    except (KeyError, TypeError, ValueError) as exc:
        raise InputError(
            "$.export: malformed sidecar evidence", kind=ErrorKind.CONTRACT_FAILURE
        ) from exc


def managed_source(workspace: Path, asset_id: str) -> tuple[dict[str, Any], Path]:
    validate_schema(
        {"schema_version": "1.0.0", "asset_id": asset_id, "parameters": {"size_m": [1, 1, 1]}},
        "recipe_request.schema.json",
    )
    policy = WorkspacePolicy(workspace)
    runs = policy.path("runs")
    candidates = []
    if runs.is_dir():
        for folder in runs.iterdir():
            policy.path(folder)
            if not folder.is_dir():
                continue
            state_path = policy.path(folder / "state.json")
            input_path = policy.path(folder / "input.json")
            if (
                state_path.is_file()
                and input_path.is_file()
                and policy.path(folder / "artifacts.json").is_file()
            ):
                state = load_json(state_path)
                job = load_json(input_path)
                if (
                    isinstance(job, dict)
                    and isinstance(job.get("recipe"), dict)
                    and job["recipe"].get("asset_id") == asset_id
                    and isinstance(state, dict)
                    and isinstance(state.get("stages"), dict)
                    and isinstance(state["stages"].get("S2"), dict)
                    and state.get("stages", {}).get("S2", {}).get("status") == "passed"
                ):
                    if not isinstance(state.get("updated_utc"), str):
                        raise InputError("$.audit.run: invalid run timestamp")
                    candidates.append((state.get("updated_utc", ""), folder, job["recipe"]))
    if not candidates:
        raise InputError("$.asset: no successful managed source; build the asset through S2 first")
    _, folder, recipe = max(candidates, key=lambda row: row[0])
    registry = load_json(policy.path(folder / "artifacts.json"))
    source = policy.path(folder / "asset/source.blend")
    entries = registry.get("artifacts", []) if isinstance(registry, dict) else []
    if not isinstance(entries, list) or any(
        not isinstance(e, dict) or not isinstance(e.get("relative_path"), str) for e in entries
    ):
        raise InputError("$.audit.registry: malformed artifact inventory")
    expected = [
        entry
        for entry in entries
        if isinstance(entry, dict) and policy.path(entry.get("relative_path", "")) == source
    ]
    if (
        len(expected) != 1
        or not source.is_file()
        or hashlib.sha256(source.read_bytes()).hexdigest() != expected[0].get("sha256")
    ):
        raise InputError("$.asset: managed source hash is missing or changed")
    return recipe, source


def audit_asset(workspace: Path, asset_id: str, *, dry_run: bool = False) -> Result:
    from polyforge.blender.adapter import execute_recipe

    recipe, source = managed_source(workspace, asset_id)
    return execute_recipe(
        recipe, RunContext(workspace, dry_run=dry_run), audit_export=True, source=source
    )
