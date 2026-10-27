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
