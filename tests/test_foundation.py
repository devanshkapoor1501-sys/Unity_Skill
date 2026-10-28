"""Public, model-free Phase 0 acceptance tests."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY = "contract.capability.validate.v1"


def cli(*args: str, cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ, PYTHONPATH=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-m", "polyforge", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def snapshot(root: Path) -> dict[str, str]:
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob("*")
        if p.is_file()
    }


class CLIAcceptanceTests(unittest.TestCase):
    def test_help_exposes_pipeline_and_capability_commands(self) -> None:
        result = cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in (
            "capability",
            "compile-contract",
            "build",
            "repair",
            "benchmark",
            "inspect-project",
            "mcp",
        ):
            self.assertIn(name, result.stdout)

    def test_version_runs_without_model_credentials(self) -> None:
        result = cli("--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("0.0.1", result.stdout)

    def test_catalog_lists_only_available_executable_capabilities(self) -> None:
        result = cli("capability", "list", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        body = json.loads(result.stdout)
        self.assertEqual(body["status"], "PASS")
        self.assertEqual(body["game_status"], "PARTIAL")
        self.assertEqual(
            [c["id"] for c in body["data"]["capabilities"]],
            [
                CAPABILITY,
                "contract.manifest.validate.v1",
                "contract.scene.compile.v1",
                "plan.scene.v1",
                "mesh.robot.modular.v1",
                "mesh.props.crate.v1",
                "mesh.architecture.wall.v1",
                "mesh.architecture.doorway.v1",
                "mesh.environment.tile.v1",
                "audit.static.multiview.v1",
                "unity.scene.static.v1",
            ],
        )

    def test_show_exposes_schema_and_requirements(self) -> None:
        result = cli("capability", "show", CAPABILITY, "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        capability = json.loads(result.stdout)["data"]["capability"]
        self.assertEqual(capability["runner"], "python.registry_validator")
        self.assertEqual(capability["requires"], ["python>=3.11"])

    def test_unknown_capability_is_invalid_input(self) -> None:
        result = cli("capability", "show", "mesh.imaginary.v1", "--json")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "FAIL")

    def test_unimplemented_pipeline_is_explicitly_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            before = snapshot(root)
            result = cli("build", "--workspace", str(root), "--through", "S5", "--json")
            self.assertEqual(result.returncode, 5, result.stderr)
            body = json.loads(result.stdout)
            self.assertEqual(body["status"], "NOT_RUN")
            self.assertEqual(body["game_status"], "PARTIAL")
            self.assertEqual(snapshot(root), before)

    def test_parser_errors_are_machine_readable(self) -> None:
        for args in (
            ("report", "--workspace", ".", "--json"),
            ("build", "--workspace", ".", "--through", "stage3", "--json"),
            ("capability", "show", "--json"),
            ("--bogus", "--json"),
        ):
            with self.subTest(args=args):
                result = cli(*args)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)["error_code"], "PF-INPUT-CLI")

    def test_capability_run_validates_good_fixture_and_returns_digest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="PolyForge Unicode Δ ") as directory:
            root = Path(directory)
            data = (ROOT / "tests/fixtures/capability_valid.json").read_text("utf-8")
            source = root / "input.json"
            source.write_text(data, encoding="utf-8")
            before = snapshot(root)
            result = cli(
                "capability",
                "run",
                CAPABILITY,
                "--input",
                str(source),
                "--workspace",
                str(root),
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            body = json.loads(result.stdout)
            self.assertEqual(body["data"]["validated_capability_id"], "mesh.robot.modular.v1")
            self.assertEqual(len(body["input_digest"]), 64)
            self.assertEqual(body["evaluated_test_status"], "NOT_RUN")
            self.assertEqual(body["game_status"], "PARTIAL")
            self.assertEqual(snapshot(root), before)

    def test_invalid_input_and_dry_run_leave_workspace_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.json"
            for content, flag, expected in (
                ('{"id":"bad"}', (), 2),
                ('{"id":NaN}', (), 2),
                ('{"id":"a","id":"b"}', (), 2),
                ("[]", (), 2),
                (
                    (ROOT / "tests/fixtures/capability_valid.json").read_text("utf-8"),
                    ("--dry-run",),
                    0,
                ),
            ):
                source.write_text(content, encoding="utf-8")
                before = snapshot(root)
                result = cli(
                    "capability",
                    "run",
                    CAPABILITY,
                    "--input",
                    str(source),
                    "--workspace",
                    str(root),
                    *flag,
                    "--json",
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                body = json.loads(result.stdout)
                if flag:
                    self.assertEqual(body["data"]["planned_writes"], [])
                    self.assertEqual(body["artifact_ids"], [])
                self.assertEqual(snapshot(root), before)

    def test_capability_refuses_input_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "managed"
            workspace.mkdir()
            source = root / "outside.json"
            source.write_text("{}", encoding="utf-8")
            result = cli(
                "capability",
                "run",
                CAPABILITY,
                "--input",
                str(source),
                "--workspace",
                str(workspace),
                "--json",
            )
            self.assertEqual(result.returncode, 4, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "BLOCKED")

    def test_input_io_error_is_structured(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = cli(
                "capability",
                "run",
                CAPABILITY,
                "--input",
                str(Path(directory) / "absent.json"),
                "--workspace",
                directory,
                "--json",
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "FAIL")

    def test_format_json_and_json_flag_are_consistent(self) -> None:
        first = cli("capability", "list", "--format", "json")
        second = cli("capability", "list", "--json")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)["data"], json.loads(second.stdout)["data"])


class ContractAcceptanceTests(unittest.TestCase):
    def test_all_error_categories_have_unambiguous_exit_codes(self) -> None:
        from polyforge.contracts.results import ErrorKind, failure

        expected = {
            "INVALID_INPUT": 2,
            "MISSING_DEPENDENCY": 3,
            "POLICY_DENIED": 4,
            "PRODUCER_FAILURE": 5,
            "CONTRACT_FAILURE": 6,
            "TEST_FAILURE": 7,
            "RETRY_EXHAUSTED": 8,
            "INTERRUPTED": 9,
        }
        for name, code in expected.items():
            with self.subTest(name=name):
                result = failure(ErrorKind[name], "PF-TEST", "Expected failure")
                self.assertEqual(result.exit_code, code)
                self.assertNotEqual(result.status, "PASS")

    def test_results_cannot_disguise_failures_as_success(self) -> None:
        from polyforge.contracts.results import Result

        for status, code in (
            ("FAIL", 0),
            ("BLOCKED", 0),
            ("NOT_RUN", 0),
            ("REVIEW", 0),
            ("PASS", 7),
            ("pass", 0),
            ("FAIL", 1),
        ):
            with self.subTest(status=status, code=code), self.assertRaises(ValueError):
                Result(status=status, exit_code=code)

    def test_registry_rejects_missing_fields_unknown_fields_and_duplicate_ids(self) -> None:
        from polyforge.capabilities.registry import validate_registry
        from polyforge.contracts.validation import InputError

        good = json.loads((ROOT / "tests/fixtures/capability_valid.json").read_text("utf-8"))
        self.assertEqual(validate_registry([good])[0]["id"], "mesh.robot.modular.v1")
        for values in (
            [{}],
            [good, good],
            [{**good, "surprise": "python code"}],
            [{**good, "input_schema": "../../escape.json"}],
            [{**good, "version": "latest"}],
        ):
            with self.subTest(values=values), self.assertRaises(InputError):
                validate_registry(values)

    def test_model_free_capability_obeys_protocol_and_context_policy(self) -> None:
        from polyforge.capabilities.protocol import Capability, RunContext
        from polyforge.capabilities.registry import RegistryValidator
        from polyforge.contracts.validation import InputError

        with tempfile.TemporaryDirectory() as directory:
            context = RunContext(workspace=Path(directory), dry_run=True)
            self.assertFalse(context.allow_network)
            self.assertEqual(context.security_scope, "TRUSTED_LOCAL")
            self.assertFalse(context.isolation_verified)
            self.assertIsInstance(RegistryValidator(), Capability)
            value = json.loads((ROOT / "tests/fixtures/capability_valid.json").read_text("utf-8"))
            result = RegistryValidator().execute(value, context)
            self.assertEqual(result.status, "PASS")
            with self.assertRaises(InputError):
                RunContext(workspace=Path(directory), security_scope="SANDBOXED_UNTRUSTED")

    def test_no_evaluator_is_not_a_passing_grade(self) -> None:
        from polyforge.benchmark.protocol import EvaluationRequest, UnavailableEvaluator

        result = UnavailableEvaluator().grade(
            EvaluationRequest(
                task_id="arena_public",
                original_brief_sha256="a" * 64,
                artifact_root=ROOT,
                task_type="COMPLETE_GAME_3D",
            )
        )
        self.assertEqual(result.status, "BLOCKED")
        self.assertEqual(result.game_status, "PARTIAL")
        self.assertEqual(result.exit_code, 3)


if __name__ == "__main__":
    unittest.main()
