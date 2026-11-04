"""Recompute technical checks before promotion; never trust supervisor labels."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.review.amendments import read_amendments
from polyforge.runner.locks import FileLock
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.workforce.models import validate_task
from polyforge.workforce.permissions import ROLES, authorize
from polyforge.workforce.workers import check_candidate, inspect_candidate

INSPECTORS = (
    "brief_compliance_inspector",
    "asset_animation_inspector",
    "unity_import_inspector",
    "gameplay_qa_inspector",
    "performance_inspector",
    "release_supervisor",
)


def _human_record(value: Any, candidate: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "schema_version",
        "candidate_digest",
        "revision",
        "operator",
        "reason",
        "verdict",
        "origin",
        "identity_authenticated",
        "amendment_digest",
    }
    if (
        not isinstance(value, dict)
        or set(value) != {"current", "history"}
        or not isinstance(value["history"], list)
        or not 1 <= len(value["history"]) <= 100
        or value["current"] != value["history"][-1]
    ):
        raise InputError("Invalid operator decision history")
    for receipt in value["history"]:
        if (
            not isinstance(receipt, dict)
            or set(receipt) != fields
            or receipt["schema_version"] != "1.0.0"
            or receipt["candidate_digest"] != candidate["candidate_digest"]
            or receipt["revision"] != candidate["revision"]
            or receipt["origin"] != "EXPLICIT_LOCAL_OPERATOR_ATTESTATION"
            or receipt["identity_authenticated"] is not False
            or not isinstance(receipt["amendment_digest"], str)
            or len(receipt["amendment_digest"]) != 64
            or not isinstance(receipt["verdict"], str)
            or receipt["verdict"] not in {"APPROVED", "REJECTED"}
            or any(
                not isinstance(receipt[key], str)
                or not receipt[key].strip()
                or len(receipt[key]) > 4096
                for key in ("operator", "reason")
            )
            or receipt["operator"] == candidate["producer_id"]
            or receipt["operator"] in ROLES
        ):
            raise InputError(
                "Operator attestation is malformed or belongs to a role/other revision"
            )
    current: dict[str, Any] = value["current"]
    return current


def record_human_review(
    policy: WorkspacePolicy, candidate: dict[str, Any], *, verdict: str, operator: str, reason: str
) -> dict[str, Any]:
    """Explicit local-operator attestation; never called by a specialist role.

    This does not authenticate the OS user's real-world identity. Role execution
    cannot write this reserved scope; trusted local operators can attest/revoke.
    """
    check_candidate(policy, candidate)
    if verdict not in {"APPROVED", "REJECTED"} or any(
        not isinstance(v, str) or not v.strip() or len(v) > 4096 for v in (operator, reason)
    ):
        raise InputError("Human decision needs a verdict, operator and explicit reason")
    if operator == candidate["producer_id"] or operator in ROLES:
        raise InputError("A producer/inspector role cannot attest as a human operator")
    receipt = {
        "schema_version": "1.0.0",
        "candidate_digest": candidate["candidate_digest"],
        "revision": candidate["revision"],
        "operator": operator,
        "reason": reason,
        "verdict": verdict,
        "origin": "EXPLICIT_LOCAL_OPERATOR_ATTESTATION",
        "identity_authenticated": False,
        "amendment_digest": read_amendments(policy, candidate["brief_digest"])["chain_digest"],
    }
    with FileLock(policy, ".polyforge/locks/human-review.lock"):
        path = ".polyforge/human-reviews/" + candidate["candidate_digest"] + ".json"
        prior = load_json(policy.path(path)) if policy.path(path).is_file() else {"history": []}
        if policy.path(path).is_file():
            _human_record(prior, candidate)
        updated = {"current": receipt, "history": [*prior["history"], receipt]}
        _human_record(updated, candidate)
        atomic_json(policy, path, updated)
    return receipt


class CandidateReader:
    """An engine read interface, not isolation from same-user native code."""

    def __init__(self, policy: WorkspacePolicy, candidate: dict[str, Any], role: str) -> None:
        check_candidate(policy, candidate)
        if role not in INSPECTORS or role == candidate["producer_id"]:
            raise InputError("Review requires a distinct registered inspector")
        self.policy, self.role = policy, role
        self.files = {item["path"]: item["sha256"] for item in candidate["files"]}
        if len(self.files) != len(candidate["files"]):
            raise InputError("Duplicate candidate evidence paths")

    def read(self, name: str) -> bytes:
        path = self.policy.path(name)
        relative = path.relative_to(self.policy.root).as_posix()
        if relative not in self.files:
            raise InputError(
                "Inspector read is outside sealed candidate", kind=ErrorKind.POLICY_DENIED
            )
        authorize(self.policy, self.role, "read", relative)
        with path.open("rb") as stream:
            data = stream.read(33_554_433)
        if len(data) > 33_554_432 or hashlib.sha256(data).hexdigest() != self.files[relative]:
            raise InputError("Candidate evidence changed or exceeds read budget")
        return data


def review_candidate(
    policy: WorkspacePolicy,
    candidate: dict[str, Any],
    task: dict[str, Any],
    *,
    human_review: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure board result. Missing subjective/evaluator evidence is never approved."""
    validate_task(task)
    check_candidate(policy, candidate)
    if any(candidate["producer_id"] == role for role in INSPECTORS):
        raise InputError("A producer cannot join its own approval board")
    # Registered checks inspect exact sealed source/metrics/test identities, not role assertions.
    technical = inspect_candidate(policy, candidate, task, technical_only=True)
    amendments = read_amendments(policy, candidate["brief_digest"])
    visual_required = task.get("input", {}).get("spec", {}).get("visual_approval_required", False)
    visual_required |= any(r["visual_approval_required"] for r in amendments["records"])
    path = policy.path(".polyforge/human-reviews/" + candidate["candidate_digest"] + ".json")
    recorded = _human_record(load_json(path), candidate) if path.is_file() else None
    if human_review is not None and human_review != recorded:
        raise InputError("Unregistered human approval receipt", kind=ErrorKind.POLICY_DENIED)
    human_review = recorded
    subjective = "REVIEW" if visual_required else "NOT_REQUIRED"
    promotion = "REVIEW" if visual_required else "APPROVED"
    if human_review is not None:
        if (
            human_review.get("candidate_digest") != candidate["candidate_digest"]
            or human_review.get("revision") != candidate["revision"]
        ):
            raise InputError("Human review belongs to another candidate revision")
        subjective = (
            human_review["verdict"]
            if human_review["verdict"] == "REJECTED"
            or human_review["amendment_digest"] == amendments["chain_digest"]
            else "REVIEW"
        )
        if subjective == "REJECTED" or visual_required:
            promotion = subjective
    game = task["task_class"] == "BUILD_GAME"
    if not game and any(r["requirements"] for r in amendments["records"]):
        promotion = "REVIEW" if promotion != "REJECTED" else promotion
    source_review = None
    if task.get("capability_id") == "sprite.unity.strip.v1":
        from polyforge.review.sprite_source import review_sprite_source

        source_review = review_sprite_source(policy, task["input"])
        if source_review["promotion"] != "APPROVED" and promotion != "REJECTED":
            promotion = source_review["promotion"]
        if source_review["subjective"] != "NOT_REQUIRED" and subjective != "REJECTED":
            subjective = source_review["subjective"]
    acceptance = None
    if game:
        from polyforge.review.acceptance import check_acceptance, public_acceptance_spec

        try:
            if task.get("capability_id") == "unity.game.platformer.v1":
                raise InputError(
                    "No independent original-brief acceptance specification "
                    "was supplied for this platformer",
                    code="PF-ACCEPTANCE-REVIEW",
                )
            acceptance_spec = public_acceptance_spec(policy)
            if acceptance_spec["original_brief_digest"] != candidate["brief_digest"]:
                raise InputError(
                    "Game candidate differs from the frozen original brief",
                    code="PF-ACCEPTANCE-REVIEW",
                )
            acceptance = check_acceptance(
                policy, acceptance_spec, {"run_id": candidate["production_run_id"]}
            )
        except InputError as exc:
            if exc.code != "PF-ACCEPTANCE-REVIEW":
                raise
            acceptance = {"status": "REVIEW", "game_status": "PARTIAL", "reason": str(exc)}
        if acceptance["status"] != "PASS":
            promotion = (
                "REVIEW"
                if acceptance["status"] == "REVIEW" and promotion != "REJECTED"
                else "REJECTED"
            )
    integrated = task.get("capability_id") in {
        "unity.game.arena.v1",
        "unity.game.platformer.v1",
        "sprite.unity.strip.v1",
    }
    records = []
    for role in INSPECTORS:
        applies = role in {"brief_compliance_inspector", "release_supervisor"}
        applies |= role == "asset_animation_inspector" and not game
        applies |= role == "unity_import_inspector" and integrated
        applies |= role == "gameplay_qa_inspector" and game
        verdict = "APPROVED" if applies else "NOT_RUN"
        if role == "release_supervisor":
            verdict = promotion
        elif (
            role in {"brief_compliance_inspector", "gameplay_qa_inspector"}
            and acceptance is not None
            and acceptance["status"] != "PASS"
        ):
            verdict = "REVIEW" if acceptance["status"] == "REVIEW" else "REJECTED"
        records.append(
            {
                "authored_by": candidate["producer_id"],
                "reviewed_by": role,
                "evaluator_owner": "PUBLIC_DEVELOPMENT",
                "tool_identity": "polyforge.registered.candidate_inspection.v1",
                "writable_paths": [],
                "readable_paths": [f["path"] for f in candidate["files"]],
                "status": verdict,
                "required": applies,
            }
        )
    board = {
        "schema_version": "1.0.0",
        "artifact_id": candidate["artifact_id"],
        "candidate_digest": candidate["candidate_digest"],
        "revision": candidate["revision"],
        "brief_digest": candidate["brief_digest"],
        "amendment_digest": amendments["chain_digest"],
        "task": copy.deepcopy(task),
        "technical": technical["verdict"],
        "subjective": subjective,
        "human_review": copy.deepcopy(human_review),
        "source_review": source_review,
        "acceptance": acceptance,
        "gameplay": "PUBLIC_CHECKS_ONLY" if game else "NOT_REQUIRED",
        "game_status": "PARTIAL",
        "promotion": promotion,
        "inspectors": records,
        "evidence_digest": canonical_digest(candidate["files"]),
        "independence": "DIFFERENT_ROLE_SAME_HOST",
        "evaluator_owner": "EXTERNAL_NOT_SUPPLIED",
        "isolation_verified": False,
        "unresolved_risks": ["Required artistic review pending"] if subjective == "REVIEW" else [],
    }
    validate_schema(board, "review_board.schema.json")
    return board


def require_promotion(
    policy: WorkspacePolicy, candidate: dict[str, Any], receipt: dict[str, Any]
) -> None:
    task = receipt.get("task")
    if not isinstance(task, dict):
        raise InputError("Promotion lacks a registered task-bound review")
    observed = review_candidate(policy, candidate, task)
    if receipt != observed or observed["promotion"] != "APPROVED":
        raise InputError(
            "Promotion needs every required approval for this revision",
            kind=ErrorKind.POLICY_DENIED,
        )
