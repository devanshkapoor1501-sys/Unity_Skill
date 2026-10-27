"""Phase 1 command behavior without launching Blender or Unity projects."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from test_foundation import cli, snapshot


class PhaseOneCLITests(unittest.TestCase):
    def test_init_dry_run_and_bad_template_do_not_write_then_real_init_is_exclusive(self) -> None:
        with tempfile.TemporaryDirectory(prefix="arena Δ ") as directory:
            root = Path(directory)
            target = root / "game"
            for args, expected in ((("--dry-run",), 0), (("--template", "unknown"), 2)):
                before = snapshot(root)
                result = cli("init", str(target), *args, "--json")
                self.assertEqual(result.returncode, expected, result.stderr)
                self.assertEqual(snapshot(root), before)
                self.assertFalse(target.exists())
            result = cli("init", str(target), "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            for name in (
                "brief.md",
                "game_manifest.json",
                "polyforge.toml",
                ".polyforge/workspace.json",
            ):
                self.assertTrue((target / name).is_file(), name)
            before = snapshot(target)
            self.assertEqual(cli("init", str(target), "--json").returncode, 2)
            self.assertEqual(snapshot(target), before)

    def test_doctor_missing_dependencies_writes_specific_report_and_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "missing.toml"
            config.write_text(
                '[tools]\nblender_executable="missing-blender.exe"\n'
                'unity_executable="missing-unity.exe"\n',
                encoding="utf-8",
            )
            result = cli("doctor", "--workspace", directory, "--config", str(config), "--json")
            self.assertEqual(result.returncode, 3, result.stderr)
            body = json.loads(result.stdout)
            report = json.loads((root / "doctor.json").read_text("utf-8"))
            self.assertEqual(body["status"], "BLOCKED")
            self.assertEqual(report["data"]["tools"]["blender"]["status"], "BLOCKED")
            self.assertEqual(report["data"]["license"]["status"], "NOT_RUN")
            run = body["run_id"]
            status = cli("status", "--workspace", directory, "--json")
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(json.loads(status.stdout)["data"]["runs"][0]["run_id"], run)
            report_result = cli("report", "--workspace", directory, "--run-id", run, "--json")
            self.assertEqual(report_result.returncode, 0, report_result.stderr)
            self.assertEqual(json.loads(report_result.stdout)["game_status"], "PARTIAL")

    def test_doctor_invalid_config_and_dry_run_have_no_filesystem_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = snapshot(root)
            result = cli("doctor", "--workspace", directory, "--dry-run", "--json")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(snapshot(root), before)
            config = root / "bad.toml"
            config.write_text("[security]\nallow_network=true\n", encoding="utf-8")
            before = snapshot(root)
            result = cli("doctor", "--workspace", directory, "--config", str(config), "--json")
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertEqual(snapshot(root), before)

    def test_status_missing_workspace_and_report_unknown_run_write_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = snapshot(root)
            self.assertEqual(
                cli("status", "--workspace", str(root / "missing"), "--json").returncode, 2
            )
            self.assertEqual(
                cli("report", "--workspace", directory, "--run-id", "unknown", "--json").returncode,
                2,
            )
            self.assertEqual(snapshot(root), before)

    def test_original_unity_project_is_only_read_statically_and_lock_is_specific(self) -> None:
        from polyforge.doctor import inspect_project

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "ProjectSettings").mkdir()
            (root / "Packages").mkdir()
            (root / "Temp").mkdir()
            (root / "ProjectSettings/ProjectVersion.txt").write_text(
                "m_EditorVersion: 6000.6.3f1\n"
            )
            (root / "Packages/manifest.json").write_text(
                json.dumps(
                    {
                        "dependencies": {
                            "com.unity.render-pipelines.universal": "17.6.0",
                            "com.unity.test-framework": "1.8.0",
                        }
                    }
                )
            )
            (root / "Temp/UnityLockfile").write_text("editor lock")
            before = snapshot(root)
            result = inspect_project(root)
            self.assertEqual(result["error_code"], "PF-UNITY-PROJECT-LOCKED")
            self.assertEqual(result["packages"]["com.unity.test-framework"], "1.8.0")
            self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
