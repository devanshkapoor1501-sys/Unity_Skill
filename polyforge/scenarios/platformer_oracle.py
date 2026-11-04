"""Public development scoring of observed 2D physics, independent of scene production."""

from __future__ import annotations

import math
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest

CORE_SCENARIOS = (
    "player_moves",
    "ground_collision",
    "grounded_jump",
    "airborne_jump",
    "checkpoint_respawn",
    "hazard_damage",
    "health_failure",
    "goal_contact",
    "restart_resets",
    "restart_failure",
    "journey",
)
MUTANT_SCENARIOS = {
    "input_disconnected": "player_moves",
    "jump_disabled": "grounded_jump",
    "platform_disabled": "ground_collision",
    "checkpoint_disabled": "checkpoint_respawn",
    "damage_no_health": "hazard_damage",
    "goal_disabled": "goal_contact",
    "win_premature": "goal_contact",
    "restart_disabled": "restart_resets",
}
INPUT_SCENARIOS = {
    "keyboard_move": "player_moves",
    "keyboard_jump": "grounded_jump",
    "keyboard_restart": "restart_resets",
}


def validate_trace(
    trace: dict[str, Any], game: dict[str, Any], identifier: str, ticks: int, schedule_digest: str
) -> None:
    """Reject malformed or unexecuted mutants before interpreting behavioral failure."""
    canonical_digest(trace)
    try:
        expected = MUTANT_SCENARIOS.get(identifier, INPUT_SCENARIOS.get(identifier, identifier))
        purpose = (
            "MUTANT"
            if identifier in MUTANT_SCENARIOS
            else ("INPUT_ADAPTER" if identifier in INPUT_SCENARIOS else "NOMINAL")
        )
        if (
            expected not in CORE_SCENARIOS
            or trace["scenario_id"] != expected
            or trace["purpose"] != purpose
            or trace["input_digest"] != game["input_digest"]
            or trace["scene_id"] != game["scene_id"]
            or trace["seed"] != game["seed"]
            or trace["schedule_digest"] != schedule_digest
            or trace.get("mutant", "") != (identifier if purpose == "MUTANT" else "")
            or not math.isclose(trace["fixed_delta_seconds"], 0.02, abs_tol=1e-7)
            or type(trace["frames_executed"]) is not int
            or not ticks <= trace["frames_executed"] <= ticks + 3
        ):
            raise ValueError("identity, purpose or executed schedule mismatch")
        samples = trace["samples"]
        if not isinstance(samples, list) or not 2 <= len(samples) <= 4000:
            raise ValueError("missing/bounded physical samples")
        frames = [s["frame"] for s in samples]
        if (
            any(type(f) is not int for f in frames)
            or any(a >= b for a, b in zip(frames, frames[1:], strict=False))
            or frames[-1] - frames[0] != trace["frames_executed"]
        ):
            raise ValueError("nonmonotonic/inconsistent frame observations")
        for s in samples:
            for field in ("position", "velocity"):
                if (
                    not isinstance(s[field], list)
                    or len(s[field]) != 3
                    or any(type(n) not in {int, float} or not math.isfinite(n) for n in s[field])
                ):
                    raise ValueError("nonfinite physical vector")
            if (
                type(s["grounded"]) is not bool
                or type(s["health"]) is not int
                or not 0 <= s["health"] <= 3
                or s["state"] not in {"RUNNING", "WON", "FAILED"}
                or type(s["round"]) is not int
                or s["round"] < 1
                or s["checkpoint"] not in {"spawn", "checkpoint"}
                or type(s["elapsed_seconds"]) not in {int, float}
                or not 0 <= s["elapsed_seconds"] <= 80
            ):
                raise ValueError("invalid observed session state")
        for field in (
            "spawn",
            "checkpoint_position",
            "goal_center",
            "goal_size",
            "hazard_center",
            "hazard_size",
        ):
            vector = trace[field]
            if (
                not isinstance(vector, list)
                or len(vector) != 3
                or any(type(n) not in {int, float} or not math.isfinite(n) for n in vector)
            ):
                raise ValueError("invalid observed scene geometry")
            # Unity serializes these metre coordinates through Vector3 float32.
            # Preserve a fixed absolute tolerance, never a size-dependent drift.
            if field in game and any(
                not math.isclose(a, b, rel_tol=0, abs_tol=1e-6)
                for a, b in zip(vector, game[field], strict=True)
            ):
                raise ValueError("geometry differs from frozen contract")
        contacts = trace.get("contacts", [])
        if not isinstance(contacts, list) or len(contacts) > 256:
            raise ValueError("invalid contact observation budget")
        for contact in contacts:
            if (
                contact["kind"] not in {"Checkpoint", "Hazard", "Goal"}
                or type(contact["frame"]) is not int
                or not frames[0] <= contact["frame"] <= frames[-1]
                or not isinstance(contact["position"], list)
                or len(contact["position"]) != 3
                or any(
                    type(n) not in {int, float} or not math.isfinite(n) for n in contact["position"]
                )
            ):
                raise ValueError("invalid observed contact")
    except (KeyError, TypeError, ValueError) as exc:
        raise InputError(
            "Invalid platformer telemetry: " + str(exc),
            kind=ErrorKind.CONTRACT_FAILURE,
            code="PF-PLATFORMER-TELEMETRY",
        ) from exc


def _contact(
    sample: dict[str, Any],
    center: list[float],
    size: list[float],
    *,
    horizontal_skin: float = 0.01,
) -> bool:
    # Frozen player BoxCollider2D is .8 x 1.6, origin at the feet.
    p = sample["position"]
    return bool(
        abs(p[0] - center[0]) <= size[0] / 2 + 0.4 + horizontal_skin
        and (
            p[1] <= center[1] + size[1] / 2 + 0.03 and p[1] + 1.6 >= center[1] - size[1] / 2 - 0.03
        )
    )


def evaluate(trace: dict[str, Any]) -> dict[str, Any]:
    """Event labels never establish movement, contact, respawn, jumping, or victory."""
    issues: list[str] = []
    try:
        canonical_digest(trace)
        samples = trace["samples"]
        first, last = samples[0], samples[-1]
        case = trace["scenario_id"]
        if len(samples) < 2 or trace["frames_executed"] < 1:
            raise ValueError("no physical execution")
        if any(abs(s["position"][2]) > 0.001 or abs(s["velocity"][2]) > 0.001 for s in samples):
            issues.append("Physics left the 2D plane")
        for a, b in zip(samples, samples[1:], strict=False):
            if (
                a["state"] in {"WON", "FAILED"}
                and b["state"] == a["state"]
                and a["round"] == b["round"]
                and (
                    math.dist(a["position"], b["position"]) > 0.02
                    or math.dist(b["velocity"], [0, 0, 0]) > 0.1
                )
            ):
                issues.append("Terminal state did not freeze the motor")
        if case == "player_moves":
            if last["position"][0] - first["position"][0] < 0.5:
                issues.append("Horizontal input produced no physical movement")
        elif case == "ground_collision":
            if (
                first["position"][1] - last["position"][1] < 0.5
                or abs(last["position"][1] - trace["platform_top"]) > 0.08
                or not last["grounded"]
                or abs(last["velocity"][1]) > 0.1
            ):
                issues.append("Falling actor did not land on the declared platform")
        elif case in {"grounded_jump", "airborne_jump"}:
            peak = max(s["position"][1] for s in samples)
            if (
                not first["grounded"]
                or peak - first["position"][1] < 0.7
                or not any(s["velocity"][1] > 1 and not s["grounded"] for s in samples)
                or not last["grounded"]
                or abs(last["position"][1] - first["position"][1]) > 0.1
            ):
                issues.append("Grounded jump did not physically rise and land")
            if case == "airborne_jump":
                for a, b in zip(samples, samples[1:], strict=False):
                    if (
                        not a["grounded"]
                        and not b["grounded"]
                        and b["velocity"][1] > a["velocity"][1] + 0.2
                    ):
                        issues.append("Airborne input increased upward velocity")
        elif case in {"hazard_damage", "checkpoint_respawn"}:
            target = (
                trace["checkpoint_position"] if case == "checkpoint_respawn" else trace["spawn"]
            )
            center = [*trace["checkpoint_position"]]
            center[1] += 1
            checkpoint = "checkpoint" if case == "checkpoint_respawn" else "spawn"
            respawned = False
            for a, b in zip(samples, samples[1:], strict=False):
                if not (
                    0 < b["health"] < a["health"]
                    and a["round"] == b["round"]
                    and a["state"] == b["state"] == "RUNNING"
                    and math.dist(b["position"], target) < 0.2
                    and b["checkpoint"] == checkpoint
                ):
                    continue
                # A reset is observed at the health transition, before held input
                # moves the actor again. Unrelated earlier contacts cannot prove it.
                witnesses = [
                    a,
                    *[
                        {"position": c["position"]}
                        for c in trace.get("contacts", [])
                        if c["kind"] == "Hazard" and a["frame"] <= c["frame"] <= b["frame"]
                    ],
                ]
                # Pinned Physics2DSettings.defaultContactOffset is .01 per collider;
                # Unity generates contacts within their sum (.02), before overlap.
                # Physics2DSettings.asset:21; Unity Physics2D.defaultContactOffset:
                # https://docs.unity.com/en-us/engine/6000.5/script-reference/unityengine/physics2d/defaultcontactoffset
                # This skin only applies to hazard proof, never the victory oracle.
                hazard = any(
                    _contact(s, trace["hazard_center"], trace["hazard_size"], horizontal_skin=0.02)
                    for s in witnesses
                )
                activated = case != "checkpoint_respawn" or any(
                    s["frame"] <= a["frame"]
                    and s["round"] == a["round"]
                    and s["health"] == a["health"]
                    and s["checkpoint"] == "checkpoint"
                    and _contact(s, center, [0.5, 2, 1])
                    for s in samples
                )
                respawned |= hazard and activated
            if not respawned:
                issues.append("Hazard did not cause observed health loss and physical respawn")
        elif case == "health_failure":
            if last["health"] != 0 or last["state"] != "FAILED":
                issues.append("Life exhaustion did not fail")
        elif case in {"goal_contact", "journey"}:
            won = [s for s in samples if s["state"] == "WON"]
            if (
                not won
                or not _contact(won[0], trace["goal_center"], trace["goal_size"])
                or any(s["health"] <= 0 for s in won)
            ):
                issues.append("Goal victory requires actual spatial contact and a live actor")
            if case == "journey" and (
                first["position"] != trace["spawn"]
                or not any(s["checkpoint"] == "checkpoint" for s in samples)
                or max(s["position"][1] for s in samples) < 0.7
            ):
                issues.append("Default layout was not traversed through jump and checkpoint")
        elif case in {"restart_resets", "restart_failure"}:
            if (
                not any(
                    s["state"] == ("WON" if case == "restart_resets" else "FAILED")
                    for s in samples[:-1]
                )
                or last["state"] != "RUNNING"
                or last["health"] != 3
                or last["checkpoint"] != "spawn"
                or last["elapsed_seconds"] > 0.1
                or last["round"] <= first["round"]
                or math.dist(last["position"], trace["spawn"]) > 0.1
                or math.dist(last["velocity"], [0, 0, 0]) > 0.1
            ):
                issues.append("Restart did not restore full initial state after a terminal state")
        else:
            issues.append("Unknown public platformer oracle")
    except (KeyError, TypeError, ValueError, InputError) as exc:
        issues.append("Invalid physical observations: " + str(exc))
    return {
        "status": "FAIL" if issues else "PASS",
        "issues": issues,
        "oracle_owner": "PUBLIC_DEVELOPMENT",
        "hidden_evaluation": "NOT_RUN",
    }
