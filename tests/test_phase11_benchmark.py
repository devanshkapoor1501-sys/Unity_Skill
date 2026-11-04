"""Public benchmark identities, honest denominators and offline reports."""

from __future__ import annotations

import copy
import importlib
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

from polyforge.benchmark.protocol import EvaluationRequest
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "benchmarks/development-v1"


def configured_suite(tmp_path: Path) -> Path:
    """External runner/evaluator inputs contain public identities, never hidden answers."""
    root = tmp_path / "suite"
    shutil.copytree(PUBLIC, root)
    path = root / "suite.json"
    value = json.loads(path.read_text("utf-8"))
    value["runs_per_task_arm"] = 1  # Focused adapter tests explicitly request one repetition.
    for task in value["tasks"]:
        task["rubric_sha256"] = "0" * 64
        task["task_success_schema"] = "public-independent-v1"
        task["budgets"]["tokens"] = 4000
    metadata = {
        "model": "test-model-v1",
        "thinking_effort": "high",
        "hardware": {"cpu": "cpu", "gpu": "gpu", "ram_gb": 32},
        "os": "test-os-v1",
        "tool_versions": {"blender": "5.2.2", "unity": "6000.6.3f1"},
        "generic_tools": {"blender-mcp": "1", "unity-mcp": "2"},
        "permissions": ["workspace-read", "workspace-write"],
        "default_tool_inventory": ["blender-mcp", "unity-mcp"],
        "external_assets": [],
        "licensing": {"blender": "GPL", "unity": "personal"},
        "manual_intervention_policy": "record-all",
        "git_commit": "a" * 40,
        "prompt_sha256": "b" * 64,
        "worker_mode": "sequential-logical",
    }
    value["execution_metadata"] = {arm: copy.deepcopy(metadata) for arm in "ABCD"}
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class PublicRunner:
    def run(self, task: EvaluationRequest, *, arm: str, seed: int) -> Result:
        assert arm in "ABCD" and seed >= 0
        assert task.original_brief_sha256 and task.artifact_root.is_dir()
        return Result(data={"tokens": 20, "tool_calls": 1, "interventions": 0})


class PublicEvaluator:
    def grade(self, request: EvaluationRequest) -> Result:
        assert request.artifact_root.is_dir()
        return Result(
            data={"evaluator_id": "external-public-test-v1", "task_success": True},
            evaluated_test_status="PASS",
            game_status="ACCEPTED",
        )


def test_required_public_interfaces_are_present() -> None:
    for module, name in (
        ("tasks", "load_suite"),
        ("runner", "run_suite"),
        ("metrics", "summarize"),
        ("analysis", "report_run"),
    ):
        qualified = f"polyforge.benchmark.{module}"
        assert importlib.util.find_spec(qualified) is not None, f"Missing {qualified}"
        assert callable(getattr(importlib.import_module(qualified), name, None))


def test_default_run_schedules_every_declared_repetition(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    suite = load_suite(PUBLIC / "suite.json")
    preview = run_suite(suite, "A", tmp_path / "preview", dry_run=True)
    assert preview.data["planned_cases"] == 12 * suite["runs_per_task_arm"] == 60
    result = run_suite(suite, "A", tmp_path / "run")
    assert len(result.data["records"]) == 60
    assert {row["seed"] for row in result.data["records"]} == set(range(42, 47))
    assert not any(row["executed"] for row in result.data["records"])


def test_explicit_seed_schedule_cannot_silently_omit_declared_repetitions(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    output = tmp_path / "incomplete"
    result = run_suite(load_suite(PUBLIC / "suite.json"), "A", output, seeds=(42,))
    assert result.status == "FAIL"
    assert not output.exists()


def test_load_suite_verifies_twelve_briefs_without_mutation(tmp_path: Path) -> None:
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    before = {p.name: p.read_bytes() for p in path.parent.rglob("*") if p.is_file()}
    suite = load_suite(path)
    assert len(suite["tasks"]) == 12
    assert len(suite["suite_digest"]) == 64
    assert suite["tasks"][0]["original_brief_sha256"] == (
        "c55d75921d17b51d44e69200aa7769ef34262189694aff67d6a458dad9c61658"
    )
    assert before == {p.name: p.read_bytes() for p in path.parent.rglob("*") if p.is_file()}
    (path.parent / "briefs/robot_mesh.md").write_text("Changed after freezing", encoding="utf-8")
    with pytest.raises(InputError):
        load_suite(path)


@pytest.mark.parametrize("change", ["duplicate", "traversal", "infinite", "huge", "bool", "plugin"])
def test_suite_rejects_unsafe_or_unbounded_inputs(tmp_path: Path, change: str) -> None:
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    value = json.loads(path.read_text("utf-8"))
    task = value["tasks"][0]
    if change == "duplicate":
        value["tasks"][1]["task_id"] = task["task_id"]
    elif change == "traversal":
        task["task_id"] = "../robot_mesh"
    elif change == "infinite":
        task["budgets"]["wall_seconds"] = float("inf")
    elif change == "huge":
        task["budgets"]["tool_calls"] = 10**30
    elif change == "bool":
        task["budgets"]["tokens"] = True
    else:
        value["runner_plugin"] = "arbitrary.module:execute"
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(InputError):
        load_suite(path)


def test_missing_adapters_are_blocked_and_dry_run_writes_nothing(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    source = configured_suite(tmp_path)
    value = json.loads(source.read_text("utf-8"))
    value["runs_per_task_arm"] = 2
    source.write_text(json.dumps(value), encoding="utf-8")
    suite = load_suite(source)
    dry = tmp_path / "dry"
    preview = run_suite(suite, "C", dry, dry_run=True)
    assert preview.status == "PASS"
    assert not dry.exists()
    output = tmp_path / "run"
    result = run_suite(suite, "C", output, seeds=(42, 43))
    assert result.status == "BLOCKED"
    records = result.data["records"]
    assert len(records) == 24
    assert {row["status"] for row in records} == {"BLOCKED"}
    assert not any(row["executed"] for row in records)
    assert all(row["evaluation_status"] == "NOT_RUN" for row in records)
    assert all(row["cost_usd"] is None for row in records)
    assert len((output / "ledger.jsonl").read_text("utf-8").splitlines()) == 24


def test_frozen_identity_is_rechecked_before_writes(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    suite = load_suite(path)
    suite["tasks"][0]["budgets"]["tool_calls"] += 1
    output = tmp_path / "output"
    result = run_suite(suite, "D", output, runner=PublicRunner(), evaluator=PublicEvaluator())
    assert result.status == "FAIL"
    assert not output.exists()


def test_real_runner_outcomes_are_retained_and_missing_evaluator_cannot_accept(
    tmp_path: Path,
) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    suite = load_suite(configured_suite(tmp_path))
    result = run_suite(suite, "D", tmp_path / "without-evaluator", runner=PublicRunner())
    assert result.status == "BLOCKED"
    assert all(row["executed"] for row in result.data["records"])
    assert all(row["evaluation_status"] == "BLOCKED" for row in result.data["records"])
    assert all(not row["task_success"] for row in result.data["records"])

    class FailingRunner(PublicRunner):
        def run(self, task: EvaluationRequest, *, arm: str, seed: int) -> Result:
            if task.task_id == "sprite_survival_game":
                raise TimeoutError("declared stop")
            return failure(ErrorKind.PRODUCER_FAILURE, "PF-TRIAL-FAILURE", "Actual failure")

    failed = run_suite(
        suite, "D", tmp_path / "failed", runner=FailingRunner(), evaluator=PublicEvaluator()
    )
    assert failed.status == "FAIL"
    records = failed.data["records"]
    assert len(records) == 12
    assert {row["status"] for row in records} == {"FAIL"}
    assert all(row["executed"] for row in records)
    game = next(row for row in records if row["task_type"] == "COMPLETE_GAME_2D")
    assert game["timed_out"] and game["censored"]
    assert game["game_status"] != "ACCEPTED"


def trial(task_type: str, *, success: bool = False, seconds: float = 10, **extra: object) -> dict:
    return {
        "arm": "D",
        "configuration_digest": "c" * 64,
        "task_id": task_type.lower(),
        "task_type": task_type,
        "executed": True,
        "eligible": True,
        "status": "PASS" if success else "FAIL",
        "evaluation_status": "PASS",
        "task_success": success,
        "game_status": "ACCEPTED" if success else "REJECTED",
        "duration_seconds": seconds,
        "cost_usd": None,
        "tokens": None,
        "interventions": 0,
        "timed_out": False,
        "censored": False,
        "seed": 42,
        "genre": "survival",
        "platform": "desktop",
        "complexity": "small",
        **extra,
    }


def test_metrics_keep_exact_complete_game_denominator_and_failure_costs() -> None:
    from polyforge.benchmark.metrics import summarize

    records = [trial("ASSET", success=True) for _ in range(4)] + [
        trial("COMPLETE_GAME_2D", success=True, seconds=2),
        trial("COMPLETE_GAME_3D", seconds=20, timed_out=True, censored=True),
        trial("COMPLETE_GAME_3D", seconds=30, status="BLOCKED"),
        trial("COMPLETE_GAME_3D", seconds=40, status="NOT_RUN", executed=False),
    ]
    summary = summarize(records)
    games = summary["accepted_game_rate"]
    assert (games["numerator"], games["denominator"]) == (1, 3)
    assert games["rate"] == pytest.approx(1 / 3)
    assert games["confidence_interval_95"] == pytest.approx([0.06149, 0.79234], abs=0.0001)
    assert games["median_attempt_seconds"] == 20
    assert games["median_accepted_seconds"] == 2
    assert games["unknown_cost_count"] == 3
    assert games["censored_count"] == 1
    assert len(summary["by_task_type"]) == 6
    assert summary["by_task_type"]["ASSET"]["denominator"] == 4
    assert summary["superiority_claim"] == "UNSUPPORTED"


def test_unexecuted_games_are_not_measurable_and_configs_never_pool() -> None:
    from polyforge.benchmark.metrics import summarize

    absent = summarize([trial("ASSET", success=True), trial("COMPLETE_GAME_2D", executed=False)])
    assert absent["accepted_game_rate"]["status"] == "NOT_MEASURABLE"
    split = summarize(
        [
            trial("COMPLETE_GAME_2D", success=True),
            trial("COMPLETE_GAME_2D", configuration_digest="d" * 64),
        ]
    )
    assert len(split["by_configuration"]) == 2
    assert split["accepted_game_rate"]["status"] == "NON_ATTRIBUTABLE"


@pytest.mark.parametrize(
    "field",
    ["generic_tools", "permissions", "hardware", "model", "thinking_effort", "external_assets"],
)
def test_c_d_mismatch_cannot_be_reported_as_attributable(tmp_path: Path, field: str) -> None:
    from polyforge.benchmark.analysis import report_run
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    value = json.loads(path.read_text("utf-8"))
    changed = value["execution_metadata"]["D"]
    original = changed[field]
    changed[field] = (
        {"other": "version"}
        if isinstance(original, dict)
        else (["other"] if isinstance(original, list) else "other")
    )
    path.write_text(json.dumps(value), encoding="utf-8")
    suite = load_suite(path)
    output = tmp_path / "out"
    result = run_suite(suite, "D", output, runner=PublicRunner(), evaluator=PublicEvaluator())
    assert result.data["comparison_status"] == "NON_ATTRIBUTABLE"
    report = report_run(output)
    assert report.data["comparison_status"] == "NON_ATTRIBUTABLE"
    assert report.data["summary"]["superiority_claim"] == "UNSUPPORTED"


def test_report_is_offline_escaped_and_preserves_unknown_cost(tmp_path: Path) -> None:
    from polyforge.benchmark.analysis import report_run

    path = tmp_path / "ledger.jsonl"
    row = trial("COMPLETE_GAME_2D", success=True, task_id="<script>alert('x')</script>")
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    before = set(tmp_path.iterdir())
    result = report_run(path)
    assert result.status == "PASS"
    assert set(tmp_path.iterdir()) == before
    assert "<script>" not in result.data["report_html"]
    assert "&lt;script&gt;" in result.data["report_html"]
    assert "unknown" in result.data["report_human"].lower()
    assert result.data["summary"]["accepted_game_rate"]["unknown_cost_count"] == 1
    json.dumps(result.to_dict(), allow_nan=False)


@pytest.mark.parametrize(
    "field,value", [("duration_seconds", float("nan")), ("cost_usd", -1), ("interventions", True)]
)
def test_metrics_reject_nonfinite_or_impossible_observations(field: str, value: object) -> None:
    from polyforge.benchmark.metrics import summarize

    with pytest.raises(InputError):
        summarize([trial("ASSET", **{field: value})])


def test_success_without_observed_independent_grade_is_not_accepted(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    class Ungraded:
        def grade(self, request: EvaluationRequest) -> Result:
            return Result(game_status="ACCEPTED", data={"task_success": True})

    suite = load_suite(configured_suite(tmp_path))
    result = run_suite(suite, "A", tmp_path / "run", runner=PublicRunner(), evaluator=Ungraded())
    assert all(not row["task_success"] for row in result.data["records"])
    assert all(row["game_status"] != "ACCEPTED" for row in result.data["records"])


def test_observed_budget_violation_cannot_pass_and_ledger_cannot_be_overwritten(
    tmp_path: Path,
) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    class OverBudget:
        def run(self, task: EvaluationRequest, *, arm: str, seed: int) -> Result:
            return Result(data={"tokens": 5000, "tool_calls": 201, "interventions": 2})

    suite = load_suite(configured_suite(tmp_path))
    output = tmp_path / "run"
    result = run_suite(suite, "B", output, runner=OverBudget(), evaluator=PublicEvaluator())
    assert all(row["status"] == "FAIL" for row in result.data["records"])
    assert all(row["interventions"] == 2 for row in result.data["records"])
    original = (output / "ledger.jsonl").read_bytes()
    repeated = run_suite(suite, "B", output, runner=PublicRunner(), evaluator=PublicEvaluator())
    assert repeated.status == "FAIL"
    assert (output / "ledger.jsonl").read_bytes() == original


def test_seed_and_metadata_validation_precede_any_output(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    suite = load_suite(path)
    for seeds in ((), (42, 42), (True,), (-1,), tuple(range(101))):
        output = tmp_path / "out"
        result = run_suite(suite, "A", output, seeds=seeds)
        assert result.status == "FAIL"
        assert not output.exists()
    value = json.loads(path.read_text("utf-8"))
    value["execution_metadata"]["D"]["hardware"] = {"ram_gb": float("nan")}
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(InputError):
        load_suite(path)


def test_bad_record_or_duplicate_json_is_an_explicit_report_failure(tmp_path: Path) -> None:
    from polyforge.benchmark.analysis import report_run

    path = tmp_path / "ledger.jsonl"
    path.write_text('{"arm":"D","arm":"C"}\n', encoding="utf-8")
    assert report_run(path).status == "FAIL"
    path.write_text(
        json.dumps({**trial("ASSET"), "task_type": "INVENTED"}) + "\n", encoding="utf-8"
    )
    assert report_run(path).status == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", ""),
        ("hardware", "unreported"),
        ("permissions", "all"),
        ("unknown_adapter", "execute"),
        ("model", "x" * 4097),
        ("hardware", {"x" * 257: 1}),
        ("hardware", {str(i): i for i in range(129)}),
        ("external_assets", ["asset"] * 257),
        ("hardware", {"x": {"x": {"x": {"x": {"x": {"x": {"x": 1}}}}}}}),
    ],
)
def test_metadata_has_bounded_typed_fields(tmp_path: Path, field: str, value: object) -> None:
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    suite = json.loads(path.read_text("utf-8"))
    suite["execution_metadata"]["A"][field] = value
    path.write_text(json.dumps(suite), encoding="utf-8")
    with pytest.raises(InputError):
        load_suite(path)


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "empty",
        "type",
        "owner",
        "acceptance",
        "strata",
        "arms",
        "duplicate-arms",
        "runs",
        "metadata",
    ],
)
def test_invalid_suite_declarations_fail_closed(tmp_path: Path, change: str) -> None:
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    value = json.loads(path.read_text("utf-8"))
    task = value["tasks"][0]
    if change == "version":
        value["schema_version"] = "future"
    elif change == "empty":
        value["tasks"] = []
    elif change == "type":
        value["tasks"][0] = "invalid"
    elif change == "owner":
        task["ownership"] = "EVALUATOR_REFERENCE"
    elif change == "acceptance":
        task["task_success_schema"] = "x" * 4097
    elif change == "strata":
        task["genre"] = ""
    elif change == "arms":
        value["arms"] = ["Z"]
    elif change == "duplicate-arms":
        value["arms"] = ["A", "A"]
    elif change == "runs":
        value["runs_per_task_arm"] = 101
    else:
        value["execution_metadata"] = {"Z": {}}
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(InputError):
        load_suite(path)


@pytest.mark.parametrize(
    "content",
    [b"", b"\xff", b"x" * 262145, None],
    ids=["empty", "invalid-utf8", "oversized", "missing"],
)
def test_missing_oversized_and_invalid_utf8_briefs_are_rejected(
    tmp_path: Path, content: bytes | None
) -> None:
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    brief = path.parent / "briefs/robot_mesh.md"
    if content is None:
        brief.unlink()
    else:
        brief.write_bytes(content)
    with pytest.raises(InputError):
        load_suite(path)


@pytest.mark.parametrize("change", ["row", "manifest", "ledger", "nonfinite", "missing"])
def test_report_checks_local_evidence_integrity(tmp_path: Path, change: str) -> None:
    from polyforge.benchmark.analysis import report_run
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    output = tmp_path / "run"
    run_suite(load_suite(PUBLIC / "suite.json"), "A", output)
    if change == "manifest":
        path = output / "run.json"
        manifest = json.loads(path.read_text("utf-8"))
        manifest["comparison_status"] = "MATCHED"
        path.write_text(json.dumps(manifest), encoding="utf-8")
    elif change == "missing":
        (output / "ledger.jsonl").unlink()
    elif change == "ledger":
        with (output / "ledger.jsonl").open("a", encoding="utf-8") as stream:
            stream.write("{}\n")
    else:
        path = tmp_path / "import.jsonl"
        row = trial("ASSET")
        if change == "row":
            row["row_digest"] = "a" * 64
        else:
            row["cost_usd"] = float("inf")
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        output = path
    assert report_run(output).status == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("task_id", ""),
        ("executed", 1),
        ("status", "INVENTED"),
        ("game_status", "PASS"),
        ("tokens", 2.5),
        ("task_success", True),
        ("timed_out", True),
        ("configuration_digest", []),
        ("resources", {"ram_peak_mb": -1}),
    ],
)
def test_invalid_observation_cannot_improve_metrics(field: str, value: object) -> None:
    from polyforge.benchmark.metrics import summarize

    with pytest.raises(InputError):
        summarize([trial("ASSET", **{field: value})])


def test_costs_and_resources_include_failed_attempts_without_hiding_unknowns() -> None:
    from polyforge.benchmark.metrics import summarize

    values = [
        trial(
            "COMPLETE_GAME_2D",
            success=True,
            cost_usd=1,
            resources={"cpu_seconds": 2, "ram_peak_mb": 100},
        ),
        trial("COMPLETE_GAME_2D", cost_usd=9, resources={"cpu_seconds": 4, "ram_peak_mb": 200}),
    ]
    metric = summarize(values)["accepted_game_rate"]
    assert metric["median_attempt_cost_usd"] == 5
    assert metric["median_accepted_cost_usd"] == 1
    assert metric["resources"]["cpu_seconds"]["variance"] == 1
    assert metric["resources"]["ram_peak_mb"]["median"] == 150
    assert metric["resources"]["gpu_peak_mb"]["unknown_count"] == 2


def test_adapter_exceptions_and_missing_usage_stay_visible(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    class Broken:
        def run(self, task: EvaluationRequest, *, arm: str, seed: int) -> Result:
            if task.task_id == "robot_mesh":
                raise RuntimeError("adapter unavailable")
            if task.task_id == "crate_mesh":
                return "not a Result"
            return Result()

    suite = load_suite(configured_suite(tmp_path))
    result = run_suite(suite, "C", tmp_path / "a/b/run", runner=Broken())
    rows = result.data["records"]
    assert result.status == "FAIL"
    assert rows[0]["diagnostics"][0]["message"] == "adapter unavailable"
    assert rows[1]["status"] == "FAIL"
    assert rows[2]["error_code"] == "PF-BENCHMARK-USAGE-UNKNOWN"


def test_unknown_suite_or_arm_is_rejected_before_creating_output(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    output = tmp_path / "output"
    assert run_suite({}, "A", output).status == "FAIL"
    suite = load_suite(PUBLIC / "suite.json")
    assert run_suite(suite, "Z", output).status == "FAIL"
    assert run_suite(suite, "A", output, dry_run=1).status == "FAIL"
    assert not output.exists()


def test_changed_brief_is_never_delivered_to_runner_after_freeze_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from polyforge.benchmark import runner as module
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    suite = load_suite(path)
    original = module.verify_frozen
    checks = 0
    calls = []

    def raced(value: dict) -> dict:
        nonlocal checks
        result = original(value)
        checks += 1
        if checks == 2:
            (path.parent / "briefs/robot_mesh.md").write_text("REPLACED", encoding="utf-8")
        return result

    class Observer(PublicRunner):
        def run(self, task: EvaluationRequest, *, arm: str, seed: int) -> Result:
            calls.append(task.task_id)
            return super().run(task, arm=arm, seed=seed)

    monkeypatch.setattr(module, "verify_frozen", raced)
    result = module.run_suite(suite, "A", tmp_path / "out", runner=Observer())
    assert result.status == "FAIL"
    assert calls == []


def test_empty_execution_evidence_never_counts_as_matched_configuration(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    value = json.loads(path.read_text("utf-8"))
    value["execution_metadata"]["C"]["hardware"] = {}
    value["execution_metadata"]["D"]["hardware"] = {}
    path.write_text(json.dumps(value), encoding="utf-8")
    result = run_suite(load_suite(path), "D", tmp_path / "out", runner=PublicRunner())
    assert result.status == "BLOCKED"
    assert result.data["comparison_status"] == "NON_ATTRIBUTABLE"
    assert not any(row["executed"] for row in result.data["records"])


def test_explicit_evaluator_failure_is_not_a_missing_dependency(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    class Rejected:
        def grade(self, request: EvaluationRequest) -> Result:
            return failure(ErrorKind.TEST_FAILURE, "PF-PUBLIC-GRADE-FAILED", "Behavior failed")

    suite = load_suite(configured_suite(tmp_path))
    result = run_suite(suite, "D", tmp_path / "out", runner=PublicRunner(), evaluator=Rejected())
    assert result.status == "FAIL"
    assert all(row["evaluation_status"] == "FAIL" for row in result.data["records"])


@pytest.mark.parametrize("arms", [[["A"]], [{"arm": "A"}], [None]])
def test_arm_container_types_fail_as_input_errors(tmp_path: Path, arms: list) -> None:
    from polyforge.benchmark.tasks import load_suite

    path = configured_suite(tmp_path)
    value = json.loads(path.read_text("utf-8"))
    value["arms"] = arms
    path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(InputError):
        load_suite(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", []),
        ("evaluation_status", {}),
        ("game_status", []),
        ("seed", {}),
    ],
)
def test_malformed_observation_types_are_typed_report_errors(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    from polyforge.benchmark.analysis import report_run

    path = tmp_path / "import.jsonl"
    path.write_text(json.dumps(trial("ASSET", **{field: value})) + "\n", encoding="utf-8")
    assert report_run(path).status == "FAIL"


def test_all_four_unexecuted_arms_have_no_measurable_game_rate() -> None:
    from polyforge.benchmark.metrics import summarize

    rows = [trial("COMPLETE_GAME_2D", arm=arm, executed=False, status="BLOCKED") for arm in "ABCD"]
    summary = summarize(rows)
    assert len(summary["by_configuration"]) == 4
    assert summary["accepted_game_rate"]["status"] == "NOT_MEASURABLE"
    assert summary["accepted_game_rate"]["rate"] is None


def test_adapter_reported_timeout_stays_censored(tmp_path: Path) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    class ReportedTimeout:
        def run(self, task: EvaluationRequest, *, arm: str, seed: int) -> Result:
            return Result(
                status="FAIL",
                exit_code=int(ErrorKind.PRODUCER_FAILURE),
                error_code="PF-ADAPTER-TIMEOUT",
                data={"timed_out": True},
            )

    path = configured_suite(tmp_path)
    value = json.loads(path.read_text("utf-8"))
    value["tasks"] = value["tasks"][-1:]
    path.write_text(json.dumps(value), encoding="utf-8")
    result = run_suite(load_suite(path), "D", tmp_path / "out", runner=ReportedTimeout())
    row = result.data["records"][0]
    assert row["timed_out"] and row["censored"]
    assert result.data["summary"]["accepted_game_rate"]["denominator"] == 1


@pytest.mark.parametrize("change", ["task", "seed", "repeated-start", "orphan-finish"])
def test_ledger_attempt_transitions_cannot_replace_execution_identity(
    tmp_path: Path,
    change: str,
) -> None:
    from polyforge.benchmark.analysis import report_run

    started = trial(
        "COMPLETE_GAME_2D",
        attempt_id="one",
        event="STARTED",
        status="NOT_RUN",
        evaluation_status="NOT_RUN",
        censored=True,
    )
    finished = {**started, "event": "FINISHED", "status": "FAIL", "censored": False}
    if change == "task":
        finished["task_id"] = "another_game"
    elif change == "seed":
        finished["seed"] = 43
    elif change == "repeated-start":
        finished = dict(started)
    rows = [finished] if change == "orphan-finish" else [started, finished]
    path = tmp_path / "ledger.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    assert report_run(path).status == "FAIL"


def test_imported_acceptance_is_descriptive_not_verified(tmp_path: Path) -> None:
    from polyforge.benchmark.analysis import report_run

    path = tmp_path / "ledger.jsonl"
    path.write_text(json.dumps(trial("COMPLETE_GAME_2D", success=True)) + "\n", encoding="utf-8")
    result = report_run(path)
    assert result.status == "PASS"
    assert result.data["summary"]["accepted_game_rate"]["numerator"] == 1
    assert result.data["acceptance_assurance"] == "DECLARED_NOT_AUTHENTICATED"
    assert "declared acceptance" in result.data["report_human"].lower()


@pytest.mark.parametrize("checkpoint", ["first-start", "first-finish", "second-start"])
def test_durable_event_before_manifest_update_is_review_with_censored_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    checkpoint: str,
) -> None:
    from polyforge.benchmark import runner as module
    from polyforge.benchmark.analysis import report_run
    from polyforge.benchmark.tasks import load_suite

    original = module.atomic_json
    fail_at = {"first-start": 2, "first-finish": 3, "second-start": 4}[checkpoint]
    writes = 0

    def interrupted(policy, path, value):
        nonlocal writes
        if str(path) == "run.json":
            writes += 1
            if writes == fail_at:
                raise OSError("simulated interruption after durable event")
        return original(policy, path, value)

    output = tmp_path / "out"
    monkeypatch.setattr(module, "atomic_json", interrupted)
    result = module.run_suite(
        load_suite(configured_suite(tmp_path)),
        "D",
        output,
        runner=PublicRunner(),
        evaluator=PublicEvaluator(),
    )
    assert result.status == "FAIL"
    before = {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}
    report = report_run(output)
    assert report.status == "REVIEW"
    assert report.data["integrity_status"] == "UNCOMMITTED_SUFFIX_REVIEW_REQUIRED"
    assert report.data["qualification_status"] == "BLOCKED"
    records = report.data["records"]
    expected_count = 2 if checkpoint == "second-start" else 1
    assert len(records) == expected_count
    pending = records[-1]
    assert pending["event"] == "STARTED" and pending["censored"]
    assert pending["executed"] and not pending["task_success"]
    assert report.data["summary"]["by_task_type"]["ASSET"]["denominator"] == expected_count
    assert before == {path.name: path.read_bytes() for path in output.iterdir() if path.is_file()}


@pytest.mark.parametrize("event", [[], {}, 1, "ABORTED"])
def test_malformed_ledger_event_is_a_typed_failure(tmp_path: Path, event: object) -> None:
    from polyforge.benchmark.analysis import report_run

    path = tmp_path / "ledger.jsonl"
    path.write_text(json.dumps(trial("ASSET", event=event)) + "\n", encoding="utf-8")
    assert report_run(path).status == "FAIL"


@pytest.mark.parametrize("flags", [{"timed_out": True, "censored": True}, {"censored": True}])
def test_censored_execution_cannot_count_as_success(flags: dict) -> None:
    from polyforge.benchmark.metrics import summarize

    with pytest.raises(InputError):
        summarize([trial("COMPLETE_GAME_2D", success=True, **flags)])


def test_changed_committed_prefix_cannot_be_treated_as_a_crash_suffix(tmp_path: Path) -> None:
    from polyforge.benchmark.analysis import report_run
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    output = tmp_path / "run"
    run_suite(load_suite(PUBLIC / "suite.json"), "A", output)
    path = output / "ledger.jsonl"
    original = path.read_bytes()
    # A plausible appended event does not excuse any change to checkpointed bytes.
    path.write_bytes(
        original.replace(b'"task_success": false', b'"task_success": true', 1)
        + original.splitlines(keepends=True)[0]
    )
    assert report_run(output).status == "FAIL"


def test_uncommitted_finish_after_crlf_checkpoint_cannot_add_acceptance(tmp_path: Path) -> None:
    import hashlib

    from polyforge.benchmark.analysis import report_run
    from polyforge.contracts.validation import canonical_digest

    started = trial(
        "COMPLETE_GAME_2D",
        attempt_id="one",
        run_id="run",
        event="STARTED",
        status="NOT_RUN",
        evaluation_status="NOT_RUN",
        censored=True,
    )
    finished = {
        **started,
        "event": "FINISHED",
        "status": "PASS",
        "evaluation_status": "PASS",
        "task_success": True,
        "game_status": "ACCEPTED",
        "censored": False,
    }
    prefix = (json.dumps({**started, "row_digest": canonical_digest(started)}) + "\r\n").encode()
    suffix = (json.dumps({**finished, "row_digest": canonical_digest(finished)}) + "\n").encode()
    manifest = {
        "run_id": "run",
        "arm": "D",
        "configuration_digest": "c" * 64,
        "ledger_bytes": len(prefix),
        "ledger_sha256": hashlib.sha256(prefix).hexdigest(),
    }
    manifest["manifest_digest"] = canonical_digest(manifest)
    (tmp_path / "ledger.jsonl").write_bytes(prefix + suffix)
    (tmp_path / "run.json").write_text(json.dumps(manifest), encoding="utf-8")
    result = report_run(tmp_path)
    assert result.status == "REVIEW"
    metric = result.data["summary"]["accepted_game_rate"]
    assert (metric["numerator"], metric["denominator"], metric["censored_count"]) == (0, 1, 1)


@pytest.mark.parametrize("retries", [-1, True, [], 0.5, float("nan"), float("inf"), 10**12 + 1])
def test_retry_observations_require_bounded_nonnegative_integers(retries: object) -> None:
    from polyforge.benchmark.metrics import summarize

    with pytest.raises(InputError):
        summarize([trial("COMPLETE_GAME_2D", success=True, retries=retries)])


def test_huge_retry_integer_is_a_typed_observation_error() -> None:
    from polyforge.benchmark.metrics import summarize

    with pytest.raises(InputError):
        summarize([trial("COMPLETE_GAME_2D", success=True, retries=10**400)])


@pytest.mark.parametrize("retries", [-1, True, [], 0.5, float("nan"), float("inf"), 10**12 + 1])
def test_malformed_adapter_retries_are_failed_attempts(tmp_path: Path, retries: object) -> None:
    from polyforge.benchmark.runner import run_suite
    from polyforge.benchmark.tasks import load_suite

    class MalformedUsage:
        def run(self, request: EvaluationRequest, *, arm: str, seed: int) -> Result:
            return Result(data={"tokens": 1, "tool_calls": 1, "retries": retries})

    path = configured_suite(tmp_path)
    value = json.loads(path.read_text("utf-8"))
    value["tasks"] = value["tasks"][-1:]
    value["tasks"][0]["budgets"]["retries"] = 2
    path.write_text(json.dumps(value), encoding="utf-8")
    result = run_suite(
        load_suite(path),
        "D",
        tmp_path / "out",
        runner=MalformedUsage(),
        evaluator=PublicEvaluator(),
    )
    row = result.data["records"][0]
    assert result.status == "FAIL"
    assert row["status"] == "FAIL" and row["error_code"] == "PF-BENCHMARK-ADAPTER"
    assert row["retries"] is None and not row["task_success"]
    assert result.data["summary"]["accepted_game_rate"]["numerator"] == 0
    assert result.data["summary"]["accepted_game_rate"]["denominator"] == 1


@pytest.mark.parametrize("outcome", ["accepted", "rejected", "blocked", "timeout", "exception"])
@pytest.mark.parametrize("elapsed", [0.75, 10.0])
def test_attempt_elapsed_time_and_wall_budget_include_evaluation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    outcome: str,
    elapsed: float,
) -> None:
    from polyforge.benchmark import runner as module
    from polyforge.benchmark.tasks import load_suite

    now = 0.0

    class TimedRunner(PublicRunner):
        def run(self, request: EvaluationRequest, *, arm: str, seed: int) -> Result:
            nonlocal now
            now = 0.1
            return super().run(request, arm=arm, seed=seed)

    class TimedEvaluator(PublicEvaluator):
        def grade(self, request: EvaluationRequest) -> Result:
            nonlocal now
            now = elapsed
            if outcome == "timeout":
                raise TimeoutError("grading timeout")
            if outcome == "exception":
                raise RuntimeError("grading exception")
            if outcome == "rejected":
                return failure(ErrorKind.TEST_FAILURE, "PF-GRADE-FAIL", "Rejected")
            if outcome == "blocked":
                return failure(ErrorKind.MISSING_DEPENDENCY, "PF-GRADE-BLOCKED", "Unavailable")
            return super().grade(request)

    path = configured_suite(tmp_path)
    value = json.loads(path.read_text("utf-8"))
    value["tasks"] = value["tasks"][-1:]
    value["tasks"][0]["budgets"]["wall_seconds"] = 1
    path.write_text(json.dumps(value), encoding="utf-8")
    monkeypatch.setattr(module.time, "monotonic", lambda: now)
    result = module.run_suite(
        load_suite(path), "D", tmp_path / "out", runner=TimedRunner(), evaluator=TimedEvaluator()
    )
    row = result.data["records"][0]
    assert row["duration_seconds"] == elapsed
    games = result.data["summary"]["accepted_game_rate"]
    assert games["median_attempt_seconds"] == elapsed
    if elapsed > 1:
        assert result.status == row["status"] == "FAIL"
        assert row["timed_out"] and row["censored"] and not row["task_success"]
        assert row["game_status"] != "ACCEPTED"
        assert games["numerator"] == 0 and games["denominator"] == 1
    elif outcome == "accepted":
        assert result.status == "PASS" and row["task_success"]
        assert games["median_accepted_seconds"] == elapsed


@pytest.mark.parametrize("field", ["gpu_peak_mb", "ram_peak_mb", "cpu_seconds", "load_seconds"])
@pytest.mark.parametrize("entrypoint", ["summarize", "report"])
def test_huge_resource_integer_is_a_typed_failure(
    tmp_path: Path,
    field: str,
    entrypoint: str,
) -> None:
    from polyforge.benchmark.analysis import report_run
    from polyforge.benchmark.metrics import summarize

    row = trial("COMPLETE_GAME_2D", resources={field: 10**400})
    if entrypoint == "summarize":
        with pytest.raises(InputError):
            summarize([row])
    else:
        path = tmp_path / "ledger.jsonl"
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        result = report_run(path)
        assert result.status == "FAIL" and result.exit_code == int(ErrorKind.INVALID_INPUT)
        assert not result.data.get("summary")


@pytest.mark.parametrize("field", ["gpu_peak_mb", "ram_peak_mb", "cpu_seconds", "load_seconds"])
@pytest.mark.parametrize("value", [True, -1, -0.5, float("nan"), float("inf")])
def test_report_rejects_malformed_resource_values(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    from polyforge.benchmark.analysis import report_run
    from polyforge.benchmark.metrics import summarize

    row = trial("COMPLETE_GAME_2D", resources={field: value})
    with pytest.raises(InputError):
        summarize([row])
    path = tmp_path / "ledger.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    assert report_run(path).status == "FAIL"


@pytest.mark.parametrize("field", ["gpu_peak_mb", "ram_peak_mb", "cpu_seconds", "load_seconds"])
def test_report_keeps_failed_resource_observations_and_finite_floats(
    tmp_path: Path,
    field: str,
) -> None:
    from polyforge.benchmark.analysis import report_run

    rows = [
        trial("COMPLETE_GAME_2D", success=True, resources={field: 0.5}),
        trial("COMPLETE_GAME_2D", resources={field: 3.5}),
        trial("COMPLETE_GAME_2D", resources={field: None}),
    ]
    path = tmp_path / "ledger.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    result = report_run(path)
    assert result.status == "PASS"
    assert len(result.data["records"]) == 3
    metric = result.data["summary"]["accepted_game_rate"]
    assert (metric["numerator"], metric["denominator"]) == (1, 3)
    resource = metric["resources"][field]
    assert (resource["observed_count"], resource["unknown_count"]) == (2, 1)
    assert resource["median"] == 2.0 and resource["variance"] == 2.25
