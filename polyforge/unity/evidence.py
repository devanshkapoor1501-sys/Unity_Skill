"""Independent checks of native observed data and executed test identities."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest

EDITMODE_TESTS = {
    "PolyForge.Editor.Tests.ForensicsTests.UndeclaredTextureBindingsAreDetected",
    *{
        f'PolyForge.Editor.Tests.ForensicsTests.SuppliedTextureFaultsAreDetected("{x}")'
        for x in ("srgb", "normalType", "normalKeyword", "reference", "bytes")
    },
    *{
        f'PolyForge.Editor.Tests.ForensicsTests.SceneOverridesAreDetected("{x}")'
        for x in ("scale", "source", "camera")
    },
    *{
        f'PolyForge.Editor.Tests.ForensicsTests.ColliderFaultsAreDetected("{x}")'
        for x in ("size", "center", "disabled", "meshReference", "none")
    },
    "PolyForge.Editor.Tests.ImportTests.ChangedMaterialValueIsDetected",
    "PolyForge.Editor.Tests.ImportTests.MissingPrefabGuidIsDetectedAndNativeBytesRestoreIt",
    "PolyForge.Editor.Tests.ImportTests.ImportedDimensionsSocketsAndBindingsMatchIndependentSource",
    "PolyForge.Editor.Tests.ImportTests.NativeMaterialParametersMatchLinearSidecars",
    "PolyForge.Editor.Tests.ImportTests.RepeatedNativeBuildPreservesGuidsHierarchyAndSceneInstances",
    *{
        f'PolyForge.Editor.Tests.ImportTests.IndependentFaultsAreDetected("{x}")'
        for x in ("scale", "material", "socket", "component")
    },
}


def verify_test_xml(path: Path, expected: set[str]) -> dict[str, Any]:
    """A zero exit with no tests, skipped cases, or different tests cannot pass."""
    try:
        payload = path.read_bytes()
        if len(payload) > 8_388_608 or re.search(rb"<!\s*(DOCTYPE|ENTITY)", payload, re.I):
            raise ValueError("Unsafe/oversized XML")
        root = ET.fromstring(payload)
        cases = list(root.iter("test-case"))
        names = [case.get("fullname") for case in cases]
        if (
            not expected
            or not cases
            or len(names) != len(set(names))
            or set(names) != expected
            or any(case.get("result") != "Passed" for case in cases)
            or root.get("result") != "Passed"
        ):
            raise ValueError("Expected executed passing test identities do not match XML")
    except (OSError, ValueError, ET.ParseError) as exc:
        raise InputError(str(exc), kind=ErrorKind.TEST_FAILURE, code="PF-UNITY-TEST-XML") from exc
    return {"status": "PASS", "executed": len(cases), "test_names": sorted(expected)}


def reconcile_report(request: dict[str, Any], report: dict[str, Any]) -> dict[str, Any]:
    """Do not trust a worker PASS: independently check identity, bindings and geometry."""
    issues: list[dict[str, Any]] = []

    def near(value: Any, wanted: list[float]) -> bool:
        return (
            isinstance(value, list)
            and len(value) == len(wanted)
            and all(
                type(n) in {int, float}
                and math.isfinite(n)
                and math.isclose(n, w, rel_tol=0.02, abs_tol=0.002)
                for n, w in zip(value, wanted, strict=True)
            )
        )

    def issue(category: str, identifier: str, expected: Any, actual: Any) -> None:
        issues.append(
            {"category": category, "asset_id": identifier, "expected": expected, "actual": actual}
        )

    if not isinstance(report, dict):
        return {
            "status": "FAIL",
            "issues": [
                {
                    "category": "contract",
                    "asset_id": "report",
                    "expected": "typed native bindings",
                    "actual": "non-object report",
                }
            ],
            "application_execution": "NOT_RUN",
            "gameplay_status": "NOT_RUN",
        }
    canonical_digest(report)

    if any(
        report.get(k) != v
        for k, v in {
            "schema_version": "1.0.0",
            "input_digest": request["input_digest"],
            "unity_version": "6000.6.3f1",
            "verification_scope": "UNITY_EDITOR_STATIC",
        }.items()
    ):
        issue("identity", "report", request["input_digest"], report.get("input_digest"))
    try:
        observed = {a["id"]: a for a in report["objects"]}
        if len(observed) != len(report["objects"]):
            raise ValueError("duplicate assets")
        if set(observed) != {a["id"] for a in request["assets"]}:
            issue("binding", "report", [a["id"] for a in request["assets"]], list(observed))
        for asset in request["assets"]:
            identifier = asset["id"]
            actual = observed.get(identifier)
            if actual is None:
                continue
            for field in ("guid", "prefab_guid"):
                if not re.fullmatch(r"[a-f0-9]{32}", actual[field]):
                    issue("binding", identifier, field, actual[field])
            if actual["prefab_id"] != f"Assets/PolyForgeGenerated/Prefabs/{identifier}.prefab":
                issue("binding", identifier, "managed prefab path", actual["prefab_id"])
            bounds = actual["bounds_m"]
            if len(bounds) != 3 or any(
                type(n) not in {int, float}
                or not math.isclose(n, wanted, rel_tol=0.02, abs_tol=0.001)
                for n, wanted in zip(bounds, asset["bounds_m"], strict=True)
            ):
                issue("scale", identifier, asset["bounds_m"], bounds)
            sockets = {s["id"]: s["position_m"] for s in actual["sockets"]}
            expected = {s["id"]: s["position_m"] for s in asset["sockets"]}
            if (
                len(sockets) != len(actual["sockets"])
                or set(sockets) != set(expected)
                or set(actual["socket_ids"]) != set(expected)
            ):
                issue("socket", identifier, list(expected), list(sockets))
            for key in set(sockets) & set(expected):
                if len(sockets[key]) != 3 or any(
                    type(n) not in {int, float} or not math.isclose(n, wanted, abs_tol=0.002)
                    for n, wanted in zip(sockets[key], expected[key], strict=True)
                ):
                    issue("axis", identifier, expected[key], sockets[key])
            if set(actual["material_ids"]) != {m["id"] for m in asset["materials"]}:
                issue(
                    "material",
                    identifier,
                    [m["id"] for m in asset["materials"]],
                    actual["material_ids"],
                )
            expected_textures = {
                (m["id"], t["kind"]): t for m in asset["materials"] for t in m.get("textures", [])
            }
            native_textures = actual.get("textures")
            if not isinstance(native_textures, list):
                issue("texture", identifier, "both observed material slots", native_textures)
                native_textures = []
            keyed_textures = {(t["material_id"], t["kind"]): t for t in native_textures}
            expected_slots = {
                (m["id"], role) for m in asset["materials"] for role in ("base_color", "normal")
            }
            if len(keyed_textures) != len(native_textures) or set(keyed_textures) != expected_slots:
                issue("texture", identifier, list(expected_slots), list(keyed_textures))
            for key in set(keyed_textures) & expected_slots:
                texture = keyed_textures[key]
                wanted_texture = expected_textures.get(key)
                normal = key[1] == "normal"
                expected_normal = (key[0], "normal") in expected_textures
                if texture["normal_keyword"] is not expected_normal:
                    issue(
                        "texture",
                        identifier,
                        "normal keyword matches declared normal slot",
                        texture,
                    )
                if wanted_texture is None:
                    if (
                        texture["has_texture"] is not False
                        or texture["path"] != ""
                        or texture["material_texture_path"] != ""
                    ):
                        issue("texture", identifier, "empty undeclared texture slot", texture)
                elif (
                    texture["has_texture"] is not True
                    or texture["path"] != wanted_texture["path"]
                    or texture["sha256"] != wanted_texture["sha256"]
                    or texture["srgb"] is not (not normal)
                    or texture["texture_type"] != ("NormalMap" if normal else "Default")
                    or texture["convert_to_normal"] is not False
                    or texture["material_texture_path"] != wanted_texture["path"]
                ):
                    issue("texture", identifier, wanted_texture, texture)
            if type(actual["transform_count"]) is not int or actual["transform_count"] < 2:
                issue("binding", identifier, "imported hierarchy", actual["transform_count"])
            nodes = actual["nodes"]
            expected_nodes = {("module", m["id"]) for m in asset.get("modules", [])} | {
                ("socket", s["id"]) for s in asset["sockets"]
            }
            if (
                not isinstance(nodes, list)
                or len(nodes) != len(expected_nodes)
                or {(n["kind"], n["id"]) for n in nodes} != expected_nodes
            ):
                issue("binding", identifier, "complete semantic node graph", nodes)
            else:
                for node in nodes:
                    if (
                        node["guid"] not in {actual["guid"], actual["prefab_guid"]}
                        or type(node["local_id"]) is not int
                        or node["local_id"] == 0
                        or not isinstance(node["path"], str)
                        or not node["path"]
                        or node["component"]
                        != ("MeshRenderer" if node["kind"] == "module" else "Transform")
                    ):
                        issue("binding", identifier, "stable GUID/local ID/path/component", node)
            collider = asset["collider"]
            details = actual["colliders"]
            modules = [n for n in nodes if n["kind"] == "module"]
            count = len(modules) if collider == "mesh" else 0 if collider == "none" else 1
            if (
                actual["collider"] != collider
                or not isinstance(details, list)
                or len(details) != count
            ):
                issue("collider", identifier, collider, details)
            else:
                mesh_paths = set()
                for detail in details:
                    valid = detail["enabled"] is True and detail["is_trigger"] is False
                    if collider in {"box", "capsule"}:
                        size = asset["bounds_m"]
                        expected_size = (
                            size
                            if collider == "box"
                            else [max(size[0], size[2]), max(size), max(size[0], size[2])]
                        )
                        valid = (
                            valid
                            and detail["kind"]
                            == {"box": "BoxCollider", "capsule": "CapsuleCollider"}[collider]
                            and detail["path"] == ""
                            and near(detail["center_m"], [0, size[1] / 2, 0])
                            and near(detail["size_m"], expected_size)
                            and (
                                collider != "capsule"
                                or type(detail["direction"]) is int
                                and detail["direction"] == 1
                            )
                        )
                    elif collider == "mesh":
                        matching = [n for n in modules if n["path"] == detail["path"]]
                        valid = (
                            valid
                            and detail["kind"] == "MeshCollider"
                            and detail["convex"] is False
                            and len(matching) == 1
                            and detail["path"] not in mesh_paths
                        )
                        if matching:
                            node = matching[0]
                            valid = (
                                valid
                                and detail["mesh_guid"] == node["mesh_guid"] == actual["guid"]
                                and type(detail["mesh_local_id"]) is int
                                and type(node["mesh_local_id"]) is int
                                and detail["mesh_local_id"] == node["mesh_local_id"] != 0
                            )
                        mesh_paths.add(detail["path"])
                    if not valid:
                        issue(
                            "collider",
                            identifier,
                            "fitted enabled solid geometry/reference",
                            detail,
                        )
        if (
            len(report["scene_guids"]) != 2
            or len(set(report["scene_guids"])) != 2
            or any(not re.fullmatch(r"[a-f0-9]{32}", s) for s in report["scene_guids"])
            or type(report["scene_object_count"]) is not int
            or report["scene_object_count"] <= 0
        ):
            issue("scene", "report", "two measured scenes", report.get("scene_guids"))
        if set(observed) == {a["id"] for a in request["assets"]}:
            expected_count = 2 * (
                3
                + sum(a["transform_count"] for a in observed.values())
                + sum(observed[a["asset_id"]]["transform_count"] for a in request.get("actors", []))
            )
            if report["scene_object_count"] != expected_count:
                issue("scene", "report", expected_count, report["scene_object_count"])
        for field in ("camera_count", "light_count"):
            if type(report[field]) is not int or report[field] != 2:
                issue("scene", "report", "one per scene: " + field, report[field])
        instances = report["scene_instances"]
        keyed = {(s["scene"], s["id"]): s for s in instances}
        wanted = {}
        for scene in ("Arena", "Training"):
            for index, asset in enumerate(request["assets"]):
                size, bounds = asset["bounds_m"], request["scene_bounds_m"]
                ground = size[0] >= bounds[0] / 2 and size[2] >= bounds[2] / 2
                pose = (
                    [0, -size[1], 0]
                    if ground
                    else [index * (-2 if scene == "Training" else 2), 0, 0]
                )
                wanted[scene, "asset:" + asset["id"]] = (asset["id"], pose)
            for actor in request.get("actors", []):
                wanted[scene, "actor:" + actor["id"]] = (actor["asset_id"], actor["spawn_xyz"])
        if len(keyed) != len(instances) or set(keyed) != set(wanted):
            issue("scene_instance", "report", sorted(wanted), sorted(keyed))
        for key in set(keyed) & set(wanted):
            instance = keyed[key]
            identifier, pose = wanted[key]
            source = observed.get(identifier, {})
            rotation = instance["rotation_xyzw"]
            rotation_ok = (
                isinstance(rotation, list)
                and len(rotation) == 4
                and all(type(n) in {int, float} and math.isfinite(n) for n in rotation)
                and math.isclose(sum(n * n for n in rotation), 1, abs_tol=0.0001)
                and math.degrees(
                    2 * math.atan2(math.sqrt(sum(n * n for n in rotation[:3])), abs(rotation[3]))
                )
                <= 0.01
            )
            if (
                instance["asset_id"] != identifier
                or instance["prefab_guid"] != source.get("prefab_guid")
                or instance["source_guid"] != source.get("guid")
                or not near(instance["position_m"], pose)
                or not near(instance["scale"], [1, 1, 1])
                or not rotation_ok
            ):
                issue("scene_instance", identifier, "declared identity/source/pose", instance)
        for value in report["issues"]:
            issue(value["category"], value["asset_id"], value["expected"], value["actual"])
        if report["status"] != "PASS" and not issues:
            issue("worker", "report", "PASS", report["status"])
    except (KeyError, TypeError, ValueError) as exc:
        issue("contract", "report", "complete typed native bindings", str(exc))
    return {
        "status": "FAIL" if issues else "PASS",
        "issues": issues,
        "application_execution": "UNITY_EDITOR_STATIC",
        "gameplay_status": "NOT_RUN",
    }
