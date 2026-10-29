"""Typed playbooks propose actions; native checks, not log labels, prove repair."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any
from uuid import uuid4

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.locks import FileLock
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.security.policy import redact
from polyforge.workforce.permissions import assert_public_path

# Versioned deterministic rules, with no source-code patch or shell execution action.
PLAYBOOKS = {
    "GUID": ("unity_integration", "rebuild_native_binding", "native GUID/reference observation"),
    "FBX_AXES": ("asset_producer", "rebuild_export", "source/export/import axis and scale metrics"),
    "GEOMETRY": ("modeler", "regenerate_geometry", "saved-source degeneracy and geometry metrics"),
    "UNITY_API": ("unity_integration", None, "pinned API, assembly and package context"),
    "MISSING_COMPONENT": (
        "unity_integration",
        "rebuild_native_binding",
        "native component/reference observation",
    ),
    "SPRITE_CURVE": (
        "unity_integration",
        "rebuild_sprite",
        "native sprite local IDs and PPtr curve",
    ),
    "ANIMATION_SLOT": (
        "rig_animation_artist",
        "rebuild_motion",
        "saved Blender action slot/channelbag and motion",
    ),
    "WORKER_TIMEOUT": (
        "original_specialist",
        "retry_registered_worker",
        "owned process exit/timeout and budget",
    ),
}
CODES = {
    "PF-GUID-MISMATCH": "GUID",
    "PF-FBX-AXES": "FBX_AXES",
    "PF-GEOMETRY-DEGENERATE": "GEOMETRY",
    "PF-UNITY-API": "UNITY_API",
    "PF-COMPONENT-MISSING": "MISSING_COMPONENT",
    "PF-SPRITE-CURVE": "SPRITE_CURVE",
    "PF-ANIMATION-SLOT": "ANIMATION_SLOT",
    "PF-WORKER-TIMEOUT": "WORKER_TIMEOUT",
    "PF-MATERIAL-SWAPPED": "GUID",
    "PF-CLIP-MISLEADING": "ANIMATION_SLOT",
    "PF-MECHANIC-MISSING": "MISSING_COMPONENT",
}
CONTEXTS = (
    (r"UnityEditor.*runtime assembly|editor.only.*assembly", "ASSEMBLY_CONTEXT"),
    (r"bpy\.ops.*mode|wrong.*context|OBJECT mode", "MODE_CONTEXT"),
    (r"package.*not found|package.*missing", "PACKAGE_ABSENCE"),
    (r"domain reload", "DOMAIN_RELOAD"),
    (r"\bCS0117\b|\bCS1061\b|API mismatch", "API_MISMATCH"),
)


def _validate(value: dict[str, Any]) -> None:
    fields = {
        "schema_version",
        "input_digest",
        "producer_id",
        "tool",
        "structured",
        "log",
        "affected_ids",
        "artifacts",
    }
    if not isinstance(value, dict) or set(value) != fields or value["schema_version"] != "1.0.0":
        raise InputError("Invalid versioned forensic evidence fields")
    if not isinstance(value["input_digest"], str) or not re.fullmatch(
        r"[a-f0-9]{64}", value["input_digest"]
    ):
        raise InputError("Forensics requires a frozen input digest")
    if not isinstance(value["producer_id"], str) or not re.fullmatch(
        r"[A-Za-z][A-Za-z0-9_-]{0,63}", value["producer_id"]
    ):
        raise InputError("Invalid producer identity")
    tool = value["tool"]
    if (
        not isinstance(tool, dict)
        or set(tool) != {"name", "version"}
        or not isinstance(tool["name"], str)
        or tool["name"] not in {"unity", "blender", "python"}
        or not isinstance(tool["version"], str)
        or not tool["version"].strip()
        or len(tool["version"]) > 128
    ):
        raise InputError("Forensics requires an explicit registered tool and version")
    structured = value["structured"]
    if (
        not isinstance(structured, dict)
        or set(structured) != {"status", "code"}
        or not isinstance(structured["status"], str)
        or structured["status"] not in {"PASS", "FAIL", "BLOCKED", "NOT_RUN"}
        or (
            structured["code"] is not None
            and (not isinstance(structured["code"], str) or len(structured["code"]) > 128)
        )
    ):
        raise InputError("Invalid structured worker result")
    if not isinstance(value["log"], str) or len(value["log"]) > 65536:
        raise InputError("Forensic excerpt exceeds its bounded text limit")
    ids = value["affected_ids"]
    if (
        not isinstance(ids, list)
        or not 1 <= len(ids) <= 128
        or any(
            not isinstance(i, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", i)
            for i in ids
        )
        or len(set(ids)) != len(ids)
    ):
        raise InputError("Forensics requires unique semantic asset IDs")
    artifacts = value["artifacts"]
    if not isinstance(artifacts, list) or not 1 <= len(artifacts) <= 128:
        raise InputError("Forensics requires bounded evidence references")
    names = []
    for item in artifacts:
        if (
            not isinstance(item, dict)
            or set(item) != {"id", "path", "sha256"}
            or not isinstance(item["id"], str)
            or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", item["id"])
        ):
            raise InputError("Invalid forensic artifact identity")
        name = item["path"]
        if (
            not isinstance(name, str)
            or not name.startswith("runs/")
            or len(name) > 4096
            or any(p in {"", ".", ".."} or ":" in p or "\\" in p for p in name.split("/"))
        ):
            raise InputError("Forensic artifact must belong to managed run evidence")
        if not isinstance(item["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"]):
            raise InputError("Forensic evidence requires a SHA-256 digest")
        names.append(name)
    if len(set(names)) != len(names):
        raise InputError("Duplicate forensic evidence paths")
    canonical_digest(value)


def diagnose_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    _validate(evidence)
    source = copy.deepcopy(evidence)
    source["log"] = redact(source["log"])
    code = source["structured"]["code"]
    recorded_status = source["structured"]["status"]
    executed_failure = recorded_status == "FAIL"
    playbook = CODES.get(code) if executed_failure else None
    role, action, verification = (
        PLAYBOOKS[playbook]
        if playbook is not None
        else (source["producer_id"], None, "independent reproduction before proposing any patch")
    )
    context = (
        next((kind for pattern, kind in CONTEXTS if re.search(pattern, source["log"], re.I)), None)
        if executed_failure
        else None
    )
    hypotheses = (
        []
        if not executed_failure
        else [{"cause": playbook, "confidence": 0.85, "falsify_with": verification}]
        if playbook
        else [
            {
                "cause": context or "missing_reference",
                "confidence": 0.35,
                "falsify_with": "independent native observation",
            },
            {
                "cause": "stale_or_wrong_execution_context",
                "confidence": 0.25,
                "falsify_with": "fresh registered worker under pinned context",
            },
        ]
    )
    nodes = [
        "input:" + source["input_digest"],
        "tool:" + source["tool"]["name"] + ":" + source["tool"]["version"],
        *["artifact:" + a["id"] for a in source["artifacts"]],
    ]
    signature = canonical_digest(
        {
            "input_digest": source["input_digest"],
            "code": code,
            "affected_ids": sorted(source["affected_ids"]),
        }
    )
    return {
        "schema_version": "1.0.0",
        "issue_id": "ISSUE-" + canonical_digest(source)[:16],
        "input_digest": source["input_digest"],
        "producer_id": source["producer_id"],
        "original_specialist": source["producer_id"] if role == "original_specialist" else role,
        "affected_ids": source["affected_ids"],
        "symptom_signature": signature,
        "playbook_version": "1.0.0",
        "playbook": playbook,
        "diagnosis_status": recorded_status
        if not executed_failure
        else "BLOCKED"
        if action is None and playbook
        else "REVIEW"
        if playbook is None
        else "FAIL",
        "recommended_action": action,
        "context_failure": context,
        "hypotheses": hypotheses,
        "rejected_alternatives": ["arbitrary source patch", "implicit package installation"],
        "repair_status": "NOT_RUN",
        "evaluated_test_status": "NOT_RUN",
        "source_evidence": source,
        "evidence_graph": {
            "nodes": [*nodes, "issue:" + signature],
            "edges": [
                {"from": node, "to": "issue:" + signature, "relation": "supports"} for node in nodes
            ],
        },
    }


def _native_plan(policy: WorkspacePolicy, issue: dict[str, Any]) -> dict[str, Any] | None:
    """Admit only a reproduced native symptom with registered original inputs."""
    registry = policy.path(".polyforge/unity-issues.json")
    if issue["source_evidence"]["tool"]["name"] != "unity" or not registry.is_file():
        return None
    from polyforge.unity.evidence import reconcile_report
    from polyforge.unity.repairs import current_request

    recorded = load_json(registry)
    path = recorded["evidence_dir"] + "/bindings.json"
    if not any(a["path"] == path for a in issue["source_evidence"]["artifacts"]):
        return None
    request = current_request(policy)
    if (
        issue["input_digest"] != request["input_digest"]
        or recorded["input_digest"] != request["input_digest"]
    ):
        raise InputError("Forensic native inputs changed; diagnose the current revision")
    observed = reconcile_report(request, load_json(policy.path(path)))
    codes = {
        "binding": "PF-GUID-MISMATCH",
        "scale": "PF-FBX-AXES",
        "axis": "PF-FBX-AXES",
        "material": "PF-MATERIAL-SWAPPED",
        "component": "PF-COMPONENT-MISSING",
    }
    try:
        claimed = json.loads(issue["source_evidence"]["log"])
    except ValueError:
        return None
    matches = [
        row
        for row in observed["issues"]
        if issue["affected_ids"] == [row["asset_id"]]
        and codes.get(row["category"]) == issue["source_evidence"]["structured"]["code"]
        and claimed
        == {**row, "issue_id": "ISSUE-" + canonical_digest(row)[:12], "repair_supported": True}
    ]
    if len(matches) != 1:
        return None
    row = matches[0]
    identifier = "ISSUE-" + canonical_digest(row)[:12]
    if {**row, "issue_id": identifier} not in recorded["issues"]:
        raise InputError("Forensic symptom differs from registered native diagnosis")
    return {
        "schema_version": "1.0.0",
        "input_digest": request["input_digest"],
        "issue_id": identifier,
        "category": row["category"],
        "asset_id": row["asset_id"],
        "operation": "rebuild_native_binding",
    }


def plan_repair(policy: WorkspacePolicy, issue: dict[str, Any]) -> dict[str, Any]:
    if (
        not isinstance(issue, dict)
        or "source_evidence" not in issue
        or diagnose_evidence(issue["source_evidence"]) != issue
    ):
        raise InputError("Repair issue differs from recorded deterministic diagnosis")
    for item in issue["source_evidence"]["artifacts"]:
        assert_public_path(policy, item["path"])
    for item in issue["source_evidence"]["artifacts"]:
        if hashlib.sha256(policy.path(item["path"]).read_bytes()).hexdigest() != item["sha256"]:
            raise InputError("Forensic evidence was substituted after diagnosis")
    action = issue["recommended_action"]
    native = _native_plan(policy, issue) if action else None
    supported = native is not None
    if supported:
        action = "rebuild_native_binding"
    targets = (
        ["UnityProject/Assets/PolyForgeGenerated"]
        if action in {"rebuild_native_binding", "rebuild_sprite"}
        else ["runs/<new_immutable_revision>"]
        if action
        else []
    )
    return {
        "schema_version": "1.0.0",
        "issue_id": issue["issue_id"],
        "diagnosis": copy.deepcopy(issue),
        "native_plan": native,
        "input_digest": issue["input_digest"],
        "symptom_signature": issue["symptom_signature"],
        "action": action,
        "original_specialist": issue["original_specialist"],
        "affected_ids": issue["affected_ids"],
        "dry_run": True,
        "status": "PROPOSED" if supported else "BLOCKED",
        "blocked_reason": None
        if supported
        else "No reconstructable registered original inputs/action; route to original specialist",
        "changed_paths": targets,
        "rollback_required": True,
        "risk": "NATIVE_REIMPORT_AND_REGRESSION_REQUIRED"
        if targets
        else "NO_SAFE_REGISTERED_ACTION",
        "verification_plan": [
            "validate exact input/evidence hashes",
            "rerun targeted native checks",
            "rerun applicable broad regression",
            "compare original native identities and scenarios after rollback",
        ],
        "attempt_limit": 2,
        "execution_authority": "REGISTERED_ENGINE_ACTION_ONLY",
        "execution_status": "NOT_RUN",
    }


def reserve_attempt(
    policy: WorkspacePolicy, issue: dict[str, Any], proposal: dict[str, Any]
) -> dict[str, Any]:
    if proposal != plan_repair(policy, issue) or proposal["status"] != "PROPOSED":
        raise InputError("No matching registered repair proposal")
    path = ".polyforge/forensic-attempts.json"
    key = issue["symptom_signature"]
    with FileLock(policy, ".polyforge/locks/forensic-attempts.lock"):
        history = load_json(policy.path(path)) if policy.path(path).is_file() else {}
        previous = history.get(key, [])
        if len(previous) >= 2 or any(
            a["proposal_digest"] == canonical_digest(proposal) for a in previous
        ):
            raise InputError(
                "Escalate repeated identical proposal or exhausted repair budget",
                kind=ErrorKind.RETRY_EXHAUSTED,
            )
        attempt = {
            "symptom_signature": key,
            "proposal_digest": canonical_digest(proposal),
            "token": uuid4().hex,
            "attempt": len(previous) + 1,
            "status": "RESERVED",
            "evidence_paths": [],
        }
        history[key] = [*previous, attempt]
        atomic_json(policy, path, history)
        return attempt


def finish_attempt(
    policy: WorkspacePolicy, attempt: dict[str, Any], *, status: str, evidence_paths: list[str]
) -> None:
    if status not in {"PASS", "FAIL", "BLOCKED"} or not evidence_paths:
        raise InputError("Repair completion requires an explicit outcome and evidence")
    for name in evidence_paths:
        if not policy.path(name).is_file():
            raise InputError("Repair completion evidence is missing")
    path = ".polyforge/forensic-attempts.json"
    with FileLock(policy, ".polyforge/locks/forensic-attempts.lock"):
        history = load_json(policy.path(path))
        matches = [
            a
            for a in history.get(attempt.get("symptom_signature"), [])
            if a["token"] == attempt.get("token") and a["status"] == "RESERVED"
        ]
        if len(matches) != 1 or matches[0] != attempt:
            raise InputError("Repair attempt ownership is stale or already completed")
        matches[0].update(
            status=status,
            evidence_paths=evidence_paths,
            evidence_hashes={
                name: hashlib.sha256(policy.path(name).read_bytes()).hexdigest()
                for name in evidence_paths
            },
        )
        atomic_json(policy, path, history)
