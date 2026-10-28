"""Upgrade only engine-owned UPM code whose old bytes have immutable provenance."""

from __future__ import annotations

import hashlib
import zipfile
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.transactions import ManagedTransaction


def sync_package(policy: WorkspacePolicy, desired: dict[str, bytes] | None = None) -> str | None:
    package = policy.path("UnityProject/Packages/com.polyforge.engine")
    if desired is None:
        resources = Path(str(files("unity_package")))
        desired = {
            p.relative_to(resources).as_posix(): p.read_bytes()
            for p in resources.rglob("*")
            if p.is_file() and (p.suffix in {".cs", ".asmdef"} or p.name == "package.json")
        }
    changed = {
        name: data
        for name, data in desired.items()
        if not policy.path(package / name).is_file()
        or policy.path(package / name).read_bytes() != data
    }
    if not changed:
        return None
    old: dict[str, bytes] = {}
    latest = policy.path(".polyforge/unity-latest.json")
    if latest.is_file():
        run = load_json(latest)["run_id"]
        archive = policy.path(f"runs/{run}/native-output.zip")
        registry = load_json(policy.path(f"runs/{run}/artifacts.json"))["artifacts"]
        entry = next((a for a in registry if policy.path(a["relative_path"]) == archive), None)
        if entry is None or hashlib.sha256(archive.read_bytes()).hexdigest() != entry["sha256"]:
            raise InputError(
                "Package upgrade baseline archive hash mismatch", kind=ErrorKind.CONTRACT_FAILURE
            )
        with zipfile.ZipFile(archive) as source:
            for name in desired:
                key = "Packages/com.polyforge.engine/" + name
                if key in source.namelist():
                    if source.getinfo(key).file_size > 1_048_576:
                        raise InputError("Package source exceeds 1MiB")
                    old[name] = source.read(key)
    provenance = policy.path(".polyforge/owned-package.json")
    if provenance.is_file():
        recorded = load_json(provenance)
        for name, item in recorded["files"].items():
            source_path = policy.path(item["source"])
            content = source_path.read_bytes()
            if hashlib.sha256(content).hexdigest() != item["sha256"]:
                raise InputError(
                    "Owned package provenance changed", kind=ErrorKind.CONTRACT_FAILURE
                )
            old[name] = content
    for name in changed:
        current = policy.path(package / name)
        if current.is_file() and current.read_bytes() != old.get(name):
            raise InputError(
                "Managed package code was modified without a matching baseline: " + name,
                kind=ErrorKind.POLICY_DENIED,
            )
    transaction = ManagedTransaction.create(policy, "package-" + uuid4().hex[:16])
    transaction.record("APPLY", operation="owned UPM source upgrade", changed=list(changed))
    for name, data in changed.items():
        target = policy.path(package / name)
        policy.mkdir(target.parent)
        target.write_bytes(data)
    applied = {}
    for name, data in desired.items():
        saved = policy.path(transaction.relative + "/applied/" + name)
        policy.mkdir(saved.parent)
        saved.write_bytes(data)
        applied[name] = {
            "source": saved.relative_to(policy.root).as_posix(),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    # Existing native .meta GUIDs are retained. New scripts receive native GUIDs
    # on import; fresh projects receive the packaged metadata at bootstrap.
    transaction.record("COMMITTED", operation="owned UPM source upgrade")
    atomic_json(
        policy,
        ".polyforge/owned-package.json",
        {"transaction_id": transaction.identifier, "files": applied},
    )
    return transaction.identifier
