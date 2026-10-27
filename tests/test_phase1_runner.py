"""Real subprocess ownership, locks and journal recovery acceptance."""

from __future__ import annotations

import json
import os
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from polyforge.contracts.validation import InputError


class StateTests(unittest.TestCase):
    def test_journal_requires_evidence_and_retries_are_bounded(self) -> None:
        from polyforge.runner.state import RunJournal
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = RunJournal.create(WorkspacePolicy(root), "test_run", retry_limit=1)
            journal.transition("S0", "running")
            with self.assertRaises(InputError):
                journal.transition("S0", "passed")
            journal.transition("S0", "failed", note="first failure")
            journal.transition("S0", "running")
            journal.transition("S0", "failed", note="second failure")
            with self.assertRaises(InputError) as error:
                journal.transition("S0", "running")
            self.assertEqual(error.exception.kind, 8)
            self.assertEqual(journal.read()["stages"]["S0"]["attempt"], 2)
            self.assertGreater(
                len((root / "runs/test_run/events.jsonl").read_text().splitlines()), 4
            )

    def test_completed_stage_requires_actual_nonempty_artifact(self) -> None:
        from polyforge.runner.state import RunJournal
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = RunJournal.create(WorkspacePolicy(root), "success")
            journal.transition("S0", "running")
            (root / "proof.json").write_text('{"tool":"observed"}', encoding="utf-8")
            journal.transition("S0", "passed", evidence=["proof.json"])
            self.assertEqual(journal.read()["stages"]["S0"]["status"], "passed")
            with self.assertRaises(InputError):
                journal.transition("S0", "running")

    def test_journal_replays_durable_event_when_state_cache_write_crashes(self) -> None:
        from polyforge.runner.state import RunJournal
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            policy = WorkspacePolicy(Path(directory))
            journal = RunJournal.create(policy, "recover")
            with patch("polyforge.runner.state.atomic_json", side_effect=OSError("injected crash")):
                with self.assertRaises(OSError):
                    journal.transition("S0", "running")
            self.assertEqual(journal.read()["stages"]["S0"]["status"], "running")
            recovered = journal.recover()
            self.assertEqual(recovered["stages"]["S0"]["status"], "failed")
            self.assertIn("interrupted", recovered["stages"]["S0"]["note"])
            with self.assertRaises(InputError):
                RunJournal.create(policy, "../escape")

    def test_lock_refuses_live_and_foreign_owners_and_reclaims_verified_dead_owner(self) -> None:
        from polyforge.runner.locks import FileLock, process_identity
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            policy = WorkspacePolicy(root)
            with FileLock(policy, "locks/test.lock"):
                with self.assertRaises(InputError):
                    with FileLock(policy, "locks/test.lock"):
                        self.fail("Second owner entered")
            target = root / "locks/test.lock"
            for host, pid, identity, allowed in (
                ("other-host", 2147483646, "dead", False),
                (socket.gethostname(), os.getpid(), process_identity(os.getpid()), False),
                (socket.gethostname(), 2147483646, "dead", True),
            ):
                target.write_text(
                    json.dumps(
                        {
                            "host": host,
                            "pid": pid,
                            "identity": identity,
                            "released": False,
                            "token": "old",
                        }
                    ),
                    encoding="utf-8",
                )
                if allowed:
                    with FileLock(policy, "locks/test.lock") as lock:
                        self.assertTrue(lock.recovered_stale)
                else:
                    with self.assertRaises(InputError):
                        with FileLock(policy, "locks/test.lock"):
                            self.fail("Unverified lock reclaimed")


class ProcessTests(unittest.TestCase):
    def invoke(
        self, code: str, *, timeout: float = 5, output_limit: int = 65536, cancelled: bool = False
    ) -> tuple[object, str]:
        from polyforge.runner.processes import ProcessPolicy, run_process
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory(prefix="worker Δ ") as directory:
            root = Path(directory)
            event = threading.Event()
            if cancelled:
                event.set()
            policy = ProcessPolicy(
                allowed_executables=(Path(sys.executable),),
                timeout_seconds=timeout,
                max_output_bytes=output_limit,
            )
            outcome = run_process(
                [sys.executable, "-c", code], WorkspacePolicy(root), "job", policy, cancel=event
            )
            text = (
                (root / "job/stdout.txt").read_text("utf-8")
                if (root / "job/stdout.txt").exists()
                else ""
            )
            return outcome, text

    def test_real_worker_output_and_environment_are_recorded_without_secret(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "phase1-secret-canary"}):
            outcome, text = self.invoke(
                "import os; print(os.getenv('OPENAI_API_KEY','absent')); "
                "print('token=phase1-secret-canary')"
            )
        self.assertEqual(outcome.reason, "exit")
        self.assertEqual(outcome.returncode, 0)
        self.assertIn("absent", text)
        self.assertNotIn("phase1-secret-canary", text)
        self.assertIn("[REDACTED]", text)
        self.assertIn(outcome.ownership, {"WINDOWS_JOB", "POSIX_PROCESS_GROUP"})

    def test_timeout_output_budget_and_cancellation_stop_owned_workers(self) -> None:
        for kwargs, code, expected in (
            ({"timeout": 0.3}, "import time; time.sleep(20)", "timeout"),
            ({"output_limit": 512}, "print('x'*100000)", "output_limit"),
            ({"cancelled": True}, "raise Exception('must not execute')", "cancelled"),
        ):
            with self.subTest(expected=expected):
                outcome, _ = self.invoke(code, **kwargs)
                self.assertEqual(outcome.reason, expected)

    def test_unapproved_or_missing_executable_is_specific_and_writes_nothing(self) -> None:
        from polyforge.runner.processes import ProcessPolicy, run_process
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(InputError):
                run_process(
                    [sys.executable, "-c", "print(1)"],
                    WorkspacePolicy(root),
                    "bad",
                    ProcessPolicy(allowed_executables=()),
                )
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
