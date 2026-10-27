"""Integrity-checked artifact reuse, distinct from unchanged planning inputs."""

from __future__ import annotations

import hashlib
from typing import Any

from polyforge.contracts.validation import InputError
from polyforge.security.paths import WorkspacePolicy


def cache_hit(task: dict[str, Any], entry: Any, policy: WorkspacePolicy) -> bool:
    """Fail closed on stale/corrupt metadata, missing outputs, or unvalidated bytes."""
    if (
        not isinstance(entry, dict)
        or entry.get("status") != "PASS"
        or entry.get("input_digest") != task["input_digest"]
        or not isinstance(entry.get("outputs"), list)
        or not entry["outputs"]
    ):
        return False
    try:
        for artifact in entry["outputs"]:
            if (
                not isinstance(artifact, dict)
                or artifact.get("validated") is not True
                or not isinstance(artifact.get("relative_path"), str)
                or type(artifact.get("bytes")) is not int
                or artifact["bytes"] <= 0
                or not isinstance(artifact.get("sha256"), str)
            ):
                return False
            relative = artifact["relative_path"]
            if relative.startswith(("/", "\\")) or ":" in relative:
                return False
            path = policy.path(relative)
            if not path.is_file() or path.stat().st_size != artifact["bytes"]:
                return False
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(65536):
                    digest.update(chunk)
            if digest.hexdigest() != artifact["sha256"]:
                return False
    except (InputError, OSError):
        return False
    return True
