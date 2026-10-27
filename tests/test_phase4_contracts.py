"""Pure PNG, export-contract and side-effect boundaries for the S3 gate."""

from __future__ import annotations

import copy
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from test_foundation import cli, snapshot

from polyforge.contracts.validation import InputError


def png(pixels: bytes, width: int = 4, height: int = 4, mode: int = 0) -> bytes:
    def chunk(kind: bytes, value: bytes) -> bytes:
        return (
            struct.pack(">I", len(value))
            + kind
            + value
            + struct.pack(">I", zlib.crc32(kind + value))
        )

    rows = []
    prior = bytes(width * 4)
    for index in range(height):
        row = pixels[index * width * 4 : (index + 1) * width * 4]
        encoded = []
        for i, value in enumerate(row):
            a = row[i - 4] if i >= 4 else 0
            b = prior[i]
            c = prior[i - 4] if i >= 4 else 0
            p = a + b - c
            distances = [abs(p - a), abs(p - b), abs(p - c)]
            predict = [0, a, b, (a + b) // 2, [a, b, c][distances.index(min(distances))]][mode]
            encoded.append((value - predict) % 256)
        rows.append(bytes([mode]) + bytes(encoded))
        prior = row
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"".join(rows)))
        + chunk(b"IEND", b"")
    )


class PNGTests(unittest.TestCase):
    def test_png_header_chunk_order_compression_and_filter_rejections(self) -> None:
        from polyforge.contracts.images import inspect_png

        signature = b"\x89PNG\r\n\x1a\n"

        def chunk(kind: bytes, value: bytes) -> bytes:
            return (
                struct.pack(">I", len(value))
                + kind
                + value
                + struct.pack(">I", zlib.crc32(kind + value))
            )

        header = chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 6, 0, 0, 0))
        data = chunk(b"IDAT", zlib.compress(bytes(68)))
        end = chunk(b"IEND", b"")
        variants = [
            signature,
            signature + header + end,
            signature + data + end,
            signature + header + header + data + end,
            signature + chunk(b"IHDR", b"bad") + data + end,
            signature
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 1025, 4, 8, 6, 0, 0, 0))
            + data
            + end,
            signature + header + chunk(b"WHAT", b"") + data + end,
            signature + header + chunk(b"IDAT", b"bad compression") + end,
            signature + header + chunk(b"IDAT", zlib.compress(b"wrong size")) + end,
            signature + header + chunk(b"IDAT", zlib.compress(bytes([5]) + bytes(67))) + end,
        ]
        for value in variants:
            with self.subTest(length=len(value)), self.assertRaises(InputError):
                inspect_png(value)
        self.assertFalse(
            inspect_png(signature + header + chunk(b"tEXt", b"note\x00fixture") + data + end)[
                "nonblank"
            ]
        )

    def test_filtered_pixels_are_measured_independently(self) -> None:
        from polyforge.contracts.images import inspect_png

        pixels = bytes(
            [0, 0, 0, 0] * 4
            + [0, 0, 0, 0, 220, 90, 30, 255, 60, 130, 200, 255, 0, 0, 0, 0] * 2
            + [0, 0, 0, 0] * 4
        )
        for mode in range(5):
            report = inspect_png(png(pixels, mode=mode))
            self.assertEqual(report["opaque_pixels"], 4)
            self.assertEqual(report["foreground_bounds_px"], [1, 1, 2, 2])
            self.assertTrue(report["nonblank"])
        self.assertFalse(inspect_png(png(bytes(64)))["nonblank"])
        self.assertFalse(inspect_png(png(bytes([80, 80, 80, 255] * 16)))["framing_pass"])

    def test_corrupt_truncated_and_unsupported_pngs_fail_boundedly(self) -> None:
        from polyforge.contracts.images import inspect_png

        value = png(bytes(64))
        for bad in (
            b"",
            b"not an image",
            value[:-4],
            value[:35] + b"bad",
            value[:-1] + b"X",
            value + b"extra",
        ):
            with self.subTest(bad=bad[:10]), self.assertRaises(InputError):
                inspect_png(bad)
        with self.assertRaises(InputError):
            inspect_png(png(bytes(64)), expected_size=256)


class S3Tests(unittest.TestCase):
    def test_s3_resolution_budget_is_validated_before_dry_run_or_publication(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "arena"
            self.assertEqual(cli("init", str(root), "--json").returncode, 0)
            (root / "polyforge.toml").write_text("[visual_audit]\npreview_resolution = 2048\n")
            before = snapshot(root)
            for flags in (["--dry-run"], []):
                result = cli("build", "--workspace", str(root), "--through", "S3", *flags, "--json")
                self.assertEqual(result.returncode, 2, result.stdout[:150])
                self.assertEqual(snapshot(root), before)

    def test_incomplete_s3_attempt_does_not_hide_last_registered_source(self) -> None:
        import hashlib

        from polyforge.blender.audit import managed_source

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("old", "new"):
                folder = root / "runs" / name
                (folder / "asset").mkdir(parents=True)
                (folder / "input.json").write_text(json.dumps({"recipe": {"asset_id": "crate"}}))
                (folder / "state.json").write_text(
                    json.dumps(
                        {
                            "updated_utc": name,
                            "stages": {
                                "S2": {"status": "passed"},
                                "S3": {"status": "failed" if name == "new" else "pending"},
                            },
                        }
                    )
                )
            source = root / "runs/old/asset/source.blend"
            source.write_bytes(b"BLENDER fixture")
            (root / "runs/old/state.json").write_text(
                json.dumps({"updated_utc": "1", "stages": {"S2": {"status": "passed"}}})
            )
            (root / "runs/new/state.json").write_text(
                json.dumps(
                    {
                        "updated_utc": "2",
                        "stages": {"S2": {"status": "passed"}, "S3": {"status": "failed"}},
                    }
                )
            )
            (root / "runs/old/artifacts.json").write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {
                                "relative_path": "runs/old/asset/source.blend",
                                "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                            }
                        ]
                    }
                )
            )
            self.assertEqual(managed_source(root, "crate")[1], source)
            state = root / "runs/old/state.json"
            value = json.loads(state.read_text())
            value["updated_utc"] = None
            state.write_text(json.dumps(value))
            with self.assertRaises(InputError):
                managed_source(root, "crate")
            value["updated_utc"] = "1"
            state.write_text(json.dumps(value))
            (root / "runs/old/artifacts.json").write_text('{"artifacts":null}')
            with self.assertRaises(InputError):
                managed_source(root, "crate")

    def test_exchange_sidecars_reject_changed_bindings_units_and_material_values(self) -> None:
        from polyforge.blender.audit import validate_exchange

        recipe = {
            "asset_id": "crate",
            "materials": [
                {"id": "base", "color_rgba": [0.2, 0.3, 0.4, 1], "metallic": 0.3, "roughness": 0.6}
            ],
            "modules": [{"id": "body", "material_id": "base"}],
        }
        metrics = {
            "asset_id": "crate",
            "bounds_m": [1, 3, 2],
            "bounds_unity_m": [1, 2, 3],
            "material_ids": ["base"],
            "module_ids": ["body"],
            "socket_ids": ["front"],
            "coordinate_basis": {"up": "Z", "forward": "-Y"},
            "meters_per_unit": 1,
            "geometry_digest": "a" * 64,
            "socket_positions_unity_m": {"front": [0, 1, 1.5]},
        }
        material = {
            "schema_version": "1.0.0",
            "asset_id": "crate",
            "materials": [
                {
                    "id": "base",
                    "base_color_rgba": [0.2, 0.3, 0.4, 1],
                    "metallic": 0.3,
                    "roughness": 0.6,
                }
            ],
            "module_materials": {"body": ["base"]},
        }
        handoff = {
            "coordinate_basis": metrics["coordinate_basis"],
            "meters_per_unit": 1,
            "objects": [
                {
                    "id": "asset:crate",
                    "bounds_m": [1, 3, 2],
                    "material_ids": ["base"],
                    "socket_ids": ["front"],
                    "geometry_digest": "a" * 64,
                    "socket_positions_unity_m": {"front": [0, 1, 1.5]},
                }
            ],
        }
        imported = {
            "status": "PASS",
            "verification_scope": "BLENDER_FBX_ROUNDTRIP",
            "unity_import_status": "NOT_RUN",
            "bounds_unity_m": [1, 2, 3],
            "socket_positions_unity_m": {"front": [0, 1, 1.5]},
            "module_ids": ["body"],
            "material_ids": ["base"],
        }
        validate_exchange(recipe, metrics, material, handoff, imported)
        palette_recipe = copy.deepcopy(recipe)
        palette_material = copy.deepcopy(material)
        palette_metrics = copy.deepcopy(metrics)
        palette_handoff = copy.deepcopy(handoff)
        palette_recipe["materials"].append({"id": "spare", "color_rgba": [1, 0, 0, 1]})
        palette_material["materials"].append(
            {"id": "spare", "base_color_rgba": [1, 0, 0, 1], "metallic": 0, "roughness": 0.65}
        )
        palette_metrics["material_ids"].append("spare")
        palette_handoff["objects"][0]["material_ids"].append("spare")
        validate_exchange(
            palette_recipe, palette_metrics, palette_material, palette_handoff, imported
        )
        for mutate in (
            lambda m, h, r: m["materials"][0].update(roughness=0.1),
            lambda m, h, r: m.update(module_materials={"body": []}),
            lambda m, h, r: h.update(meters_per_unit=0.01),
            lambda m, h, r: r.update(material_ids=[]),
            lambda m, h, r: r.update(status="FAIL"),
            lambda m, h, r: r.update(bounds_unity_m=[1, 3, 2]),
        ):
            m, h, r = copy.deepcopy((material, handoff, imported))
            mutate(m, h, r)
            with self.assertRaises(InputError):
                validate_exchange(recipe, metrics, m, h, r)

    def test_blender_user_caches_are_redirected_inside_owned_temporary_directory(self) -> None:
        from polyforge.security.policy import worker_environment

        root = Path.cwd() / ".tmp/owned"
        env = worker_environment(
            Path("C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"), root, {}
        )
        for name in (
            "BLENDER_USER_CONFIG",
            "BLENDER_USER_SCRIPTS",
            "BLENDER_USER_DATAFILES",
            "BLENDER_USER_EXTENSIONS",
        ):
            self.assertTrue(Path(env[name]).is_relative_to(root))

    def test_handoff_checks_asymmetric_axis_units_and_binding_faults(self) -> None:
        from polyforge.invariants.handoff import check_handoff

        contract = {
            "objects": [
                {
                    "id": "asset:arrows",
                    "kind": "asset",
                    "bounds_m": [1, 2, 3],
                    "material_ids": ["axis"],
                    "socket_ids": ["front"],
                }
            ]
        }
        source = {
            "coordinate_basis": {"up": "Z", "forward": "-Y"},
            "meters_per_unit": 1,
            "objects": [
                {
                    "id": "asset:arrows",
                    "bounds_m": [1, 3, 2],
                    "material_ids": ["axis"],
                    "socket_ids": ["front"],
                }
            ],
        }
        imported = {
            "coordinate_basis": {"up": "Y", "forward": "Z"},
            "meters_per_unit": 1,
            "objects": [
                {
                    "id": "asset:arrows",
                    "bounds_m": [1, 2, 3],
                    "material_ids": ["axis"],
                    "socket_ids": ["front"],
                    "prefab_id": "arrows",
                }
            ],
        }
        self.assertEqual(check_handoff(contract, source, imported)["status"], "PASS")
        for mutate in (
            lambda x: x.update(coordinate_basis={"up": "Z", "forward": "Y"}),
            lambda x: x.update(meters_per_unit=0.01),
            lambda x: x["objects"][0].update(socket_ids=[]),
            lambda x: x["objects"][0].update(material_ids=[]),
            lambda x: x["objects"][0].update(bounds_m=[1, 3, 2]),
        ):
            value = copy.deepcopy(imported)
            mutate(value)
            result = check_handoff(contract, source, value)
            self.assertEqual(result["status"], "FAIL")
            self.assertEqual(result["application_execution"], "NOT_RUN")

    def test_corrupt_saved_source_and_bad_config_are_read_only_failures(self) -> None:
        from polyforge.blender.audit import managed_source

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "runs/mesh-a"
            (run / "asset").mkdir(parents=True)
            (run / "input.json").write_text(json.dumps({"recipe": {"asset_id": "crate"}}))
            (run / "state.json").write_text(
                json.dumps({"stages": {"S2": {"status": "passed"}}, "updated_utc": "2026"})
            )
            (run / "asset/source.blend").write_bytes(b"BLENDER corrupt")
            (run / "artifacts.json").write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {"relative_path": "runs/mesh-a/asset/source.blend", "sha256": "0" * 64}
                        ]
                    }
                )
            )
            before = snapshot(root)
            with self.assertRaises(InputError):
                managed_source(root, "crate")
            self.assertEqual(snapshot(root), before)

    def test_bad_audit_input_and_s3_dry_run_write_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "arena"
            self.assertEqual(cli("init", str(root), "--json").returncode, 0)
            before = snapshot(root)
            result = cli(
                "build", "--workspace", str(root), "--through", "S3", "--dry-run", "--json"
            )
            self.assertEqual(result.returncode, 0, result.stdout)
            self.assertEqual(snapshot(root), before)
            result = cli("audit", "--workspace", str(root), "--asset", "absent", "--json")
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(snapshot(root), before)
            result = cli("audit", "--workspace", str(root), "--asset", "robot_a", "--json")
            self.assertEqual(result.returncode, 2, result.stdout)
            self.assertEqual(snapshot(root), before)

    def test_export_metadata_cannot_claim_unity_verification_or_accept_fake_views(self) -> None:
        from polyforge.blender.audit import validate_audit

        metrics = {
            "asset_id": "crate",
            "geometry_digest": "a" * 64,
            "material_ids": ["base"],
            "socket_ids": ["front"],
        }
        good = {
            "schema_version": "1.0.0",
            "asset_id": "crate",
            "geometry_digest": "a" * 64,
            "diagnostics": {"status": "PASS", "issues": []},
            "visual_review_status": "REVIEW",
            "unity_import_status": "NOT_RUN",
            "export": {
                "axis_forward": "-Z",
                "axis_up": "Y",
                "global_scale": 1.0,
                "apply_unit_scale": True,
                "apply_scale_options": "FBX_SCALE_UNITS",
                "bake_space_transform": False,
                "bake_anim": False,
                "use_selection": True,
                "use_custom_props": True,
                "object_types": ["EMPTY", "MESH"],
            },
            "view_ids": ["front", "side", "top", "iso"],
            "material_ids": ["base"],
            "socket_ids": ["front"],
        }
        validate_audit(good, metrics)
        for mutate in (
            lambda x: x.update(unity_import_status="PASS"),
            lambda x: x.update(visual_review_status="PASS"),
            lambda x: x.update(view_ids=["front"] * 4),
            lambda x: x["export"].update(global_scale=100),
            lambda x: x["diagnostics"].update(
                status="FAIL", issues=[{"category": "reversed_normals"}]
            ),
            lambda x: x.update(geometry_digest="b" * 64),
        ):
            changed = copy.deepcopy(good)
            mutate(changed)
            with self.assertRaises(InputError):
                validate_audit(changed, metrics)


if __name__ == "__main__":
    unittest.main()
