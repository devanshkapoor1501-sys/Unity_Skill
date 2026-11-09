"""Run a frozen internal Codex pair through fixed, data-only native tools."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from polyforge.doctor import discover_tool
from polyforge.runner.ownership import WindowsJob
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.security.paths import WorkspacePolicy

REPO = Path(__file__).resolve().parents[1]
NATIVE = Path(__file__).with_name("phase13_blender_native.py").resolve()
ARTIFACTS = ("source.blend", "asset.fbx", "lod.fbx", "preview.png")
ID = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path: Path) -> Any:
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError("Pilot JSON exceeds size cap")
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")


def obj(fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": fields,
        "required": list(fields),
        "additionalProperties": False,
    }


def schema(arm: str) -> dict[str, Any]:
    string = {"type": "string"}
    number = {"type": "number"}
    vector = {"type": "array", "items": number}
    socket = obj({"id": string, "position": vector})
    module = obj(
        {
            "id": string,
            "primitive": {"type": "string", "enum": ["box", "cylinder"]},
            "size": vector,
            "position": vector,
            "rotation_degrees": number,
            "material": {"type": "string", "enum": ["base", "trim", "accent"]},
        }
    )
    return obj(
        {
            "backend": {
                "type": "string",
                "enum": ["blender"] if arm == "C" else ["blender", "polyforge"],
            },
            "reflect_export_x": {"type": "boolean"},
            "modules": {"type": "array", "items": module},
            "sockets": {"type": "array", "items": socket},
        }
    )


def request(result: Any, arm: str, asset: str) -> dict[str, Any]:
    if not isinstance(result, dict) or set(result) != {
        "backend",
        "reflect_export_x",
        "modules",
        "sockets",
    }:
        raise ValueError("Unexpected tool request fields")
    if result["backend"] not in ({"blender"} if arm == "C" else {"blender", "polyforge"}):
        raise ValueError("Backend is unavailable in this arm")
    if type(result["reflect_export_x"]) is not bool:
        raise ValueError("Expected explicit X reflection toggle")

    def vector(values: Any, low: float, high: float) -> None:
        if (
            not isinstance(values, list)
            or len(values) != 3
            or any(
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not low <= value <= high
                for value in values
            )
        ):
            raise ValueError("Invalid bounded XYZ")

    seen = set()
    for group, fields in (
        ("modules", {"id", "primitive", "size", "position", "rotation_degrees", "material"}),
        ("sockets", {"id", "position"}),
    ):
        entries = result[group]
        if not isinstance(entries, list) or not 1 <= len(entries) <= 12:
            raise ValueError("Invalid bounded object count")
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != fields:
                raise ValueError("Unexpected object fields")
            identifier = entry["id"]
            if (
                not isinstance(identifier, str)
                or not ID.fullmatch(identifier)
                or len(identifier) > 48
                or identifier in seen
            ):
                raise ValueError("Invalid or duplicate object ID")
            seen.add(identifier)
            vector(entry["position"], -12, 12)
            if group == "modules":
                vector(entry["size"], 0.01, 12)
                angle = entry["rotation_degrees"]
                if type(angle) not in (float, int) or not math.isfinite(angle) or abs(angle) > 180:
                    raise ValueError("Invalid rotation")
                if entry["primitive"] not in {"box", "cylinder"} or entry["material"] not in {
                    "base",
                    "trim",
                    "accent",
                }:
                    raise ValueError("Unsupported primitive or material")
                entry["rotation_z"] = angle
    return {"asset_id": asset, **result}


def model_prompt(brief: str, arm: str) -> str:
    baseline = (
        "Both arms have the same fixed generic Blender tool followed by managed Unity import. "
        "Use backend blender to call cube or cylinder mesh creation, set Blender-local size, "
        "location and Z rotation, assign material, add empties and export the main and lower "
        "resolution LOD with Forward=-Z, Up=Y. Blender source coordinates are (x,-z,y) "
        "for Unity (x,y,z). A native Unity FBX import may require export-only reflection "
        "of the shared root on X to preserve signed X. Set reflect_export_x accordingly. "
        "Use short IDs from the brief after :module: or :socket:. Return only a tool request "
        "matching the supplied JSON schema. Do not call shell tools. The broker will execute "
        "the request, build the preview and verify actual native files. You may not execute code."
    )
    extra = (
        "\nArm D also has the pinned PolyForge modeling skill and its installed compose tool. "
        "Prefer backend polyforge for supported shapes with at least one cylinder. "
        "The pinned compose tool rejects box-only meshes because it requires a reduced LOD. "
        "Give size and position in Unity XYZ and rotation about Unity Y in rotation_degrees. "
        "The engine handles the export reflection. Use the common Blender tool for box-only jobs."
        if arm == "D"
        else ""
    )
    return baseline + extra + "\n\n" + brief


def ask(
    exe: Path, cwd: Path, arm: str, brief: str, skill: Path, evidence: Path, limit: float
) -> Any:
    state = evidence / "state"
    state.mkdir()
    result = evidence / "tool-request.json"
    schema_path = evidence / "tool-schema.json"
    write(schema_path, schema(arm))
    skills = '{name="polyforge",enabled=false}'
    if arm == "D":
        local = cwd / ".agents/skills/polyforge"
        shutil.copytree(skill, local)
        skills += f",{{path={json.dumps((local / 'SKILL.md').as_posix())},enabled=true}}"
    args = [
        str(exe),
        "exec",
        "--ignore-user-config",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--model",
        "gpt-6-astra",
        "--skip-git-repo-check",
        "--cd",
        str(cwd),
        "--json",
        "-c",
        'model_reasoning_effort="low"',
        "-c",
        f"skills.config=[{skills}]",
        "-c",
        f"sqlite_home={json.dumps(state.as_posix())}",
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(result),
        model_prompt(brief, arm),
    ]
    out = evidence / "session.jsonl"
    err = evidence / "session.stderr.txt"
    job = WindowsJob(8192)
    try:
        with out.open("xb") as stdout, err.open("xb") as stderr:
            with subprocess.Popen(
                args,
                cwd=cwd,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                creationflags=0x08000204,
            ) as process:
                try:
                    job.assign_and_resume(process.pid)
                    returncode = process.wait(timeout=limit)
                except OSError:
                    process.kill()
                    process.wait(timeout=10)
                    raise
                finally:
                    job.terminate()
    finally:
        job.close()
    if returncode != 0 or not result.is_file():
        raise RuntimeError(f"Codex producer returned {returncode}")
    return read(result)


def export_request(
    job: dict[str, Any], workspace: Path, blender: Path, python: Path, limit: float
) -> Path:
    policy = WorkspacePolicy(workspace)
    payload = workspace / "native-request.json"
    if job["backend"] == "blender":
        write(payload, job)
        args = [
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
            "build",
            str(payload),
        ]
        output = policy.path("native")
        executable = blender
    else:
        compose = {
            "schema_version": "1.0.0",
            "asset_id": job["asset_id"],
            "parameters": {"size_m": [12, 8, 12], "lod_ratio": 0.75},
            "objects": [
                {
                    "id": entry["id"],
                    "primitive": entry["primitive"],
                    "size_m": entry["size"],
                    "location": entry["position"],
                    "rotation_deg": [0, entry["rotation_z"], 0],
                    "material_id": entry["material"],
                    "export": True,
                    "modifiers": [],
                }
                for entry in job["modules"]
            ],
            "sockets": job["sockets"],
        }
        write(payload, compose)
        args = [
            str(python),
            "-I",
            "-m",
            "polyforge",
            "capability",
            "run",
            "mesh.modeling.compose.v1",
            "--workspace",
            str(workspace),
            "--input",
            str(payload),
            "--json",
        ]
        executable = python
        output = None
    process = run_process(args, policy, "native", ProcessPolicy((executable,), limit))
    write(workspace / "native-process.json", asdict(process))
    if process.returncode != 0 or process.reason != "exit":
        raise RuntimeError(f"Native build {process.reason}, exit {process.returncode}")
    if output is None:
        result = read(policy.path(process.stdout_path))
        if result["status"] != "PASS":
            raise RuntimeError("PolyForge output did not pass its own contract")
        output = policy.path(result["data"]["source_blend"]).parent
        shutil.copyfile(policy.path(output / "iso.png"), output / "preview.png")
    return output


def run_one(manifest: dict[str, Any], case: dict[str, Any], arm: str, directory: Path) -> None:
    case_id = case["id"]
    assert ID.fullmatch(case_id) and arm in {"C", "D"}
    brief = REPO / case["brief_path"]
    if sha(brief) != case["brief_sha256"]:
        raise ValueError("Frozen brief hash mismatch")
    blender = discover_tool("blender")
    if blender is None or sha(blender) != manifest["blender_sha256"]:
        raise ValueError("Frozen Blender executable differs")
    python = REPO / manifest["arm_d_python"]
    exe = Path(os.environ["APPDATA"]) / manifest["codex_executable_relative_to_appdata"]
    if sha(exe) != manifest["codex_executable_sha256"]:
        raise ValueError("Frozen Codex executable differs")
    skill = REPO / manifest["arm_d_skill"]
    if sha(skill / "SKILL.md") != manifest["arm_d_skill_sha256"]:
        raise ValueError("Frozen skill differs")
    directory.mkdir(parents=True, exist_ok=False)
    scratch = Path(tempfile.mkdtemp(prefix=f"polyforge-p13-{arm.lower()}-"))
    started = time.monotonic()
    status = "BLOCKED"
    detail = None
    artifacts = {}
    outcome: dict[str, Any] = {
        "id": f"{case_id}_{arm.lower()}",
        "case_id": case_id,
        "arm": arm,
        "start_utc": datetime.now(UTC).isoformat(),
        "brief_sha256": case["brief_sha256"],
        "manual_corrections": 0,
        "cost": None,
        "retries": 0,
    }
    try:
        remaining = (
            (datetime.fromisoformat(manifest["deadline_utc"]) - datetime.now(UTC)).total_seconds()
            if "deadline_utc" in manifest
            else math.inf
        )
        cap = min(manifest["attempt_timeout_seconds"], remaining)
        if cap <= 1:
            raise RuntimeError("Pilot deadline elapsed")
        proposal = ask(
            exe,
            scratch,
            arm,
            brief.read_text(encoding="utf-8"),
            skill,
            directory,
            min(cap / 2, 140),
        )
        job = request(proposal, arm, case_id)
        outcome["backend"] = job["backend"]
        outcome["model_seconds"] = time.monotonic() - started
        output = export_request(job, scratch, blender, python, cap - (time.monotonic() - started))
        for name in ARTIFACTS:
            file = WorkspacePolicy(output).path(name)
            if not file.is_file() or file.stat().st_size > 32 * 1024 * 1024:
                raise ValueError(f"Output {name} absent or above size cap")
            shutil.copyfile(file, directory / name)
            artifacts[name] = sha(directory / name)
        status = "PRODUCED"
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        detail = str(error)
        if isinstance(error, subprocess.TimeoutExpired):
            status = "TIMEOUT"
    finally:
        if (scratch / "native-process.json").is_file():
            shutil.copyfile(scratch / "native-process.json", directory / "native-process.json")
        for filename in ("stdout.txt", "stderr.txt"):
            if (scratch / "native" / filename).is_file():
                shutil.copyfile(scratch / "native" / filename, directory / ("native-" + filename))
        usage = {}
        events = directory / "session.jsonl"
        if events.is_file() and events.stat().st_size <= 4 * 1024 * 1024:
            for line in events.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "turn.completed":
                    usage = event.get("usage", {})
        write(
            directory / "receipt.json",
            {
                **outcome,
                "status": status,
                "detail": detail,
                "artifacts": artifacts,
                "producer_seconds": round(time.monotonic() - started, 3),
                "token_usage": usage,
                "end_utc": datetime.now(UTC).isoformat(),
                "workspace": str(scratch),
            },
        )
        print(f"{outcome['id']} {status}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--reuse", metavar="CASE_ID")
    parser.add_argument("--reuse-python", type=Path)
    parser.add_argument("--reuse-skill", type=Path)
    args = parser.parse_args()
    if sha(args.manifest) != args.manifest_sha256:
        raise ValueError("Frozen manifest SHA-256 mismatch")
    manifest = read(args.manifest)
    if manifest["parity_status"] != "VERIFIED_FOR_DATA_ONLY_BROKER":
        raise ValueError("Producer parity has not passed preflight")
    for file, expected in manifest["fixed_file_sha256"].items():
        if sha(REPO / file) != expected:
            raise ValueError(f"Frozen file differs: {file}")
    cases = {item["id"]: item for item in manifest["cases"]}
    if len(cases) != 5:
        raise ValueError("Exactly five frozen cases are required")
    pairs = [(args.reuse, "D")] if args.reuse else manifest["attempt_order"]
    if not args.reuse and (
        len(pairs) != 10
        or {(case, arm) for case, arm in pairs}
        != {(case, arm) for case in cases for arm in ("C", "D")}
    ):
        raise ValueError("Attempt schedule must include all ten pairs")
    if args.reuse:
        if args.reuse_python is None or args.reuse_skill is None:
            raise ValueError("Clean reuse requires a fresh installation and skill checkout")
        manifest = {
            **manifest,
            "arm_d_python": str(args.reuse_python.resolve()),
            "arm_d_skill": str(args.reuse_skill.resolve()),
        }
    elif args.reuse_python is not None or args.reuse_skill is not None:
        raise ValueError("Reuse overrides are available only during the immediate reuse test")
    args.output.mkdir(exist_ok=False)
    for case, arm in pairs:
        run_one(manifest, cases[case], arm, args.output / f"{case}_{arm.lower()}")


if __name__ == "__main__":
    main()
