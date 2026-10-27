"""Offline recipe expansion and adversarial geometry report checks."""

from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from test_foundation import cli, snapshot

from polyforge.contracts.validation import InputError, canonical_digest


def request(asset: str = "robot_a", size: list[float] | None = None) -> dict:
    return {
        "schema_version": "1.0.0",
        "asset_id": asset,
        "parameters": {"size_m": size or [1, 1.8, 0.8]},
    }


class RecipeTests(unittest.TestCase):
    def test_nonfinite_producer_payload_is_contract_failure(self) -> None:
        from polyforge.blender.recipes import expand_recipe, validate_geometry

        recipe = expand_recipe("crate", request(), seed=42)
        with self.assertRaises(InputError) as error:
            validate_geometry(recipe, {"value": float("nan")})
        self.assertEqual(int(error.exception.kind), 6)

    def test_logical_faces_ignore_storage_order_but_preserve_winding_and_uv_binding(self) -> None:
        from polyforge.blender.worker import canonical_faces

        vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]]
        faces = [[0, 1, 2], [0, 2, 3]]
        uvs = [[[0, 0], [1, 0], [0, 1]], [[0, 0], [0, 1], [1, 1]]]
        first = canonical_faces(vertices, faces, uvs)
        self.assertEqual(
            first,
            canonical_faces(
                vertices,
                [[2, 3, 0], [1, 2, 0]],
                [[[0, 1], [1, 1], [0, 0]], [[1, 0], [0, 1], [0, 0]]],
            ),
        )
        self.assertNotEqual(first, canonical_faces(vertices, [[0, 2, 1], [0, 2, 3]], uvs))

    def test_five_recipes_expand_deterministically_with_real_semantic_parts(self) -> None:
        from polyforge.blender.recipes import RECIPES, expand_recipe, validate_recipe

        self.assertEqual(len(RECIPES), 5)
        for kind in RECIPES:
            first = expand_recipe(kind, request(), seed=42)
            self.assertEqual(first, expand_recipe(kind, request(), seed=42))
            self.assertEqual(validate_recipe(first), first)
            self.assertTrue(first["sockets"])
            self.assertEqual(first["pivot"], "base_center")
        robot = expand_recipe("robot", request(), seed=42)
        self.assertGreaterEqual(len(robot["modules"]), 12)
        self.assertTrue(any("attach_to" in module for module in robot["modules"]))
        larger = expand_recipe("robot", request(size=[2, 3, 1]), seed=42)
        self.assertNotEqual(canonical_digest(robot), canonical_digest(larger))

    def test_parameter_budgets_unknown_fields_and_impossible_doorways_fail(self) -> None:
        from polyforge.blender.recipes import expand_recipe

        for value in (
            {**request(), "python": "arbitrary code"},
            {**request(), "parameters": {"size_m": [1, 0, 1]}},
            {**request(), "parameters": {"size_m": [1, float("nan"), 1]}},
            {**request(), "parameters": {"size_m": [1, 2, 1], "repeat": 100000000}},
        ):
            with self.subTest(value=value), self.assertRaises(InputError):
                expand_recipe("robot", value, seed=42)
        for parameters in (
            {"size_m": [2, 3, 0.2], "opening_width_m": 3},
            {"size_m": [2, 3, 0.2], "opening_height_m": 3},
        ):
            with self.assertRaises(InputError):
                expand_recipe("doorway", {**request(), "parameters": parameters}, seed=42)

    def test_primitive_dsl_rejects_expansion_bombs_and_broken_attachments(self) -> None:
        from polyforge.blender.recipes import expand_recipe, validate_recipe

        recipe = expand_recipe("robot", request(), seed=42)
        for change in (
            lambda r: r.update(modules=r["modules"] * 300),
            lambda r: r["modules"][1].update(parent="absent"),
            lambda r: r["modules"][1].update(parent=r["modules"][1]["id"]),
            lambda r: r["modules"][1].update(attach_to="absent"),
            lambda r: r["modules"][0].update(material_id="missing"),
            lambda r: r["sockets"][0].update(module_id="absent"),
        ):
            value = copy.deepcopy(recipe)
            change(value)
            with self.subTest(value=value), self.assertRaises(InputError):
                validate_recipe(value)

    def test_geometry_diagnostics_refuse_broken_uv_reversed_sockets_and_degeneracy(self) -> None:
        from polyforge.blender.recipes import expand_recipe, validate_geometry

        recipe = expand_recipe("robot", request(), seed=42)
        good = {
            "schema_version": "1.0.0",
            "asset_id": "robot_a",
            "status": "PASS",
            "bounds_unity_m": [1, 1.8, 0.8],
            "polygon_count": 1200,
            "degenerate_faces": 0,
            "invalid_uv_faces": 0,
            "nonfinite_values": 0,
            "module_ids": [m["id"] for m in recipe["modules"]],
            "socket_ids": [s["id"] for s in recipe["sockets"]],
            "material_ids": [m["id"] for m in recipe["materials"]],
            "socket_positions_unity_m": {"hand_l": [-0.4, 0.5, 0], "hand_r": [0.4, 0.5, 0]},
            "pivot_unity_m": [0, 0, 0],
            "coordinate_basis": {"up": "Z", "forward": "-Y"},
            "meters_per_unit": 1,
            "minimum_native_m": [-0.5, -0.4, 0],
            "geometry_digest": "a" * 64,
        }
        validate_geometry(recipe, good)
        for change in (
            lambda r: r.update(invalid_uv_faces=1),
            lambda r: r.update(degenerate_faces=1),
            lambda r: r.update(nonfinite_values=1),
            lambda r: r.update(polygon_count=1000000),
            lambda r: r.update(bounds_unity_m=[1, 180, 0.8]),
            lambda r: r.update(module_ids=[]),
            lambda r: r.update(socket_ids=[]),
            lambda r: r.update(material_ids=[]),
            lambda r: r.update(minimum_native_m=[1.5, -0.4, 0]),
            lambda r: r.update(pivot_unity_m=[2, 0, 0]),
            lambda r: r.update(meters_per_unit=0.01),
            lambda r: r["socket_positions_unity_m"].update(hand_l=[0.4, 0.5, 0]),
        ):
            value = copy.deepcopy(good)
            change(value)
            with self.subTest(value=value), self.assertRaises(InputError) as error:
                validate_geometry(recipe, value)
            self.assertEqual(int(error.exception.kind), 6)

    def test_capability_dry_run_and_bad_recipe_make_no_workspace_changes(self) -> None:
        import json

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "request.json"
            source.write_text(json.dumps(request()), encoding="utf-8")
            before = snapshot(root)
            result = cli(
                "capability",
                "run",
                "mesh.robot.modular.v1",
                "--input",
                "request.json",
                "--workspace",
                directory,
                "--dry-run",
                "--json",
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(snapshot(root), before)
            self.assertEqual(
                {p.relative_to(root).as_posix() for p in root.rglob("*")}, {"request.json"}
            )
            source.write_text('{"schema_version":"1.0.0"}', encoding="utf-8")
            before = snapshot(root)
            result = cli(
                "capability",
                "run",
                "mesh.robot.modular.v1",
                "--input",
                "request.json",
                "--workspace",
                directory,
                "--json",
            )
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(snapshot(root), before)


if __name__ == "__main__":
    unittest.main()
