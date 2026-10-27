"""Regression checks for schema, policy, and command-consistency boundaries."""

from __future__ import annotations

import contextlib
import io
import json
import math
import shlex
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_foundation import ROOT, cli


class BoundaryTests(unittest.TestCase):
    def test_equals_format_json_also_emits_json(self) -> None:
        result = cli("capability", "list", "--format=json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS")

    def test_deeply_nested_json_is_an_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "deep.json"
            source.write_text("[" * 20000 + "0" + "]" * 20000, encoding="utf-8")
            result = cli(
                "capability",
                "run",
                "contract.capability.validate.v1",
                "--input",
                str(source),
                "--workspace",
                directory,
                "--json",
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "FAIL")

    def test_oversized_integer_is_an_input_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "integer.json"
            source.write_text('{"n":' + "1" * 5000 + "}", encoding="utf-8")
            result = cli(
                "capability",
                "run",
                "contract.capability.validate.v1",
                "--input",
                str(source),
                "--workspace",
                directory,
                "--json",
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "FAIL")

    def test_unregistered_option_abbreviations_are_rejected(self) -> None:
        for option in ("--form=json", "--j"):
            with self.subTest(option=option):
                result = cli("capability", "list", option, "--json")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(json.loads(result.stdout)["error_code"], "PF-INPUT-CLI")

    def test_last_format_option_controls_successful_output(self) -> None:
        result = cli("capability", "list", "--format", "json", "--format", "human")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("PASS:"))
        result = cli("capability", "list", "--format", "human", "--format", "json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "PASS")

    def test_schema_identifiers_and_hashes_reject_trailing_newlines(self) -> None:
        from polyforge.contracts.results import Result
        from polyforge.contracts.validation import InputError, validate_schema

        descriptor = json.loads((ROOT / "tests/fixtures/capability_valid.json").read_text("utf-8"))
        for field in ("id", "version", "input_schema", "runner"):
            with self.subTest(field=field), self.assertRaises(InputError):
                validate_schema(
                    {**descriptor, field: descriptor[field] + "\n"}, "capability.schema.json"
                )
        task = json.loads((ROOT / "benchmarks/tasks/arena_development.json").read_text("utf-8"))
        for field in ("task_id", "original_brief_sha256"):
            with self.subTest(field=field), self.assertRaises(InputError):
                validate_schema({**task, field: task[field] + "\n"}, "benchmark_task.schema.json")
        with self.assertRaises(InputError):
            validate_schema(
                {**Result().to_dict(), "input_digest": "a" * 64 + "\n"}, "result.schema.json"
            )

    def test_input_limits_bad_encoding_and_nonfinite_hashes_fail_closed(self) -> None:
        from polyforge.contracts.validation import InputError, canonical_digest, load_json

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.json"
            for content in (b"\xff", b'"' + b"a" * 1_048_576 + b'"', b"{"):
                source.write_bytes(content)
                with self.subTest(content_length=len(content)), self.assertRaises(InputError):
                    load_json(source)
            with self.assertRaises(InputError):
                load_json(Path(directory))
        for value in (math.inf, {"value": object()}):
            with self.subTest(value=value), self.assertRaises(InputError):
                canonical_digest(value)
        self.assertEqual(
            canonical_digest({"a": 1, "b": 2}),
            "43258cff783fe7036d8a43033f830adfc60ec037382473548ac742b888292777",
        )

    def test_unknown_schema_is_not_loaded_from_a_user_path(self) -> None:
        from polyforge.contracts.validation import InputError, schema_document

        with self.assertRaises(InputError):
            schema_document("https://attacker.invalid/schema.json")

    def test_missing_validator_is_dependency_blocked(self) -> None:
        from polyforge.contracts.validation import InputError, validate_schema

        with (
            patch.dict("sys.modules", {"jsonschema": None}),
            self.assertRaises(InputError) as error,
        ):
            validate_schema({}, "capability.schema.json")
        self.assertEqual(error.exception.kind, 3)

    def test_policy_refuses_traversal_nonexistent_roots_and_resolved_escape(self) -> None:
        from polyforge.contracts.validation import InputError
        from polyforge.security.paths import workspace_input

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for workspace, value, expected in (
                (root, Path("../outside.json"), 4),
                (root / "absent", Path("input.json"), 2),
                (root / "managed", root / "outside.json", 4),
            ):
                with self.subTest(value=value), self.assertRaises(InputError) as error:
                    workspace_input(workspace, value)
                self.assertEqual(error.exception.kind, expected)

    def test_context_cannot_claim_network_or_isolation_and_rejects_invalid_budgets(self) -> None:
        from polyforge.capabilities.protocol import RunContext
        from polyforge.contracts.validation import InputError

        for kwargs in (
            {"allow_network": True},
            {"isolation_verified": True},
            {"timeout_seconds": 0},
            {"max_output_bytes": 0},
            {"retry_limit": -1},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(InputError):
                RunContext(workspace=ROOT, **kwargs)

    def test_result_schema_rejects_false_success_and_status_drift(self) -> None:
        from polyforge.contracts.results import ErrorKind, Result, failure
        from polyforge.contracts.validation import InputError, validate_schema

        good = Result().to_dict()
        validate_schema(good, "result.schema.json")
        for kind in ErrorKind:
            validate_schema(
                failure(kind, "PF-TEST", "Expected failure").to_dict(), "result.schema.json"
            )
        for mutation in (
            {"status": "BLOCKED", "exit_code": 0},
            {"status": "pass"},
            {"operation_status": "FAIL"},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(InputError):
                validate_schema({**good, **mutation}, "result.schema.json")
        for kwargs in (
            {"game_status": "accepted"},
            {"evaluated_test_status": "pending"},
            {"status": "BLOCKED", "exit_code": 7},
            {"status": "REVIEW", "exit_code": 3},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Result(**kwargs)
        validate_schema(
            failure(ErrorKind.POLICY_DENIED, "PF-TEST", "Review", status="REVIEW").to_dict(),
            "result.schema.json",
        )

    def test_benchmark_task_requires_category_and_matching_frozen_brief(self) -> None:
        from polyforge.contracts.validation import InputError, validate_schema

        task = json.loads((ROOT / "benchmarks/tasks/arena_development.json").read_text("utf-8"))
        validate_schema(task, "benchmark_task.schema.json")
        for mutation in (
            {"task_type": "GAME"},
            {"original_brief_sha256": "invented"},
            {"budgets": {"wall_seconds": 0}},
            {"hidden_answers": []},
        ):
            with self.subTest(mutation=mutation), self.assertRaises(InputError):
                validate_schema({**task, **mutation}, "benchmark_task.schema.json")

    def test_generated_command_examples_parse_and_unimplemented_commands_do_not_run(self) -> None:
        from polyforge.cli import build_parser, dispatch
        from polyforge.commands import COMMANDS

        fixture = json.loads((ROOT / "tests/fixtures/cli_commands.json").read_text("utf-8"))
        self.assertEqual(len(fixture["commands"]), len(COMMANDS))
        parser = build_parser()
        for example in fixture["commands"]:
            with self.subTest(argv=example["argv"]):
                args = parser.parse_args(example["argv"])
                if not example["implemented"]:
                    result = dispatch(args)
                    self.assertEqual(result.status, "NOT_RUN")
                    self.assertEqual(result.exit_code, 5)

    def test_readme_and_skill_commands_parse_and_execute(self) -> None:
        paths = (ROOT / "README.md", ROOT / ".agents/skills/polyforge/SKILL.md")
        for path in paths:
            commands = [
                line
                for line in path.read_text("utf-8").splitlines()
                if line.startswith("polyforge ")
            ]
            self.assertTrue(commands, str(path))
            for command in commands:
                with self.subTest(command=command):
                    result = cli(*shlex.split(command)[1:])
                    self.assertEqual(result.returncode, 0, result.stderr)

    def test_keyboard_interrupt_and_human_output_preserve_result_semantics(self) -> None:
        from polyforge.cli import main

        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(main(["capability", "list"]), 0)
        self.assertIn("game=PARTIAL", stream.getvalue())
        with (
            patch("polyforge.cli.dispatch", side_effect=KeyboardInterrupt),
            contextlib.redirect_stdout(io.StringIO()) as stream,
        ):
            self.assertEqual(main(["capability", "list", "--json"]), 9)
        self.assertEqual(json.loads(stream.getvalue())["status"], "FAIL")
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(main(["report", "--workspace", ".", "--run-id", "none"]), 5)
        self.assertIn("PF-CAPABILITY-NOT-IMPLEMENTED", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
