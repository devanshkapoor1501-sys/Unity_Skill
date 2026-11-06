"""Pure task-first reference selection. Reference prose has no execution authority."""

from __future__ import annotations

import copy
import re
from typing import Any

from polyforge.blender.modeling import MODELING_CAPABILITIES
from polyforge.contracts.validation import InputError, canonical_digest
from polyforge.knowledge.catalog import catalog_cards, validate_cards
from polyforge.security.paths import WorkspacePolicy

DOMAINS = {"blender", "unity", "game_design", "workforce", "quality", "security"}
OUTPUTS = {"EXPLAIN", "INSPECT", "ASSET", "ANIMATE", "SPRITE", "MECHANIC", "REPAIR", "GAME"}


def _validate(request: Any) -> None:
    if (
        not isinstance(request, dict)
        or not {"schema_version", "query", "output"} <= set(request)
        or set(request) - {"schema_version", "query", "output", "domain"}
    ):
        raise InputError("Reference route needs exact versioned query/output and optional domain")
    if (
        request["schema_version"] != "1.0.0"
        or not isinstance(request["query"], str)
        or not 1 <= len(request["query"].strip()) <= 8192
    ):
        raise InputError("Reference query exceeds its bounded text contract")
    if (
        not isinstance(request["output"], str)
        or request["output"] not in OUTPUTS
        or (
            "domain" in request
            and (not isinstance(request["domain"], str) or request["domain"] not in DOMAINS)
        )
    ):
        raise InputError("Unknown output/domain; no arbitrary execution route")


def discovery_proposal(request: dict[str, Any]) -> dict[str, Any]:
    _validate(request)
    return {
        "schema_version": "1.0.0",
        "request_digest": canonical_digest(request),
        "query": request["query"],
        "lane": "SAFE_DISCOVERY",
        "execution_status": "BLOCKED",
        "isolation_verified": False,
        "owner_approval_required": True,
        "scratch_scope": "a new disposable project copy with read-only original references",
        "original_project_writes": [],
        "network": "DISABLED",
        "budget": {"attempts": 2, "timeout_seconds": 60},
        "required_proposal_fields": [
            "requirement_ids",
            "exact_api_tool_package_versions",
            "patch_diff",
            "scratch_path",
            "expected_writes",
            "risk_class",
            "validation_plan",
            "owner_approval",
        ],
        "validation_plan": [
            "consult official versioned sources and local API",
            "static scope/security review",
            "compile and isolated positive/negative probe",
            "measure actual outputs and compare original hashes",
        ],
        "promotion_requirements": [
            "owner review",
            "typed registered capability",
            "positive and negative fixtures",
            "version applicability",
            "benchmark slot",
        ],
        "reason": "Generated code needs separate authorization and verified or disclosed isolation",
    }


def route_reference(
    policy: WorkspacePolicy, request: dict[str, Any], *, cards: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    _validate(request)
    available = validate_cards(cards) if cards is not None else catalog_cards()
    query = request["query"].casefold()
    output = request["output"]
    forced = {
        "SPRITE": "unity.sprites",
        "ANIMATE": "blender.animation",
        "REPAIR": "quality.recovery",
    }.get(output)
    ranked = []
    for card in available:
        if request.get("domain", card["domain"]) != card["domain"]:
            continue
        score = sum(
            bool(re.search(r"(?<!\w)" + re.escape(t) + r"(?!\w)", query))
            for t in card["intent_triggers"]
        )
        if forced:
            score = 100 if card["knowledge_id"] == forced else 0
        if score:
            ranked.append((score, card["knowledge_id"], card))
    selected = [copy.deepcopy(row[2]) for row in sorted(ranked, key=lambda r: (-r[0], r[1]))[:3]]
    capabilities = []
    modeling_kind = None
    # These are engine-owned typed routes, never instructions or aliases from a document.
    sprite_bake = output == "SPRITE" and "robot" in query and "bake" in query
    if output == "SPRITE" and sprite_bake:
        capabilities = ["sprite.robot.bake.v1"]
    elif output == "SPRITE" and any(
        re.search(r"\b" + word + r"\b", query) for word in ("supplied", "existing", "import")
    ):
        capabilities = ["sprite.unity.strip.v1"]
    elif output == "ASSET":
        advanced = [
            kind
            for phrase, kind in (
                ("room kit", "room_kit"),
                ("vehicle", "vehicle"),
                ("mechanical prop", "mechanical_prop"),
                ("organic practice", "organic"),
                ("modeling composition", "compose"),
            )
            if re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", query)
        ]
        assisted = re.search(
            r"\b(?:sculpt(?:ing|ed)?|retopology|retopo|text|grease pencil|simulation)\b", query
        )
        if len(advanced) == 1 and assisted is None:
            modeling_kind = advanced[0]
            capabilities.append(MODELING_CAPABILITIES[modeling_kind])
        for word, identifier in {
            "crate": "mesh.props.crate.v1",
            "robot": "mesh.robot.modular.v1",
            "wall": "mesh.architecture.wall.v1",
            "doorway": "mesh.architecture.doorway.v1",
            "tile": "mesh.environment.tile.v1",
        }.items():
            if not advanced and re.search(r"\b" + word + r"\b", query):
                capabilities.append(identifier)
    elif output == "ANIMATE" and "robot" in query:
        capabilities = ["animation.robot.rig.v1"]
    elif (
        output == "GAME"
        and re.search(r"\b2d\b", query)
        and "checkpoint" in query
        and "platformer" in query
    ):
        capabilities = ["unity.game.platformer.v1"]
    elif output == "GAME" and "arena" in query and "survival" in query:
        capabilities = ["unity.game.arena.v1"]
    permitted = {cap for card in selected for cap in card["capability_ids"]}
    capabilities = [cap for cap in capabilities if cap in permitted]
    tools = (
        sorted({tool for c in selected for tool in c["versions"] if tool != "python"})
        if output != "EXPLAIN"
        else []
    )
    if sprite_bake and capabilities:
        tools = ["blender"]
    from polyforge.workforce.discovery import discover

    discovered = discover(policy)["tools"] if tools else {}
    from polyforge.knowledge.probes import read_probe

    observations = {tool: read_probe(policy, tool) for tool in tools}
    for card in selected:
        relevant = [tool for tool in card["versions"] if tool in observations]
        if relevant and all(
            (observed := observations[tool]) is not None
            and observed["tool_version"] in card["versions"][tool]
            and observed["receipt"]["probe_id"] == card["api_probe_id"]
            for tool in relevant
        ):
            card["knowledge_state"] = "VERSION_PROBED"
    missing = [t for t in tools if discovered[t]["availability"] == "UNAVAILABLE"]
    # A keyword match is a candidate, never proof of all mandatory brief criteria.
    status = "PASS" if selected and output == "EXPLAIN" else "REVIEW"
    if capabilities and missing:
        status = "BLOCKED"
    roles = (
        []
        if output in {"EXPLAIN", "INSPECT"}
        else ["unity_integration", "asset_inspector"]
        if output == "SPRITE" and not sprite_bake
        else ["asset_producer", "asset_inspector"]
        if sprite_bake
        else ["asset_producer", "asset_inspector"]
        if output == "ASSET"
        else ["rig_animation_artist", "animation_inspector"]
        if output == "ANIMATE"
        else ["intent_analyst", "unity_integration", "gameplay_qa_inspector"]
        if output == "GAME"
        else ["release_supervisor"]
    )
    if modeling_kind is not None and capabilities:
        from polyforge.workforce.permissions import MODELING_ROLES

        roles = ["asset_architect", MODELING_ROLES[modeling_kind], "asset_inspector"]
    return {
        "schema_version": "1.0.0",
        "query": request["query"],
        "request_digest": canonical_digest(request),
        "output": output,
        "status": status,
        "game_status": "PARTIAL",
        "cards": selected,
        "context_digest": canonical_digest(selected),
        "loaded_reference_paths": sorted({c["reference_path"] for c in selected}),
        "capability_ids": capabilities,
        "requirement_coverage": "NOT_APPLICABLE" if output == "EXPLAIN" else "UNVERIFIED",
        "roles": roles,
        "required_probes": [
            {
                "tool": t,
                "status": "VERSION_PROBED" if observations[t] is not None else "UNKNOWN",
                "availability": discovered[t]["availability"],
                "command": "polyforge knowledge probe --workspace ROOT --tool " + t,
            }
            for t in tools
        ],
        "missing_tools": missing,
        "tool_observations": observations,
        "gap": None
        if status == "PASS"
        else "Typed requirement coverage review required; candidate matches do not cover the brief",
        "operation_plan": [
            "preserve exact user constraints",
            "read selected DATA_ONLY references",
            "probe required installed versions",
            "validate typed capability input",
            "obtain required review and execute registered action only",
            "inspect actual artifacts and independent acceptance",
        ]
        if capabilities
        else ["explain selected concepts without tool execution"]
        if output == "EXPLAIN"
        else ["review gaps and prepare bounded SAFE_DISCOVERY proposal"],
        "discovery": discovery_proposal(request) if status == "REVIEW" else None,
        "planned_writes": [],
        "network": "DISABLED",
        "reference_trust": "DATA_ONLY",
        "permissions_from_references": False,
        "host_delegation": "UNKNOWN",
        "host_vision": "UNKNOWN",
        "unity_ui": "UNKNOWN",
        "precedence": "EXPLICIT_USER_REQUIREMENTS_CURRENT_APPENDIX_G_AND_CANONICAL_CLI",
    }
