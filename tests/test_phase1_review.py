"""Independent-review regressions and observed Windows write contention."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from polyforge.contracts.validation import InputError


class ReviewTests(unittest.TestCase):
    def test_quoted_and_json_credentials_are_redacted(self) -> None:
        from polyforge.security.policy import redact

        for value in (
            'token="new-secret-123"',
            "password='new-secret-123'",
            '{"api_key": "new-secret-123"}',
        ):
            with self.subTest(value=value):
                self.assertNotIn("new-secret-123", redact(value, {}))

    def test_output_limit_never_persists_a_secret_prefix(self) -> None:
        from polyforge.runner.processes import ProcessPolicy, run_process
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict(os.environ, {"TEST_SECRET": "phase1-canary-sensitive-value"}):
                run_process(
                    [sys.executable, "-c", "print('phase1-canary-sensitive-value')"],
                    WorkspacePolicy(root),
                    "boundary",
                    ProcessPolicy((Path(sys.executable),), max_output_bytes=20),
                )
            output = (root / "boundary/stdout.txt").read_text("utf-8")
            self.assertNotIn("phase1-canary", output)
            self.assertLessEqual(len(output.encode()), 20)

    def test_malformed_static_project_never_passes_or_escapes_contract(self) -> None:
        from polyforge.doctor import inspect_project

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ProjectSettings").mkdir()
            (root / "Packages").mkdir()
            version = root / "ProjectSettings/ProjectVersion.txt"
            manifest = root / "Packages/manifest.json"
            manifest.write_text(
                '{"dependencies":{"com.unity.render-pipelines.universal":null,"com.unity.test-framework":false}}'
            )
            for content in (b"", b"invalid version", b"\xff", b"x" * 5000):
                version.write_bytes(content)
                with self.subTest(content_length=len(content)), self.assertRaises(InputError):
                    inspect_project(root)
            version.write_text("m_EditorVersion: 6000.6.3f1\n")
            with self.assertRaises(InputError):
                inspect_project(root)
            manifest.write_text(
                '{"dependencies":{"com.unity.render-pipelines.universal":"17.6.0",'
                '"com.unity.test-framework":"1.8.0",'
                '"custom":"https://user:password@example.invalid/repo"}}'
            )
            self.assertNotIn("user:password", str(inspect_project(root)))

    def test_atomic_replace_retries_only_twice_and_preserves_old_state_on_denial(self) -> None:
        from polyforge.runner.state import atomic_json
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = WorkspacePolicy(root)
            atomic_json(policy, "state.json", {"value": 1})
            original_replace = os.replace
            failures = 0

            def transient(source: Path, target: Path) -> None:
                nonlocal failures
                if failures < 2:
                    failures += 1
                    raise PermissionError("temporary sharing violation")
                original_replace(source, target)

            with patch("polyforge.runner.state.os.replace", side_effect=transient):
                atomic_json(policy, "state.json", {"value": 2})
            self.assertIn('"value": 2', (root / "state.json").read_text())
            before = (root / "state.json").read_bytes()
            with patch("polyforge.runner.state.os.replace", side_effect=PermissionError("denied")):
                with self.assertRaises(InputError):
                    atomic_json(policy, "state.json", {"value": 3})
            self.assertEqual((root / "state.json").read_bytes(), before)
            self.assertEqual(len(list(root.iterdir())), 1)


if __name__ == "__main__":
    unittest.main()
