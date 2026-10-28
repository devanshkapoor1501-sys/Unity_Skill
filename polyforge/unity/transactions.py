"""Small managed-project snapshots; full cross-application recovery is Phase 9."""

from __future__ import annotations

import hashlib
import re
import shutil
from datetime import UTC, datetime
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy

SCOPES = (
    "game_manifest.json",
    "recipes",
    ".polyforge/unity-request.json",
    ".polyforge/owned-package.json",
    "UnityProject/Assets/PolyForgeGenerated",
    "UnityProject/ProjectSettings",
    "UnityProject/Packages/manifest.json",
    "UnityProject/Packages/packages-lock.json",
    "UnityProject/Packages/com.polyforge.engine",
)


def inventory(policy: WorkspacePolicy) -> dict[str, str]:
    result = {}
    for scope in SCOPES:
        path = policy.path(scope)
        for child in [path] if path.is_file() else sorted(path.rglob("*")):
            child = policy.path(child)
            if child.is_file():
                result[child.relative_to(policy.root).as_posix()] = hashlib.sha256(
                    child.read_bytes()
                ).hexdigest()
    return result


class ManagedTransaction:
    def __init__(self, policy: WorkspacePolicy, identifier: str) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", identifier):
            raise InputError("Invalid transaction ID")
        self.policy, self.identifier = policy, identifier
        self.relative = f"transactions/{identifier}"

    @classmethod
    def create(cls, policy: WorkspacePolicy, identifier: str) -> ManagedTransaction:
        tx = cls(policy, identifier)
        if policy.path(tx.relative).exists():
            raise InputError("Transaction already exists")
        original = inventory(policy)
        for name in original:
            target = policy.path(f"{tx.relative}/snapshot/{name}")
            policy.mkdir(target.parent)
            shutil.copyfile(policy.path(name), target)
        tx.record("SNAPSHOT", original=original)
        return tx

    def record(self, status: str, **data: Any) -> None:
        path = self.policy.path(f"{self.relative}/journal.json")
        journal = (
            load_json(path)
            if path.is_file()
            else {"transaction_id": self.identifier, "events": [], "original": {}}
        )
        journal.update(data)
        journal["status"] = status
        journal["events"].append({"status": status, "utc": datetime.now(UTC).isoformat()})
        atomic_json(self.policy, path, journal)

    def restore(self) -> None:
        journal = load_json(self.policy.path(f"{self.relative}/journal.json"))
        original = journal["original"]
        # Validate every saved byte and path before mutating current files.
        for name, expected in original.items():
            if not any(name == scope or name.startswith(scope + "/") for scope in SCOPES):
                raise InputError("Snapshot path is outside managed scope")
            source = self.policy.path(f"{self.relative}/snapshot/{name}")
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise InputError("Snapshot hash mismatch", kind=ErrorKind.CONTRACT_FAILURE)
        self.record("RESTORING")
        for name in inventory(self.policy).keys() - original.keys():
            self.policy.path(name).unlink()
        for name in original:
            path = self.policy.path(name)
            self.policy.mkdir(path.parent)
            shutil.copyfile(self.policy.path(f"{self.relative}/snapshot/{name}"), path)
        self.record("RESTORED_BYTES")

    def verify_restored(self) -> bool:
        journal = load_json(self.policy.path(f"{self.relative}/journal.json"))
        return bool(inventory(self.policy) == journal["original"])
