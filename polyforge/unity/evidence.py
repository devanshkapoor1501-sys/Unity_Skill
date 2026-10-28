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
