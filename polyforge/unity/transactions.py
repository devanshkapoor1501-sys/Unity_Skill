"""Crash-resumable managed snapshots; native proof is required after restoring bytes."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from datetime import UTC, datetime
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy

SCOPES = (
    "game_manifest.json",
    "recipes",
    ".polyforge/unity-request.json",
    ".polyforge/owned-package.json",
    ".polyforge/game-latest.json",
    ".polyforge/platformer-latest.json",
    ".polyforge/unity-latest.json",
    ".polyforge/native-inputs",
    "UnityProject/Assets/PolyForgeGenerated",
    "UnityProject/ProjectSettings",
    "UnityProject/Packages/manifest.json",
    "UnityProject/Packages/packages-lock.json",
    "UnityProject/Packages/com.polyforge.engine",
)
PROOF_FIELDS = ("prestate", "recovery", "after_state")


def inventory(policy: WorkspacePolicy, dependencies: list[str] | None = None) -> dict[str, str]:
    result = {}
    for scope in (*SCOPES, *(dependencies or [])):
        path = policy.path(scope)
        for child in [path] if path.is_file() else sorted(path.rglob("*")):
            child = policy.path(child)
            if child.is_file():
                if child.stat().st_nlink > 1:
                    raise InputError("Hardlinked files cannot enter a managed transaction")
                result[child.relative_to(policy.root).as_posix()] = hashlib.sha256(
                    child.read_bytes()
                ).hexdigest()
    return result


def _dependency_registry(policy: WorkspacePolicy, name: str) -> str:
    relative = policy.path(name).relative_to(policy.root).as_posix()
    parts = relative.split("/")
    if (
        len(parts) < 4
        or parts[0] != "runs"
        or parts[2] != "asset"
        or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", parts[1])
        or not relative.endswith((".blend", ".fbx", ".json", ".png"))
    ):
        raise InputError("Transaction dependency is not a registered source artifact")
    return "/".join(parts[:2]) + "/artifacts.json"


def _registered_dependencies(policy: WorkspacePolicy, names: list[str]) -> list[str]:
    if (
        not isinstance(names, list)
        or len(names) > 256
        or any(not isinstance(n, str) for n in names)
        or len(set(names)) != len(names)
    ):
        raise InputError("Invalid bounded transaction dependency closure")
    result: set[str] = set()
    for name in names:
        registry_path = _dependency_registry(policy, name)
        relative = policy.path(name).relative_to(policy.root).as_posix()
        records = load_json(policy.path(registry_path))["artifacts"]
        matches = [a for a in records if policy.path(a["relative_path"]) == policy.path(name)]
        if (
            len(matches) != 1
            or hashlib.sha256(policy.path(name).read_bytes()).hexdigest() != matches[0]["sha256"]
        ):
            raise InputError("Transaction source lacks matching artifact provenance")
        result.update((relative, registry_path))
    return sorted(result)


class ManagedTransaction:
    def __init__(self, policy: WorkspacePolicy, identifier: str) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", identifier):
            raise InputError("Invalid transaction ID")
        self.policy, self.identifier = policy, identifier
        self.relative = f"transactions/{identifier}"

    @classmethod
    def create(
        cls, policy: WorkspacePolicy, identifier: str, *, dependencies: list[str] | None = None
    ) -> ManagedTransaction:
        tx = cls(policy, identifier)
        if policy.path(tx.relative).exists():
            raise InputError("Transaction already exists")
        closure = _registered_dependencies(policy, dependencies or [])
        original = inventory(policy, closure)
        if len(json.dumps({"original": original, "dependencies": closure})) > 524288:
            raise InputError("Snapshot inventory exceeds journal metadata budget")
        if (
            len(original) > 8192
            or sum(policy.path(n).stat().st_size for n in original) > 1_073_741_824
        ):
            raise InputError("Managed snapshot exceeds file/byte budget")
        for name in original:
            target = policy.path(f"{tx.relative}/snapshot/{name}")
            policy.mkdir(target.parent)
            with policy.path(name).open("rb") as source, target.open("wb") as saved:
                shutil.copyfileobj(source, saved)
                saved.flush()
                os.fsync(saved.fileno())
            if hashlib.sha256(target.read_bytes()).hexdigest() != original[name]:
                raise InputError("Source changed during snapshot")
        tx.record(
            "PREPARED",
            original=original,
            dependencies=closure,
            snapshot_digest=canonical_digest(original),
            journal_version="2.0.0",
        )
        return tx

    def _validate_scope(self, journal: dict[str, Any]) -> None:
        original = journal["original"]
        dependencies = journal.get("dependencies", [])
        if (
            not isinstance(dependencies, list)
            or len(dependencies) > 512
            or any(not isinstance(n, str) for n in dependencies)
            or len(set(dependencies)) != len(dependencies)
        ):
            raise InputError("Invalid saved transaction dependency closure")
        outside = set()
        for name, expected in original.items():
            if (
                not isinstance(name, str)
                or not isinstance(expected, str)
                or not re.fullmatch(r"[a-f0-9]{64}", expected)
            ):
                raise InputError("Malformed snapshot scope/hash")
            if self.policy.path(name).relative_to(self.policy.root).as_posix() != name:
                raise InputError("Snapshot scope paths must be canonical workspace paths")
            if not any(name == scope or name.startswith(scope + "/") for scope in SCOPES):
                outside.add(name)
        if set(dependencies) != outside:
            raise InputError("Saved dependency closure differs from snapshot scope")
        scope = {"original": original, "dependencies": dependencies}
        if "scope_digest" in journal and journal["scope_digest"] != canonical_digest(scope):
            raise InputError("Saved dependency scope digest mismatch")
        registries: dict[str, Any] = {}
        for name in outside:
            registry = (
                name
                if re.fullmatch(r"runs/[A-Za-z0-9_-]{1,80}/artifacts.json", name)
                else _dependency_registry(self.policy, name)
            )
            if registry not in dependencies:
                raise InputError("Saved dependency lacks its registered provenance")
            if registry not in registries:
                saved = self.policy.path(f"{self.relative}/snapshot/{registry}")
                if hashlib.sha256(saved.read_bytes()).hexdigest() != original[registry]:
                    raise InputError("Saved source registry hash mismatch")
                entries = load_json(saved).get("artifacts")
                if not isinstance(entries, list):
                    raise InputError("Malformed saved source provenance")
                registries[registry] = entries
            if name == registry:
                if not any(
                    n.startswith(registry.removesuffix("artifacts.json") + "asset/")
                    for n in outside
                ):
                    raise InputError("Orphan source registry cannot expand transaction scope")
            else:
                matches = [
                    a
                    for a in registries[registry]
                    if isinstance(a, dict)
                    and isinstance(a.get("relative_path"), str)
                    and self.policy.path(a["relative_path"]) == self.policy.path(name)
                    and a.get("sha256") == original[name]
                ]
                if len(matches) != 1:
                    raise InputError("Saved dependency is not a unique registered source artifact")

    def read(self) -> dict[str, Any]:
        # Earlier Phase 9 development journals embedded proof inline; allow a bounded migration.
        journal: dict[str, Any] = load_json(
            self.policy.path(f"{self.relative}/journal.json"), max_bytes=33_554_432
        )
        if journal.get("transaction_id") != self.identifier or not isinstance(
            journal.get("original"), dict
        ):
            raise InputError("Transaction journal identity/inventory mismatch")
        if (
            "snapshot_digest" in journal
            and canonical_digest(journal["original"]) != journal["snapshot_digest"]
        ):
            raise InputError("Snapshot inventory digest mismatch")
        self._validate_scope(journal)
        for field in PROOF_FIELDS:
            value = journal.get(field)
            if not isinstance(value, dict) or "evidence_path" not in value:
                continue
            if (
                set(value) != {"evidence_path", "sha256"}
                or not isinstance(value["evidence_path"], str)
                or not re.fullmatch(
                    re.escape(self.relative) + "/evidence/" + field + r"-[a-f0-9]{64}\.json",
                    value["evidence_path"],
                )
            ):
                raise InputError("Native proof reference is outside this transaction")
            proof = self.policy.path(value["evidence_path"])
            if hashlib.sha256(proof.read_bytes()).hexdigest() != value["sha256"]:
                raise InputError("Native proof hash mismatch")
            journal[field] = load_json(proof, max_bytes=33_554_432)
        return journal

    def record(self, status: str, **data: Any) -> None:
        path = self.policy.path(f"{self.relative}/journal.json")
        journal = (
            self.read()
            if path.is_file()
            else {"transaction_id": self.identifier, "events": [], "original": {}}
        )
        if path.is_file() and any(
            k in data
            for k in (
                "original",
                "snapshot_digest",
                "scope_digest",
                "dependencies",
                "transaction_id",
            )
        ):
            raise InputError("Snapshot identity and scope cannot change after preparation")
        journal.update(data)
        aliases = {
            "SNAPSHOT": "PREPARED",
            "APPLY": "APPLIED",
            "RESTORING": "ROLLING_BACK",
            "RESTORED_BYTES": "ROLLING_BACK",
        }
        normalized = aliases.get(status, status)
        if normalized in {
            "PREPARED",
            "APPLIED",
            "VERIFYING",
            "COMMITTED",
            "ROLLING_BACK",
            "ROLLED_BACK",
            "ROLLBACK_FAILED",
        }:
            journal["status"] = normalized
        journal["events"].append({"status": status, "utc": datetime.now(UTC).isoformat()})
        stored = dict(journal)
        for field in PROOF_FIELDS:
            if field not in journal:
                continue
            value = journal[field]
            relative = f"{self.relative}/evidence/{field}-{canonical_digest(value)}.json"
            proof = self.policy.path(relative)
            if proof.is_file():
                if load_json(proof, max_bytes=33_554_432) != value:
                    raise InputError("Immutable native proof was changed")
            else:
                if len(json.dumps(value, indent=2, ensure_ascii=True).encode()) > 33_554_431:
                    raise InputError("Native proof exceeds evidence byte budget")
                atomic_json(self.policy, proof, value)
            stored[field] = {
                "evidence_path": relative,
                "sha256": hashlib.sha256(proof.read_bytes()).hexdigest(),
            }
        stored["scope_digest"] = canonical_digest(
            {"original": journal["original"], "dependencies": journal.get("dependencies", [])}
        )
        stored["journal_version"] = "2.2.0"
        atomic_json(self.policy, path, stored)

    def restore(self) -> None:
        journal = self.read()
        original = journal["original"]
        # Validate every saved byte and path before mutating current files.
        for name, expected in original.items():
            if (
                not isinstance(name, str)
                or not isinstance(expected, str)
                or not re.fullmatch(r"[a-f0-9]{64}", expected)
            ):
                raise InputError("Malformed snapshot path/hash")
            if not any(name == scope or name.startswith(scope + "/") for scope in SCOPES):
                if name not in journal.get("dependencies", []):
                    raise InputError("Snapshot path is outside managed scope")
                registry = (
                    name
                    if re.fullmatch(r"runs/[A-Za-z0-9_-]{1,80}/artifacts.json", name)
                    else _dependency_registry(self.policy, name)
                )
                if registry != name:
                    records = load_json(self.policy.path(f"{self.relative}/snapshot/{registry}"))[
                        "artifacts"
                    ]
                    if not any(
                        self.policy.path(a["relative_path"]) == self.policy.path(name)
                        and a["sha256"] == expected
                        for a in records
                    ):
                        raise InputError("Snapshot source is not in its saved artifact registry")
            source = self.policy.path(f"{self.relative}/snapshot/{name}")
            if hashlib.sha256(source.read_bytes()).hexdigest() != expected:
                raise InputError("Snapshot hash mismatch", kind=ErrorKind.CONTRACT_FAILURE)
        current = inventory(self.policy, journal.get("dependencies", []))
        self.record("ROLLING_BACK")
        for name in current.keys() - original.keys():
            self.policy.path(name).unlink()
        for name in original:
            path = self.policy.path(name)
            self.policy.mkdir(path.parent)
            shutil.copyfile(self.policy.path(f"{self.relative}/snapshot/{name}"), path)
        self.record("ROLLING_BACK", bytes_restored=True)

    def verify_restored(self) -> bool:
        journal = self.read()
        return bool(inventory(self.policy, journal.get("dependencies", [])) == journal["original"])
