"""Cross-engine units, dimensions and semantic reference checks over typed reports."""

from __future__ import annotations

import math
from typing import Any

from polyforge.contracts.validation import InputError, canonical_digest


def _report(value: dict[str, Any], location: str) -> dict[str, dict[str, Any]]:
    canonical_digest(value)
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("objects"), list)
        or not isinstance(value.get("coordinate_basis"), dict)
        or type(value.get("meters_per_unit")) not in {int, float}
        or value["meters_per_unit"] <= 0
    ):
        raise InputError(f"$.{location}: invalid normalized handoff report")
    objects = {}
    for item in value["objects"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("id"), str)
            or item["id"] in objects
            or not isinstance(item.get("bounds_m"), list)
            or len(item["bounds_m"]) != 3
            or any(type(n) not in {int, float} for n in item["bounds_m"])
            or ("prefab_id" in item and not isinstance(item["prefab_id"], str))
            or any(
                not isinstance(item.get(key), list)
                or any(not isinstance(v, str) for v in item[key])
                for key in ("material_ids", "socket_ids")
            )
        ):
            raise InputError(f"$.{location}.objects: invalid/duplicate semantic object")
        objects[item["id"]] = item
    return objects


def check_handoff(
    contract: dict[str, Any],
    source: dict[str, Any],
    imported: dict[str, Any],
    *,
    relative_tolerance: float = 0.02,
) -> dict[str, Any]:
    """Validate synthetic or observed payloads; a PASS does not prove Unity ran."""
    if not math.isfinite(relative_tolerance) or not 0 <= relative_tolerance <= 0.1:
        raise InputError("$.relative_tolerance: must be finite and between 0 and 0.1")
    canonical_digest(contract)
    if not isinstance(contract, dict) or not isinstance(contract.get("objects"), list):
        raise InputError("$.contract.objects: required semantic object list")
    reports = {"source": _report(source, "source"), "imported": _report(imported, "imported")}
    issues: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []

    def issue(category: str, identifier: str, expected: Any, actual: Any, location: str) -> None:
        issues.append(
            {
                "category": category,
                "asset_id": identifier,
                "expected": expected,
                "actual": actual,
                "location": location,
            }
        )

    for name, report in (("source", source), ("imported", imported)):
        basis = report["coordinate_basis"]
        if basis not in ({"up": "Y", "forward": "Z"}, {"up": "Z", "forward": "-Y"}):
            issue("axis", "report", {"up": "Y", "forward": "Z"}, basis, name)
        if name == "imported" and basis != {"up": "Y", "forward": "Z"}:
            issue("axis", "report", {"up": "Y", "forward": "Z"}, basis, name)
    expected_ids = set()
    for expected in contract["objects"]:
        if not isinstance(expected, dict):
            raise InputError("$.contract.objects: invalid object")
        if expected.get("kind") != "asset":
            continue
        identifier = expected.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in expected_ids:
            raise InputError("$.contract.objects.id: required unique semantic ID")
        for field in ("material_ids", "socket_ids"):
            values = expected.get(field, [])
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise InputError(f"$.contract.objects.{field}: expected string list")
        expected_ids.add(identifier)
        bounds = expected.get("bounds_m")
        if (
            not isinstance(bounds, list)
            or len(bounds) != 3
            or any(type(n) not in {int, float} or n <= 0 for n in bounds)
        ):
            raise InputError("$.contract.objects.bounds_m: expected positive dimensions")
        previous = "contract:" + identifier
        nodes.append({"id": previous, "kind": "expected", "asset_id": identifier})
        for name in ("source", "imported"):
            observed = reports[name].get(identifier)
            evidence_id = name + ":" + identifier
            nodes.append({"id": evidence_id, "kind": name, "asset_id": identifier})
            edges.append({"source": previous, "target": evidence_id, "relation": "handoff"})
            previous = evidence_id
            if observed is None:
                issue("binding", identifier, "semantic object", None, name)
                continue
            actual = list(observed["bounds_m"])
            report = source if name == "source" else imported
            if report["coordinate_basis"] == {"up": "Z", "forward": "-Y"}:
                actual = [actual[0], actual[2], actual[1]]
            actual = [n * report["meters_per_unit"] for n in actual]
            if any(
                not math.isclose(want, got, rel_tol=relative_tolerance, abs_tol=0.001)
                for want, got in zip(bounds, actual, strict=True)
            ):
                issue("scale", identifier, bounds, actual, name)
            for field, category in (("material_ids", "material"), ("socket_ids", "socket")):
                if set(expected.get(field, [])) != set(observed[field]):
                    issue(category, identifier, expected.get(field, []), observed[field], name)
            if name == "imported" and not observed.get("prefab_id"):
                issue("binding", identifier, "prefab binding", observed.get("prefab_id"), name)
    if not expected_ids:
        raise InputError("$.contract.objects: at least one asset invariant is required")
    for name, objects in reports.items():
        for identifier in set(objects) - expected_ids:
            issue("dangling_reference", identifier, "declared asset", identifier, name)
    return {
        "status": "FAIL" if issues else "PASS",
        "issues": issues,
        "evidence_graph": {"nodes": nodes, "edges": edges},
        "relative_tolerance": relative_tolerance,
        "application_execution": "NOT_RUN",
    }
