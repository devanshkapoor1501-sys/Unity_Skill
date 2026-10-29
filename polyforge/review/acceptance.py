"""A frozen public fixture oracle; generator annotations cannot reduce its duties."""

from __future__ import annotations

import json
import re
from importlib.resources import files
from typing import Any

from polyforge.contracts.manifest import load_manifest
from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.review.amendments import read_amendments
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
    with policy.path(".polyforge/original_prompt.txt").open("rb") as stream:
        payload = stream.read(262145)
    if len(payload) > 262144:
        raise InputError("Frozen brief exceeds the 256 KiB read limit")
    try:
        frozen = payload.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeError as exc:
        raise InputError("Frozen brief is not UTF-8") from exc
    if frozen != spec["original_brief"]:
        raise InputError(
            "No independently authored public acceptance specification for this brief",
            kind=ErrorKind.POLICY_DENIED,
            code="PF-ACCEPTANCE-REVIEW",
        )
    spec["original_brief_digest"] = canonical_digest(frozen)
    amendments = read_amendments(policy, spec["original_brief_digest"])
    spec["amendment_digest"] = amendments["chain_digest"]
    spec["requirements"] += [row for r in amendments["records"] for row in r["requirements"]]
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
    known = json.loads(
        files("polyforge").joinpath("data/arena_acceptance.json").read_text("utf-8")
    )["requirements"]
    for requirement in spec["requirements"]:
        supported = any(
            all(
                requirement[k] == r[k]
                for k in ("feature_id", "artifact_id", "unity_component", "oracles")
            )
            for r in known
        )
        rows.append(
            {
                **requirement,
                "status": "REVIEW"
                if not supported
                else "PASS"
                if all(
                    scored["scenarios"][name]["gate_status"] == "PASS"
                    for name in requirement["oracles"]
                )
                else "FAIL",
                "evidence": [
                    relative + "/telemetry/" + name + ".json" for name in requirement["oracles"]
                ]
                if supported
                else [],
            }
        )
    return {
        "status": "FAIL"
        if scored["status"] != "PASS"
        else "REVIEW"
        if any(r["status"] == "REVIEW" for r in rows)
        else "PASS",
        "game_status": "PARTIAL",
        "oracle_owner": "PUBLIC_DEVELOPMENT",
        "evaluator_owner": "EXTERNAL_NOT_SUPPLIED",
        "acceptance_digest": spec["acceptance_digest"],
        "traceability": rows,
        "mutations": {k: v for k, v in scored["scenarios"].items() if v["mutant"]},
    }
