"""Reopen producer outputs and score them against the frozen Phase 13 rubric."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from statistics import median
from typing import Any

from polyforge.contracts.images import inspect_png
from polyforge.doctor import discover_tool
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.security.paths import WorkspacePolicy
from tools.phase13_run_pilot import ARTIFACTS, NATIVE, REPO, read, sha, write
from tools.phase13_unity_verify import verify


def score(manifest: dict[str, Any], producer: Path, output: Path, cache: Path) -> dict[str, Any]:
    rubric_path = REPO / manifest["rubric_path"]
    if sha(rubric_path) != manifest["rubric_sha256"]:
        raise ValueError("Frozen verifier rubric changed")
    rubric = read(rubric_path)
    cases = {entry["id"]: entry for entry in rubric["cases"]}
    blender = discover_tool("blender")
    if blender is None or sha(blender) != manifest["blender_sha256"]:
        raise ValueError("Verifier Blender differs from frozen native tool")
    output.mkdir(exist_ok=False)
    policy = WorkspacePolicy(output)
    source_receipts = []
    rows: dict[str, dict[str, Any]] = {}
    bound: dict[Path, str] = {}
    for folder in sorted(producer.iterdir()):
        if not folder.is_dir():
            continue
        receipt_path = WorkspacePolicy(folder).path("receipt.json")
        receipt = read(receipt_path)
        identifier = receipt["id"]
        if identifier != folder.name or identifier not in {
            f"{case}_{arm}" for case in cases for arm in ("c", "d")
        }:
            raise ValueError("Unrecognized producer receipt identity")
        row: dict[str, Any] = {
            "id": identifier,
            "arm": receipt["arm"],
            "case_id": receipt["case_id"],
            "producer_receipt_sha256": sha(receipt_path),
            "producer_status": receipt["status"],
            "producer_seconds": receipt["producer_seconds"],
            "manual_corrections": receipt["manual_corrections"],
            "token_usage": receipt["token_usage"],
            "backend": receipt.get("backend"),
            "failures": [],
        }
        rows[identifier] = row
        if receipt["status"] != "PRODUCED":
            row["failures"].append(receipt.get("detail") or "No complete native artifact set")
            continue
        for name in ARTIFACTS:
            file = WorkspacePolicy(folder).path(name)
            digest = sha(file)
            if digest != receipt["artifacts"].get(name):
                raise ValueError(f"Producer artifact digest changed: {identifier}/{name}")
            bound[file] = digest
        try:
            preview = inspect_png((folder / "preview.png").read_bytes())
            row["preview_nonblank"] = preview["nonblank"]
            if not preview["nonblank"]:
                row["failures"].append("Preview is blank")
        except (OSError, ValueError) as error:
            row["failures"].append(f"Invalid preview: {error}")
        expected = policy.path(f"{identifier}-rubric.json")
        write(expected, cases[row["case_id"]])
        observation = run_process(
            [
                str(blender),
                "--background",
                "--factory-startup",
                "--disable-autoexec",
                "--threads",
                "2",
                "--python-exit-code",
                "17",
                "--python",
                str(NATIVE),
                "--",
                "inspect",
                str(expected),
                str(folder / "source.blend"),
            ],
            policy,
            identifier,
            ProcessPolicy((blender,), 90),
        )
        row["blender_process"] = asdict(observation)
        result_file = policy.path(f"{identifier}/blender-inspection.json")
        if observation.returncode == 0 and observation.reason == "exit" and result_file.is_file():
            row["blender"] = read(result_file)
            row["failures"].extend(row["blender"]["failures"])
        else:
            row["failures"].append("Native Blender reopen did not finish")
        source_receipts.append({"id": identifier, "case_id": row["case_id"], "root": str(folder)})

    unity = verify(rubric, source_receipts, policy.path("unity"), cache)
    unchanged = unity["source_unchanged"] and all(
        sha(file) == digest for file, digest in bound.items()
    )
    for identifier, row in rows.items():
        native = unity["attempts"].get(identifier, {})
        row["unity_status"] = native.get("status", "NOT_RUN")
        row["failures"].extend(native.get("failures", []))
        observations = native.get("observations", [])
        row["negative_cases"] = [
            negative for model in observations for negative in model["negatives"]
        ]
        row["native_seconds"] = round(
            row.get("blender_process", {}).get("duration_seconds", 0)
            + sum(model["elapsedSeconds"] for model in observations),
            3,
        )
        row["total_seconds"] = round(row["producer_seconds"] + row["native_seconds"], 3)
        if not unchanged:
            row["failures"].append("Verifier modified producer artifacts")
        if (
            not row["failures"]
            and row.get("blender", {}).get("passed") is True
            and row["unity_status"] == "PASS"
            and row.get("preview_nonblank") is True
        ):
            row["verdict"] = "ACCEPTED"
        else:
            row["verdict"] = "REJECTED" if row["producer_status"] == "PRODUCED" else "PARTIAL"
    arms: dict[str, dict[str, Any]] = {}
    for arm in ("C", "D"):
        values = [row for row in rows.values() if row["arm"] == arm]
        if values:
            arms[arm] = {
                "attempts": len(values),
                "accepted": sum(row["verdict"] == "ACCEPTED" for row in values),
                "median_total_seconds": median(row["total_seconds"] for row in values),
                "manual_corrections": sum(row["manual_corrections"] for row in values),
            }
    report = {
        "scope": "V7_1_PHASE_13_NATIVE_VERIFICATION",
        "assurance": "SAME_HOST_NONBLIND",
        "input_artifacts_unchanged": unchanged,
        "unity_native_status": unity["status"],
        "unity_batch_setup_and_import_seconds": unity["process"]["duration_seconds"],
        "time_policy": (
            "Model and build time plus measured per-attempt Blender and Unity checks. "
            "Shared Unity startup is reported separately."
        ),
        "rows": rows,
        "arms": arms,
    }
    write(output / "score.json", report)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ("manifest", "producer", "output", "template-cache"):
        parser.add_argument("--" + arg, type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    args = parser.parse_args()
    if sha(args.manifest) != args.manifest_sha256:
        raise ValueError("Frozen manifest SHA-256 mismatch")
    manifest = read(args.manifest)
    for path, expected in manifest["fixed_file_sha256"].items():
        if sha(REPO / path) != expected:
            raise ValueError(f"Frozen verifier file differs: {path}")
    report = score(
        manifest, args.producer.resolve(), args.output.resolve(), args.template_cache.resolve()
    )
    print(json.dumps({"arms": report["arms"], "unity_status": report["unity_native_status"]}))


if __name__ == "__main__":
    main()
