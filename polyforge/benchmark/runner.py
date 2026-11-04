"""Offline orchestration for injected, trusted benchmark adapters."""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.benchmark.protocol import AcceptanceEvaluator, BaselineRunner, EvaluationRequest
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy

from .metrics import summarize, validate_record
from .tasks import ARMS, comparison_status, metadata_ready, read_brief, verify_frozen


def _output_path(output: Path) -> Path:
    candidate = output.absolute()
    ancestor = candidate.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    return WorkspacePolicy(ancestor).path(candidate)


def _observed_result(value: Any) -> Result:
    if not isinstance(value, Result):
        raise InputError("Benchmark adapters must return the stable Result contract")
    canonical_digest(value.to_dict())
    return value


def _execute(
    row: dict[str, Any],
    request: EvaluationRequest,
    task: dict[str, Any],
    runner: BaselineRunner,
    evaluator: AcceptanceEvaluator | None,
) -> dict[str, Any]:
    start = time.monotonic()
    try:
        produced = _observed_result(runner.run(request, arm=row["arm"], seed=row["seed"]))
        row.update(status=produced.status, execution_result=produced.to_dict())
        reported_timeout = produced.data.get("timed_out", False)
        if type(reported_timeout) is not bool:
            raise InputError("Adapter timeout observation must be boolean")
        if reported_timeout:
            row.update(
                status="FAIL", timed_out=True, censored=True, error_code="PF-BENCHMARK-TIMEOUT"
            )
        for field in ("tokens", "tool_calls", "interventions", "cost_usd", "retries"):
            row[field] = produced.data.get(field)
        row["resources"] = produced.data.get("resources", {})
        row["duration_seconds"] = time.monotonic() - start
        validate_record(row)
        budgets = task["budgets"]
        exceeded = [
            key
            for key in ("tokens", "tool_calls", "retries")
            if row.get(key) is not None and row[key] > budgets[key]
        ]
        if row["duration_seconds"] > budgets["wall_seconds"]:
            exceeded.append("wall_seconds")
            row.update(timed_out=True, censored=True)
        if exceeded:
            row.update(
                status="FAIL",
                error_code="PF-BENCHMARK-BUDGET",
                diagnostics=[{"message": "Observed budget exceeded", "budgets": exceeded}],
            )
        if row["status"] != "PASS":
            return row
        if row["tokens"] is None or row["tool_calls"] is None:
            row.update(status="BLOCKED", error_code="PF-BENCHMARK-USAGE-UNKNOWN")
            return row
        if evaluator is None:
            row.update(evaluation_status="BLOCKED", error_code="PF-EVALUATOR-UNAVAILABLE")
            return row
        grade = _observed_result(evaluator.grade(request))
        row["evaluation_result"] = grade.to_dict()
        identity = grade.data.get("evaluator_id")
        graded = (
            grade.status == "PASS"
            and grade.evaluated_test_status == "PASS"
            and isinstance(identity, str)
            and 0 < len(identity) <= 256
        )
        row["evaluation_status"] = (
            "PASS" if graded else (grade.status if grade.status != "PASS" else "BLOCKED")
        )
        row["evaluator_id"] = identity if isinstance(identity, str) else None
        row["task_success"] = graded and grade.data.get("task_success") is True
        if task["task_type"].startswith("COMPLETE_GAME"):
            row["task_success"] = row["task_success"] and grade.game_status == "ACCEPTED"
        row["game_status"] = grade.game_status if graded else "PARTIAL"
        return row
    except TimeoutError as exc:
        row.update(
            status="FAIL",
            timed_out=True,
            censored=True,
            error_code="PF-BENCHMARK-TIMEOUT",
            diagnostics=[{"message": str(exc)[:4096]}],
        )
    except Exception as exc:  # Trusted adapters may fail; keep the failed attempt and continue.
        row.update(
            status="FAIL",
            error_code="PF-BENCHMARK-ADAPTER",
            diagnostics=[{"message": str(exc)[:4096], "type": type(exc).__name__}],
        )
        row.update(task_success=False, game_status="PARTIAL")
        # Malformed reported numbers cannot enter finite JSON or become zero-cost evidence.
        for key in ("tokens", "tool_calls", "interventions", "cost_usd", "retries"):
            row[key] = None
        row.pop("execution_result", None)
        row.pop("evaluation_result", None)
        row["resources"] = {}
    finally:
        row["duration_seconds"] = time.monotonic() - start
        if row["duration_seconds"] > task["budgets"]["wall_seconds"]:
            row.update(
                status="FAIL",
                task_success=False,
                game_status="PARTIAL",
                timed_out=True,
                censored=True,
                error_code="PF-BENCHMARK-BUDGET",
                diagnostics=[
                    {
                        "message": "End-to-end execution and evaluation wall budget exceeded",
                        "budgets": ["wall_seconds"],
                        "observed_seconds": row["duration_seconds"],
                        "limit_seconds": task["budgets"]["wall_seconds"],
                    },
                    *row.get("diagnostics", []),
                ],
            )
    return row


def run_suite(
    suite: dict[str, Any],
    arm: str,
    output: Path,
    *,
    runner: BaselineRunner | None = None,
    evaluator: AcceptanceEvaluator | None = None,
    seeds: tuple[int, ...] | None = None,
    dry_run: bool = False,
) -> Result:
    """Retain actual attempts; missing adapters never synthesize model trials.

    Trusted adapters own their process deadlines. This synchronous compatibility
    interface applies the wall budget to observed execution plus evaluation time
    and verifies reported usage; it cannot safely kill arbitrary injected Python
    or authenticate provider/evaluator identities.
    """
    try:
        frozen = verify_frozen(suite)
        if arm not in ARMS or arm not in frozen.get("arms", ARMS):
            raise InputError("Unknown or undeclared benchmark arm")
        repetitions = frozen.get("runs_per_task_arm", 5)
        if seeds is None:
            seeds = tuple(range(42, 42 + repetitions))
        if (
            not isinstance(seeds, tuple)
            or not 1 <= len(seeds) <= 100
            or any(type(seed) is not int or not 0 <= seed <= 2147483647 for seed in seeds)
            or len(set(seeds)) != len(seeds)
        ):
            raise InputError("Seeds must be 1..100 unique integers in 0..2147483647")
        if len(seeds) != repetitions:
            raise InputError("Seed schedule must match declared runs_per_task_arm")
        if type(dry_run) is not bool:
            raise InputError("dry_run must be boolean")
        target = _output_path(output)
        if target.exists():
            raise InputError("Benchmark output already exists; preserve previous evidence")
        metadata = frozen.get("execution_metadata", {}).get(arm, {})
        configuration = canonical_digest(
            {
                "arm": arm,
                "metadata": metadata,
                "suite_digest": frozen["suite_digest"],
                "tasks": frozen["tasks"],
            }
        )
        parity = comparison_status(frozen)
        if dry_run:
            return Result(
                data={
                    "dry_run": True,
                    "planned_cases": len(frozen["tasks"]) * len(seeds),
                    "comparison_status": parity,
                    "configuration_digest": configuration,
                    "qualification_status": "BLOCKED",
                }
            )
        target.mkdir(parents=True, exist_ok=False)
        policy = WorkspacePolicy(target)
        run_id = "benchmark_" + uuid4().hex
        ledger = policy.path("ledger.jsonl")
        records: list[dict[str, Any]] = []
        manifest: dict[str, Any] = {
            "schema_version": "1.0.0",
            "run_id": run_id,
            "arm": arm,
            "created_at": datetime.now(UTC).isoformat(),
            "suite": frozen,
            "configuration_digest": configuration,
            "comparison_status": parity,
            "qualification_status": "BLOCKED",
            "adapter_boundary": "TRUSTED_INJECTED_PROTOCOL",
            "identity_assurance": "DECLARED_NOT_AUTHENTICATED",
            "seeds": list(seeds),
            "planned_cases": len(frozen["tasks"]) * len(seeds),
            "completed_cases": 0,
        }
        with ledger.open("xb"):
            pass

        def checkpoint() -> None:
            raw = ledger.read_bytes()
            manifest["ledger_sha256"] = hashlib.sha256(raw).hexdigest()
            manifest["ledger_bytes"] = len(raw)
            manifest["manifest_digest"] = canonical_digest(
                {key: value for key, value in manifest.items() if key != "manifest_digest"}
            )
            atomic_json(policy, "run.json", manifest)

        checkpoint()

        def append(row: dict[str, Any]) -> None:
            validate_record(row)
            entry = {**row, "row_digest": canonical_digest(row)}
            payload = (json.dumps(entry, ensure_ascii=True, allow_nan=False) + "\n").encode()
            with policy.path("ledger.jsonl").open("ab") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            checkpoint()

        for task in frozen["tasks"]:
            for seed in seeds:
                attempt_id = f"{arm}_{task['task_id']}_{seed}"
                row: dict[str, Any] = {
                    "schema_version": "1.0.0",
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "arm": arm,
                    "task_id": task["task_id"],
                    "task_type": task["task_type"],
                    "original_brief_sha256": task["original_brief_sha256"],
                    "rubric_sha256": task["rubric_sha256"],
                    "task_success_schema": task["task_success_schema"],
                    "suite_digest": frozen["suite_digest"],
                    "configuration_digest": configuration,
                    "execution_metadata": metadata,
                    "budgets": task["budgets"],
                    "seed": seed,
                    "comparison_status": parity,
                    "executed": False,
                    "eligible": False,
                    "status": "BLOCKED",
                    "evaluation_status": "NOT_RUN",
                    "task_success": False,
                    "game_status": "PARTIAL",
                    "duration_seconds": None,
                    "tokens": None,
                    "tool_calls": None,
                    "cost_usd": None,
                    "interventions": None,
                    "retries": None,
                    "timed_out": False,
                    "censored": False,
                    "event": "FINISHED",
                    "resources": {},
                    "evaluator_id": None,
                    **{
                        field: task.get(field, "UNDECLARED")
                        for field in ("genre", "platform", "complexity")
                    },
                }
                missing = []
                if runner is None:
                    missing.append("baseline model/host runner")
                if not metadata_ready(metadata, arm):
                    missing.append("frozen execution metadata")
                if task["budgets"]["tokens"] is None:
                    missing.append("finite token budget")
                if (
                    task["rubric_sha256"] is None
                    or "PUBLIC_DEVELOPMENT_ONLY" in task["task_success_schema"]
                ):
                    missing.append("frozen public acceptance rubric")
                if missing:
                    row["diagnostics"] = [{"message": "Missing " + ", ".join(missing)}]
                    row["error_code"] = "PF-BENCHMARK-UNAVAILABLE"
                else:
                    verify_frozen(frozen)
                    row.update(
                        executed=True,
                        eligible=True,
                        status="NOT_RUN",
                        event="STARTED",
                        censored=True,
                    )
                    append(
                        row
                    )  # A crash leaves an attempted, unaccepted case, never a vanished trial.
                    artifact_root = policy.mkdir("artifacts/" + attempt_id)
                    brief = read_brief(Path(frozen["suite_path"]), task)
                    atomic_json(
                        policy,
                        artifact_root / "public-input.json",
                        {
                            "task": task,
                            "original_brief": brief,
                            "arm": arm,
                            "seed": seed,
                            "execution_metadata": metadata,
                            "identity_assurance": "DECLARED_ONLY",
                        },
                    )
                    request = EvaluationRequest(
                        task["task_id"],
                        task["original_brief_sha256"],
                        artifact_root,
                        task["task_type"],
                    )
                    row.update(status="PASS", event="FINISHED", censored=False)
                    assert runner is not None
                    row = _execute(row, request, task, runner, evaluator)
                manifest["completed_cases"] += 1
                append(row)
                records.append(row)
        summary = summarize(records)
        data = {
            "records": records,
            "summary": summary,
            "comparison_status": parity,
            "qualification_status": "BLOCKED",
            "ledger_path": str(ledger),
            "run_id": run_id,
            "identity_assurance": "DECLARED_NOT_AUTHENTICATED",
        }
        if any(row["status"] == "FAIL" or row["evaluation_status"] == "FAIL" for row in records):
            return Result(
                status="FAIL",
                exit_code=int(ErrorKind.TEST_FAILURE),
                error_code="PF-BENCHMARK-TRIAL-FAILED",
                data=data,
            )
        if any(row["status"] != "PASS" or row["evaluation_status"] != "PASS" for row in records):
            return Result(
                status="BLOCKED",
                exit_code=int(ErrorKind.MISSING_DEPENDENCY),
                error_code="PF-BENCHMARK-INCOMPLETE",
                data=data,
            )
        return Result(data=data)
    except InputError as exc:
        return failure(exc.kind, exc.code, str(exc))
    except OSError as exc:
        return failure(ErrorKind.PRODUCER_FAILURE, "PF-BENCHMARK-IO", str(exc))
