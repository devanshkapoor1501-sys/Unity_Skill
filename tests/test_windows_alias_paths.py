"""Actual Windows short-name aliases remain confined to the physical workspace."""

from __future__ import annotations

import ctypes
import os
import tempfile
import unittest
from pathlib import Path

from test_foundation import cli

from polyforge.contracts.validation import InputError
from polyforge.security.paths import WorkspacePolicy


def short_path(path: Path) -> Path:
    if os.name != "nt":
        return path
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    kernel.GetShortPathNameW.restype = ctypes.c_uint32
    required = kernel.GetShortPathNameW(str(path), None, 0)
    if not required:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_unicode_buffer(required)
    if not kernel.GetShortPathNameW(str(path), buffer, required):
        raise ctypes.WinError(ctypes.get_last_error())
    return Path(buffer.value)


class WorkspaceAliasTests(unittest.TestCase):
    def test_short_and_long_absolute_names_share_authorization_without_allowing_escape(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="PolyForge Unicode alias Δ ") as directory:
            root = Path(directory)
            physical = root.resolve()
            alias = short_path(root)
            (root / "inside.json").write_text("{}", encoding="utf-8")
            for spelling in (root, physical, alias):
                policy = WorkspacePolicy(spelling)
                for candidate in (
                    root / "inside.json",
                    physical / "inside.json",
                    alias / "inside.json",
                    Path("inside.json"),
                ):
                    self.assertEqual(policy.path(candidate), physical / "inside.json")
                with self.assertRaises(InputError):
                    policy.path(alias.parent / "outside.json")
                with self.assertRaises(InputError):
                    policy.path(alias / ".." / "outside.json")

    def test_initialization_and_manifest_validation_accept_real_short_temp_parent(self) -> None:
        with tempfile.TemporaryDirectory(prefix="PolyForge init alias Δ ") as directory:
            root = short_path(Path(directory)) / "arena"
            result = cli("init", str(root), "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = cli("validate", "--workspace", str(root), "--json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
