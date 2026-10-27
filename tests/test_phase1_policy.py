"""Phase 1 config and filesystem policy acceptance tests."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from polyforge.contracts.validation import InputError


class PolicyTests(unittest.TestCase):
    def test_config_defaults_and_explicit_tool_overrides(self) -> None:
        from polyforge.config import load_config

        config = load_config()
        self.assertFalse(config.allow_network)
        self.assertEqual(config.retry_limit, 2)
        self.assertEqual(config.unity_timeout_seconds, 1800)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "polyforge.toml"
            path.write_text(
                '[tools]\nblender_executable = "C:/Tools/Blender/blender.exe"\n'
                "[execution]\nretry_limit = 1\n",
                encoding="utf-8",
            )
            config = load_config(path)
            self.assertEqual(config.blender_executable, "C:/Tools/Blender/blender.exe")
            self.assertEqual(config.retry_limit, 1)

    def test_invalid_config_never_enables_network_or_untrusted_execution(self) -> None:
        from polyforge.config import load_config

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.toml"
            for value in (
                "[security]\nallow_network = true",
                "[security]\nallow_outside_workspace = true",
                "[security]\nrequire_approval_for_download = false",
                '[security]\nmode = "SANDBOXED_UNTRUSTED"',
                "[execution]\nretry_limit = 3",
                "[execution]\nretry_limit = true",
                "[execution]\nblender_timeout_seconds = 0",
                "[tools]\nblender_executable = 42",
                "[unknown]\nx = 1",
                "[execution]\nunknown = 1",
                "not valid TOML",
            ):
                path.write_text(value, encoding="utf-8")
                with self.subTest(value=value), self.assertRaises(InputError):
                    load_config(path)
            with self.assertRaises(InputError):
                load_config(Path(directory) / "missing.toml")

    def test_confined_paths_reject_traversal_drives_devices_and_alternate_streams(self) -> None:
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory(prefix="PolyForge Δ ") as directory:
            root = Path(directory)
            policy = WorkspacePolicy(root)
            self.assertEqual(policy.path("runs/demo/state.json"), root / "runs/demo/state.json")
            for value in (
                "../bad",
                "a/../../bad",
                "C:/outside",
                "C:relative",
                "\\\\host\\share",
                "a\\..\\bad",
                "NUL",
                "CON.txt",
                "a/file:stream",
                "bad\x00name",
                "a/trailing.",
                "a/trailing ",
            ):
                with self.subTest(value=value), self.assertRaises(InputError):
                    policy.path(value)
            with self.assertRaises(InputError):
                policy.path(root.parent / "outside")
            with self.assertRaises(InputError):
                WorkspacePolicy(root / "absent")

    def test_atomic_json_writes_are_confined_and_preserve_original_on_invalid_data(self) -> None:
        from polyforge.runner.state import atomic_json
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = WorkspacePolicy(root)
            atomic_json(policy, "state.json", {"value": 1})
            before = (root / "state.json").read_bytes()
            with self.assertRaises(InputError):
                atomic_json(policy, "state.json", {"value": float("nan")})
            self.assertEqual((root / "state.json").read_bytes(), before)
            self.assertEqual(json.loads(before), {"value": 1})
            self.assertEqual([p.name for p in root.iterdir()], ["state.json"])

    def test_real_directory_link_is_denied_before_writing(self) -> None:
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root, outside = base / "root", base / "outside"
            root.mkdir()
            outside.mkdir()
            link = root / "link"
            if os.name == "nt":
                result = subprocess.run(
                    [os.environ["COMSPEC"], "/d", "/c", "mklink", "/J", str(link), str(outside)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                link.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(InputError):
                WorkspacePolicy(root).path("link/escaped.json")
            self.assertEqual(list(outside.iterdir()), [])

    def test_redaction_and_environment_do_not_forward_secret_canaries(self) -> None:
        from polyforge.security.policy import isolation_profile, redact, worker_environment

        values = {
            "OPENAI_API_KEY": "canary-top-secret",
            "AWS_SECRET_ACCESS_KEY": "canary-aws",
            "PATH": "/something",
            "SystemRoot": "C:/Windows",
        }
        env = worker_environment(Path("C:/tools/tool.exe"), Path("C:/work"), values)
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
        text = redact("api_key=canary-top-secret Authorization: Bearer abcdefghijk", values)
        self.assertNotIn("canary-top-secret", text)
        self.assertNotIn("abcdefghijk", text)
        profile = isolation_profile(values)
        self.assertFalse(profile["isolation_verified"])
        self.assertEqual(profile["status"], "UNSANDBOXED")
        self.assertIn("OPENAI_API_KEY", profile["secret_variable_names"])
        self.assertNotIn("canary", json.dumps(profile))


if __name__ == "__main__":
    unittest.main()
