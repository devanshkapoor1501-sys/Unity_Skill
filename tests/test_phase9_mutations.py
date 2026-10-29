"""Mutation credit requires an executed, valid trace that fails the right oracle."""

import copy

import pytest

from polyforge.contracts.validation import InputError
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy

MUTANTS = {
    "collision_disabled": "wall_collision",
    "restart_disabled": "restart_resets",
    "win_reversed": "survival_win",
    "damage_no_health": "contact_damage",
    "navigation_stuck": "enemy_patrols",
    "input_disconnected": "player_moves",
}
GAME = {"input_digest": "a" * 64, "scene_id": "main", "seed": 42, "enemies": [{"id": "enemy"}]}


def trace(scenario, mutant=None):
    first = {
        "frame": 0,
        "round": 1,
        "state": "RUNNING",
        "health": 100,
        "elapsed_seconds": 0,
        "player_position": [0, 0, 0],
        "enemy_positions": [{"id": "enemy", "position": [3, 0, 3]}],
    }
    last = {
        **copy.deepcopy(first),
        "frame": 1500,
        "player_position": [0, 0, 2],
        "elapsed_seconds": 30,
    }
    value = {
        "schema_version": "1.0.0",
        "scenario_id": scenario,
        "purpose": "MUTANT" if mutant else "NOMINAL",
        "mutant": mutant,
        "seed": 42,
        "input_digest": "a" * 64,
        "scene_id": "main",
        "frames_executed": 1500,
        "fixed_delta_seconds": 0.02,
        "samples": [first, last],
        "events": [],
        "arena_half_extents": [10, 10],
        "wall_thickness": 0.5,
        "player_radius": 0.35,
        "baseline_player_position": [-3, 0, -3],
        "baseline_enemy_positions": [{"id": "enemy", "position": [3, 0, 3]}],
    }
    if scenario == "wall_collision":
        first["player_position"] = [-7, 0, 0]
        last["player_position"] = [-9.1, 0, 0]
    elif scenario == "enemy_patrols":
        last["enemy_positions"][0]["position"] = [5, 0, 3]
    elif scenario == "contact_damage":
        last["health"] = 75
        value["events"] = [{"name": "damage"}]
    elif scenario == "health_failure":
        last.update(health=0, state="FAILED")
    elif scenario == "survival_win":
        last.update(state="WON", elapsed_seconds=30)
    elif scenario == "restart_resets":
        first.update(health=0, state="FAILED")
        last.update(round=2, elapsed_seconds=0, player_position=[-3, 0, -3])
    if mutant == "collision_disabled":
        last["player_position"] = [-20, 0, 0]
    elif mutant == "restart_disabled":
        last.update(round=1, elapsed_seconds=2, health=0, state="FAILED")
    elif mutant == "win_reversed":
        last.update(state="WON", elapsed_seconds=0.02)
    elif mutant == "damage_no_health":
        last["health"] = 100  # Keep damage event: event-only assertions would falsely pass.
    elif mutant == "navigation_stuck":
        last["enemy_positions"] = copy.deepcopy(first["enemy_positions"])
    elif mutant == "input_disconnected":
        last["player_position"] = first["player_position"][:]
    return value


def test_all_six_mutations_have_explicit_independent_scenarios():
    from polyforge.scenarios.arena_oracle import MUTANT_SCENARIOS, evaluate, validate_trace

    assert MUTANT_SCENARIOS == MUTANTS
    for name, scenario in MUTANTS.items():
        value = trace(scenario, name)
        validate_trace(value, GAME, name, 1500)
        assert evaluate(value)["status"] == "FAIL"


def populated(tmp_path, monkeypatch):
    from polyforge.scenarios.arena_oracle import CORE_SCENARIOS
    from polyforge.unity import game

    p = WorkspacePolicy(tmp_path)
    monkeypatch.setattr(
        game,
        "core_suite",
        lambda g: {
            "scenarios": [
                {"id": name, "steps": [{"ticks": 1500}], "expected": []} for name in CORE_SCENARIOS
            ]
        },
    )
    for name in CORE_SCENARIOS:
        atomic_json(p, "runs/probe/telemetry/" + name + ".json", trace(name))
    for name, scenario in {
        "keyboard_input": "player_moves",
        "keyboard_restart": "restart_resets",
    }.items():
        value = trace(scenario)
        value["purpose"] = "INPUT_ADAPTER"
        if name == "keyboard_restart":
            value["frames_executed"] += 1
            value["samples"][-1]["frame"] += 1
        atomic_json(p, "runs/probe/telemetry/" + name + ".json", value)
    for name, scenario in MUTANTS.items():
        atomic_json(p, "runs/probe/telemetry/" + name + ".json", trace(scenario, name))
    return p


def test_score_counts_all_six_actual_failures_and_rejects_a_surviving_mutant(tmp_path, monkeypatch):
    from polyforge.unity.game import score_telemetry

    p = populated(tmp_path, monkeypatch)
    scored = score_telemetry(p, "runs/probe", GAME)
    assert scored["status"] == "PASS"
    assert {n for n, r in scored["scenarios"].items() if r["mutant"]} == set(MUTANTS)
    surviving = trace("contact_damage")
    surviving.update(purpose="MUTANT", mutant="damage_no_health")
    atomic_json(p, "runs/probe/telemetry/damage_no_health.json", surviving)
    assert score_telemetry(p, "runs/probe", GAME)["status"] == "FAIL"


@pytest.mark.parametrize("fault", ["missing", "not_run", "wrong_identity"])
def test_unexecuted_or_invalid_mutant_never_counts_as_killed(tmp_path, monkeypatch, fault):
    from polyforge.unity.game import score_telemetry

    p = populated(tmp_path, monkeypatch)
    path = p.path("runs/probe/telemetry/win_reversed.json")
    if fault == "missing":
        path.unlink()
    else:
        value = trace("survival_win", "win_reversed")
        if fault == "not_run":
            value["frames_executed"] = 0
        else:
            value["input_digest"] = "b" * 64
        atomic_json(p, path, value)
    with pytest.raises(InputError):
        score_telemetry(p, "runs/probe", GAME)
