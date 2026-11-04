"""Rendered Windows player profiles; public development evidence is not game acceptance."""

from __future__ import annotations

import hashlib
import math
import re
import statistics
from dataclasses import asdict
from pathlib import Path
from typing import Any, TypeGuard
from uuid import uuid4

from polyforge.contracts.results import ErrorKind, Result
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.artifacts import complete_records
from polyforge.runner.locks import unity_project_lock
from polyforge.runner.metrics import ProcessObservation
from polyforge.runner.processes import ProcessOutcome, ProcessPolicy, run_process
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bridge import configuration

DEFAULT_PROFILE: dict[str, Any] = {
    "schema_version": "1.0.0",
    "resolution": [1280, 720],
    "quality_setting": "PC",
    "focus_policy": "OBSERVE_CONTINUOUS_BACKGROUND_ENABLED",
    "renderer_observation": "UNITY_END_OF_FRAME",
    "run_in_background": True,
    "warmup_seconds": 10,
    "samples": 3,
    "sample_seconds": 60,
    "targets": {
        "median_fps_min": 30,
        "p95_frame_ms_max": 50,
        "peak_rss_bytes_max": 2147483648,
        "load_seconds_max": 30,
    },
}


def _finite(value: Any, *, positive: bool = False) -> TypeGuard[int | float]:
    try:
        return (
            type(value) in {int, float}
            and math.isfinite(value)
            and (value > 0 if positive else value >= 0)
        )
    except OverflowError:
        return False


def _sample(item: dict[str, Any], index: int) -> dict[str, Any]:
    issues: list[str] = []
    metrics: dict[str, Any] = {
        "sample_index": index,
        "median_fps": None,
        "p95_frame_ms": None,
        "cpu_seconds": None,
    }

    def require(condition: bool, message: str) -> None:
        if not condition:
            issues.append(message)

    require(item.get("schema_version") == "1.0.0", "Unknown evidence version")
    require(item.get("scope") == "WINDOWS_STANDALONE_RENDERED", "Not rendered player evidence")
    require(
        type(item.get("sample_index")) is int and item["sample_index"] == index,
        "Missing/duplicate/out-of-order sample index",
    )
    require(
        item.get("complete") is True and item.get("sample_overflow") is False,
        "Incomplete or truncated frame sample",
    )
    require(
        item.get("is_editor") is False and item.get("batchmode") is False,
        "Editor/headless samples cannot qualify",
    )
    require(
        item.get("graphics_type") in ("Direct3D11", "Direct3D12", "Vulkan", "OpenGLCore"),
        "Missing/Null/unknown graphics device",
    )
    require([item.get("width"), item.get("height")] == [1280, 720], "Resolution mismatch")
    require(item.get("quality") == "PC", "Declared PC quality mismatch")
    require(
        item.get("v_sync") == 0 and item.get("target_frame_rate") == -1,
        "Frame pacing differs from declared profile",
    )
    require(
        item.get("focus_policy") == DEFAULT_PROFILE["focus_policy"]
        and item.get("renderer_observation") == DEFAULT_PROFILE["renderer_observation"]
        and item.get("run_in_background") is True,
        "Missing/mismatched continuous render-loop focus/background policy",
    )
    require(
        item.get("gpu_presentation") == "NOT_MEASURED",
        "GPU/display presentation was not independently measured",
    )
    focus_counts_valid = all(
        type(item.get(key)) is int and 0 <= item[key] <= 1_000_000
        for key in ("focused_frames", "unfocused_frames", "focus_changes")
    )
    require(focus_counts_valid, "Missing/invalid measurement focus counts")
    if focus_counts_valid:
        frames = item.get("frames_recorded")
        require(
            type(frames) is int
            and item["focused_frames"] + item["unfocused_frames"] == frames
            and item["focus_changes"] <= frames,
            "Focus counts do not cover the recorded measurement frames",
        )
        require(
            type(item.get("focused")) is bool
            and item["focused"] == (item["unfocused_frames"] == 0),
            "Focused aggregate contradicts measured closing-state counts",
        )
        minority = min(item["focused_frames"], item["unfocused_frames"])
        require(
            item["focus_changes"] <= 2 * minority + 1
            and (minority == 0 or item["focus_changes"] >= 1),
            "Focus transition count is impossible for the recorded closing states",
        )
    metrics.update(
        {
            key: item.get(key)
            for key in (
                "focus_policy",
                "renderer_observation",
                "run_in_background",
                "focused",
                "focused_frames",
                "unfocused_frames",
                "focus_changes",
            )
        }
    )
    metrics["gpu_presentation"] = "NOT_MEASURED"
    require(
        all(
            type(item.get(key)) is int
            for key in ("width", "height", "v_sync", "target_frame_rate", "frames_recorded")
        ),
        "Invalid integer profile fields",
    )
    warmup, duration = item.get("warmup_seconds"), item.get("measurement_seconds")
    require(_finite(warmup) and 10 <= warmup <= 11, "Warmup incomplete/outside declared window")
    require(_finite(duration) and 60 <= duration <= 61, "Measurement window incomplete/overlong")
    for key in ("input_digest", "profile_digest", "executable_sha256"):
        value = item.get(key)
        require(
            isinstance(value, str)
            and len(value) == 64
            and all(c in "0123456789abcdef" for c in value),
            "Invalid " + key,
        )
    for key in ("scene_id", "scene", "unity_version", "build_type"):
        require(isinstance(item.get(key), str) and bool(item[key]), "Missing " + key)
    require(item.get("unity_version") == "6000.6.3f1", "Unsupported Unity version")
    require(item.get("build_type") in ("Development", "Release"), "Unknown build type")
    require(item.get("game_kind") == "arena", "Unsupported profile workload")
    hardware = item.get("hardware", {})
    require(
        isinstance(hardware, dict)
        and all(
            isinstance(hardware.get(key), str) and bool(hardware[key].strip())
            for key in ("cpu", "gpu", "gpu_driver")
        )
        and all(
            type(hardware.get(key)) is int and hardware[key] > 0
            for key in ("logical_cpus", "ram_bytes")
        ),
        "Missing hardware identity",
    )
    times = item.get("frame_times_ms")
    if (
        isinstance(times, list)
        and 0 < len(times) <= 1_000_000
        and all(_finite(value, positive=True) for value in times)
    ):
        require(item.get("frames_recorded") == len(times), "Frame count mismatch/truncation")
        require(
            _finite(duration) and abs(sum(times) / 1000 - duration) <= 0.1,
            "Recorded intervals do not cover the measurement window",
        )
        median = statistics.median(1000 / value for value in times)
        p95 = sorted(times)[math.ceil(0.95 * len(times)) - 1]
        require(math.isfinite(median), "Computed FPS is nonfinite")
        metrics.update(
            median_fps=median if math.isfinite(median) else None,
            p95_frame_ms=p95,
            elapsed_fps=len(times) / (sum(times) / 1000) if sum(times) / 1000 > 0 else None,
        )
        require(median >= 30, "Median FPS below 30")
        require(p95 <= 50, "P95 frame time above 50ms")
    else:
        issues.append("Missing/nonfinite/zero/overflowed frame intervals")
    activity = item.get("activity", {})
    require(
        isinstance(activity, dict)
        and all(
            _finite(activity.get(key), positive=True)
            for key in ("ticks", "restarts", "player_distance", "enemy_distance")
        ),
        "Active game workload missing/frozen",
    )
    process = item.get("process", {})
    if not isinstance(process, dict):
        process = {}
    require(
        process.get("reason") == "exit"
        and type(process.get("returncode")) is int
        and process["returncode"] == 0,
        "Player process failed/timed out",
    )
    require(
        type(process.get("pid")) is int
        and 0 < process["pid"] < 2**31
        and isinstance(process.get("birth"), str)
        and re.fullmatch(r"[0-9]{1,20}", process["birth"]) is not None
        and 0 < int(process["birth"]) < 2**64
        and process.get("identity_status") == "BOUND"
        and process.get("rss_source") == "WINDOWS_PEAK_WORKING_SET",
        "Missing or invalid owned process identity/resource source",
    )
    require(
        process.get("fatal") is False and process.get("errors") == [],
        "Process observation failed or is incomplete",
    )
    require(process.get("ready_observed") is True, "No externally observed rendered readiness")
    load, rss = process.get("ready_seconds"), process.get("peak_rss_bytes")
    require(_finite(load, positive=True) and load <= 30, "Load exceeds 30s or is unknown")
    require(type(rss) is int and 0 < rss <= 2147483648, "Peak RSS exceeds 2GiB or is unknown")
    cpu = process.get("cpu_seconds")
    require(cpu is None or _finite(cpu), "Invalid CPU observation")
    metrics.update(
        cpu_seconds=cpu,
        load_seconds=load,
        peak_rss_bytes=rss,
        status="FAIL" if issues else "PASS",
        issues=issues,
    )
    return metrics


def score_profile(samples: list[dict[str, Any]]) -> dict[str, Any]:
    """Every sample must pass; never discard a run or average a failure away."""
    issues = (
        []
        if isinstance(samples, list) and len(samples) == 3
        else ["Exactly three samples required"]
    )
    results = []
    identities = []
    for index, raw in enumerate(samples if isinstance(samples, list) else []):
        item = raw if isinstance(raw, dict) else {}
        result = _sample(item, index)
        results.append(result)
        issues.extend(f"Sample {index}: {message}" for message in result["issues"])
        identities.append(
            {
                key: item.get(key)
                for key in (
                    "input_digest",
                    "profile_digest",
                    "scene_id",
                    "scene",
                    "game_kind",
                    "unity_version",
                    "build_type",
                    "hardware",
                    "quality",
                    "width",
                    "height",
                    "graphics_type",
                    "executable_sha256",
                    "build_digest",
                    "focus_policy",
                    "renderer_observation",
                    "run_in_background",
                )
            }
        )
    if identities and any(identity != identities[0] for identity in identities[1:]):
        issues.append("Hardware/build/scene/profile identity changed between samples")
    medians = [item["median_fps"] for item in results if item["median_fps"] is not None]
    return {
        "status": "FAIL" if issues else "PASS",
        "scope": "PUBLIC_DEVELOPMENT",
        "qualification": False,
        "samples": results,
        "issues": issues,
        "median_fps_across_samples": statistics.median(medians) if medians else None,
        "fps_spread_percent": ((max(medians) - min(medians)) / statistics.median(medians) * 100)
        if medians
        else None,
        "gpu_utilization": "UNKNOWN",
        "focus_policy": DEFAULT_PROFILE["focus_policy"],
        "renderer_observation": DEFAULT_PROFILE["renderer_observation"],
        "gpu_presentation": "NOT_MEASURED",
        "measurement_limitations": [
            "CPU wall-clock end-of-frame intervals do not independently measure GPU execution "
            "or physical display presentation.",
            "Focus counts classify each interval at its closing observation, not its entire "
            "duration or intervening focus events.",
        ],
    }


def _player_run(policy: WorkspacePolicy, player: Path) -> Path:
    relative = player.relative_to(policy.root).as_posix()
    if not re.fullmatch(
        r"runs/game-check-[A-Za-z0-9_-]{1,80}/player/PolyForgeArena\.exe", relative
    ):
        raise InputError("Player is not an engine-owned arena build", kind=ErrorKind.POLICY_DENIED)
    if configuration(policy).mode != "TRUSTED_LOCAL":
        raise InputError("Player profiling requires TRUSTED_LOCAL", kind=ErrorKind.POLICY_DENIED)
    return player.parent.parent


def _file_record(policy: WorkspacePolicy, path: Path) -> dict[str, Any]:
    path = policy.path(path)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1_048_576):
            digest.update(chunk)
    return {
        "relative_path": path.relative_to(policy.root).as_posix(),
        "sha256": digest.hexdigest(),
        "bytes": path.stat().st_size,
    }


def _payload_records(policy: WorkspacePolicy, player: Path) -> list[dict[str, Any]]:
    records = []
    for source in sorted(player.parent.rglob("*")):
        source = policy.path(source)
        relative = source.relative_to(player.parent)
        # Only fixed non-executable engine reports may appear after the build seal.
        if relative.parts[0] != "profiles" and relative.as_posix() != "smoke-evidence.json":
            if source.is_file():
                records.append(_file_record(policy, source))
    return records


def _build_inputs(policy: WorkspacePolicy, player: Path) -> tuple[dict[str, Any], list[Path]]:
    run = _player_run(policy, player)
    paths = [run / "game-input.json", run / "player-input.json", run / "player-build/process.json"]
    job, build, process = [load_json(policy.path(path)) for path in paths]
    if not all(isinstance(value, dict) for value in (job, build, process)):
        raise InputError("Malformed native player build provenance")
    output = build.get("player_output")
    argv = process.get("argv", [])
    if (
        not isinstance(output, str)
        or policy.path(output) != player
        or {key: value for key, value in build.items() if key != "player_output"} != job
        or not re.fullmatch(r"[a-f0-9]{64}", str(job.get("input_digest", "")))
        or not isinstance(job.get("scene_id"), str)
        or not job["scene_id"]
        or process.get("reason") != "exit"
        or process.get("returncode") != 0
        or not isinstance(argv, list)
        or not all(isinstance(arg, str) for arg in argv)
        or not argv
        or Path(argv[0]).stem.lower() != "unity"
    ):
        raise InputError("Player build provenance does not bind the owned native build")
    for flag, value in (
        ("-executeMethod", "PolyForge.Game.Editor.GameBuilder.BuildPlayerBatch"),
        ("-polyforgeGameInput", str(paths[1])),
    ):
        if (
            argv.count(flag) != 1
            or argv.index(flag) + 1 >= len(argv)
            or argv[argv.index(flag) + 1] != value
        ):
            raise InputError("Player build provenance has a different native entry point/input")
    return job, paths


def seal_player_build(policy: WorkspacePolicy, player: Path) -> Path:
    """Called by the owned builder immediately after native build, before smoke."""
    player = policy.path(player)
    job, paths = _build_inputs(policy, player)
    run = _player_run(policy, player)
    payload = _payload_records(policy, player)
    records = complete_records(
        policy,
        run.name,
        "S5",
        payload + [_file_record(policy, path) for path in paths],
        input_digest=job["input_digest"],
    )
    return atomic_json(
        policy,
        run / "player-build-artifacts.json",
        {
            "schema_version": "1.0.0",
            "scope": "OWNED_NATIVE_PLAYER_BUILD",
            "input_digest": job["input_digest"],
            "payload": payload,
            "artifacts": records,
        },
    )


def _registered_player(
    policy: WorkspacePolicy, player: Path
) -> tuple[dict[str, Any], tuple[dict[str, Any], ...]]:
    run = _player_run(policy, player)
    job, _ = _build_inputs(policy, player)
    receipt_path = policy.path(run / "player-build-artifacts.json")
    registry = load_json(policy.path(run / "artifacts.json"))
    receipt = load_json(receipt_path)
    payload = _payload_records(policy, player)
    if (
        not isinstance(registry, dict)
        or not isinstance(receipt, dict)
        or receipt.get("scope") != "OWNED_NATIVE_PLAYER_BUILD"
        or receipt.get("input_digest") != job["input_digest"]
        or receipt.get("payload") != payload
    ):
        raise InputError("Player payload differs from its registered owned build")
    rows = registry.get("artifacts", [])
    receipt_record = _file_record(policy, receipt_path)
    if not isinstance(rows, list) or not any(
        isinstance(row, dict)
        and row.get("run_id") == run.name
        and all(row.get(key) == value for key, value in receipt_record.items())
        for row in rows
    ):
        raise InputError("Player build receipt is not sealed in its game-check artifact registry")
    sealed = receipt.get("artifacts")
    if not isinstance(sealed, list) or not sealed:
        raise InputError("Player build receipt has no observed artifacts")
    for row in sealed:
        if (
            not isinstance(row, dict)
            or row.get("run_id") != run.name
            or not isinstance(row.get("relative_path"), str)
        ):
            raise InputError("Player build artifact ownership is invalid")
        observed = _file_record(policy, policy.path(row["relative_path"]))
        if any(row.get(key) != value for key, value in observed.items()):
            raise InputError("Player build input/data artifacts were changed after registration")
    return job, tuple(payload)


def _build_digest(policy: WorkspacePolicy, player: Path) -> str:
    """Fingerprint current payload for comparison with the validated build records."""
    return canonical_digest(_payload_records(policy, player))


def profile_player(workspace: Path, player: Path, *, dry_run: bool = False) -> Result:
    """Measure an existing arena player in three owned, rendered Windows launches."""
    policy = WorkspacePolicy(workspace)
    player = policy.path(player)
    if not player.is_file() or player.suffix.lower() != ".exe":
        raise InputError("Profile requires a workspace-owned Windows player executable")
    job, registered_payload = _registered_player(policy, player)
    if dry_run:
        return Result(
            data={
                "dry_run": True,
                "execution_status": "NOT_RUN",
                "launches": 3,
                "warmup_seconds": 10,
                "sample_seconds": 60,
                "profile": DEFAULT_PROFILE,
                "planned_writes": [],
            }
        )
    config = configuration(policy)
    run_id = "profile-" + uuid4().hex[:16]
    relative = (player.parent.relative_to(policy.root) / "profiles" / run_id).as_posix()
    profile_digest = canonical_digest(DEFAULT_PROFILE)
    player_relative = player.relative_to(policy.root).as_posix()
    player_record = next(
        (row for row in registered_payload if row["relative_path"] == player_relative), None
    )
    if player_record is None:
        raise InputError("Registered player payload has no executable identity")
    player_hash: str = player_record["sha256"]
    build_digest = canonical_digest(registered_payload)
    samples = []
    evidence_paths = []
    with unity_project_lock(policy, policy.path("UnityProject")):
        if tuple(_payload_records(policy, player)) != registered_payload:
            raise InputError("Player executable/data changed after registration validation")
        for index in range(3):
            sample_relative = relative + f"/sample-{index}"
            ready = policy.path(sample_relative + "/ready.json")
            evidence = policy.path(sample_relative + "/evidence.json")
            request = atomic_json(
                policy,
                sample_relative + "/input.json",
                {
                    "schema_version": "1.0.0",
                    "game_kind": "arena",
                    "sample_index": index,
                    "scene_id": job["scene_id"],
                    "input_digest": job["input_digest"],
                    "profile_digest": profile_digest,
                    "executable_sha256": player_hash,
                    "quality_name": "PC",
                    "focus_policy": DEFAULT_PROFILE["focus_policy"],
                    "renderer_observation": DEFAULT_PROFILE["renderer_observation"],
                    "run_in_background": True,
                    "ready_path": str(ready),
                    "evidence_path": str(evidence),
                },
            )
            observation = ProcessObservation(policy, sample_relative, str(ready))
            launch_error = None
            try:
                if _build_digest(policy, player) != build_digest:
                    raise InputError("Player executable/data changed during profile")
                outcome = run_process(
                    [
                        str(player),
                        "-screen-width",
                        "1280",
                        "-screen-height",
                        "720",
                        "-screen-fullscreen",
                        "0",
                        "-logFile",
                        "-",
                        "-polyforgeProfileInput",
                        str(request),
                    ],
                    policy,
                    sample_relative,
                    ProcessPolicy(
                        (player,),
                        timeout_seconds=120,
                        max_output_bytes=config.max_output_bytes,
                        memory_limit_mb=config.memory_limit_mb,
                    ),
                    observation=observation,
                )
            except (InputError, OSError, KeyboardInterrupt) as exc:
                launch_error = str(exc) or "Profile interrupted"
                outcome = ProcessOutcome(
                    None,
                    "cancelled" if isinstance(exc, KeyboardInterrupt) else "launch_failure",
                    observation.data["pid"],
                    "UNKNOWN",
                    0,
                    "",
                    "",
                    False,
                )
            atomic_json(policy, sample_relative + "/process.json", asdict(outcome))
            try:
                raw = (
                    load_json(policy.path(evidence), max_bytes=33_554_432)
                    if evidence.is_file()
                    else {}
                )
                canonical_digest(raw)
            except (InputError, OSError) as exc:
                raw = {"error": str(exc)}
            if not isinstance(raw, dict):
                raw = {}
            if launch_error is not None:
                raw.update(error=launch_error, complete=False)
            raw["build_digest"] = build_digest
            raw["process"] = {
                **observation.data,
                "reason": outcome.reason,
                "returncode": outcome.returncode,
            }
            # Player evidence must bind the exact request, not merely agree with other samples.
            if any(
                raw.get(key) != value
                for key, value in {
                    "sample_index": index,
                    "scene_id": job["scene_id"],
                    "input_digest": job["input_digest"],
                    "profile_digest": profile_digest,
                    "executable_sha256": player_hash,
                }.items()
            ):
                raw["complete"] = False
            if _build_digest(policy, player) != build_digest:
                raw.update(
                    complete=False, error="Player executable/data changed during measurement"
                )
            samples.append(raw)
            atomic_json(policy, sample_relative + "/observed.json", raw)
            evidence_paths.append(sample_relative + "/observed.json")
            if _sample(raw, index)["status"] != "PASS":
                break
    verdict = score_profile(samples)
    verdict.update(
        profile=DEFAULT_PROFILE, executable_sha256=player_hash, build_digest=build_digest
    )
    atomic_json(policy, relative + "/profile.json", verdict)
    evidence_paths.append(relative + "/profile.json")
    records = []
    for path in sorted(policy.path(relative).rglob("*")):
        path = policy.path(path)
        if path.is_file():
            records.append(
                {
                    "relative_path": path.relative_to(policy.root).as_posix(),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size,
                }
            )
    artifacts = complete_records(policy, run_id, "S5", records, input_digest=job["input_digest"])
    atomic_json(policy, relative + "/artifacts.json", {"artifacts": artifacts})
    passed = verdict["status"] == "PASS"
    return Result(
        status="PASS" if passed else "FAIL",
        exit_code=0 if passed else 7,
        error_code=None if passed else "PF-PLAYER-PROFILE",
        run_id=run_id,
        evaluated_test_status="PASS" if passed else "FAIL",
        input_digest=job["input_digest"],
        data=verdict,
        evidence_paths=evidence_paths,
        artifact_ids=[item["artifact_id"] for item in artifacts],
    )
