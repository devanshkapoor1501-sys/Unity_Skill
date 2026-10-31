"""Versioned task, candidate and review boundaries."""

from copy import deepcopy
from pathlib import Path
from typing import Any

from polyforge.contracts.validation import InputError, canonical_digest, validate_schema


def validate_review(review: dict[str, Any]) -> None:
    validate_schema(review, "review_verdict.schema.json")
    if review["producer_id"] == review["reviewer_id"]:
        raise InputError("A producer cannot approve its own candidate")
    if any(".." in p.replace("\\", "/").split("/") for p in review["evidence"]):
        raise InputError("Review evidence cannot escape its workspace")


def validate_task(value: dict[str, Any]) -> str:
    validate_schema(value, "workforce_task.schema.json")
    if not value["brief"].strip():
        raise InputError("Task brief cannot be blank")
    return canonical_digest(value)


def job_context(
    value: dict[str, Any],
    workspace_inputs: dict[str, str],
    role: str,
    *,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """Freeze relevant data and provenance; execution authority stays in permissions.py."""
    from polyforge.knowledge.catalog import catalog_cards
    from polyforge.knowledge.probes import read_probe
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.workforce.permissions import ROLES

    identifiers = {value.get("capability_id")}
    if value["task_class"] == "ANIMATE" and "unity" in value["domain_tags"]:
        identifiers.add("animation.robot.unity.v1")
    relevant = [
        c
        for c in catalog_cards()
        if c["domain"] in value["domain_tags"] or identifiers.intersection(c["capability_ids"])
    ]
    cards = sorted(relevant, key=lambda c: not bool(identifiers.intersection(c["capability_ids"])))[
        :3
    ]
    tools = sorted(
        {t for c in cards for t in c["versions"] if t in {"blender", "unity"}}
        | ({"blender", "unity"} & set(value["domain_tags"]))
    )
    observations = {
        tool: read_probe(WorkspacePolicy(workspace), tool) if workspace is not None else None
        for tool in tools
    }
    return {
        "schema_version": "1.0.0",
        "task_digest": canonical_digest(value),
        "brief_digest": canonical_digest(value["brief"]),
        "task_class": value["task_class"],
        "required_concepts": value["domain_tags"],
        "selected_knowledge_cards": [
            {k: c[k] for k in ("knowledge_id", "doc_digest", "knowledge_state", "versions")}
            for c in cards
        ],
        "toolchain_probes": [
            {
                "tool": tool,
                "status": "VERSION_PROBED" if observations[tool] else "UNKNOWN",
                "evidence_digest": canonical_digest(observations[tool])
                if observations[tool]
                else None,
            }
            for tool in tools
        ],
        "reference_digest": canonical_digest(cards),
        "support_state": "REGISTERED_TYPED_INPUT_REQUIREMENTS_UNVERIFIED",
        "originality_or_license": "REQUEST_METADATA_ONLY_NOT_INFERRED",
        "observed_inputs": workspace_inputs,
        "capability_gap": "Free-text brief coverage requires separate requirement review",
        "proposed_experiment_id": None,
        "risk_level": "TRUSTED_REGISTERED_LOCAL",
        "approval_owner": "EXISTING_REVIEW_GATES",
        "evaluator_ref": "EXTERNAL_NOT_SUPPLIED",
        "evaluator_access": "DENIED",
        "tool_allowlist": list(ROLES[role]["tools"]),
        "read_roots": ["runs/", "workforce/", "recipes/"],
        "authorized_write_roots": list(ROLES[role]["writes"]),
        "permissions_from_references": False,
        "seed": value.get("seed", 42),
        "original_task_input_digest": canonical_digest(value.get("input", {})),
        "expected_evidence": ["registered capability result", "candidate/review artifacts"],
        "review_policy": "EXISTING_L1_L2_L3_GATES",
        "deadline_policy": "START_PLUS_BUDGET_SECONDS",
        "lease_ref": "RUNTIME_LEDGER",
        "resources": deepcopy(value.get("resources", {})),
    }


def resume_plan(stored: dict[str, Any], fresh: dict[str, Any]) -> dict[str, Any]:
    """Keep historical probe provenance while checking immutable task/job contracts."""
    if {k: v for k, v in stored.items() if k != "jobs"} != {
        k: v for k, v in fresh.items() if k != "jobs"
    } or len(stored.get("jobs", [])) != len(fresh["jobs"]):
        raise InputError("Stored plan differs from the frozen task identity")
    for old, new in zip(stored["jobs"], fresh["jobs"], strict=True):
        validate_schema(old, "job_ticket.schema.json")
        if {k: v for k, v in old.items() if k not in {"context", "context_digest"}} != {
            k: v for k, v in new.items() if k not in {"context", "context_digest"}
        }:
            raise InputError("Stored job contract changed")
        if "context" not in old:
            # Legacy tickets keep their original lack of optional context; never relabel them.
            continue
        if canonical_digest(old["context"]) != old["context_digest"]:
            raise InputError("Stored job context digest mismatch")
        optional = {"toolchain_probes"}
        if "resources" not in old["context"]:
            # Execution still receives floors from the frozen original request.
            optional.add("resources")
        if {k: v for k, v in old["context"].items() if k not in optional} != {
            k: v for k, v in new["context"].items() if k not in optional
        }:
            raise InputError("Stored job context changed beyond a probe refresh")
    return stored
