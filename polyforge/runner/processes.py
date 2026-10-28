"""Bounded, allowlisted, shell-free worker execution and sanitized log capture."""

from __future__ import annotations

import math
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError
from polyforge.runner.ownership import WindowsJob
from polyforge.security.paths import WorkspacePolicy
from polyforge.security.policy import redact, worker_environment


@dataclass(frozen=True)
class ProcessPolicy:
    allowed_executables: tuple[Path, ...]
    timeout_seconds: float = 600
    max_output_bytes: int = 10_485_760
    memory_limit_mb: int = 8192


@dataclass(frozen=True)
class ProcessOutcome:
    returncode: int | None
    reason: str
    pid: int | None
    ownership: str
    duration_seconds: float
    stdout_path: str
    stderr_path: str
    memory_limit_verified: bool


def run_process(
    argv: list[str],
    workspace: WorkspacePolicy,
    relative: str,
    policy: ProcessPolicy,
    *,
    cancel: threading.Event | None = None,
) -> ProcessOutcome:
    """Launch only an explicitly allowed binary; cleanup targets only its owned tree."""
    if not argv or any(not isinstance(arg, str) or "\x00" in arg for arg in argv):
        raise InputError("Process arguments must be nonempty NUL-free strings")
    executable = Path(argv[0]).resolve()
    if executable not in {path.resolve() for path in policy.allowed_executables}:
        raise InputError(
            "Executable is not on this operation's allowlist",
            kind=ErrorKind.POLICY_DENIED,
            code="PF-POLICY-EXECUTABLE",
        )
    if not executable.is_file():
        raise InputError(
            "Configured executable is missing",
            kind=ErrorKind.MISSING_DEPENDENCY,
            code="PF-DEPENDENCY-EXECUTABLE",
        )
    if executable.suffix.lower() in {".bat", ".cmd"}:
        raise InputError("Shell script launchers are not allowed", kind=ErrorKind.POLICY_DENIED)
    if (
        not math.isfinite(policy.timeout_seconds)
        or policy.timeout_seconds <= 0
        or policy.max_output_bytes <= 0
        or policy.memory_limit_mb <= 0
    ):
        raise InputError("Invalid worker resource budget")
    destination = workspace.path(relative)
    ownership = "WINDOWS_JOB" if os.name == "nt" else "POSIX_PROCESS_GROUP"
    if cancel is not None and cancel.is_set():
        return ProcessOutcome(None, "cancelled", None, ownership, 0, "", "", False)
    workspace.mkdir(destination)
    temporary = workspace.mkdir(destination / "tmp")
    unity_profile = None
    if executable.stem.lower() == "unity":
        unity_profile = workspace.mkdir(".polyforge/unity-profile")
        for directory in ("AppData/Local", "AppData/Roaming", "ProgramData", "upm-cache"):
            workspace.mkdir(unity_profile / directory)
    started = time.monotonic()
    job = WindowsJob(policy.memory_limit_mb) if os.name == "nt" else None
    process: subprocess.Popen[bytes] | None = None
    buffers: list[bytearray] = [bytearray(), bytearray()]
    exceeded = threading.Event()
    guard = threading.Lock()
    total = 0

    def collect(stream: BinaryIO, index: int) -> None:
        nonlocal total
        try:
            while chunk := stream.read(4096):
                with guard:
                    available = max(0, policy.max_output_bytes - total)
                    buffers[index].extend(chunk[:available])
                    total += len(chunk)
                    if total > policy.max_output_bytes:
                        exceeded.set()
        finally:
            stream.close()

    def terminate() -> None:
        if process is None:
            return
        if job is not None:
            job.terminate()
        elif sys.platform != "win32":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    reason = "exit"
    try:
        process = subprocess.Popen(
            [str(executable), *argv[1:]],
            cwd=destination,
            env=worker_environment(executable, temporary, unity_profile=unity_profile),
            shell=False,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=os.name != "nt",
            creationflags=0x08000204 if job is not None else 0,
        )
        if job is not None:
            try:
                job.assign_and_resume(process.pid)
            except OSError:
                process.kill()
                process.wait()
                raise
        assert process.stdout is not None and process.stderr is not None
        readers = [
            threading.Thread(target=collect, args=(stream, index), daemon=True)
            for index, stream in enumerate((process.stdout, process.stderr))
        ]
        for reader in readers:
            reader.start()
        while process.poll() is None:
            if cancel is not None and cancel.is_set():
                reason = "cancelled"
                break
            if exceeded.is_set():
                reason = "output_limit"
                break
            if time.monotonic() - started >= policy.timeout_seconds:
                reason = "timeout"
                break
            time.sleep(0.02)
        terminate()  # Also remove owned descendants if the parent exited normally.
        process.wait(timeout=10)
        for reader in readers:
            reader.join(timeout=10)
        if exceeded.is_set() and reason == "exit":
            reason = "output_limit"
    except KeyboardInterrupt:
        terminate()
        if process is not None:
            process.wait(timeout=10)
        raise
    except OSError as exc:
        raise InputError(
            f"Worker launch/ownership failed: {exc}",
            kind=ErrorKind.PRODUCER_FAILURE,
            code="PF-RUN-LAUNCH",
        ) from exc
    finally:
        if job is not None:
            job.close()
    stdout, stderr = destination / "stdout.txt", destination / "stderr.txt"
    remaining = policy.max_output_bytes
    for path, content in zip((stdout, stderr), buffers, strict=True):
        sanitized = redact(content.decode("utf-8", errors="ignore")).encode("utf-8")[:remaining]
        workspace.path(path).write_bytes(sanitized)
        remaining -= len(sanitized)
    return ProcessOutcome(
        process.returncode,
        reason,
        process.pid,
        ownership,
        round(time.monotonic() - started, 3),
        str(stdout.relative_to(workspace.root)),
        str(stderr.relative_to(workspace.root)),
        job is not None,
    )
