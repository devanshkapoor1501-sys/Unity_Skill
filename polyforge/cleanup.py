"""Conservative cleanup of completed workers' private temporary files.

This trusted-local maintenance is not a sandbox against hostile filesystem races.
Sources, evidence, registries, recovery data and directories are never deleted.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import ExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from polyforge.contracts.results import ErrorKind, Result
from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.locks import FileLock
from polyforge.runner.ownership import process_identity
from polyforge.runner.state import RunJournal
from polyforge.security.paths import WorkspacePolicy

SUFFIXES = frozenset({".tmp", ".temp", ".cache"})
MAX_ENTRIES = 10_000
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_DEPTH = 32
TERMINAL_REASONS = frozenset(
    {"exit", "timeout", "cancelled", "memory_limit", "output_limit", "observation_failure"}
)


@dataclass(frozen=True)
class _Candidate:
    relative_path: str
    bytes: int
    sha256: str
    identity: tuple[int, int, int, int, int]
    run_id: str
    process: str

    def public(self) -> dict[str, Any]:
        return {"relative_path": self.relative_path, "bytes": self.bytes, "sha256": self.sha256}


def _identity(info: os.stat_result) -> tuple[int, int, int, int, int]:
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _regular(policy: WorkspacePolicy, path: Path) -> os.stat_result:
    info = policy.path(path).lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise InputError("Cleanup rejects special files and hardlinks")
    return info


def _json(policy: WorkspacePolicy, path: Path) -> Any:
    before = _regular(policy, path)
    value = load_json(path, max_bytes=MAX_FILE_BYTES)
    if _identity(before) != _identity(_regular(policy, path)):
        raise InputError("Cleanup metadata changed while reading")
    return value


def _journal_ready(policy: WorkspacePolicy, run_id: str) -> tuple[bool, dict[str, Any]]:
    journal = RunJournal(policy, run_id)
    events = policy.path(f"runs/{run_id}/events.jsonl")
    if not events.exists():
        return False, {}
    before = _regular(policy, events)
    if before.st_size:
        with events.open("rb") as stream:
            stream.seek(-1, os.SEEK_END)
            if stream.read(1) != b"\n":
                return False, {}
    state = journal.read()
    if _identity(before) != _identity(_regular(policy, events)):
        raise InputError("Cleanup journal changed while reading")
    statuses = [stage["status"] for stage in state["stages"].values()]
    ready = "running" not in statuses and any(s in {"passed", "failed"} for s in statuses)
    return ready, state


def _process_ready(policy: WorkspacePolicy, process: Path) -> bool:
    record = _json(policy, policy.path(process / "process.json"))
    if (
        not isinstance(record, dict)
        or type(record.get("returncode")) is not int
        or not isinstance(record.get("reason"), str)
        or record["reason"] not in TERMINAL_REASONS
        or type(record.get("pid")) is not int
        or not 0 < record["pid"] < 2**31
        or not isinstance(record.get("ownership"), str)
        or record["ownership"] not in {"WINDOWS_JOB", "POSIX_PROCESS_GROUP"}
    ):
        raise InputError("Cleanup requires a valid completed native process record")
    try:
        return process_identity(record["pid"]) is None
    except OSError:
        return False  # Permission uncertainty never establishes that a process is dead.


def _strings(value: Any, references: set[str]) -> None:
    pending = [value]
    count = 0
    while pending:
        count += 1
        if count + len(pending) > MAX_ENTRIES * 10:
            raise InputError("Cleanup registry reference inventory exceeds its bound")
        item = pending.pop()
        if isinstance(item, str):
            normalized = os.path.normcase(item).replace("\\", "/").rstrip("/")
            while normalized.startswith("./"):
                normalized = normalized[2:]
            references.add(normalized)
            if ":" in normalized:
                references.add(normalized.split(":", 1)[1])
            if len(references) > MAX_ENTRIES * 10:
                raise InputError("Cleanup protected reference set exceeds its bound")
        elif isinstance(item, dict):
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def _protected(
    policy: WorkspacePolicy, path: Path, run: Path, process: Path, references: set[str]
) -> bool:
    spellings = {
        path.relative_to(policy.root).as_posix(),
        str(path),
        path.relative_to(run).as_posix(),
        path.relative_to(process).as_posix(),
        path.name,
    }
    for spelling in spellings:
        normalized = os.path.normcase(spelling).replace("\\", "/").rstrip("/")
        parts = normalized.split("/")
        if any("/".join(parts[:end]) in references for end in range(1, len(parts) + 1)):
            return True
    return False


def _candidate(policy: WorkspacePolicy, path: Path, run_id: str, process: Path) -> _Candidate:
    before = _regular(policy, path)
    if before.st_size > MAX_FILE_BYTES:
        raise InputError("Cleanup temporary file exceeds its byte bound")
    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        # Windows fstat reports a different ctime meaning than path lstat.
        if _identity(opened)[:4] != _identity(before)[:4] or opened.st_nlink != 1:
            raise InputError("Cleanup temporary file changed before reading")
        raw = stream.read(MAX_FILE_BYTES + 1)
    after = _regular(policy, path)
    if len(raw) > MAX_FILE_BYTES or _identity(before) != _identity(after):
        raise InputError("Cleanup temporary file changed while reading")
    return _Candidate(
        path.relative_to(policy.root).as_posix(),
        len(raw),
        hashlib.sha256(raw).hexdigest(),
        _identity(after),
        run_id,
        process.relative_to(policy.root).as_posix(),
    )


# These subtrees can contain editable projects, caches, authentication or recovery
# sources. They are never cleanup candidates, even inside a process-private tmp.
PROTECTED_TREES = frozenset(
    {
        "unityproject",
        "library",
        "assets",
        "packages",
        "projectsettings",
        ".polyforge",
        "transactions",
        "workforce",
        "snapshot",
        "snapshots",
        "unity-profile",
        "upm-cache",
    }
)
METADATA_PRUNED_TREES = frozenset({"unityproject", "library", "unity-profile", "upm-cache"})


@dataclass
class _Protection:
    files: dict[Path, tuple[int, int, int, int, int]]
    directories: dict[Path, tuple[int, int, int, int, int]]

    def check(self, policy: WorkspacePolicy) -> None:
        for path, expected in self.files.items():
            if _identity(_regular(policy, path)) != expected:
                raise InputError("Cleanup protection metadata changed before deletion")
        for path, expected in self.directories.items():
            if _identity(policy.path(path).stat()) != expected:
                raise InputError("Cleanup protection inventory changed before deletion")

    def after_unlink(self, policy: WorkspacePolicy, path: Path) -> None:
        # The cleaner's own unlink changes exactly its parent directory metadata.
        self.directories[path.parent] = _identity(policy.path(path.parent).stat())


def _json_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise InputError("Cleanup rejects duplicate metadata keys")
        value[key] = item
    return value


def _nonfinite(value: str) -> None:
    raise InputError("Cleanup rejects non-finite metadata")


def _metadata(policy: WorkspacePolicy, path: Path, references: set[str]) -> None:
    if path.suffix.lower() == ".json":
        _strings(_json(policy, path), references)
        return
    before = _regular(policy, path)
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    if len(raw) > MAX_FILE_BYTES:
        raise InputError("Cleanup metadata exceeds its file byte bound")
    try:
        for line in raw.splitlines(keepends=True):
            if line.endswith(b"\n"):
                _strings(
                    json.loads(
                        line.decode("utf-8"),
                        object_pairs_hook=_json_pairs,
                        parse_constant=_nonfinite,
                    ),
                    references,
                )
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise InputError(f"Cleanup cannot establish metadata references: {exc}") from exc
    if _identity(before) != _identity(_regular(policy, path)):
        raise InputError("Cleanup metadata changed while reading")


def _inventory(
    policy: WorkspacePolicy,
) -> tuple[list[_Candidate], list[dict[str, str]], _Protection]:
    candidates: list[_Candidate] = []
    skipped: list[dict[str, str]] = []
    protection = _Protection({}, {policy.root: _identity(policy.root.stat())})
    files: list[Path] = []
    pending: list[tuple[Path, int]] = []
    for name in ("runs", "workforce", "transactions", ".polyforge"):
        path = policy.path(name)
        if path.exists():
            if not path.is_dir():
                raise InputError("Cleanup metadata roots must be directories")
            pending.append((path, 0))
    count = 0
    while pending:
        directory, depth = pending.pop()
        if depth > MAX_DEPTH:
            raise InputError("Cleanup directory nesting exceeds its bound")
        before = policy.path(directory).stat()
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1
                if count > MAX_ENTRIES:
                    raise InputError("Cleanup inventory exceeds its entry bound")
                path = policy.path(entry.path)
                if path.is_dir():
                    if path.name.casefold() not in METADATA_PRUNED_TREES:
                        pending.append((path, depth + 1))
                else:
                    _regular(policy, path)
                    files.append(path)
        if _identity(before) != _identity(policy.path(directory).stat()):
            raise InputError("Cleanup directory changed during inventory")
        protection.directories[directory] = _identity(before)
    references: set[str] = set()
    metadata_bytes = 0
    for path in files:
        if path.suffix.lower() in {".json", ".jsonl"}:
            info = _regular(policy, path)
            metadata_bytes += info.st_size
            if metadata_bytes > MAX_TOTAL_BYTES:
                raise InputError("Cleanup metadata exceeds its aggregate byte bound")
            _metadata(policy, path, references)
            protection.files[path] = _identity(info)
    runs = policy.path("runs")
    run_paths = sorted(path for path in protection.directories if path.parent == runs)
    total = 0
    for run in run_paths:
        ready, _ = _journal_ready(policy, run.name)
        if not ready:
            skipped.append(
                {
                    "process": run.relative_to(policy.root).as_posix(),
                    "reason": "RUN_NOT_PROVEN_TERMINAL",
                }
            )
            continue
        run_files = [path for path in files if path.is_relative_to(run)]
        processes = [
            path.parent
            for path in run_files
            if path.name == "process.json" and policy.path(path.parent / "tmp").is_dir()
        ]
        temporary_roots = {policy.path(process / "tmp") for process in processes}
        if any(parent in temporary_roots for path in temporary_roots for parent in path.parents):
            raise InputError("Cleanup rejects overlapping private temporary scopes")
        for process in sorted(processes):
            if not _process_ready(policy, process):
                skipped.append(
                    {
                        "process": process.relative_to(policy.root).as_posix(),
                        "reason": "PROCESS_LIVE_OR_LIVENESS_UNCERTAIN",
                    }
                )
                continue
            temporary = policy.path(process / "tmp")
            for path in sorted(run_files):
                if not path.is_relative_to(temporary):
                    continue
                if any(
                    part.casefold() in PROTECTED_TREES
                    for part in path.relative_to(temporary).parts[:-1]
                ):
                    continue
                if path.suffix.lower() in SUFFIXES and not _protected(
                    policy, path, run, process, references
                ):
                    row = _candidate(policy, path, run.name, process)
                    total += row.bytes
                    if total > MAX_TOTAL_BYTES:
                        raise InputError("Cleanup candidates exceed their aggregate byte bound")
                    candidates.append(row)
    protection.check(policy)
    return sorted(candidates, key=lambda row: row.relative_path), skipped, protection


def _check_lock(policy: WorkspacePolicy, relative: str) -> None:
    path = policy.path(relative)
    if path.exists():
        _regular(policy, path)


def _data(
    candidates: list[_Candidate], skipped: list[dict[str, str]], preview: bool, deleted: list[str]
) -> dict[str, Any]:
    return {
        "scope": "COMPLETED_PRIVATE_PROCESS_TEMPORARIES_ONLY",
        "dry_run": preview,
        "candidates": [row.public() for row in candidates],
        "deleted": deleted,
        "skipped": skipped,
        "total_candidate_bytes": sum(row.bytes for row in candidates),
    }


def clean_workspace(root: Path, *, dry_run: bool = False, confirm: bool = False) -> Result:
    """Preview without writes; explicit confirmation unlinks checked files only."""
    if type(dry_run) is not bool or type(confirm) is not bool:
        raise InputError("Cleanup flags must be booleans")
    policy = WorkspacePolicy(root)
    deleted: list[str] = []
    candidates: list[_Candidate] = []
    skipped: list[dict[str, str]] = []
    try:
        marker = _json(policy, policy.path(".polyforge/workspace.json"))
        if (
            not isinstance(marker, dict)
            or marker.get("schema_version") != "1.0.0"
            or not isinstance(marker.get("workspace_id"), str)
            or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", marker["workspace_id"])
            or marker.get("security_scope") != "TRUSTED_LOCAL"
            or marker.get("trusted_local_approved") is not True
        ):
            raise InputError("Cleanup requires an initialized trusted-local PolyForge workspace")
        candidates, skipped, _ = _inventory(policy)
        preview = dry_run or not confirm
        if preview or not candidates:
            return Result(data=_data(candidates, skipped, preview, deleted))
        cleanup_lock = ".polyforge/locks/cleanup.lock"
        _check_lock(policy, cleanup_lock)
        for run_id in {row.run_id for row in candidates}:
            _check_lock(policy, RunJournal(policy, run_id).lock)
        with FileLock(policy, cleanup_lock), ExitStack() as locks:
            for run_id in sorted({row.run_id for row in candidates}):
                locks.enter_context(FileLock(policy, RunJournal(policy, run_id).lock))
            rechecked, _, protection = _inventory(policy)
            if rechecked != candidates:
                raise InputError("Cleanup inventory changed before deletion")
            for row in candidates:
                protection.check(policy)
                if (
                    not _journal_ready(policy, row.run_id)[0]
                    or not _process_ready(policy, policy.path(row.process))
                    or _candidate(
                        policy, policy.path(row.relative_path), row.run_id, policy.path(row.process)
                    )
                    != row
                ):
                    raise InputError("Cleanup candidate or process changed before deletion")
                path = policy.path(row.relative_path)
                path.unlink()
                deleted.append(row.relative_path)
                protection.after_unlink(policy, path)
        return Result(data=_data(candidates, skipped, False, deleted))
    except (InputError, OSError) as exc:
        if deleted:
            return Result(
                status="FAIL",
                exit_code=int(ErrorKind.PRODUCER_FAILURE),
                error_code="PF-CLEAN-PARTIAL",
                data=_data(candidates, skipped, False, deleted),
                diagnostics=[{"code": "PF-CLEAN-PARTIAL", "message": str(exc)}],
            )
        if isinstance(exc, InputError):
            raise
        raise InputError(f"Cleanup inventory or mutation failed: {exc}") from exc
