"""A frozen public fixture oracle; generator annotations cannot reduce its duties."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Any

from polyforge.contracts.manifest import load_manifest
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.evidence import verify_test_xml
from polyforge.unity.game import (
    GAME_EDIT_TESTS,
    PLAY_TESTS,
    compile_game_request,
    score_telemetry,
    validate_game_job,
)


def public_acceptance_spec(policy: WorkspacePolicy) -> dict[str, Any]:
    spec: dict[str, Any] = json.loads(
        files("polyforge").joinpath("data/arena_acceptance.json").read_text("utf-8")
    )
    frozen = policy.path(".polyforge/original_prompt.txt").read_text(encoding="utf-8")
    if frozen != spec["original_brief"]:
        raise InputError("No independently authored public acceptance specification for this brief")
    spec["original_brief_digest"] = canonical_digest(frozen)
    spec["acceptance_digest"] = canonical_digest(spec)
    return spec


def check_acceptance(
    policy: WorkspacePolicy, spec: dict[str, Any], evidence: dict[str, Any]
) -> dict[str, Any]:
    if spec != public_acceptance_spec(policy):
        raise InputError("Acceptance obligations differ from the frozen original brief")
    identifier = evidence.get("run_id")
    if not isinstance(identifier, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", identifier):
        raise InputError("Acceptance requires one native run identity")
    relative = "runs/" + identifier
    verify_test_xml(policy.path(relative + "/editmode.xml"), GAME_EDIT_TESTS)
    verify_test_xml(policy.path(relative + "/playmode.xml"), PLAY_TESTS)
    # Re-score actual traces, never accept public-oracles.json/supervisor labels as the oracle.
    game = compile_game_request(load_manifest(policy.path("game_manifest.json")))
    job = load_json(policy.path(relative + "/game-input.json"))
    validate_game_job(job, game)
    scored = score_telemetry(policy, relative, job)
    rows = []
    for requirement in spec["requirements"]:
        rows.append(
            {
                **requirement,
                "status": "PASS"
                if all(
                    scored["scenarios"][name]["gate_status"] == "PASS"
                    for name in requirement["oracles"]
                )
                else "FAIL",
                "evidence": [
                    relative + "/telemetry/" + name + ".json" for name in requirement["oracles"]
                ],
            }
        )
    return {
        "status": scored["status"],
        "game_status": "PARTIAL",
        "oracle_owner": "PUBLIC_DEVELOPMENT",
        "evaluator_owner": "EXTERNAL_NOT_SUPPLIED",
        "acceptance_digest": spec["acceptance_digest"],
        "traceability": rows,
        "mutations": {k: v for k, v in scored["scenarios"].items() if v["mutant"]},
    }
