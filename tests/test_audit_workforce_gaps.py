"""Audit regressions: proposal uncertainty, frozen context, budgets and breadth."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError, canonical_digest, validate_schema
from polyforge.security.paths import WorkspacePolicy


def task(**changes):
    return {
        "schema_version": "1.0.0",
        "brief": "Make a crate with editable source",
        "task_class": "CREATE_ASSET",
        "domain_tags": ["blender"],
        "feature_ids": ["editable"],
        "capability_id": "mesh.props.crate.v1",
        "input": {
            "schema_version": "1.0.0",
            "asset_id": "crate",
            "parameters": {"size_m": [1, 1, 1]},
        },
        **changes,
    }


@pytest.mark.parametrize(
    "query,output,candidate",
    [
        ("Make a crate and sculpt a detailed organic dragon", "ASSET", "mesh.props.crate.v1"),
        (
            "Build a multiplayer survival arena with inventory and save/load",
            "GAME",
            "unity.game.arena.v1",
        ),
        (
            "Animate a robot with facial expressions and humanoid retargeting",
            "ANIMATE",
            "animation.robot.rig.v1",
        ),
        ("Make a crate", "ASSET", "mesh.props.crate.v1"),
    ],
)
def test_natural_language_candidate_never_proves_complete_requirements(
    tmp_path, monkeypatch, query, output, candidate
):
    from polyforge.knowledge.router import route_reference
    from polyforge.workforce import discovery

    monkeypatch.setattr(discovery, "discover_tool", lambda *args: Path(sys.executable))
    result = route_reference(
        WorkspacePolicy(tmp_path), {"schema_version": "1.0.0", "query": query, "output": output}
    )
    assert result["status"] == "REVIEW"
    assert candidate in result["capability_ids"]
    assert result["requirement_coverage"] == "UNVERIFIED"
    assert result["gap"] and result["discovery"]["execution_status"] == "BLOCKED"


def test_job_context_binds_original_task_and_engine_owned_scope(tmp_path):
    from polyforge.workforce.router import plan_task

    request = task()
    plan = plan_task(request, workspace=tmp_path)
    job = plan["jobs"][1]
    context = job["context"]
    assert context["schema_version"] == "1.0.0"
    assert context["task_digest"] == canonical_digest(request)
    assert context["brief_digest"] == canonical_digest(request["brief"])
    assert context["task_class"] == "CREATE_ASSET"
    assert context["selected_knowledge_cards"]
    assert context["toolchain_probes"][0]["status"] == "UNKNOWN"
    assert context["tool_allowlist"] and "shell.execute" not in context["tool_allowlist"]
    assert context["permissions_from_references"] is False
    assert context["approval_owner"] == "EXISTING_REVIEW_GATES"
    assert context["evaluator_ref"] == "EXTERNAL_NOT_SUPPLIED"
    assert context["evaluator_access"] == "DENIED"
    assert context["observed_inputs"] == plan["workspace_inputs"]
    assert job["context_digest"] == canonical_digest(context)
    for ticket in plan["jobs"]:
        validate_schema(ticket, "job_ticket.schema.json")
    legacy = {k: v for k, v in job.items() if k not in {"context", "context_digest"}}
    validate_schema(legacy, "job_ticket.schema.json")


def test_cross_engine_job_context_preserves_both_toolchains():
    from polyforge.workforce.router import plan_task

    plan = plan_task(
        task(
            task_class="ANIMATE",
            capability_id="animation.robot.rig.v1",
            domain_tags=["blender", "unity", "animation"],
        )
    )
    context = plan["jobs"][1]["context"]
    assert {p["tool"] for p in context["toolchain_probes"]} == {"blender", "unity"}
    assert any(c["knowledge_id"] == "unity.animation" for c in context["selected_knowledge_cards"])
    assert any(
        c["knowledge_id"] == "blender.animation" for c in context["selected_knowledge_cards"]
    )
    assert plan["jobs"][3]["context"]["original_task_input_digest"] == canonical_digest(
        task()["input"]
    )
    assert "input_digest" not in plan["jobs"][3]["context"]


def test_job_context_cannot_grant_a_role_new_tools(tmp_path):
    from polyforge.workforce.ledger import JobLedger
    from polyforge.workforce.orchestrator import execute_leased
    from polyforge.workforce.router import plan_task

    ticket = plan_task(task())["jobs"][1]
    ticket["role_id"] = "intent_analyst"
    ticket["context"]["tool_allowlist"] = ["mesh.props.crate.v1"]
    ticket["context_digest"] = canonical_digest(ticket["context"])
    ledger = JobLedger(tmp_path, "permission_task")
    lease = ledger.claim("job_1", "crate")
    with pytest.raises(InputError, match="Role lacks authorization"):
        execute_leased(
            ledger, "job_1", lease, ticket["capability_id"], task()["input"], 42, job_ticket=ticket
        )
    assert not list((tmp_path / ".polyforge/operations").glob("*"))


@pytest.mark.parametrize("budget,ceiling,expected", [(1, 600, 1), (30, 7, 7)])
def test_execute_leased_consumes_job_budget_and_native_ceiling(
    tmp_path, monkeypatch, budget, ceiling, expected
):
    import polyforge.workforce.orchestrator as module
    from polyforge.contracts.results import Result
    from polyforge.workforce.ledger import JobLedger
    from polyforge.workforce.router import plan_task

    (tmp_path / "polyforge.toml").write_text(
        f"[execution]\nblender_timeout_seconds = {ceiling}\n", encoding="utf-8"
    )
    ticket = plan_task(task(budget_seconds=budget), workspace=tmp_path)["jobs"][1]
    ledger = JobLedger(tmp_path, "budget_task")
    lease = ledger.claim("job_1", "crate")

    # Trusted native dispatch is replaced to observe the real coordinator boundary.
    def execute(identifier, inputs, context):
        return Result(data={"timeout": context.timeout_seconds})

    monkeypatch.setattr(module, "execute", execute)
    result = module.execute_leased(
        ledger, "job_1", lease, ticket["capability_id"], task()["input"], 42, job_ticket=ticket
    )
    assert result.data["timeout"] == expected
    intent = json.loads(
        next((tmp_path / ".polyforge/operations").glob("*.intent.json")).read_text()
    )
    assert intent["context_digest"] == ticket["context_digest"]
    assert intent["input_digest"] == canonical_digest(task()["input"])


@pytest.mark.parametrize("expired", [False, True])
def test_inspection_failure_or_deadline_never_commits_or_reads_success_data(
    tmp_path, monkeypatch, expired
):
    import time

    import polyforge.workforce.orchestrator as module
    from polyforge.contracts.results import ErrorKind, Result, failure
    from polyforge.workforce.ledger import JobLedger

    monkeypatch.setattr(module, "seal_candidate", lambda *args: {})
    monkeypatch.setattr(module, "require_approval", lambda *args: None)

    def execute(identifier, inputs, context):
        if identifier == "artifact.candidate.inspect.v1":
            if expired:
                time.sleep(1.1)
                return Result(data={"review": {}, "board": {}})
            return failure(ErrorKind.TEST_FAILURE, "PF-TEST-INSPECT", "Inspection rejected")
        return Result()

    monkeypatch.setattr(module, "execute", execute)
    result = module.run_task(tmp_path, task(budget_seconds=1))
    assert result.status == "FAIL"
    assert result.error_code == ("PF-WORKFORCE-DEADLINE" if expired else "PF-TEST-INSPECT")
    plan = module.plan_task(task(budget_seconds=1), workspace=tmp_path)
    ledger = JobLedger(tmp_path, plan["task_id"])
    assert ledger.completed("job_2") is None
    assert not ledger.policy.path(ledger.relative + "/review.json").exists()


def test_probe_refresh_preserves_original_plan_and_committed_job_context(tmp_path, monkeypatch):
    import polyforge.knowledge.probes as probes
    import polyforge.workforce.orchestrator as module
    from polyforge.contracts.results import ErrorKind, failure
    from polyforge.runner.state import atomic_json
    from polyforge.workforce.ledger import JobLedger

    receipt = {"receipt": {"run_id": "knowledge-1111111111111111"}}
    monkeypatch.setattr(probes, "read_probe", lambda *args: copy.deepcopy(receipt))
    request = task()
    frozen = module.plan_task(request, workspace=tmp_path)
    ledger = JobLedger(tmp_path, frozen["task_id"])
    atomic_json(ledger.policy, ledger.relative + "/plan.json", frozen)
    lease = ledger.claim("job_0", "crate")
    ledger.commit(
        "job_0",
        lease,
        {"original_request": request, "brief_digest": canonical_digest(request["brief"])},
    )
    prior = ledger.completed("job_0")
    receipt["receipt"]["run_id"] = "knowledge-2222222222222222"
    refreshed = module.plan_task(request, workspace=tmp_path)
    assert frozen["task_id"] == refreshed["task_id"]
    assert frozen["jobs"][1]["context_digest"] != refreshed["jobs"][1]["context_digest"]
    monkeypatch.setattr(
        module,
        "execute",
        lambda *args: failure(ErrorKind.TEST_FAILURE, "PF-TEST-STOP", "Stop before native work"),
    )
    result = module.run_task(tmp_path, request)
    assert result.status == "FAIL"
    retained = json.loads(ledger.policy.path(ledger.relative + "/plan.json").read_text())
    assert retained == frozen
    assert ledger.completed("job_0") == prior
    intent = json.loads(
        next((tmp_path / ".polyforge/operations").glob("*.intent.json")).read_text()
    )
    assert intent["context_digest"] == frozen["jobs"][1]["context_digest"]


def test_execute_leased_deadline_cancels_work_and_cannot_report_pass(tmp_path, monkeypatch):
    import polyforge.workforce.orchestrator as module
    from polyforge.contracts.results import Result
    from polyforge.workforce.ledger import JobLedger
    from polyforge.workforce.router import plan_task

    ticket = plan_task(task(budget_seconds=1))["jobs"][1]
    ledger = JobLedger(tmp_path, "deadline_task")
    lease = ledger.claim("job_1", "crate")

    def execute(identifier, inputs, context):
        assert context.cancel.wait(3), "Coordinator did not cancel the expired job"
        return Result()

    monkeypatch.setattr(module, "execute", execute)
    result = module.execute_leased(
        ledger, "job_1", lease, ticket["capability_id"], task()["input"], 42, job_ticket=ticket
    )
    assert result.status == "FAIL" and result.error_code == "PF-WORKFORCE-DEADLINE"


def test_hardware_admission_denies_unmeasured_gpu_and_disk_before_writes(tmp_path):
    from polyforge.workforce.models import validate_task
    from polyforge.workforce.orchestrator import run_task

    for resources in [{"gpu_required": True}, {"min_free_disk_bytes": 2**63 - 1}]:
        validate_task(task(resources=resources))
        with pytest.raises(InputError):
            run_task(tmp_path, task(resources=resources))
        assert not list(tmp_path.iterdir())


def test_coverage_generator_includes_fixed_gaps_and_retains_historical_records(tmp_path):
    root = Path(__file__).resolve().parents[1]
    output = tmp_path / "coverage.json"
    result = subprocess.run(
        [
            sys.executable,
            str(root / "tools/generate_knowledge_coverage.py"),
            "--output",
            str(output),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["denominator"]["subfeature_count"] == 20
    assert len(report["entries"]) == 20
    assert {e["domain"] for e in report["entries"]} == {"blender", "unity"}
    assert len(report["records"]) == 3
    sculpt = next(e for e in report["entries"] if e["id"] == "blender.sculpt-retopo")
    assert sculpt["states"]["executable"] == "NONE"
    assert sculpt["states"]["independent_validation"] == "NONE"
    assert sculpt["gap"]
    assert report["coverage_percentage"] is None
    assert all(e["priority"] in {"T1", "T2", "T3"} for e in report["entries"])
    assert any(e["evidence"] for e in report["entries"])

    taxonomy = json.loads((root / "polyforge/data/knowledge-taxonomy.json").read_text())
    damaged = copy.deepcopy(taxonomy)
    damaged["entries"].pop()
    source = tmp_path / "shrunk.json"
    source.write_text(json.dumps(damaged), encoding="utf-8")
    refused = subprocess.run(
        [
            sys.executable,
            str(root / "tools/generate_knowledge_coverage.py"),
            "--taxonomy",
            str(source),
            "--output",
            str(tmp_path / "shrunk-report.json"),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert refused.returncode != 0
    assert not (tmp_path / "shrunk-report.json").exists()
