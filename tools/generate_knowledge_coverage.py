"""Report the frozen minimum inventory without converting narrow fixtures into mastery."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polyforge.contracts.validation import canonical_digest
from polyforge.knowledge.catalog import catalog_cards

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_DIGEST = "dbee3a7cfced9bc6e1a5cd50dbf136f995385d126c874f3336bd82da1b69c7a8"

# Evidence is intentionally narrow. No row below covers its whole bundled subfeature.
CARD_IDS = {
    "blender.scene-transforms": ["blender.modeling"],
    "blender.mesh-modeling": ["blender.modeling"],
    "blender.geometry-nodes": ["blender.modeling"],
    "blender.sculpt-retopo": ["blender.modeling"],
    "blender.uv-pbr": ["blender.uv-pbr"],
    "blender.rig-animation": ["blender.animation"],
    "blender.automation-export": ["blender.context"],
    "unity.scene-editor": ["unity.editor"],
    "unity.csharp-architecture": ["unity.architecture"],
    "unity.input-cameras": ["game.mechanics"],
    "unity.physics": ["unity.physics"],
    "unity.animation": ["unity.animation"],
    "unity.navigation-ai": ["unity.ai"],
    "unity.rendering": ["unity.shaders", "unity.packages"],
    "unity.ui-audio": ["unity.ui"],
    "unity.assets-loading": ["unity.packages"],
    "unity.world-platform": ["game.worlds"],
}
MOTION = (
    "reports/phase-7-evidence/native/four_roles/"
    "rig-op_f7e2be21a41c5639150d0dc8b74ee106/asset/motion.json"
)
ANIMATION = (
    "reports/phase-7-evidence/native/four_roles/"
    "animation-646c4cbdd8db44b97701acdbab0ae96c/editmode.xml"
)
METRICS = "reports/phase-8-evidence/native/assets/mesh-a9e8f9820ae64dae/asset/metrics.json"
ARENA = "reports/phase-7-evidence/baseline-native/game-check-c9766313637d42af/editmode.xml"
NATIVE = {
    "blender.scene-transforms": (METRICS, "recipe transforms only", "5.2.2", "2026-10-28"),
    "blender.mesh-modeling": (
        METRICS,
        "parameterized hard-surface recipe only",
        "5.2.2",
        "2026-10-28",
    ),
    "blender.uv-pbr": (
        METRICS,
        "recipe UV/material metrics only; no texture painting mastery",
        "5.2.2",
        "2026-10-28",
    ),
    "blender.rig-animation": (
        MOTION,
        "mechanical robot ActionSlots and sampled motion only",
        "5.2.2",
        "2026-10-28",
    ),
    "unity.scene-editor": (
        ARENA,
        "managed arena scene/prefab bindings only",
        "6000.6.3f1",
        "2026-10-28",
    ),
    "unity.physics": (ARENA, "managed static collider fixture only", "6000.6.3f1", "2026-10-28"),
    "unity.animation": (
        ANIMATION,
        "two-state mechanical Animator fixture only; no IK",
        "6000.6.3f1",
        "2026-10-28",
    ),
}
PROBES = {
    "blender.automation-export": (
        "reports/phase-10-completion-evidence/blender-receipt-reverified.json",
        "fixed mesh repair/operator context probe only",
        "5.2.2",
        "2026-10-29",
    ),
    "unity.csharp-architecture": (
        "reports/phase-10-completion-evidence/headless-receipt-reverified.json",
        "fixed TypeCache/editor assembly probe only",
        "6000.6.3f1",
        "2026-10-29",
    ),
}


def local_evidence(path: str, kind: str, scope: str, version: str, date: str) -> dict[str, Any]:
    source = ROOT / path
    if not source.is_file():
        raise ValueError("Missing retained evidence: " + path)
    return {
        "kind": kind,
        "path": path,
        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "scope": scope,
        "tool_version": version,
        "verified_at": date,
        "qualification": "Historical evidence; no new native run or whole-row validation",
    }


def generate(taxonomy: dict[str, Any]) -> dict[str, Any]:
    if canonical_digest(taxonomy) != TAXONOMY_DIGEST:
        raise ValueError(
            "Frozen taxonomy/priority denominator changed; explicit versioned migration required"
        )
    cards = {c["knowledge_id"]: c for c in catalog_cards()}
    entries = []
    for row in taxonomy["entries"]:
        states = dict.fromkeys(
            (
                "documented",
                "version_probed",
                "workflow_verified",
                "executable",
                "independent_validation",
            ),
            "NONE",
        )
        evidence = []
        references = [cards[key] for key in CARD_IDS.get(row["id"], [])]
        for card in references:
            evidence.append(
                {
                    "kind": "documented",
                    "knowledge_id": card["knowledge_id"],
                    "sources": card["sources"],
                    "doc_digest": card["doc_digest"],
                    "reference_versions": card["versions"],
                    "verified_at": card["retrieved_or_verified_at"],
                    "scope": "Curated concept summary only; not all concepts in the inventory row",
                }
            )
            states["documented"] = "PARTIAL"
        if row["id"] in PROBES:
            evidence.append(
                local_evidence(PROBES[row["id"]][0], "version_probed", *PROBES[row["id"]][1:])
            )
            states["version_probed"] = "PARTIAL"
        if row["id"] in NATIVE:
            evidence.append(
                local_evidence(NATIVE[row["id"]][0], "workflow_verified", *NATIVE[row["id"]][1:])
            )
            states["version_probed"] = "PARTIAL"
            states["workflow_verified"] = "PARTIAL"
            states["executable"] = "PARTIAL"
        entries.append(
            {
                **row,
                "states": states,
                "evidence": evidence,
                "support_state": "REFERENCE_ONLY" if references else "UNSUPPORTED",
                "gap": "Whole subfeature unqualified; absent concepts stay in the denominator",
                "concept_selection_test": "NOT_EVALUATED_FOR_WHOLE_ROW",
                "good_bad_fixtures": "NARROW_FIXTURE_ONLY" if row["id"] in NATIVE else "NOT_RUN",
                "unseen_transfer": "NOT_RUN",
                "required_manual_approvals": "SCOPE_AND_AESTHETIC_REVIEW",
                "test_count": None,
                "confidence": None,
                "cost": "NOT_MEASURED",
                "independence": "EXTERNAL_EVALUATOR_NOT_SUPPLIED",
            }
        )
    counts = {
        state: {
            level: sum(e["states"][state] == level for e in entries)
            for level in ("NONE", "PARTIAL", "COMPLETE")
        }
        for state in entries[0]["states"]
    }
    history = json.loads(
        (ROOT / "polyforge/data/knowledge-history.json").read_text(encoding="utf-8")
    )
    return {
        "schema_version": "2.0.0",
        "scope": "V5_1_SECTION18_8_MINIMUM_BUNDLED_INVENTORY",
        "generated_at": datetime.now(UTC).date().isoformat(),
        "taxonomy_version": taxonomy["taxonomy_version"],
        "taxonomy_digest": TAXONOMY_DIGEST,
        "denominator": {
            "domain_count": 2,
            "subfeature_count": len(entries),
            "inventory_weight": sum(e["weight"] for e in entries),
            "frozen_at": taxonomy["frozen_at"],
        },
        "priority_policy": taxonomy["priority_policy"],
        "coverage_percentage": None,
        "counts": counts,
        "entries": entries,
        "records": history,
        "limitations": [
            "The minimum inventory is not a denominator for all production knowledge.",
            "No broad task evaluation, complete subfeature or production percentage is claimed.",
            "Partial evidence covers named fixtures only. All five evidence states stay separate.",
            "Historical records preserved verbatim; external evaluator evidence absent.",
            "Absent concepts, fixtures, transfer cases, cost and approvals remain explicit gaps.",
        ],
        "unfamiliar_code_execution": "BLOCKED",
        "host_native_delegation": "UNAVAILABLE_NO_VERIFIED_ADAPTER",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--taxonomy", type=Path, default=ROOT / "polyforge/data/knowledge-taxonomy.json"
    )
    parser.add_argument("--output", type=Path, default=ROOT / "reports/knowledge_coverage.json")
    args = parser.parse_args()
    report = generate(json.loads(args.taxonomy.read_text(encoding="utf-8")))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
