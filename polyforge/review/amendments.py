"""Original-bound, append-only local operator amendments; never erase obligations."""

from __future__ import annotations

import re
from typing import Any

from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.locks import FileLock
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.workforce.models import validate_task
from polyforge.workforce.permissions import ROLES


def _validate_amendment(value: Any) -> None:
    if (
        not isinstance(value, dict)
        or set(value) != {"text", "requirements", "visual_approval_required"}
        or not isinstance(value["text"], str)
        or not 1 <= len(value["text"].strip()) <= 16384
        or type(value["visual_approval_required"]) is not bool
        or not isinstance(value["requirements"], list)
        or len(value["requirements"]) > 64
    ):
        raise InputError("Invalid bounded amendment fields")
    for row in value["requirements"]:
        if (
            not isinstance(row, dict)
            or set(row)
            != {"original_phrase", "feature_id", "artifact_id", "unity_component", "oracles"}
            or any(
                not isinstance(row[k], str) or not 1 <= len(row[k]) <= 4096
                for k in ("original_phrase", "feature_id", "artifact_id", "unity_component")
            )
            or row["original_phrase"] not in value["text"]
            or not isinstance(row["oracles"], list)
            or not 1 <= len(row["oracles"]) <= 32
            or any(
                not isinstance(o, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}", o)
                for o in row["oracles"]
            )
        ):
            raise InputError(
                "Amendment obligations need phrases and explicit typed oracle mappings"
            )


def read_amendments(policy: WorkspacePolicy, brief_digest: str) -> dict[str, Any]:
    if not re.fullmatch(r"[a-f0-9]{64}", brief_digest):
        raise InputError("Invalid original brief identity")
    empty = {"original_brief_digest": brief_digest, "records": []}
    previous = canonical_digest(empty)
    path = policy.path(".polyforge/amendments/" + brief_digest + ".json")
    if not path.is_file():
        return {**empty, "chain_digest": previous}
    chain: dict[str, Any] = load_json(path)
    if (
        not isinstance(chain, dict)
        or set(chain) != {"original_brief_digest", "original_brief", "records", "chain_digest"}
        or chain["original_brief_digest"] != brief_digest
        or not isinstance(chain["original_brief"], str)
        or canonical_digest(chain["original_brief"]) != brief_digest
        or not isinstance(chain["records"], list)
        or not 1 <= len(chain["records"]) <= 100
    ):
        raise InputError("Amendment chain differs from its frozen original brief")
    for index, record in enumerate(chain["records"], 1):
        fields = {
            "text",
            "requirements",
            "visual_approval_required",
            "original_brief_digest",
            "sequence",
            "previous_digest",
            "operator",
            "reason",
            "origin",
            "identity_authenticated",
            "record_digest",
        }
        if not isinstance(record, dict) or set(record) != fields:
            raise InputError("Malformed amendment record")
        _validate_amendment(
            {k: record[k] for k in ("text", "requirements", "visual_approval_required")}
        )
        if (
            record["original_brief_digest"] != brief_digest
            or type(record["sequence"]) is not int
            or record["sequence"] != index
            or record["previous_digest"] != previous
            or record["origin"] != "EXPLICIT_LOCAL_OPERATOR_ATTESTATION"
            or record["identity_authenticated"] is not False
            or any(
                not isinstance(record[k], str) or not 1 <= len(record[k].strip()) <= 4096
                for k in ("operator", "reason")
            )
            or record["operator"] in {*ROLES, "producer", "inspector"}
            or record["record_digest"]
            != canonical_digest({k: v for k, v in record.items() if k != "record_digest"})
        ):
            raise InputError("Amendment history was reordered or substituted")
        previous = record["record_digest"]
    if chain["chain_digest"] != previous:
        raise InputError("Amendment chain digest mismatch")
    return chain


def append_amendment(
    policy: WorkspacePolicy,
    task: dict[str, Any],
    amendment: dict[str, Any],
    *,
    operator: str,
    reason: str,
) -> dict[str, Any]:
    validate_task(task)
    _validate_amendment(amendment)
    if any(
        not isinstance(v, str) or not 1 <= len(v.strip()) <= 4096 for v in (operator, reason)
    ) or operator in {*ROLES, "producer", "inspector"}:
        raise InputError("Amendments require an explicit local operator, not a worker role")
    digest = canonical_digest(task["brief"])
    with FileLock(policy, ".polyforge/locks/amendments.lock"):
        chain = read_amendments(policy, digest)
        if len(chain["records"]) >= 100:
            raise InputError("Amendment history limit reached")
        record = {
            **amendment,
            "original_brief_digest": digest,
            "sequence": len(chain["records"]) + 1,
            "previous_digest": chain["chain_digest"],
            "operator": operator,
            "reason": reason,
            "origin": "EXPLICIT_LOCAL_OPERATOR_ATTESTATION",
            "identity_authenticated": False,
        }
        record["record_digest"] = canonical_digest(record)
        chain = {
            **chain,
            "original_brief": task["brief"],
            "records": [*chain["records"], record],
            "chain_digest": record["record_digest"],
        }
        atomic_json(policy, ".polyforge/amendments/" + digest + ".json", chain)
    return read_amendments(policy, digest)
