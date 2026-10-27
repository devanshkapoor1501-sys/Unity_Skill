"""OS-exclusive locks with PID/host/birth identity and conservative stale recovery."""

from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from types import TracebackType
from typing import BinaryIO
from uuid import uuid4

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError
from polyforge.runner.ownership import process_identity
from polyforge.security.paths import WorkspacePolicy


def unity_project_lock(policy: WorkspacePolicy, project: Path) -> FileLock:
    """Use one physical lock per approved project, even under nested workspace roots."""
    project = policy.path(project)
    if not project.is_dir():
        raise InputError("Unity project directory does not exist")
    if policy.path(project / "Temp/UnityLockfile").exists():
        raise InputError(
            "Unity Editor has a project lock; close the Editor first",
            kind=ErrorKind.POLICY_DENIED,
            code="PF-UNITY-PROJECT-LOCKED",
        )
    return FileLock(policy, str(project / ".polyforge/worker.lock"))


class FileLock:
    """Keep a persistent lock file; release OS locks on exit/crash, never unlink races."""

    def __init__(self, policy: WorkspacePolicy, relative: str) -> None:
        self.policy, self.relative = policy, relative
        self.stream: BinaryIO | None = None
        self.recovered_stale = False
        self.record: dict[str, object] = {}

    def __enter__(self) -> FileLock:
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
