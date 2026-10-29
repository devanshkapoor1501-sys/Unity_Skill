"""Recompute technical checks before promotion; never trust supervisor labels."""

from __future__ import annotations

import copy
import hashlib
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest, load_json, validate_schema
from polyforge.runner.locks import FileLock
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.workforce.models import validate_task
from polyforge.workforce.permissions import authorize
from polyforge.workforce.workers import check_candidate, inspect_candidate

INSPECTORS = (
    "brief_compliance_inspector",
    "asset_animation_inspector",
    "unity_import_inspector",
    "gameplay_qa_inspector",
    "performance_inspector",
    "release_supervisor",
)


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
    if operator == candidate["producer_id"] or operator in INSPECTORS:
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
    }
    with FileLock(policy, ".polyforge/locks/human-review.lock"):
        path = ".polyforge/human-reviews/" + candidate["candidate_digest"] + ".json"
        prior = load_json(policy.path(path)) if policy.path(path).is_file() else {"history": []}
        atomic_json(policy, path, {"current": receipt, "history": [*prior["history"], receipt]})
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
    visual_required = task.get("input", {}).get("spec", {}).get("visual_approval_required", False)
    path = policy.path(".polyforge/human-reviews/" + candidate["candidate_digest"] + ".json")
    recorded = load_json(path)["current"] if path.is_file() else None
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
        subjective = human_review["verdict"]
        if subjective == "REJECTED" or visual_required:
            promotion = subjective
    game = task["task_class"] == "BUILD_GAME"
    acceptance = None
    if game:
        from polyforge.review.acceptance import check_acceptance, public_acceptance_spec

        acceptance = check_acceptance(
            policy, public_acceptance_spec(policy), {"run_id": candidate["production_run_id"]}
        )
        if acceptance["status"] != "PASS":
            promotion = "REJECTED"
    integrated = task.get("capability_id") in {"unity.game.arena.v1", "sprite.unity.strip.v1"}
    records = []
    for role in INSPECTORS:
        applies = role in {"brief_compliance_inspector", "release_supervisor"}
        applies |= role == "asset_animation_inspector" and not game
        applies |= role == "unity_import_inspector" and integrated
        applies |= role == "gameplay_qa_inspector" and game
        records.append(
            {
                "authored_by": candidate["producer_id"],
                "reviewed_by": role,
                "evaluator_owner": "PUBLIC_DEVELOPMENT",
                "tool_identity": "polyforge.registered.candidate_inspection.v1",
                "writable_paths": [],
                "readable_paths": [f["path"] for f in candidate["files"]],
                "status": "APPROVED" if applies else "NOT_RUN",
                "required": applies,
            }
        )
    board = {
        "schema_version": "1.0.0",
        "artifact_id": candidate["artifact_id"],
        "candidate_digest": candidate["candidate_digest"],
        "revision": candidate["revision"],
        "brief_digest": candidate["brief_digest"],
        "task": copy.deepcopy(task),
        "technical": technical["verdict"],
        "subjective": subjective,
        "human_review": copy.deepcopy(human_review),
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
