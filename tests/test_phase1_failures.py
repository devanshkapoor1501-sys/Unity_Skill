"""Recovery and producer failures must stay structured and side-effect bounded."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from polyforge.contracts.validation import InputError


class FailureTests(unittest.TestCase):
    def test_journal_container_shape_is_a_contract_failure(self) -> None:
        from polyforge.runner.state import RunJournal
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = RunJournal.create(WorkspacePolicy(root), "shape")
            path = root / "runs/shape/events.jsonl"
            event = json.loads(path.read_text())
            event["state"]["stages"] = [f"S{i}" for i in range(6)]
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaises(InputError) as error:
                journal.read()
            self.assertEqual(error.exception.kind, 6)

    def test_doctor_policy_denial_uses_exit_four_not_missing_dependency(self) -> None:
        from polyforge.contracts.results import ErrorKind
        from polyforge.doctor import doctor

        with tempfile.TemporaryDirectory() as directory:
            with patch(
                "polyforge.doctor.probe_tool",
                side_effect=InputError(
                    "policy denied", kind=ErrorKind.POLICY_DENIED, code="PF-POLICY-TEST"
                ),
            ):
                result = doctor(Path(directory))
            self.assertEqual(result.exit_code, 4)

    def test_unity_project_lock_is_shared_by_nested_workspace_roots(self) -> None:
        from polyforge.runner.locks import unity_project_lock
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "game"
            project.mkdir()
            with unity_project_lock(WorkspacePolicy(root), project):
                with self.assertRaises(InputError):
                    with unity_project_lock(WorkspacePolicy(project), project):
                        self.fail("Two workers entered the same Unity project")
            (project / "Temp").mkdir()
            (project / "Temp/UnityLockfile").touch()
            with self.assertRaises(InputError) as error:
                with unity_project_lock(WorkspacePolicy(root), project):
                    self.fail("Active Editor lock bypassed")
            self.assertEqual(error.exception.code, "PF-UNITY-PROJECT-LOCKED")

    def test_live_lock_with_missing_birth_identity_is_never_reclaimed(self) -> None:
        import socket

        from polyforge.runner.locks import FileLock
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "lock.json").write_text(
                json.dumps({"host": socket.gethostname(), "pid": os.getpid(), "released": False}),
                encoding="utf-8",
            )
            with self.assertRaises(InputError):
                with FileLock(WorkspacePolicy(root), "lock.json"):
                    self.fail("Live ambiguous owner was reclaimed")

    def test_corrupt_stage_fields_fail_with_contract_error(self) -> None:
        from polyforge.runner.state import RunJournal
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = RunJournal.create(WorkspacePolicy(root), "corrupt")
            path = root / "runs/corrupt/events.jsonl"
            event = json.loads(path.read_text())
            event["state"]["stages"]["S0"] = {"status": "invented"}
            path.write_text(json.dumps(event) + "\n", encoding="utf-8")
            with self.assertRaises(InputError) as error:
                journal.read()
            self.assertEqual(error.exception.kind, 6)

    def test_unity_editor_installation_wins_over_unrelated_path_cli(self) -> None:
        from polyforge.doctor import discover_tool

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            editor = root / "Unity/Hub/Editor/6000.6.3f1/Editor/Unity.exe"
            editor.parent.mkdir(parents=True)
            editor.touch()
            with (
                patch.dict(os.environ, {"ProgramFiles": str(root)}),
                patch("polyforge.doctor.sys.platform", "win32"),
                patch("polyforge.doctor.shutil.which", return_value=str(root / "unrelated.exe")),
            ):
                self.assertEqual(discover_tool("unity"), editor.resolve())

    def test_filesystem_permission_error_is_structured_and_redacted(self) -> None:
        from polyforge.cli import main

        with (
            patch(
                "polyforge.workspace.init_workspace",
                side_effect=PermissionError("token=do-not-print"),
            ),
            contextlib.redirect_stdout(io.StringIO()) as output,
        ):
            code = main(["init", "unused", "--json"])
        self.assertEqual(code, 5)
        self.assertEqual(json.loads(output.getvalue())["status"], "FAIL")
        self.assertNotIn("do-not-print", output.getvalue())

    def test_missing_allowed_executable_and_invalid_worker_budget_write_nothing(self) -> None:
        from polyforge.runner.processes import ProcessPolicy, run_process
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            missing = root / "missing.exe"
            for arguments, policy, expected in (
                ([str(missing)], ProcessPolicy((missing,)), 3),
                ([sys.executable], ProcessPolicy((Path(sys.executable),), timeout_seconds=0), 2),
                (
                    [sys.executable],
                    ProcessPolicy((Path(sys.executable),), timeout_seconds=float("inf")),
                    2,
                ),
                (
                    [sys.executable],
                    ProcessPolicy((Path(sys.executable),), timeout_seconds=float("nan")),
                    2,
                ),
                ([], ProcessPolicy(()), 2),
            ):
                with self.subTest(arguments=arguments), self.assertRaises(InputError) as error:
                    run_process(arguments, WorkspacePolicy(root), "job", policy)
                self.assertEqual(error.exception.kind, expected)
                self.assertEqual(list(root.iterdir()), [])

    def test_partial_journal_tail_is_recovered_but_corrupt_complete_event_is_rejected(self) -> None:
        from polyforge.runner.state import RunJournal
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = RunJournal.create(WorkspacePolicy(root), "tail")
            path = root / "runs/tail/events.jsonl"
            with path.open("ab") as stream:
                stream.write(b'{"partial":')
            self.assertEqual(journal.read()["sequence"], 1)
            journal.recover()
            self.assertEqual(journal.read()["sequence"], 2)
            with path.open("ab") as stream:
                stream.write(b'{"state":{}}\n')
            with self.assertRaises(InputError) as error:
                journal.read()
            self.assertEqual(error.exception.kind, 6)

    def test_worker_descendants_are_terminated_on_timeout(self) -> None:
        from polyforge.runner.ownership import process_identity
        from polyforge.runner.processes import ProcessPolicy, run_process
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            code = (
                "import subprocess,sys,time; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
                "print(p.pid,flush=True); time.sleep(60)"
            )
            outcome = run_process(
                [sys.executable, "-c", code],
                WorkspacePolicy(root),
                "owned",
                ProcessPolicy((Path(sys.executable),), timeout_seconds=1),
            )
            self.assertEqual(outcome.reason, "timeout")
            child_pid = int((root / "owned/stdout.txt").read_text().strip())
            self.assertIsNone(process_identity(child_pid))

    def test_redaction_covers_url_credentials_and_nonzero_worker_exit(self) -> None:
        from polyforge.security.policy import redact

        self.assertNotIn("user:password", redact("https://user:password@example.invalid/repo"))


if __name__ == "__main__":
    unittest.main()
