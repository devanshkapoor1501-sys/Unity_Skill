"""Asset-stage preflight, stage availability and dependency diagnostics."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from test_foundation import cli, snapshot


class BuildTests(unittest.TestCase):
    def test_invalid_build_configuration_makes_no_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "arena"
            self.assertEqual(cli("init", str(root), "--json").returncode, 0)
            (root / "polyforge.toml").write_text("[execution]\nretry_limit = -1\n")
            before = snapshot(root)
            for flags in (["--dry-run"], []):
                result = cli("build", "--workspace", str(root), "--through", "S2", *flags, "--json")
                self.assertEqual(result.returncode, 2, result.stdout[:300])
                self.assertEqual(snapshot(root), before)

    def test_effective_material_overrides_are_validated_before_any_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "arena"
            self.assertEqual(cli("init", str(root), "--json").returncode, 0)
            path = root / "game_manifest.json"
            value = json.loads(path.read_text())
            value["materials"] = [
                {**value["materials"][0], "id": f"material_{i}"} for i in range(17)
            ]
            value["assets"][0]["material_ids"] = [m["id"] for m in value["materials"]]
            for asset in value["assets"][1:]:
                asset["material_ids"] = ["material_0"]
            path.write_text(json.dumps(value))
            before = snapshot(root)
            for flags in (["--dry-run"], []):
                result = cli(
                    "build",
                    "--workspace",
                    str(root),
                    "--through",
                    "S2",
                    "--only",
                    "ground_a",
                    *flags,
                    "--json",
                )
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(snapshot(root), before)

    def test_invalid_context_budgets_are_rejected_before_execution(self) -> None:
        from polyforge.capabilities.protocol import RunContext
        from polyforge.contracts.validation import InputError

        for kwargs in (
            {"timeout_seconds": float("nan")},
            {"max_output_bytes": float("inf")},
            {"seed": -1},
            {"seed": True},
            {"retry_limit": 3},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(InputError):
                RunContext(Path.cwd(), **kwargs)

    def test_build_dry_run_validates_every_recipe_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "arena"
            self.assertEqual(cli("init", str(root), "--json").returncode, 0)
            before = snapshot(root)
            result = cli(
                "build", "--workspace", str(root), "--through", "S2", "--dry-run", "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(snapshot(root), before)
            recipe = root / "recipes/crate_a.json"
            content = json.loads(recipe.read_text())
            content["modules"][0]["attach_to"] = "absent"
            recipe.write_text(json.dumps(content))
            before = snapshot(root)
            result = cli(
                "build", "--workspace", str(root), "--through", "S2", "--only", "robot_a", "--json"
            )
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(snapshot(root), before)

    def test_ineligible_later_stage_stays_not_run(self) -> None:
        result = cli("resume", "--workspace", ".", "--run-id", "example", "--json")
        self.assertEqual(result.returncode, 5, result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "NOT_RUN")

    def test_wrong_tool_version_blocks_precheck_instead_of_claiming_success(self) -> None:
        from polyforge.blender.adapter import BlenderCapability
        from polyforge.capabilities.protocol import RunContext

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "polyforge.toml").write_text(
                "[tools]\nblender_executable = " + json.dumps(sys.executable) + "\n"
            )
            result = BlenderCapability("crate").execute(
                {
                    "schema_version": "1.0.0",
                    "asset_id": "crate",
                    "parameters": {"size_m": [1, 1, 1]},
                },
                RunContext(root),
            )
            self.assertEqual(result.exit_code, 3, result.to_dict())
            state = json.loads((root / f"runs/{result.run_id}/state.json").read_text())
            self.assertEqual(state["stages"]["S0"]["status"], "failed")
            self.assertEqual(state["stages"]["S2"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
