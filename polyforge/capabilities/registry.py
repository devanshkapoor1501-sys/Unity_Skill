"""Validated capability catalog; no dynamic imports from registry runner strings."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import Result
from polyforge.contracts.validation import InputError, canonical_digest, validate_schema


def validate_registry(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject malformed or duplicate capability metadata before dispatch."""
    seen: set[str] = set()
    for entry in entries:
        validate_schema(entry, "capability.schema.json")
        identifier = entry["id"]
        if identifier in seen:
            raise InputError(f"Duplicate capability ID: {identifier}")
        seen.add(identifier)
    return entries


def catalog() -> list[dict[str, Any]]:
    """List implemented capabilities only; fixtures do not advertise availability."""
    entries: list[dict[str, Any]] = json.loads(
        files("polyforge").joinpath("data/catalog.json").read_text("utf-8")
    )
    return validate_registry(entries)


def lookup(identifier: str) -> dict[str, Any]:
    """Look up an implemented, versioned capability or reject the unknown ID."""
    for entry in catalog():
        if entry["id"] == identifier:
            return entry
    raise InputError(f"Unknown or unavailable capability: {identifier}")


class RegistryValidator:
    """Validate one capability descriptor without Blender, Unity, models, or writes."""

    def execute(self, inputs: dict[str, Any], context: RunContext) -> Result:
        validate_registry([inputs])
        return Result(
            operation_id=context.operation_id,
            run_id=context.run_id,
            input_digest=canonical_digest(inputs),
            data={
                "validated_capability_id": inputs["id"],
                "dry_run": context.dry_run,
                "planned_writes": [],
                "security_scope": context.security_scope,
                "isolation_verified": context.isolation_verified,
            },
        )


class ManifestCapability:
    """Pure JSON-in/JSON-out planning operations; persistence stays in CLI orchestration."""

    def __init__(self, operation: str) -> None:
        if operation not in {"validate", "compile", "plan"}:
            raise InputError("Unknown manifest capability operation")
        self.operation = operation

    def execute(self, inputs: dict[str, Any], context: RunContext) -> Result:
        from polyforge.compiler.commands import _check_frozen
        from polyforge.compiler.contract_compiler import compile_contract
        from polyforge.contracts.manifest import parse_manifest
        from polyforge.planner.plans import build_plan

        model = parse_manifest(inputs, context.workspace)
        from polyforge.security.paths import WorkspacePolicy

        _check_frozen(model, WorkspacePolicy(context.workspace))
        if self.operation == "plan":
            data = build_plan(model)
        else:
            compiled = compile_contract(model)
            data = (
                compiled
                if self.operation == "compile"
                else {
                    "manifest_digest": model.digest,
                    "asset_order": list(model.asset_order),
                    "requirement_coverage": compiled["requirement_coverage"],
                }
            )
        return Result(
            input_digest=model.input_digest,
            data={**data, "planned_writes": [], "dry_run": context.dry_run},
            operation_id=context.operation_id,
            run_id=context.run_id,
        )
