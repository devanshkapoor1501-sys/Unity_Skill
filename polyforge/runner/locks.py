"""OS-exclusive locks with PID/host/birth identity and conservative stale recovery."""

from __future__ import annotations

import json
import os
import socket
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import TracebackType
from typing import BinaryIO
from uuid import uuid4

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError
from polyforge.runner.ownership import process_identity
from polyforge.security.paths import WorkspacePolicy


@contextmanager
def unity_project_lock(
    policy: WorkspacePolicy,
    project: Path,
    *,
    cancel: threading.Event | None = None,
    recovery: bool = False,
) -> Iterator[FileLock]:
    """Use one physical lock per approved project, even under nested workspace roots."""
    project = policy.path(project)
    if project.exists() and not project.is_dir():
        raise InputError("Unity project path is not a directory")

    def check() -> None:
        if policy.path(project / "Temp/UnityLockfile").exists():
            raise InputError(
                "Unity Editor has a project lock; close the Editor first",
                kind=ErrorKind.POLICY_DENIED,
                code="PF-UNITY-PROJECT-LOCKED",
            )
        if policy.path(project / ".polyforge/repair-quarantine.json").exists() and not recovery:
            raise InputError(
                "Managed project is quarantined after unverified recovery",
                kind=ErrorKind.POLICY_DENIED,
                code="PF-ROLLBACK-QUARANTINE",
            )

    check()
    with FileLock(
        policy, str(project.parent / ("." + project.name + ".polyforge.lock")), cancel=cancel
    ) as lock:
        check()
        yield lock


class FileLock:
    """Keep a persistent lock file; release OS locks on exit/crash, never unlink races."""

    def __init__(
        self,
        policy: WorkspacePolicy,
        relative: str,
        *,
        wait_seconds: float = 0,
        cancel: threading.Event | None = None,
    ) -> None:
        if type(wait_seconds) not in {int, float} or not 0 <= wait_seconds <= 3600:
            raise InputError("Invalid bounded lock wait")
        self.policy, self.relative = policy, relative
        self.wait_seconds, self.cancel = wait_seconds, cancel
        self.stream: BinaryIO | None = None
        self.recovered_stale = False
        self.record: dict[str, object] = {}

    def __enter__(self) -> FileLock:
        deadline = time.monotonic() + self.wait_seconds
        while True:
            if self.cancel is not None and self.cancel.is_set():
                raise InputError(
                    "Cancelled while waiting for owned worker", kind=ErrorKind.INTERRUPTED
                )
            try:
                return self._enter_once()
            except InputError as error:
                # Only OS contention is queued. Malformed/still-live stale ownership fails closed.
                if not isinstance(error.__cause__, OSError) or time.monotonic() >= deadline:
                    raise
                time.sleep(min(0.02, max(0, deadline - time.monotonic())))

    def _enter_once(self) -> FileLock:
        path = self.policy.path(self.relative)
        self.policy.mkdir(path.parent)
        stream = path.open("a+b")
        locked = False
        try:
            stream.seek(0)
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
            content = stream.read(65537)
            if content:
                old = json.loads(content)
                if not isinstance(old, dict) or not isinstance(old.get("released"), bool):
                    raise ValueError("Malformed lock owner metadata")
                if not old["released"]:
                    if old.get("host") != socket.gethostname():
                        raise ValueError("Cannot reclaim a foreign-host lock")
                    if not isinstance(old.get("identity"), str) or not old["identity"]:
                        raise ValueError("Cannot verify lock owner birth identity")
                    identity = process_identity(old["pid"])
                    if identity is not None and identity == old.get("identity"):
                        raise ValueError("Lock owner is still alive")
                    self.recovered_stale = True
            self.record = {
                "pid": os.getpid(),
                "host": socket.gethostname(),
                "identity": process_identity(os.getpid()),
                "token": uuid4().hex,
                "released": False,
            }
            self.stream = stream
            self._write()
            return self
        except (OSError, ValueError, KeyError, TypeError) as exc:
            if locked:
                self._unlock(stream)
            stream.close()
            raise InputError(
                f"Worker/project lock unavailable: {exc}",
                kind=ErrorKind.POLICY_DENIED,
                code="PF-RUN-LOCKED",
            ) from exc

    def _write(self) -> None:
        assert self.stream is not None
        self.stream.seek(0)
        self.stream.truncate()
        self.stream.write(json.dumps(self.record).encode())
        self.stream.flush()
        os.fsync(self.stream.fileno())

    @staticmethod
    def _unlock(stream: BinaryIO) -> None:
        stream.seek(0)
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.stream is not None:
            try:
                self.record["released"] = True
                self._write()
            finally:
                self._unlock(self.stream)
                self.stream.close()
                self.stream = None
