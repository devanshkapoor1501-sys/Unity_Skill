"""Score copied Phase 13 FBX assets in a fresh managed Unity project."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import stat
from dataclasses import asdict
from pathlib import Path
from typing import Any

from polyforge.doctor import discover_tool
from polyforge.runner.locks import unity_project_lock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bootstrap import installed_template, prepare_project

PROBE = Path(__file__).resolve().parents[1] / "tests/fixtures/modeling/Phase13ImportProbe.cs"


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def cache_copy(source: Path, destination: Path) -> None:
    """Refuse links or reparse points before copying only the selected cache subtree."""
    for item in (source, *source.rglob("*")):
        info = item.lstat()
        if (
            item.is_symlink()
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
        ):
            raise ValueError("Reparse point in managed Unity cache")
        if not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)):
            raise ValueError("Unexpected entry in managed Unity cache")
    shutil.copytree(source, destination)


def verify(
    rubric: dict[str, Any], attempts: list[dict[str, str]], root: Path, cache: Path
) -> dict[str, Any]:
    editor = discover_tool("unity")
    if editor is None or editor.parent.parent.name != "6000.6.3f1":
        raise ValueError("Pinned Unity 6000.6.3f1 not found")
    root.mkdir(parents=False, exist_ok=False)
    policy = WorkspacePolicy(root)
    cases = {case["id"]: case for case in rubric["cases"]}
    by_id: dict[str, dict[str, Any]] = {}
    expected = []
    sources = {}
    with unity_project_lock(policy, policy.path("UnityProject")):
        project = prepare_project(policy, installed_template(editor))
        old_project = WorkspacePolicy(cache).path("UnityProject")
        relative = "ProjectSettings/ProjectVersion.txt"
        old_version = (old_project / relative).read_text(encoding="utf-8").splitlines()[0]
        new_version = (project / relative).read_text(encoding="utf-8").splitlines()[0]
        if old_version != new_version or digest(old_project / "Packages/manifest.json") != digest(
            project / "Packages/manifest.json"
        ):
            raise ValueError("Cached Unity project version or package manifest differs")
        shutil.copyfile(
            old_project / "Packages/packages-lock.json", project / "Packages/packages-lock.json"
        )
        cache_copy(old_project / "Library/PackageCache", project / "Library/PackageCache")
        for name in ("content-v2", "index-v5"):
            relative = f".polyforge/unity-profile/upm-cache/db/{name}"
            cache_copy(WorkspacePolicy(cache).path(relative), policy.path(relative))
        scripts = policy.mkdir(project / "Assets/Editor")
        shutil.copyfile(PROBE, scripts / PROBE.name)
        assets = policy.mkdir(project / "Assets/Phase13")
        for attempt in attempts:
            identifier = attempt["id"]
            if not re.fullmatch(r"[a-z0-9_]{1,64}", identifier) or identifier in by_id:
                raise ValueError("Invalid or duplicate attempt ID")
            case = cases[attempt["case_id"]]
            score: dict[str, Any] = {"case_id": case["id"], "status": "NOT_RUN", "failures": []}
            by_id[identifier] = score
            output = WorkspacePolicy(Path(attempt["root"]))
            paths = {kind: output.path(kind + ".fbx") for kind in ("asset", "lod")}
            if any(
                not file.is_file() or file.stat().st_size > 32 * 1024 * 1024
                for file in paths.values()
            ):
                score["failures"].append("Main or LOD FBX absent or above size cap")
                continue
            for kind, file in paths.items():
                sha = digest(file)
                sources[str(file)] = sha
                name = f"{identifier}_{kind}.fbx"
                shutil.copyfile(file, assets / name)
                expected.append(
                    {
                        "attemptId": identifier,
                        "kind": kind,
                        "path": f"Assets/Phase13/{name}",
                        "sha256": sha,
                        "coordinateTolerance": rubric["coordinate_tolerance_m"],
                        "boundsTolerance": rubric["bounds_tolerance_m"],
                        "sockets": case["sockets"],
                        "boundsMin": case["bounds_min"],
                        "boundsMax": case["bounds_max"],
                        "materials": case["materials"],
                        "modules": [
                            {
                                "id": obj["id"],
                                "material": obj["material"],
                                "boundsMin": obj["bounds_min"],
                                "boundsMax": obj["bounds_max"],
                            }
                            for obj in case["modules"]
                        ]
                        if kind == "asset"
                        else [],
                    }
                )
        input_path = policy.path("unity-input.json")
        input_path.write_text(json.dumps({"models": expected}, allow_nan=False), encoding="utf-8")
        result_path = policy.path("unity-result.json")
        process = run_process(
            [
                str(editor),
                "-batchmode",
                "-nographics",
                "-quit",
                "-job-worker-count",
                "2",
                "-projectPath",
                str(project),
                "-logFile",
                "-",
                "-executeMethod",
                "Phase13ImportProbe.Run",
                "-phase13Input",
                str(input_path),
                "-phase13Result",
                str(result_path),
            ],
            policy,
            "unity-process",
            ProcessPolicy((editor,), 600),
        )
    unchanged = all(digest(Path(file)) == expected_hash for file, expected_hash in sources.items())
    native = (
        json.loads(result_path.read_text(encoding="utf-8-sig")) if result_path.is_file() else {}
    )
    ready = (
        process.returncode == 0
        and process.reason == "exit"
        and native.get("unityVersion") == "6000.6.3f1"
        and not native.get("fatal")
    )
    for identifier, score in by_id.items():
        rows = [item for item in native.get("observations", []) if item["attemptId"] == identifier]
        score["observations"] = rows
        if not ready or len(rows) != 2 or not unchanged:
            score["status"] = "BLOCKED"
            continue
        for row in rows:
            score["failures"].extend(row["failures"])
        counts = {row["kind"]: row["triangleCount"] for row in rows}
        if counts["lod"] > counts["asset"] or (
            cases[score["case_id"]]["requires_lower_lod"] and counts["lod"] == counts["asset"]
        ):
            score["failures"].append("LOD triangle count outside rubric")
        score["status"] = "PASS" if not score["failures"] else "FAIL"
    result = {
        "status": "PASS" if ready and unchanged else "BLOCKED",
        "source_unchanged": unchanged,
        "process": asdict(process),
        "native": native,
        "attempts": by_id,
    }
    policy.path("receipt.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("rubric", "attempts", "workspace", "template-cache"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    result = verify(
        json.loads(args.rubric.read_text(encoding="utf-8")),
        json.loads(args.attempts.read_text(encoding="utf-8")),
        args.workspace.resolve(),
        args.template_cache.resolve(),
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "attempts": {key: value["status"] for key, value in result["attempts"].items()},
            }
        )
    )


if __name__ == "__main__":
    main()
