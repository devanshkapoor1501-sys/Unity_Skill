"""Public development oracles, independent of generator intent and success events."""

from __future__ import annotations

import math
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest

CORE_SCENARIOS = (
    "player_moves",
    "wall_collision",
    "enemy_patrols",
    "contact_damage",
    "health_failure",
    "survival_win",
    "restart_resets",
)

MUTANT_SCENARIOS = {
    "collision_disabled": "wall_collision",
    "restart_disabled": "restart_resets",
    "win_reversed": "survival_win",
    "damage_no_health": "contact_damage",
    "navigation_stuck": "enemy_patrols",
    "input_disconnected": "player_moves",
}


def validate_trace(
    trace: dict[str, Any], game: dict[str, Any], identifier: str, ticks: int
) -> None:
    """Malformed/unexecuted mutants must not count as detected regressions."""
    canonical_digest(trace)
    expected_case = {
        "keyboard_input": "player_moves",
        "keyboard_restart": "restart_resets",
        **MUTANT_SCENARIOS,
    }.get(identifier, identifier)
    mutant = identifier in MUTANT_SCENARIOS
    purpose = (
        "MUTANT" if mutant else "INPUT_ADAPTER" if identifier.startswith("keyboard_") else "NOMINAL"
    )
    try:
        if (
            trace["input_digest"] != game["input_digest"]
            or trace["scene_id"] != game["scene_id"]
            or trace["scenario_id"] != expected_case
            or trace["purpose"] != purpose
            or trace["seed"] != game["seed"]
            or (mutant and trace["mutant"] != identifier)
            or not math.isclose(trace["fixed_delta_seconds"], 0.02, abs_tol=1e-6)
            or not ticks <= trace["frames_executed"] <= ticks + 3
            or len(trace["samples"]) < 2
        ):
            raise ValueError("identity/role/frame schedule mismatch")
        frames = [s["frame"] for s in trace["samples"]]
        if any(type(f) is not int for f in frames) or any(
            a >= b for a, b in zip(frames, frames[1:], strict=False)
        ):
            raise ValueError("nonmonotonic observed frames")
        if frames[-1] - frames[0] != trace["frames_executed"]:
            raise ValueError("frame count mismatch")
        enemy_ids = {e["id"] for e in game["enemies"]}

        def positions(records: Any) -> None:
            if (
                not isinstance(records, list)
                or len(records) != len(enemy_ids)
                or {e["id"] for e in records} != enemy_ids
            ):
                raise ValueError("missing/duplicate semantic enemy IDs")
            for record in records:
                vector(record["position"])

        def vector(value: Any) -> None:
            if (
                not isinstance(value, list)
                or len(value) != 3
                or any(type(n) not in {int, float} or not math.isfinite(n) for n in value)
            ):
                raise ValueError("invalid position vector")

        if not isinstance(trace["events"], list) or any(
            not isinstance(e["name"], str) for e in trace["events"]
        ):
            raise ValueError("invalid events")
        if expected_case == "wall_collision":
            half = trace["arena_half_extents"]
            if (
                not isinstance(half, list)
                or len(half) != 2
                or any(type(n) not in {int, float} or not math.isfinite(n) or n <= 0 for n in half)
            ):
                raise ValueError("invalid arena bounds")
            for key in ("player_radius", "wall_thickness"):
                if type(trace[key]) not in {int, float} or not 0 < trace[key] < min(half):
                    raise ValueError("invalid collision dimensions")
        if expected_case == "restart_resets":
            vector(trace["baseline_player_position"])
            positions(trace["baseline_enemy_positions"])
        for sample in trace["samples"]:
            positions(sample["enemy_positions"])
            if (
                len(sample["player_position"]) != 3
                or sample["state"] not in {"RUNNING", "WON", "FAILED"}
                or type(sample["health"]) is not int
                or not 0 <= sample["health"] <= 100
                or type(sample["round"]) is not int
                or sample["round"] < 1
                or not 0 <= sample["elapsed_seconds"] <= 30.1
                or {e["id"] for e in sample["enemy_positions"]}
                != {e["id"] for e in game["enemies"]}
            ):
                raise ValueError("invalid observed state")
            for position in [
                sample["player_position"],
                *[e["position"] for e in sample["enemy_positions"]],
            ]:
                if len(position) != 3 or any(
                    type(n) not in {int, float} or not math.isfinite(n) for n in position
                ):
                    raise ValueError("invalid position vector")
    except (KeyError, TypeError, ValueError) as exc:
        raise InputError(
            "Invalid gameplay telemetry: " + str(exc),
            kind=ErrorKind.CONTRACT_FAILURE,
            code="PF-GAME-TELEMETRY",
        ) from exc


def distance(a: list[float], b: list[float]) -> float:
    return math.dist([a[0], a[2]], [b[0], b[2]])


def evaluate(trace: dict[str, Any]) -> dict[str, Any]:
    """Score observed transforms/health/state; event labels alone never suffice."""
    issues = []
    try:
        samples = trace["samples"]
        if len(samples) < 2 or trace["frames_executed"] < 1:
            raise ValueError("No executed observations")
        first, last = samples[0], samples[-1]
        identifier = trace["scenario_id"]
        if identifier == "player_moves":
            if distance(first["player_position"], last["player_position"]) < 0.5:
                issues.append("Player did not move at least 0.5m")
        elif identifier == "wall_collision":
            half = trace["arena_half_extents"]
            limit = half[0] - trace["wall_thickness"] - trace["player_radius"]
            if (
                last["player_position"][0] < -limit - 0.1
                or last["player_position"][0] > -limit + 0.5
                or distance(first["player_position"], last["player_position"]) < 1
            ):
                issues.append("Wall did not stop actual player movement at its inner boundary")
        elif identifier == "enemy_patrols":
            initial = {e["id"]: e["position"] for e in first["enemy_positions"]}
            final = {e["id"]: e["position"] for e in last["enemy_positions"]}
            if (
                not initial
                or set(initial) != set(final)
                or any(distance(initial[k], final[k]) < 0.5 for k in initial)
            ):
                issues.append("One or more declared enemies did not patrol")
        elif identifier == "contact_damage":
            if last["health"] >= first["health"] or not any(
                e["name"] == "damage" for e in trace["events"]
            ):
                issues.append("Contact produced no observed health loss and damage evidence")
        elif identifier == "health_failure":
            if last["health"] != 0 or last["state"] != "FAILED":
                issues.append("Zero health did not produce failure")
        elif identifier == "survival_win":
            if last["state"] != "WON" or last["elapsed_seconds"] < 29.94 or last["health"] <= 0:
                issues.append("Surviving thirty seconds did not win")
        elif identifier == "restart_resets":
            if (
                last["state"] != "RUNNING"
                or last["health"] != 100
                or last["elapsed_seconds"] > 0.2
                or last["round"] <= first["round"]
                or distance(last["player_position"], trace["baseline_player_position"]) > 0.1
            ):
                issues.append("Restart did not restore position, health, time and running state")
            expected = {e["id"]: e["position"] for e in trace["baseline_enemy_positions"]}
            actual = {e["id"]: e["position"] for e in last["enemy_positions"]}
            if set(actual) != set(expected) or any(
                distance(actual[k], expected[k]) > 0.1 for k in expected
            ):
                issues.append("Restart did not restore enemy positions")
        else:
            issues.append("Unknown public arena oracle")
        for sample in samples:
            if any(not math.isfinite(n) for n in sample.get("player_position", [])):
                issues.append("Nonfinite observed position")
    except (KeyError, TypeError, ValueError) as exc:
        issues.append("Invalid observed telemetry: " + str(exc))
    return {
        "status": "FAIL" if issues else "PASS",
        "issues": issues,
        "oracle_owner": "PUBLIC_DEVELOPMENT",
        "hidden_evaluation": "NOT_RUN",
    }
