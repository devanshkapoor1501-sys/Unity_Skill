"""Complete local artifact ownership records from observed file bytes."""

from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime
from typing import Any

from polyforge.contracts.validation import InputError, load_json
from polyforge.security.paths import WorkspacePolicy


def complete_records(
    policy: WorkspacePolicy,
    run_id: str,
    stage: str,
    records: list[dict[str, Any]],
    *,
    input_digest: str | None = None,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Check recorded hashes before adding metadata; never publish or grant permission."""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", run_id) or stage not in {
        "S0",
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
    }:
        raise InputError("Artifact records require a bounded run identity and canonical stage")
    if not isinstance(records, list) or len(records) > 16384:
        raise InputError("Artifact registry exceeds its bounded record count")
    if project_id is None:
        manifest = policy.path("game_manifest.json")
        if manifest.is_file():
            value = load_json(manifest)
            project = value.get("project", {}) if isinstance(value, dict) else {}
            project_id = project.get("id") if isinstance(project, dict) else None
        if not isinstance(project_id, str) or not project_id:
            project_id = "workspace_" + hashlib.sha256(str(policy.root).encode()).hexdigest()[:16]
    output = []
    seen = set()
    timestamp = datetime.now(UTC).isoformat()
    for row in records:
        if not isinstance(row, dict) or not isinstance(row.get("relative_path"), str):
            raise InputError("Artifact registry needs typed workspace-relative paths")
        path = policy.path(row["relative_path"])
        if not path.is_file():
            raise InputError("Artifact registration requires an existing regular file")
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while block := stream.read(1_048_576):
                digest.update(block)
        sha = digest.hexdigest()
        size = path.stat().st_size
        if row.get("sha256", sha) != sha or row.get("bytes", size) != size:
            raise InputError("Artifact bytes differ from their recorded hash or size")
        relative = path.relative_to(policy.root).as_posix()
        identifier = row.get("artifact_id", run_id + ":" + relative)
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise InputError("Artifact identities must be nonempty and unique within a registry")
        seen.add(identifier)
        upstream = row.get("input_digest", row.get("upstream_input_digest", input_digest))
        output.append(
            {
                **row,
                "artifact_id": identifier,
                "project_id": project_id,
                "run_id": run_id,
                "stage": stage,
                "kind": row.get("kind", path.suffix.lstrip(".") or "file"),
                "relative_path": relative,
                "resolved_location": str(path),
                "sha256": sha,
                "bytes": size,
                "timestamp": timestamp,
                "upstream_input_hashes": [upstream] if upstream else [],
                "validation_status": row.get("validation_status", "HASH_VERIFIED"),
                "validator": row.get("validator", "polyforge.artifact.sha256.v1"),
            }
        )
    return output
