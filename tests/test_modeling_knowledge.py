"""Modeling references select bounded candidates without claiming broad expertise."""

import json
from importlib.resources import files

import pytest

from polyforge.blender.modeling import MODELING_CAPABILITIES
from polyforge.contracts.validation import canonical_digest, validate_schema
from polyforge.knowledge.router import route_reference
from polyforge.security.paths import WorkspacePolicy
from polyforge.workforce.permissions import MODELING_ROLES


@pytest.mark.parametrize(
    "query,kind",
    [
        ("Create a modular room kit", "room_kit"),
        ("Create a stylized vehicle", "vehicle"),
        ("Create a detailed mechanical prop", "mechanical_prop"),
        ("Create an organic practice asset", "organic"),
        ("Create a modeling composition using a curve and Boolean", "compose"),
    ],
)
def test_modeling_candidate_preserves_review_and_zero_writes(tmp_path, query, kind):
    result = route_reference(
        WorkspacePolicy(tmp_path),
        {"schema_version": "1.0.0", "query": query, "output": "ASSET", "domain": "blender"},
    )
    assert result["capability_ids"] == [MODELING_CAPABILITIES[kind]]
    assert result["roles"] == ["asset_architect", MODELING_ROLES[kind], "asset_inspector"]
    assert result["status"] in {"REVIEW", "BLOCKED"}
    assert result["requirement_coverage"] == "UNVERIFIED"
    assert result["game_status"] == "PARTIAL"
    assert result["planned_writes"] == []
    assert result["network"] == "DISABLED"
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("need", ["sculpt", "retopology", "text", "grease pencil", "simulation"])
def test_assisted_domain_is_not_silently_substituted_with_vehicle(tmp_path, need):
    result = route_reference(
        WorkspacePolicy(tmp_path),
        {
            "schema_version": "1.0.0",
            "query": f"Create a vehicle with {need}",
            "output": "ASSET",
            "domain": "blender",
        },
    )
    assert not result["capability_ids"]
    assert result["status"] == "REVIEW"
    assert result["discovery"]["execution_status"] == "BLOCKED"


def test_explanation_loads_concept_guidance_without_execution(tmp_path):
    result = route_reference(
        WorkspacePolicy(tmp_path),
        {
            "schema_version": "1.0.0",
            "query": "Explain modifiers and curve modeling composition",
            "output": "EXPLAIN",
            "domain": "blender",
        },
    )
    assert result["status"] == "PASS"
    assert result["roles"] == result["capability_ids"] == result["required_probes"] == []
    advanced = next(c for c in result["cards"] if c["knowledge_id"] == "blender.advanced-modeling")
    assert advanced["knowledge_state"] == "REFERENCE_ONLY"
    assert advanced["doc_digest"] == canonical_digest(advanced["reference_text"])
    assert "Object Mode" in advanced["reference_text"]


def test_modeling_card_is_schema_valid_and_frozen_taxonomy_is_unchanged():
    data = files("polyforge").joinpath("data")
    cards = json.loads(data.joinpath("knowledge.json").read_text("utf-8"))
    card = next(c for c in cards if c["knowledge_id"] == "blender.advanced-modeling")
    validate_schema(card, "knowledge_card.schema.json")
    assert set(card["capability_ids"]) == set(MODELING_CAPABILITIES.values())
    taxonomy = json.loads(data.joinpath("knowledge-taxonomy.json").read_text("utf-8"))
    assert len(taxonomy["entries"]) == 20
    assert taxonomy["taxonomy_version"] == "18.8-minimum-v1"
    assert (
        canonical_digest(taxonomy)
        == "dbee3a7cfced9bc6e1a5cd50dbf136f995385d126c874f3336bd82da1b69c7a8"
    )
