"""Task-stratified descriptive metrics without unsupported comparative claims."""

from __future__ import annotations

import math
from statistics import median, pvariance
from typing import Any

from polyforge.contracts.results import GAME_STATUSES, STATUSES
from polyforge.contracts.validation import InputError, canonical_digest

from .tasks import ARMS, TASK_TYPES

RESOURCE_FIELDS = ("cpu_seconds", "gpu_peak_mb", "ram_peak_mb", "load_seconds")


def validate_record(row: Any) -> None:
    """Reject malformed observations instead of silently dropping failures."""
    if not isinstance(row, dict):
        raise InputError("A benchmark observation must be an object")
    canonical_digest(row)
    if row.get("arm") not in ARMS or row.get("task_type") not in TASK_TYPES:
        raise InputError("Unknown benchmark arm or task type")
    if not isinstance(row.get("task_id"), str) or not 1 <= len(row["task_id"]) <= 4096:
        raise InputError("Missing bounded task identity")
    for key in ("executed", "eligible", "task_success", "timed_out", "censored"):
        if type(row.get(key)) is not bool:
            raise InputError(f"Observation {key} must be boolean")
    for field in ("status", "evaluation_status"):
        if not isinstance(row.get(field), str) or row[field] not in STATUSES:
            raise InputError("Unknown observation status")
    if not isinstance(row.get("game_status"), str) or row["game_status"] not in GAME_STATUSES:
        raise InputError("Unknown observed game acceptance status")
    if row.get("seed") is not None and (
        type(row["seed"]) is not int or not 0 <= row["seed"] <= 2147483647
    ):
        raise InputError("Observation seed must be a bounded integer or undeclared")
    for key in ("duration_seconds", "cost_usd", "tokens", "tool_calls", "interventions", "retries"):
        value = row.get(key)
        if value is None:
            continue
        numeric = type(value) in {int, float} and 0 <= value <= 1e12 and math.isfinite(value)
        if not numeric:
            raise InputError(f"Observation {key} must be finite and nonnegative or unknown")
        if key in {"tokens", "tool_calls", "interventions", "retries"} and type(value) is not int:
            raise InputError(f"Observation {key} must be an integer or unknown")
    if row["task_success"] and (
        not row["executed"]
        or not row["eligible"]
        or row["status"] != "PASS"
        or row["evaluation_status"] != "PASS"
        or row["censored"]
    ):
        raise InputError("Success requires an eligible executed and evaluated passing attempt")
    if row["timed_out"] and not row["censored"]:
        raise InputError("Timeout observations must retain their censoring flag")
    resources = row.get("resources", {})
    if not isinstance(resources, dict) or set(resources) - set(RESOURCE_FIELDS):
        raise InputError("Resource observations require declared resource fields")
    for value in resources.values():
        if value is not None and (
            type(value) not in {int, float} or not 0 <= value <= 1e12 or not math.isfinite(value)
        ):
            raise InputError("Resource observations must be finite and nonnegative or unknown")


def _accepted(row: dict[str, Any], *, game: bool) -> bool:
    return bool(row["task_success"] and (not game or row["game_status"] == "ACCEPTED"))


def _interval(successes: int, count: int) -> list[float] | None:
    if not count:
        return None
    z = 1.959963984540054
    rate = successes / count
    denominator = 1 + z * z / count
    center = (rate + z * z / (2 * count)) / denominator
    margin = z * math.sqrt(rate * (1 - rate) / count + z * z / (4 * count * count)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def _distribution(rows: list[dict[str, Any]], *, game: bool = False) -> dict[str, Any]:
    attempted = [row for row in rows if row["executed"] and row["eligible"]]
    accepted = [row for row in attempted if _accepted(row, game=game)]
    times = [
        row["duration_seconds"] for row in attempted if row.get("duration_seconds") is not None
    ]
    accepted_times = [
        row["duration_seconds"] for row in accepted if row.get("duration_seconds") is not None
    ]
    known_costs = [row["cost_usd"] for row in attempted if row.get("cost_usd") is not None]
    accepted_costs = [row["cost_usd"] for row in accepted if row.get("cost_usd") is not None]
    resources = {}
    for field in RESOURCE_FIELDS:
        values = [
            row["resources"][field]
            for row in attempted
            if row.get("resources", {}).get(field) is not None
        ]
        resources[field] = {
            "observed_count": len(values),
            "unknown_count": len(attempted) - len(values),
            "median": median(values) if values else None,
            "variance": pvariance(values) if values else None,
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
        }
    count, success = len(attempted), len(accepted)
    return {
        "status": "MEASURED" if count else "NOT_MEASURABLE",
        "numerator": success,
        "denominator": count,
        "rate": success / count if count else None,
        "confidence_interval_95": _interval(success, count),
        "median_attempt_seconds": median(times) if times else None,
        "median_accepted_seconds": median(accepted_times) if accepted_times else None,
        "unknown_duration_count": count - len(times),
        "known_cost_total_usd": sum(known_costs) if known_costs else None,
        "unknown_cost_count": count - len(known_costs),
        "median_attempt_cost_usd": median(known_costs) if known_costs else None,
        "median_accepted_cost_usd": median(accepted_costs) if accepted_costs else None,
        "unknown_accepted_cost_count": len(accepted) - len(accepted_costs),
        "resources": resources,
        "known_tokens_total": sum(row.get("tokens") or 0 for row in attempted),
        "unknown_tokens_count": sum(row.get("tokens") is None for row in attempted),
        "known_interventions_total": sum(row.get("interventions") or 0 for row in attempted),
        "unknown_interventions_count": sum(row.get("interventions") is None for row in attempted),
        "timed_out_count": sum(row["timed_out"] for row in attempted),
        "censored_count": sum(row["censored"] for row in attempted),
        "planned_not_executed_count": sum(not row["executed"] for row in rows),
        "ineligible_executed_count": sum(row["executed"] and not row["eligible"] for row in rows),
        "status_counts": {
            status: sum(row["status"] == status for row in rows) for status in sorted(STATUSES)
        },
        "task_count": len({row["task_id"] for row in attempted}),
        "seed_count": len({row.get("seed") for row in attempted}),
    }


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    games = [row for row in rows if row["task_type"] in {"COMPLETE_GAME_2D", "COMPLETE_GAME_3D"}]
    strata: dict[str, list[dict[str, Any]]] = {}
    for row in games:
        key = canonical_digest(
            [row.get(field, "UNDECLARED") for field in ("genre", "platform", "complexity")]
        )
        strata.setdefault(key, []).append(row)
    return {
        "accepted_game_rate": _distribution(games, game=True),
        "by_task_type": {
            task_type: _distribution(
                [row for row in rows if row["task_type"] == task_type],
                game=task_type.startswith("COMPLETE_GAME"),
            )
            for task_type in TASK_TYPES
        },
        "complete_game_strata": [
            {
                **{
                    field: members[0].get(field, "UNDECLARED")
                    for field in ("genre", "platform", "complexity")
                },
                **_distribution(members, game=True),
            }
            for members in strata.values()
        ],
    }


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Keep all attempts and configurations separate, using Wilson uncertainty."""
    if not isinstance(records, list) or len(records) > 51200:
        raise InputError("Benchmark report exceeds its bounded observation count")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in records:
        validate_record(row)
        configuration = row.get("configuration_digest", "UNDECLARED")
        if not isinstance(configuration, str) or len(configuration) > 128:
            raise InputError("Invalid configuration identity")
        groups.setdefault((row["arm"], configuration), []).append(row)
    configurations = [
        {"arm": arm, "configuration_digest": digest, **_metrics(rows)}
        for (arm, digest), rows in groups.items()
    ]
    combined = _metrics(records if len(groups) <= 1 else [])
    if len(groups) > 1:
        # Never silently pool arms or changes to model/tools/budgets/worker configuration.
        measured = _metrics(records)
        if measured["accepted_game_rate"]["denominator"]:
            combined["accepted_game_rate"]["status"] = "NON_ATTRIBUTABLE"
        for task_type, category in combined["by_task_type"].items():
            if measured["by_task_type"][task_type]["denominator"]:
                category["status"] = "NON_ATTRIBUTABLE"
    return {
        **combined,
        "by_configuration": configurations,
        "record_count": len(records),
        "superiority_claim": "UNSUPPORTED",
        "uncertainty": "EXPLORATORY; Wilson 95% binomial intervals; no causal superiority test",
        "denominator_policy": (
            "Executed eligible attempts, including failures, blocked and timeouts"
        ),
        "time_policy": (
            "End-to-end execution and evaluation times include failures and censored lower bounds; "
            "accepted-only separate"
        ),
        "qualification_status": "BLOCKED",
        "acceptance_assurance": "DECLARED_NOT_AUTHENTICATED",
    }
