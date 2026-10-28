"""Atomic job commits and fenced, process-aware asset ownership leases."""

import hashlib
import os
import re
import socket
import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.locks import FileLock
from polyforge.runner.ownership import process_identity
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


class JobLedger:
    def __init__(self, workspace: Path, task_id: str) -> None:
        self.policy = WorkspacePolicy(workspace)
        self.task_id = self.identifier(task_id)
        self.relative = "workforce/" + task_id

    @staticmethod
    def identifier(value: str) -> str:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", value):
            raise InputError("Invalid job/task identifier")
        return value

    def _state(self, job: str) -> str:
        return self.relative + "/jobs/" + self.identifier(job) + ".json"

    def completed(self, job: str) -> dict[str, Any] | None:
        path = self.policy.path(self._state(job))
        if not path.is_file():
            return None
        state = load_json(path)
        if state["state"] != "COMMITTED":
            return None
        result: dict[str, Any] = state["result"]
        if canonical_digest(result) != state["result_digest"]:
            raise InputError("Committed result digest mismatch", kind=ErrorKind.CONTRACT_FAILURE)
        return result

    def claim(self, job: str, asset: str, *, ttl: int = 3600) -> dict[str, Any] | None:
        self.identifier(job)
        self.identifier(asset)
        if type(ttl) is not int or not 1 <= ttl <= 3600:
            raise InputError("Lease TTL must be 1..3600 seconds")
        relative = ".polyforge/leases/" + hashlib.sha256(asset.encode()).hexdigest() + ".json"
        with FileLock(self.policy, ".polyforge/locks/workforce-state.lock", wait_seconds=5):
            if self.completed(job) is not None:
                return None
            own = self.policy.path(self._state(job))
            if own.is_file() and load_json(own).get("state") == "CANCELLED":
                raise InputError("Job is cancelled", kind=ErrorKind.INTERRUPTED)
            path = self.policy.path(relative)
            if path.is_file():
                old = load_json(path)
                old_state_path = self.policy.path(
                    "workforce/"
                    + self.identifier(old["task_id"])
                    + "/jobs/"
                    + self.identifier(old["job_id"])
                    + ".json"
                )
                if old_state_path.is_file():
                    old_state = load_json(old_state_path)
                    if (
                        old_state.get("state") == "COMMITTED"
                        and old_state["lease"]["token"] == old["token"]
                    ):
                        if canonical_digest(old_state["result"]) != old_state["result_digest"]:
                            raise InputError(
                                "Committed lease owner has corrupt result",
                                kind=ErrorKind.CONTRACT_FAILURE,
                            )
                        old["released"] = True
                if not old["released"] and (
                    old["until"] > time.time()
                    or old["host"] != socket.gethostname()
                    or process_identity(old["pid"]) == old["identity"]
                ):
                    raise InputError(
                        "Asset owner is active or lease has not expired",
                        kind=ErrorKind.POLICY_DENIED,
                    )
            lease = {
                "token": uuid4().hex,
                "job_id": job,
                "task_id": self.task_id,
                "asset_id": asset,
                "pid": os.getpid(),
                "identity": process_identity(os.getpid()),
                "host": socket.gethostname(),
                "until": time.time() + ttl,
                "released": False,
                "path": relative,
            }
            atomic_json(self.policy, relative, lease)
            atomic_json(self.policy, self._state(job), {"state": "RUNNING", "lease": lease})
            return lease

    def heartbeat(self, job: str, lease: dict[str, Any], *, ttl: int = 3600) -> None:
        if type(ttl) is not int or not 1 <= ttl <= 3600:
            raise InputError("Invalid lease TTL")
        with FileLock(self.policy, ".polyforge/locks/workforce-state.lock", wait_seconds=5):
            current = self._check(job, lease)
            current["until"] = time.time() + ttl
            atomic_json(self.policy, current["path"], current)

    def _check(self, job: str, lease: dict[str, Any]) -> dict[str, Any]:
        state = load_json(self.policy.path(self._state(job)))
        current: dict[str, Any] = load_json(self.policy.path(state["lease"]["path"]))
        if (
            state["state"] != "RUNNING"
            or current["released"]
            or current["token"] != lease["token"]
            or current["task_id"] != self.task_id
            or current["job_id"] != job
            or current["until"] < time.time()
            or current["pid"] != os.getpid()
            or current["identity"] != process_identity(os.getpid())
        ):
            raise InputError(
                "Stale/cancelled job ownership; commit denied", kind=ErrorKind.POLICY_DENIED
            )
        return current

    def commit(self, job: str, lease: dict[str, Any] | None, result: dict[str, Any]) -> None:
        canonical_digest(result)
        if lease is None:
            raise InputError("No ownership lease")
        with FileLock(self.policy, ".polyforge/locks/workforce-state.lock", wait_seconds=5):
            current = self._check(job, lease)
            atomic_json(
                self.policy,
                self._state(job),
                {
                    "state": "COMMITTED",
                    "lease": current,
                    "result": result,
                    "result_digest": canonical_digest(result),
                },
            )
            current["released"] = True
            atomic_json(self.policy, current["path"], current)

    def cancel(self, job: str) -> None:
        with FileLock(self.policy, ".polyforge/locks/workforce-state.lock", wait_seconds=5):
            state = load_json(self.policy.path(self._state(job)))
            if state["state"] == "COMMITTED":
                raise InputError("Committed job cannot be cancelled")
            state["state"] = "CANCELLED"
            atomic_json(self.policy, self._state(job), state)
            lease = load_json(self.policy.path(state["lease"]["path"]))
            if lease["token"] == state["lease"]["token"]:
                lease["released"] = True
                atomic_json(self.policy, lease["path"], lease)
