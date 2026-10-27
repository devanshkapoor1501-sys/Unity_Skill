"""Model-free manifest, recipe, semantic compiler and invariant contracts."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from test_foundation import ROOT, cli, snapshot

from polyforge.contracts.validation import InputError, canonical_digest


def arena(root: Path) -> dict:
    source = ROOT / "examples/simple_arena"
    shutil.copytree(source, root, dirs_exist_ok=True)
    return json.loads((root / "game_manifest.json").read_text("utf-8"))


def save(root: Path, manifest: dict) -> None:
    (root / "game_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class ManifestTests(unittest.TestCase):
    def test_recipe_binding_duplicates_and_input_budgets_are_enforced(self) -> None:
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            path = root / "recipes/robot_a.json"
            recipe = json.loads(path.read_text())
            cases = [
                {**recipe, "asset_id": "crate_a"},
                {**recipe, "modules": recipe["modules"] * 2},
                {**recipe, "sockets": recipe["sockets"] * 2},
                {**recipe, "sockets": [{**recipe["sockets"][0], "module_id": "absent"}]},
            ]
            for case in cases:
                path.write_text(json.dumps(case))
                with self.subTest(case=case), self.assertRaises(InputError):
                    load_manifest(root / "game_manifest.json")
            path.write_text(json.dumps(recipe))
            brief = root / "brief.md"
            for content in (b"x" * 262145, b"\xff"):
                brief.write_bytes(content)
                with self.assertRaises(InputError):
                    load_manifest(root / "game_manifest.json")
            value.pop("intent")
            brief.unlink()
            save(root, value)
            self.assertIsNone(load_manifest(root / "game_manifest.json").brief)
            with (root / "oversize.png").open("wb") as stream:
                stream.truncate(33_554_433)
            value["materials"][0]["textures"] = [
                {"kind": "base_color", "color_space": "srgb", "path": "oversize.png"}
            ]
            save(root, value)
            with self.assertRaises(InputError):
                load_manifest(root / "game_manifest.json")

    def test_named_golden_contract_fixtures(self) -> None:
        from polyforge.contracts.manifest import load_manifest

        cases = json.loads((ROOT / "tests/fixtures/manifests/cases.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = arena(root)
            for case in cases:
                value = copy.deepcopy(original)
                for parts, replacement in case["patches"]:
                    target = value
                    for part in parts[:-1]:
                        target = target[part]
                    target[parts[-1]] = replacement
                save(root, value)
                with self.subTest(case=case["id"]):
                    if case["valid"]:
                        self.assertEqual(load_manifest(root / "game_manifest.json").data, value)
                    else:
                        with self.assertRaises(InputError):
                            load_manifest(root / "game_manifest.json")

    def test_public_arena_roundtrips_and_orders_dependencies(self) -> None:
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = arena(root)
            model = load_manifest(root / "game_manifest.json")
            self.assertEqual(json.loads(model.canonical_json()), original)
            self.assertEqual(set(model.asset_order), {"ground_a", "crate_a", "robot_a"})
            self.assertEqual(model.digest, canonical_digest(original))
            self.assertEqual(len(model.recipe_digests), 3)

    def test_eight_negative_manifest_classes_fail_with_a_field_location(self) -> None:
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = arena(root)
            invalid = []
            for field, value in (("schema_version", "2.0.0"), ("unknown_script", "exec('bad')")):
                changed = copy.deepcopy(original)
                changed[field] = value
                invalid.append(changed)
            for mutate in (
                lambda m: m["assets"].append(copy.deepcopy(m["assets"][0])),
                lambda m: m["assets"][0].update(dependencies=["absent"]),
                lambda m: m["assets"][0].update(dependencies=["crate_a"])
                or m["assets"][1].update(dependencies=["ground_a"]),
                lambda m: m["assets"][0].update(material_ids=["missing_material"]),
                lambda m: m["assets"][0].update(target_size_m=[1, 0, 1]),
                lambda m: m["actors"][0].update(spawn_xyz=[10000, 0, 0]),
                lambda m: m["assets"][0].update(recipe="../escape.json"),
                lambda m: m["assets"][0].update(recipe="C:/escape.json"),
                lambda m: m["materials"][0].update(metallic=1.1),
                lambda m: m["assets"][0].update(id="ground_a\n"),
            ):
                changed = copy.deepcopy(original)
                mutate(changed)
                invalid.append(changed)
            for changed in invalid:
                save(root, changed)
                with self.subTest(manifest=changed), self.assertRaises(InputError) as error:
                    load_manifest(root / "game_manifest.json")
                self.assertIn("$", str(error.exception))

    def test_recipe_files_missing_case_colliding_and_cyclic_modules_are_rejected(self) -> None:
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = arena(root)
            for recipe in (
                "recipes/missing.json",
                "recipes/../robot_a.json",
                "recipes\\robot_a.json",
            ):
                changed = copy.deepcopy(original)
                changed["assets"][0]["recipe"] = recipe
                save(root, changed)
                with self.subTest(recipe=recipe), self.assertRaises(InputError):
                    load_manifest(root / "game_manifest.json")
            changed = copy.deepcopy(original)
            changed["assets"][1]["recipe"] = "recipes/GROUND_A.json"
            save(root, changed)
            with self.assertRaises(InputError):
                load_manifest(root / "game_manifest.json")
            save(root, original)
            path = root / "recipes/robot_a.json"
            recipe = json.loads(path.read_text())
            recipe["modules"] = [
                {"id": "a", "primitive": "cube", "parent": "b"},
                {"id": "b", "primitive": "cube", "parent": "a"},
            ]
            path.write_text(json.dumps(recipe))
            with self.assertRaises(InputError):
                load_manifest(root / "game_manifest.json")

    def test_minor_schema_version_is_explicitly_compatible_and_unknown_major_has_hint(self) -> None:
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            value["schema_version"] = "1.1.0"
            save(root, value)
            self.assertEqual(
                load_manifest(root / "game_manifest.json").data["schema_version"], "1.1.0"
            )
            value["schema_version"] = "3.0.0"
            save(root, value)
            with self.assertRaisesRegex(InputError, "migration"):
                load_manifest(root / "game_manifest.json")


class CompilerTests(unittest.TestCase):
    def test_contract_has_stable_ids_basis_bindings_and_never_accepts_a_game(self) -> None:
        from polyforge.compiler.contract_compiler import compile_contract
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arena(root)
            model = load_manifest(root / "game_manifest.json")
            first = compile_contract(model)
            second = compile_contract(model)
            self.assertEqual(first, second)
            self.assertEqual(
                first["scene_contract"]["coordinate_basis"], {"up": "Y", "forward": "Z"}
            )
            ids = [o["id"] for o in first["scene_contract"]["objects"]]
            self.assertIn("asset:robot_a", ids)
            self.assertIn("actor:enemy_01", ids)
            self.assertEqual(len(ids), len(set(ids)))
            coverage = first["requirement_coverage"]
            self.assertEqual(coverage["game_status"], "PARTIAL")
            self.assertEqual(coverage["independently_verified_features_total"], 0)
            self.assertTrue(coverage["blocked_requirements"])
            self.assertEqual(first["feature_contract"]["authority"], "DEVELOPMENT_ONLY")

    def test_explicit_unknown_features_and_missing_annotations_are_not_silently_satisfied(
        self,
    ) -> None:
        from polyforge.compiler.contract_compiler import compile_contract
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            value["intent"]["requirements"][0]["feature_id"] = "stealth.sound_alert.v1"
            save(root, value)
            result = compile_contract(load_manifest(root / "game_manifest.json"))
            self.assertEqual(
                result["feature_contract"]["requirements"][0]["support_state"], "UNSUPPORTED"
            )
            value.pop("intent")
            save(root, value)
            result = compile_contract(load_manifest(root / "game_manifest.json"))
            self.assertIn(
                "unannotated_brief", result["requirement_coverage"]["unresolved_requirements"]
            )

    def test_incompatible_movement_ports_are_rejected(self) -> None:
        from polyforge.compiler.contract_compiler import compile_contract
        from polyforge.contracts.manifest import load_manifest

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            original = value["intent"]["requirements"][0]
            for name in ("movement.character_controller.v1", "movement.rigidbody.v1"):
                value["intent"]["requirements"].append(
                    {**original, "id": name.split(".")[1], "feature_id": name}
                )
            save(root, value)
            with self.assertRaisesRegex(InputError, "incompatible"):
                compile_contract(load_manifest(root / "game_manifest.json"))

    def test_normalized_handoff_catches_scale_socket_material_and_missing_binding(self) -> None:
        from polyforge.invariants.handoff import check_handoff

        contract = {
            "objects": [
                {
                    "id": "asset:robot_a",
                    "kind": "asset",
                    "bounds_m": [1, 1.8, 0.8],
                    "material_ids": ["metal_blue"],
                    "socket_ids": ["hand_l"],
                }
            ]
        }
        good = {
            "coordinate_basis": {"up": "Y", "forward": "Z"},
            "meters_per_unit": 1,
            "objects": [
                {
                    "id": "asset:robot_a",
                    "bounds_m": [1, 1.8, 0.8],
                    "material_ids": ["metal_blue"],
                    "socket_ids": ["hand_l"],
                    "prefab_id": "prefab:robot_a",
                }
            ],
        }
        self.assertEqual(check_handoff(contract, good, good)["status"], "PASS")
        bad = copy.deepcopy(good)
        bad["objects"][0].update(
            bounds_m=[100, 180, 80], socket_ids=[], material_ids=[], prefab_id=""
        )
        result = check_handoff(contract, good, bad)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(
            {"scale", "socket", "material", "binding"}.issubset(
                {issue["category"] for issue in result["issues"]}
            )
        )
        self.assertTrue(result["evidence_graph"]["edges"])


class PlannerTests(unittest.TestCase):
    def test_material_changes_leave_geometry_fingerprints_unchanged(self) -> None:
        from polyforge.contracts.manifest import load_manifest
        from polyforge.planner.plans import build_plan, changed_tasks

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            first = build_plan(load_manifest(root / "game_manifest.json"))
            value["materials"][0]["roughness"] = 0.2
            save(root, value)
            second = build_plan(load_manifest(root / "game_manifest.json"))
            affected = changed_tasks(first, second)
            self.assertIn("material:metal_blue", affected)
            self.assertIn("verify:scene", affected)
            self.assertFalse(
                any(name.startswith("mesh:") or name == "runtime:gameplay" for name in affected)
            )
            self.assertTrue(all(task["execution_status"] == "NOT_RUN" for task in second["tasks"]))

    def test_collider_changes_invalidate_scenarios_without_rebuilding_mesh(self) -> None:
        from polyforge.contracts.manifest import load_manifest
        from polyforge.planner.plans import build_plan, changed_tasks

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            first = build_plan(load_manifest(root / "game_manifest.json"))
            value["assets"][0]["collider"] = "mesh"
            save(root, value)
            second = build_plan(load_manifest(root / "game_manifest.json"))
            affected = changed_tasks(first, second)
            self.assertIn("verify:scene", affected)
            self.assertNotIn("mesh:ground_a", affected)


class PhaseTwoCLITests(unittest.TestCase):
    def test_validate_and_dry_run_are_read_only_and_compile_writes_derived_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            arena(root)
            before = snapshot(root)
            for args in (
                ("validate", "--workspace", directory),
                ("plan", "--workspace", directory, "--dry-run"),
                ("compile-contract", "--manifest", str(root / "game_manifest.json"), "--dry-run"),
            ):
                result = cli(*args, "--json")
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                self.assertEqual(json.loads(result.stdout)["game_status"], "PARTIAL")
                self.assertEqual(snapshot(root), before)
            result = cli(
                "compile-contract", "--manifest", str(root / "game_manifest.json"), "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            for name in (
                "scene_contract.json",
                "feature_contract.json",
                "requirement_coverage.json",
            ):
                self.assertTrue((root / name).is_file(), name)
            self.assertTrue((root / ".polyforge/original_prompt.txt").is_file())
            self.assertEqual(
                (root / ".polyforge/original_prompt.txt").read_bytes(),
                (root / "brief.md").read_bytes(),
            )
            result = cli("plan", "--workspace", directory, "--json")
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertTrue((root / "plan.json").is_file())

    def test_invalid_manifest_has_no_side_effects_for_all_phase_two_commands(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            value = arena(root)
            value["assets"][0]["dependencies"] = ["absent"]
            save(root, value)
            before = snapshot(root)
            for args in (
                ("validate", "--workspace", directory),
                ("plan", "--workspace", directory),
                ("compile-contract", "--manifest", str(root / "game_manifest.json")),
            ):
                result = cli(*args, "--json")
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
