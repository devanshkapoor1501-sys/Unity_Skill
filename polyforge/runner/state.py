"""Atomic state and append-only recovery events under an authorized workspace."""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest
from polyforge.runner.locks import FileLock
from polyforge.security.paths import WorkspacePolicy
from polyforge.security.policy import redact


def atomic_json(policy: WorkspacePolicy, relative: str | Path, value: Any) -> Path:
    """Validate before writing; fsync a sibling temporary file before replacement."""
    canonical_digest(value)
    payload = (json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()
    path = policy.path(relative)
    parent = policy.mkdir(path.parent)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=parent, prefix=".polyforge-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in range(3):
            policy.path(path)
            try:
                os.replace(temporary, path)
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.02 * (attempt + 1))
    except OSError as exc:
        raise InputError(
            f"Atomic state write failed: {exc}",
            kind=ErrorKind.PRODUCER_FAILURE,
            code="PF-STATE-WRITE",
        ) from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return path


class RunJournal:
    """The append-only journal is authoritative; state.json is an atomic cache."""

    def __init__(self, policy: WorkspacePolicy, run_id: str) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", run_id):
            raise InputError("Invalid run_id")
        self.policy, self.run_id = policy, run_id
        self.relative = f"runs/{run_id}"
        self.lock = f".polyforge/locks/run-{run_id}.lock"

    @classmethod
    def create(cls, policy: WorkspacePolicy, run_id: str, *, retry_limit: int = 2) -> RunJournal:
        journal = cls(policy, run_id)
        if type(retry_limit) is not int or not 0 <= retry_limit <= 2:
            raise InputError("retry_limit must be 0..2")
        if policy.path(f"{journal.relative}/events.jsonl").exists():
            raise InputError("Run already exists")
        with FileLock(policy, journal.lock):
            if policy.path(f"{journal.relative}/events.jsonl").exists():
                raise InputError("Run already exists")
            snapshot = {
                "schema_version": "1.0.0",
                "run_id": run_id,
                "sequence": 0,
                "retry_limit": retry_limit,
                "game_status": "PARTIAL",
                "stages": {
                    f"S{i}": {"status": "pending", "attempt": 0, "evidence": [], "note": ""}
                    for i in range(6)
                },
            }
            journal._save(snapshot, "created")
        return journal

    def read(self) -> dict[str, Any]:
        """Replay complete events without mutating the source or launching a worker."""
        events = self.policy.path(f"{self.relative}/events.jsonl")
        try:
            with events.open("rb") as stream:
                content = stream.read(16_777_217)
        except OSError as exc:
            raise InputError(f"Cannot read run journal: {exc}") from exc
        if len(content) > 16_777_216:
            raise InputError("Run journal exceeds the recovery limit")
        snapshot: dict[str, Any] | None = None
        for index, line in enumerate(content.splitlines(keepends=True)):
            if not line.endswith(b"\n"):
                break  # A killed append leaves an incomplete tail, never a completed stage.
            try:
                event = json.loads(line)
                candidate = event["state"]
                if (
                    not isinstance(candidate, dict)
                    or candidate.get("schema_version") != "1.0.0"
                    or candidate["run_id"] != self.run_id
                    or type(candidate["sequence"]) is not int
                    or candidate["sequence"] != index + 1
                ):
                    raise ValueError("Journal identity/sequence mismatch")
                if not isinstance(candidate["stages"], dict) or set(candidate["stages"]) != {
                    f"S{i}" for i in range(6)
                }:
                    raise ValueError("Invalid journal stage set")
                if (
                    type(candidate["retry_limit"]) is not int
                    or not 0 <= candidate["retry_limit"] <= 2
                ):
                    raise ValueError("Invalid retry limit")
                for stage in candidate["stages"].values():
                    if (
                        stage["status"]
                        not in {"pending", "running", "passed", "failed", "skipped", "needs_review"}
                        or type(stage["attempt"]) is not int
                        or not 0 <= stage["attempt"] <= candidate["retry_limit"] + 1
                        or not isinstance(stage["evidence"], list)
                        or any(not isinstance(path, str) for path in stage["evidence"])
                        or not isinstance(stage["note"], str)
                    ):
                        raise ValueError("Invalid stage state")
                snapshot = candidate
            except (ValueError, TypeError, KeyError, RecursionError) as exc:
                raise InputError(
                    f"Corrupt run journal: {exc}",
                    kind=ErrorKind.CONTRACT_FAILURE,
                    code="PF-STATE-CORRUPT",
                ) from exc
        if snapshot is None:
            raise InputError("Run has no complete durable events")
        return snapshot

    def _save(self, snapshot: dict[str, Any], event_type: str) -> None:
        snapshot["sequence"] += 1
        snapshot["updated_utc"] = datetime.now(UTC).isoformat()
        event = {"event": event_type, "state": snapshot}
        payload = (json.dumps(event, allow_nan=False) + "\n").encode()
        self.policy.mkdir(self.relative)
        path = self.policy.path(f"{self.relative}/events.jsonl")
        with path.open("a+b") as stream:
            # Remove only an incomplete owned tail before appending a new full event.
            stream.seek(0)
            content = stream.read()
            if content and not content.endswith(b"\n"):
                stream.truncate(content.rfind(b"\n") + 1)
            stream.seek(0, os.SEEK_END)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_json(self.policy, f"{self.relative}/state.json", snapshot)

    def transition(
        self, stage: str, status: str, *, evidence: list[str] | None = None, note: str = ""
    ) -> dict[str, Any]:
        with FileLock(self.policy, self.lock):
            snapshot = self.read()
            if stage not in snapshot["stages"]:
                raise InputError("Unknown stage")
            current = snapshot["stages"][stage]
            edges = {
                "pending": {"running", "skipped", "needs_review"},
                "running": {"passed", "failed", "needs_review"},
                "failed": {"running"},
                "needs_review": {"running"},
            }
            if status not in edges.get(current["status"], set()):
                raise InputError("Invalid stage transition")
            if status == "running":
                if current["attempt"] >= snapshot["retry_limit"] + 1:
                    raise InputError(
                        "Stage retry budget exhausted",
                        kind=ErrorKind.RETRY_EXHAUSTED,
                        code="PF-RUN-RETRY-EXHAUSTED",
                    )
                current["attempt"] += 1
            evidence = evidence or []
            if status == "passed" and (
                not evidence
                or any(
                    not self.policy.path(path).is_file()
                    or self.policy.path(path).stat().st_size == 0
                    for path in evidence
                )
            ):
                raise InputError("A passed stage needs actual nonempty evidence")
            current.update(status=status, evidence=evidence, note=redact(note))
            self._save(snapshot, f"{stage}:{status}")
            return snapshot

    def recover(self) -> dict[str, Any]:
        """Reconcile interrupted state without pretending any producer was retried."""
        with FileLock(self.policy, self.lock):
            snapshot = self.read()
            for stage in snapshot["stages"].values():
                if stage["status"] == "running":
                    stage.update(
                        status="failed", note="interrupted worker; explicit retry required"
                    )
            self._save(snapshot, "recovered")
            return snapshot
