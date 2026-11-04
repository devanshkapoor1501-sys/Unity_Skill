"""Optional observations of one owned process; unavailable counters stay unknown."""

from __future__ import annotations

import ctypes as ct
import sys
import time
from collections.abc import Callable
from ctypes import wintypes as wt
from typing import Any

from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.ownership import process_identity
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


class ProcessCounters:
    """Retain one birth-bound Windows handle through the final exited-process read."""

    kernel: Any
    psapi: Any
    handle: int | None
    birth: str | None
    memory_type: type[ct.Structure]
    last_error: Callable[[], int]

    def __init__(self, pid: int, expected_birth: str | None = None) -> None:
        if sys.platform != "win32":
            raise OSError("Windows process counters unavailable")

        class MemoryCounters(ct.Structure):
            _fields_ = [("cb", wt.DWORD), ("faults", wt.DWORD)] + [
                (name, ct.c_size_t)
                for name in (
                    "peak_rss",
                    "rss",
                    "peak_paged",
                    "paged",
                    "peak_nonpaged",
                    "nonpaged",
                    "pagefile",
                    "peak_pagefile",
                )
            ]

        self.memory_type = MemoryCounters
        native_library: Callable[..., Any] | None = getattr(ct, "WinDLL", None)
        last_error: Callable[[], int] | None = getattr(ct, "get_last_error", None)
        if native_library is None or last_error is None:
            raise OSError("Windows process counter APIs unavailable")
        self.last_error = last_error
        self.kernel = native_library("kernel32", use_last_error=True)
        self.psapi = native_library("psapi", use_last_error=True)
        self.kernel.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
        self.kernel.OpenProcess.restype = wt.HANDLE
        self.kernel.CloseHandle.argtypes = [wt.HANDLE]
        self.kernel.GetProcessTimes.argtypes = [wt.HANDLE, *([ct.POINTER(wt.FILETIME)] * 4)]
        self.psapi.GetProcessMemoryInfo.argtypes = [wt.HANDLE, ct.POINTER(MemoryCounters), wt.DWORD]
        self.handle = self.kernel.OpenProcess(0x0410, False, pid)
        self.birth = expected_birth
        if not self.handle:
            raise OSError(self.last_error(), "Cannot query owned process counters")
        try:
            self._times()  # Bind before the first poll; never reopen by PID after exit.
        except BaseException:
            self.close()
            raise

    def _times(self) -> list[int]:
        times = [wt.FILETIME() for _ in range(4)]
        if not self.kernel.GetProcessTimes(self.handle, *(ct.byref(value) for value in times)):
            raise OSError(self.last_error(), "Cannot query owned process times")
        ticks = [(value.dwHighDateTime << 32) | value.dwLowDateTime for value in times]
        if self.birth is not None and str(ticks[0]) != self.birth:
            raise OSError("Owned process birth identity changed")
        return ticks

    def read(self) -> dict[str, Any]:
        ticks = self._times()
        memory = self.memory_type()
        memory.cb = ct.sizeof(memory)
        if not self.psapi.GetProcessMemoryInfo(self.handle, ct.byref(memory), memory.cb):
            raise OSError(self.last_error(), "Cannot query owned process RSS")
        return {
            "peak_rss_bytes": int(memory.peak_rss),
            "cpu_seconds": (ticks[2] + ticks[3]) / 10_000_000,
        }

    def close(self) -> None:
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


def process_counters(pid: int, expected_birth: str | None = None) -> dict[str, Any]:
    """Read one snapshot; long-running observations retain their own handle."""
    counters = ProcessCounters(pid, expected_birth)
    try:
        return counters.read()
    finally:
        counters.close()


class ProcessObservation:
    """Fixed ready-sidecar and counters; no subprocess or arbitrary callback authority."""

    def __init__(self, policy: WorkspacePolicy, relative: str, ready_path: str) -> None:
        self.policy = policy
        self.relative = policy.path(relative).relative_to(policy.root).as_posix()
        self.ready_path = policy.path(ready_path)
        if not self.ready_path.is_relative_to(policy.path(self.relative)):
            raise InputError("Ready observation must stay within its process run")
        self.started = 0.0
        self.birth: str | None = None
        self.counters: ProcessCounters | None = None
        self.fatal = False
        self.data: dict[str, Any] = {
            "pid": None,
            "birth": None,
            "identity_status": "NOT_RUN",
            "fatal": False,
            "ready_observed": False,
            "ready_seconds": None,
            "peak_rss_bytes": None,
            "cpu_seconds": None,
            "poll_interval_seconds": 0.02,
            "errors": [],
            "rss_source": "WINDOWS_PEAK_WORKING_SET",
            "gpu_utilization": "UNKNOWN",
        }

    def _error(self, message: str) -> None:
        if message not in self.data["errors"] and len(self.data["errors"]) < 32:
            self.data["errors"].append(message[:512])

    def start(self, pid: int, started: float) -> None:
        self.started = started
        self.data["pid"] = pid
        self.birth = process_identity(pid)
        if self.birth is None:
            raise OSError("Owned process exited before birth identity observation")
        self.counters = ProcessCounters(pid, self.birth)
        self.data.update(birth=self.birth, identity_status="BOUND")

    def poll(self, *, final: bool = False) -> None:
        # Observe ready even if the process exited between two runner polls.
        if not self.data["ready_observed"] and self.ready_path.is_file():
            try:
                if (
                    load_json(self.policy.path(self.ready_path), max_bytes=65536).get("ready")
                    is True
                ):
                    self.data.update(
                        ready_observed=True, ready_seconds=time.monotonic() - self.started
                    )
            except (InputError, OSError, AttributeError) as exc:
                self._error("Ready observation: " + str(exc))
        if not self.data["ready_observed"] and time.monotonic() - self.started > 30:
            self.fatal = True
            self._error("Rendered readiness exceeded 30 seconds")
        pid = self.data["pid"]
        if pid is None:
            return
        try:
            if not final:
                identity = process_identity(pid)
                if identity is None:
                    return
                if identity != self.birth:
                    self.data["identity_status"] = "CHANGED"
                    self.fatal = True
                    self._error("Owned process birth identity changed")
                    return
            if self.counters is None:
                raise OSError("Owned process counter handle unavailable")
            counters = self.counters.read()
            for name in ("peak_rss_bytes", "cpu_seconds"):
                value = counters[name]
                if value is not None:
                    previous = self.data[name]
                    self.data[name] = value if previous is None else max(previous, value)
            if self.data["peak_rss_bytes"] is not None and self.data["peak_rss_bytes"] > 2147483648:
                self.fatal = True
                self._error("Peak RSS exceeded 2 GiB")
        except OSError as exc:
            self._error("Process counters: " + str(exc))
            self.fatal = True

    def finish(self) -> None:
        try:
            self.poll(final=True)
        finally:
            if self.counters is not None:
                self.counters.close()
                self.counters = None
            self.data["fatal"] = self.fatal
        atomic_json(self.policy, self.relative + "/observations.json", self.data)
