"""Scenario, cache, and provenance behavior without game-tool execution."""

from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_foundation import ROOT, cli, snapshot
from test_phase2_contracts import arena, save

from polyforge.contracts.validation import InputError


class ScenarioTests(unittest.TestCase):
    def test_actions_timing_and_entity_references_are_checked(self) -> None:
        from polyforge.scenarios.schema import validate_scenario

        value = {
            "schema_version": "1.0.0",
            "id": "movement",
            "seed": 42,
            "setup": {"scene_id": "main", "entity_ids": ["enemy_01"]},
            "steps": [{"action": "move", "actor_id": "enemy_01", "direction": [1, 0], "ticks": 20}],
            "expected": [{"event": "actor_moved", "count_gte": 1}],
            "tolerance": {"position_m": 0.02, "time_frames": 2},
            "fixed_delta_seconds": 0.02,
            "timeout_s": 5,
        }
        self.assertEqual(validate_scenario(value, scene_id="main", entity_ids={"enemy_01"}), value)
        for field, replacement in (
            ("steps", [{"action": "eval", "ticks": 1}]),
            ("steps", [{"action": "move", "ticks": 1, "actor_id": "absent", "direction": [0, 1]}]),
            ("steps", [{"action": "move", "ticks": 1, "actor_id": "enemy_01"}]),
            ("timeout_s", 0.01),
            ("setup", {"scene_id": "other", "entity_ids": []}),
            ("setup", {"scene_id": "main", "entity_ids": ["absent"]}),
            ("fixed_delta_seconds", float("inf")),
        ):
            with self.subTest(field=field), self.assertRaises(InputError):
                validate_scenario(
                    {**value, field: replacement}, scene_id="main", entity_ids={"enemy_01"}
                )


class CacheTests(unittest.TestCase):
    def test_rig_changes_invalidate_sprite_bakes_and_scene(self) -> None:
        from polyforge.contracts.manifest import load_manifest
        from polyforge.planner.plans import build_plan, changed_tasks

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            value["animations"] = [
                {
                    "id": "walk",
                    "kind": "rig",
                    "asset_id": "robot_a",
                    "action_id": "walk",
                    "fps": 24,
                    "frames": [0, 24],
                }
            ]
            value["assets"][2]["animation_ids"] = ["walk"]
            value["spritesheets"] = [
                {
                    "id": "walk_sheet",
                    "kind": "bake",
                    "asset_id": "robot_a",
                    "frame_indices": [0, 4, 8, 12, 16, 20],
                    "fps": 6,
                    "pixels_per_unit": 100,
                    "pivot": [0.5, 0],
                }
            ]
            save(root, value)
            first = build_plan(load_manifest(root / "game_manifest.json"))
            value["animations"][0]["frames"][1] = 48
            save(root, value)
            second = build_plan(load_manifest(root / "game_manifest.json"))
            affected = changed_tasks(first, second)
            self.assertIn("sprite:walk_sheet", affected)
            self.assertIn("scene:assemble", affected)
            self.assertNotIn("mesh:robot_a", affected)
            value["materials"][0]["roughness"] = 0.17
            save(root, value)
            third = build_plan(load_manifest(root / "game_manifest.json"))
            affected = changed_tasks(second, third)
            self.assertIn("sprite:walk_sheet", affected)
            self.assertNotIn("mesh:robot_a", affected)

    def test_hits_require_validated_existing_matching_artifacts(self) -> None:
        from polyforge.planner.cache import cache_hit
        from polyforge.security.paths import WorkspacePolicy

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task = {"id": "mesh:robot_a", "input_digest": "a" * 64}
            output = root / "mesh.bin"
            output.write_bytes(b"geometry fixture")
            entry = {
                "input_digest": "a" * 64,
                "status": "PASS",
                "outputs": [
                    {
                        "relative_path": "mesh.bin",
                        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                        "bytes": output.stat().st_size,
                        "validated": True,
                    }
                ],
            }
            policy = WorkspacePolicy(root)
            self.assertTrue(cache_hit(task, entry, policy))
            for mutate in (
                lambda e: e.update(status="NOT_RUN"),
                lambda e: e.update(input_digest="b" * 64),
                lambda e: e["outputs"][0].update(validated=False),
                lambda e: e.update(outputs=[]),
                lambda e: e["outputs"][0].update(relative_path="../outside.bin"),
            ):
                changed = copy.deepcopy(entry)
                mutate(changed)
                self.assertFalse(cache_hit(task, changed, policy))
            output.write_bytes(b"corrupt")
            self.assertFalse(cache_hit(task, entry, policy))
            output.unlink()
            self.assertFalse(cache_hit(task, entry, policy))

    def test_plan_order_and_stage_dependencies_are_consistent(self) -> None:
        from polyforge.contracts.manifest import load_manifest
        from polyforge.planner.plans import build_plan

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arena(root)
            seen = {}
            for task in build_plan(load_manifest(root / "game_manifest.json"))["tasks"]:
                for dependency in task["dependencies"]:
                    self.assertIn(dependency, seen)
                    self.assertLessEqual(seen[dependency], task["stage"])
                seen[task["id"]] = task["stage"]


class ProvenanceTests(unittest.TestCase):
    def test_input_identity_covers_recipe_bytes_beyond_manifest_document(self) -> None:
        from polyforge.compiler.commands import manifest_command

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arena(root)
            manifest = root / "game_manifest.json"
            original = manifest.read_bytes()
            first = manifest_command(manifest, "compile", dry_run=True)
            path = root / "recipes/robot_a.json"
            recipe = json.loads(path.read_text())
            recipe["max_polygons"] -= 1
            path.write_text(json.dumps(recipe))
            second = manifest_command(manifest, "compile", dry_run=True)
            self.assertEqual(manifest.read_bytes(), original)
            self.assertNotEqual(first.input_digest, second.input_digest)
            self.assertIn("input_fingerprints", second.data["scene_contract"])

    def test_derived_outputs_cannot_overwrite_manifest_recipe_or_texture_inputs(self) -> None:
        for kind in ("manifest", "recipe", "texture", "brief", "lock"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                value = arena(root)
                manifest = root / "game_manifest.json"
                if kind == "manifest":
                    manifest = root / "scene_contract.json"
                    manifest.write_text(json.dumps(value), encoding="utf-8")
                elif kind in {"recipe", "lock"}:
                    target = (
                        "feature_contract.json"
                        if kind == "recipe"
                        else ".polyforge/locks/planning.lock"
                    )
                    (root / target).parent.mkdir(parents=True, exist_ok=True)
                    (root / target).write_bytes((root / value["assets"][0]["recipe"]).read_bytes())
                    value["assets"][0]["recipe"] = target
                    save(root, value)
                elif kind == "texture":
                    (root / "requirement_coverage.json").write_bytes(b"texture fixture")
                    value["materials"][0]["textures"] = [
                        {
                            "kind": "base_color",
                            "color_space": "srgb",
                            "path": "requirement_coverage.json",
                        }
                    ]
                    save(root, value)
                else:
                    (root / "scene_contract.json").write_bytes((root / "brief.md").read_bytes())
                    value["intent"]["brief_path"] = "scene_contract.json"
                    save(root, value)
                before = snapshot(root)
                for flags in ([], ["--dry-run"]):
                    result = cli("compile-contract", "--manifest", str(manifest), *flags, "--json")
                    self.assertEqual(result.returncode, 2, result.stdout)
                    self.assertEqual(snapshot(root), before)

    def test_handoff_rejects_malformed_contracts_and_vacuous_success(self) -> None:
        from polyforge.invariants.handoff import check_handoff

        good = {
            "coordinate_basis": {"up": "Y", "forward": "Z"},
            "meters_per_unit": 1,
            "objects": [
                {
                    "id": "asset:crate",
                    "bounds_m": [1, 1, 1],
                    "material_ids": [],
                    "socket_ids": [],
                    "prefab_id": "crate",
                }
            ],
        }
        asset = {
            "id": "asset:crate",
            "kind": "asset",
            "bounds_m": [1, 1, 1],
            "material_ids": [],
            "socket_ids": [],
        }
        for objects in (
            [],
            [{"kind": "asset", "bounds_m": [1, 1, 1]}],
            [asset, asset],
            [{**asset, "material_ids": "bad"}],
        ):
            with self.subTest(objects=objects), self.assertRaises(InputError):
                check_handoff({"objects": objects}, good, good)
        bad = copy.deepcopy(good)
        bad["objects"][0]["prefab_id"] = 123
        with self.assertRaises(InputError):
            check_handoff({"objects": [asset]}, good, bad)

    def test_typed_texture_sprite_and_animation_declarations_are_validated(self) -> None:
        from polyforge.contracts.manifest import load_manifest
        from polyforge.planner.plans import build_plan, changed_tasks

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            (root / "textures").mkdir()
            texture = root / "textures/albedo.png"
            texture.write_bytes(b"fixture image bytes")
            value["materials"][0]["textures"] = [
                {"kind": "base_color", "path": "textures/albedo.png", "color_space": "srgb"}
            ]
            value["spritesheets"] = [
                {
                    "id": "robot_sprite",
                    "kind": "bake",
                    "asset_id": "robot_a",
                    "frame_indices": [0, 5, 10, 15, 20, 25],
                    "fps": 12,
                    "pixels_per_unit": 100,
                    "pivot": [0.5, 0.5],
                }
            ]
            value["animations"] = [
                {
                    "id": "robot_idle",
                    "kind": "rig",
                    "asset_id": "robot_a",
                    "action_id": "idle",
                    "fps": 24,
                    "frames": [0, 24],
                }
            ]
            value["assets"][2]["animation_ids"] = ["robot_idle"]
            save(root, value)
            first = build_plan(load_manifest(root / "game_manifest.json"))
            self.assertIn("animation:robot_idle", {task["id"] for task in first["tasks"]})
            self.assertIn("sprite:robot_sprite", {task["id"] for task in first["tasks"]})
            texture.write_bytes(b"changed image fixture")
            second = build_plan(load_manifest(root / "game_manifest.json"))
            affected = changed_tasks(first, second)
            self.assertIn("material:metal_blue", affected)
            self.assertNotIn("mesh:robot_a", affected)
            value["animations"][0]["frames"] = [24, 0]
            save(root, value)
            with self.assertRaises(InputError):
                load_manifest(root / "game_manifest.json")

    def test_new_workspace_template_validates_and_core_capabilities_run_without_tools(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "game"
            self.assertEqual(cli("init", str(root), "--json").returncode, 0)
            result = cli("validate", "--workspace", str(root), "--json")
            self.assertEqual(result.returncode, 0, result.stdout)
            before = snapshot(root)
            for capability in (
                "contract.manifest.validate.v1",
                "contract.scene.compile.v1",
                "plan.scene.v1",
            ):
                result = cli(
                    "capability",
                    "run",
                    capability,
                    "--workspace",
                    str(root),
                    "--input",
                    "game_manifest.json",
                    "--json",
                )
                self.assertEqual(result.returncode, 0, result.stdout)
                self.assertEqual(snapshot(root), before)
                if capability == "contract.scene.compile.v1":
                    original_brief = (ROOT / "examples/simple_arena/brief.md").read_text("utf-8")
                    for requirement in json.loads(result.stdout)["data"]["feature_contract"][
                        "requirements"
                    ]:
                        span = requirement["source_span"]
                        self.assertEqual(
                            requirement["source_text"], original_brief[span["start"] : span["end"]]
                        )

    def test_changed_frozen_brief_is_refused_without_mutating_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arena(root)
            result = cli(
                "compile-contract", "--manifest", str(root / "game_manifest.json"), "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            with (root / "brief.md").open("a", encoding="utf-8") as stream:
                stream.write("\nExtra mandatory stealth mechanic.\n")
            before = snapshot(root)
            result = cli("plan", "--workspace", directory, "--json")
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(snapshot(root), before)
            result = cli(
                "capability",
                "run",
                "contract.scene.compile.v1",
                "--input",
                "game_manifest.json",
                "--workspace",
                directory,
                "--json",
            )
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(snapshot(root), before)

    def test_texture_case_collisions_and_unknown_recipe_interfaces_are_rejected(self) -> None:
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            (root / "textures").mkdir()
            (root / "textures/color.png").write_bytes(b"fixture")
            value["materials"][0]["textures"] = [
                {"kind": "base_color", "path": "textures/color.png", "color_space": "srgb"},
                {"kind": "normal", "path": "textures/COLOR.png", "color_space": "linear"},
            ]
            save(root, value)
            with self.assertRaises(InputError):
                load_manifest(root / "game_manifest.json")
            value["materials"][0].pop("textures")
            save(root, value)
            recipe = root / "recipes/robot_a.json"
            content = json.loads(recipe.read_text())
            content["capability_id"] = "unrecognized.runner.v1"
            recipe.write_text(json.dumps(content))
            with self.assertRaises(InputError):
                load_manifest(root / "game_manifest.json")

    def test_corrupt_previous_plan_is_typed_error_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arena(root)
            (root / "plan.json").write_text('{"tasks":[{}]}', encoding="utf-8")
            before = snapshot(root)
            result = cli("plan", "--workspace", directory, "--json")
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertEqual(snapshot(root), before)

    def test_source_ranges_bindings_and_animation_references_are_checked(self) -> None:
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = arena(root)
            for mutate in (
                lambda m: m["intent"]["requirements"][0].update(
                    source_span={"start": 0, "end": 999999}
                ),
                lambda m: m["intent"]["requirements"][0].update(binding_ids=["missing"]),
                lambda m: m["intent"]["requirements"].append(
                    copy.deepcopy(m["intent"]["requirements"][0])
                ),
                lambda m: m["assets"][0].update(animation_ids=["missing"]),
            ):
                value = copy.deepcopy(original)
                mutate(value)
                save(root, value)
                with self.subTest(value=value), self.assertRaises(InputError):
                    load_manifest(root / "game_manifest.json")

    def test_public_stealth_and_dungeon_cases_are_unsupported(self) -> None:
        from polyforge.compiler.contract_compiler import compile_contract
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = arena(root)
            for name in ("stealth", "dungeon"):
                fixture = json.loads((ROOT / f"tests/fixtures/intent/{name}.json").read_text())
                value = copy.deepcopy(original)
                (root / "brief.md").write_text(fixture["brief"], encoding="utf-8")
                value["intent"]["requirements"] = fixture["requirements"]
                save(root, value)
                result = compile_contract(load_manifest(root / "game_manifest.json"))
                self.assertEqual(
                    result["feature_contract"]["requirements"][0]["support_state"], "UNSUPPORTED"
                )
                self.assertEqual(result["requirement_coverage"]["game_status"], "PARTIAL")


if __name__ == "__main__":
    unittest.main()
