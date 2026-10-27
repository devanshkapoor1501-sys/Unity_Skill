"""Native Windows job ownership; POSIX workers use a new process group."""

from __future__ import annotations

import ctypes as ct
import os
import sys
from ctypes import wintypes as wt
from pathlib import Path
from typing import Any


def _kernel() -> Any:
    if sys.platform != "win32":
        raise OSError("Windows native process ownership is unavailable on this host")
    api = ct.WinDLL("kernel32", use_last_error=True)
    for name, arguments, result in (
        ("OpenProcess", [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE),
        ("CloseHandle", [wt.HANDLE], wt.BOOL),
        ("GetExitCodeProcess", [wt.HANDLE, ct.POINTER(wt.DWORD)], wt.BOOL),
        ("GetProcessTimes", [wt.HANDLE, *([ct.POINTER(wt.FILETIME)] * 4)], wt.BOOL),
        ("CreateJobObjectW", [ct.c_void_p, wt.LPCWSTR], wt.HANDLE),
        ("SetInformationJobObject", [wt.HANDLE, ct.c_int, ct.c_void_p, wt.DWORD], wt.BOOL),
        ("AssignProcessToJobObject", [wt.HANDLE, wt.HANDLE], wt.BOOL),
        ("TerminateJobObject", [wt.HANDLE, wt.UINT], wt.BOOL),
        ("CreateToolhelp32Snapshot", [wt.DWORD, wt.DWORD], wt.HANDLE),
        ("OpenThread", [wt.DWORD, wt.BOOL, wt.DWORD], wt.HANDLE),
        ("ResumeThread", [wt.HANDLE], wt.DWORD),
    ):
        function = getattr(api, name)
        function.argtypes, function.restype = arguments, result
    return api


def process_identity(pid: int) -> str | None:
    """Return a birth token; permission uncertainty never proves an owner dead."""
    if type(pid) is not int or not 0 < pid < 2**31:
        raise OSError("Invalid process identity")
    if sys.platform == "win32":
        api = _kernel()
        handle = api.OpenProcess(0x1000, False, pid)
        if not handle:
            error = ct.get_last_error()
            if error == 87:
                return None
            raise OSError(error, "Cannot verify lock owner")
        try:
            exit_code = wt.DWORD()
            if not api.GetExitCodeProcess(handle, ct.byref(exit_code)):
                raise OSError("Cannot verify owner liveness")
            if exit_code.value != 259:
                return None
            times = [wt.FILETIME() for _ in range(4)]
            if not api.GetProcessTimes(handle, *(ct.byref(value) for value in times)):
                raise OSError("Cannot verify owner birth time")
            return str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
        finally:
            api.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    process_stat = Path(f"/proc/{pid}/stat")
    if process_stat.exists():
        fields = process_stat.read_text().rsplit(")", 1)[1].split()
        return None if fields[0] == "Z" else fields[19]
    return "alive"  # Other POSIX hosts conservatively refuse live-owner reclamation.


class _BasicLimits(ct.Structure):
    _fields_ = [
        ("process_time", ct.c_int64),
        ("job_time", ct.c_int64),
        ("flags", wt.DWORD),
        ("min_ws", ct.c_size_t),
        ("max_ws", ct.c_size_t),
        ("processes", wt.DWORD),
        ("affinity", ct.c_size_t),
        ("priority", wt.DWORD),
        ("scheduling", wt.DWORD),
    ]


class _ExtendedLimits(ct.Structure):
    _fields_ = [
        ("basic", _BasicLimits),
        ("io", ct.c_uint64 * 6),
        ("process_memory", ct.c_size_t),
        ("job_memory", ct.c_size_t),
        ("peak_process", ct.c_size_t),
        ("peak_job", ct.c_size_t),
    ]


class _ThreadEntry(ct.Structure):
    _fields_ = [
        ("size", wt.DWORD),
        ("usage", wt.DWORD),
        ("thread", wt.DWORD),
        ("owner", wt.DWORD),
        ("base_priority", wt.LONG),
        ("delta_priority", wt.LONG),
        ("flags", wt.DWORD),
    ]


class WindowsJob:
    """Assign a suspended owned worker before any of its code can execute.

    This guarantees process-tree cleanup/resource budgets, not filesystem/network
    isolation. A nested-job assignment failure denies the launch, never downgrades.
    """

    def __init__(self, memory_limit_mb: int) -> None:
        self.api = _kernel()
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise OSError("Cannot create owned worker job")
        limits = _ExtendedLimits()
        limits.basic.flags = 0x2000 | 0x200 | 0x8  # kill-on-close, job memory, process count
        limits.basic.processes = 32
        limits.job_memory = memory_limit_mb * 1024 * 1024
        if not self.api.SetInformationJobObject(
            self.handle, 9, ct.byref(limits), ct.sizeof(limits)
        ):
            self.close()
            raise OSError("Cannot configure owned job resource limits")

    def assign_and_resume(self, pid: int) -> None:
        process = self.api.OpenProcess(0x100 | 0x1, False, pid)
        if not process:
            raise OSError("Cannot acquire owned worker")
        try:
            if not self.api.AssignProcessToJobObject(self.handle, process):
                raise OSError("Cannot assign worker to its job; execution denied")
        finally:
            self.api.CloseHandle(process)
        snapshot = self.api.CreateToolhelp32Snapshot(4, 0)
        if snapshot == ct.c_void_p(-1).value or not snapshot:
            raise OSError("Cannot enumerate suspended worker thread")
        entry = _ThreadEntry()
        entry.size = ct.sizeof(entry)
        for name in ("Thread32First", "Thread32Next"):
            function = getattr(self.api, name)
            function.argtypes = [wt.HANDLE, ct.POINTER(_ThreadEntry)]
            function.restype = wt.BOOL
        try:
            present = self.api.Thread32First(snapshot, ct.byref(entry))
            while present:
                if entry.owner == pid:
                    thread = self.api.OpenThread(2, False, entry.thread)
                    if not thread:
                        raise OSError("Cannot open owned suspended thread")
                    try:
                        if self.api.ResumeThread(thread) == 0xFFFFFFFF:
                            raise OSError("Cannot resume owned worker")
                    finally:
                        self.api.CloseHandle(thread)
                    return
                present = self.api.Thread32Next(snapshot, ct.byref(entry))
            raise OSError("Owned suspended thread was not found")
        finally:
            self.api.CloseHandle(snapshot)

    def terminate(self) -> None:
        if self.handle:
            self.api.TerminateJobObject(self.handle, 1)

    def close(self) -> None:
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
