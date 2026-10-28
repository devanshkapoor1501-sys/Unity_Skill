"""Regression cases from the one fresh Phase 7 review."""

import copy
import hashlib
import json
import threading

import pytest

from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import Result
from polyforge.contracts.validation import InputError, canonical_digest
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


def approved(tmp_path):
    from test_animation import fixture

    from polyforge.workforce.workers import inspect_candidate, seal_candidate

    p = WorkspacePolicy(tmp_path)
    p.mkdir("runs/rig_a/asset")
    request = {
        "schema_version": "1.0.0",
        "task_class": "ANIMATE",
        "domain_tags": ["blender", "animation"],
        "feature_ids": ["idle_walk"],
        "brief": "Animate only in Blender.",
        "capability_id": "animation.robot.rig.v1",
        "input": {
            "schema_version": "1.0.0",
            "asset_id": "robot_a",
            "parameters": {"size_m": [1, 2, 1]},
        },
    }
    records = []
    for name, data in [
        ("robot.fbx", b"Kaydara FBX Binary fixture"),
        ("source.blend", b"BLENDER fixture"),
        ("motion.json", json.dumps(fixture()).encode()),
    ]:
        path = p.path("runs/rig_a/asset/" + name)
        path.write_bytes(data)
        records.append(
            {
                "relative_path": path.relative_to(p.root).as_posix(),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    atomic_json(p, "runs/rig_a/artifacts.json", {"artifacts": records})
    result = Result(run_id="rig_a", data={"fbx_path": "runs/rig_a/asset/robot.fbx"})
    candidate = seal_candidate(p, result, canonical_digest(request["brief"]))
    review = inspect_candidate(p, candidate, request)
    return p, request, candidate, review, result


def test_import_rejects_substituted_fbx_before_native_writes(tmp_path):
    from polyforge.animation.integration import validate_import_source

    p, request, candidate, review, result = approved(tmp_path)
    altered = result.to_dict()
    altered["data"]["fbx_path"] = "runs/other/robot.fbx"
    before = set(tmp_path.rglob("*"))
    with pytest.raises(InputError):
        validate_import_source(p, candidate, altered)
    assert set(tmp_path.rglob("*")) == before


def test_review_rejects_wrong_task_brief_unsealed_motion_and_forged_owner(tmp_path):
    from polyforge.workforce.workers import inspect_candidate, require_approval

    p, request, candidate, review, result = approved(tmp_path)
    for changed in [{"task_class": "EXPLAIN"}, {"brief": "Another original brief"}]:
        with pytest.raises(InputError):
            inspect_candidate(p, candidate, {**request, **changed})
    with pytest.raises(InputError):
        require_approval(p, candidate, {**review, "reviewer_id": "producer_alias"})
    unsealed = copy.deepcopy(candidate)
    unsealed["files"] = [f for f in unsealed["files"] if not f["path"].endswith("motion.json")]
    unsealed["candidate_digest"] = canonical_digest(
        {k: v for k, v in unsealed.items() if k != "candidate_digest"}
    )
    with pytest.raises(InputError):
        inspect_candidate(p, unsealed, request)


def test_blender_only_animation_never_requests_unity(tmp_path):
    from polyforge.workforce.router import plan_task

    p, request, candidate, review, result = approved(tmp_path)
    plan = plan_task(request)
    assert len(plan["jobs"]) == 3
    assert "S4" not in plan["stages"]


def test_manifest_changes_invalidate_game_workforce_plan(tmp_path):
    from polyforge.workforce.router import plan_task

    request = {
        "schema_version": "1.0.0",
        "task_class": "BUILD_GAME",
        "domain_tags": ["unity", "gameplay"],
        "feature_ids": [],
        "brief": "Build my arena",
        "capability_id": "unity.game.arena.v1",
        "input": {"schema_version": "1.0.0"},
    }
    (tmp_path / "game_manifest.json").write_text('{"seed":1}')
    a = plan_task(request, workspace=tmp_path)
    (tmp_path / "game_manifest.json").write_text('{"seed":2}')
    b = plan_task(request, workspace=tmp_path)
    assert a["task_id"] != b["task_id"]


def test_completed_operation_reused_after_crash_before_job_commit_and_detects_mutation(
    tmp_path, monkeypatch
):
    import polyforge.capabilities.dispatch as module
    from polyforge.capabilities.dispatch import execute
    from polyforge.workforce.operations import operation_context

    calls = []

    def native(identifier, inputs, context):
        calls.append(1)
        p = WorkspacePolicy(tmp_path)
        p.mkdir("runs/native")
        p.path("runs/native/output.json").write_text('{"status":"PASS"}')
        return Result(run_id="native", evidence_paths=["runs/native/output.json"])

    monkeypatch.setattr(module, "_execute", native)
    context = operation_context(tmp_path, "task_a", "job_a", 42, None)
    first = execute("contract.capability.validate.v1", {}, context)
    second = execute("contract.capability.validate.v1", {}, context)
    assert first == second and len(calls) == 1
    (tmp_path / "runs/native/output.json").write_text("changed")
    with pytest.raises(InputError):
        execute("contract.capability.validate.v1", {}, context)


def test_game_dispatch_propagates_cancellation(tmp_path, monkeypatch):
    import polyforge.blender.build as module
    from polyforge.capabilities.dispatch import execute

    event = threading.Event()
    observed = []

    def build(workspace, **kwargs):
        observed.append(kwargs.get("cancel"))
        return Result()

    monkeypatch.setattr(module, "build_assets", build)
    execute("unity.game.arena.v1", {"schema_version": "1.0.0"}, RunContext(tmp_path, cancel=event))
    assert observed == [event]


def test_cancellation_stops_an_actual_owned_child(tmp_path, monkeypatch):
    import sys
    import time
    from pathlib import Path

    import polyforge.workforce.orchestrator as module
    from polyforge.contracts.results import ErrorKind, failure
    from polyforge.runner.processes import ProcessPolicy, run_process
    from polyforge.workforce.ledger import JobLedger

    ledger = JobLedger(tmp_path, "cancel_actual")
    lease = ledger.claim("produce", "crate")
    outcomes = []
    results = []

    def native(identifier, inputs, context):
        outcome = run_process(
            [
                sys.executable,
                "-u",
                "-c",
                "import time;from pathlib import Path;"
                "Path('child-started.txt').write_text('running');time.sleep(60)",
            ],
            ledger.policy,
            "child",
            ProcessPolicy((Path(sys.executable),), 10, 1048576, 8192),
            cancel=context.cancel,
        )
        outcomes.append(outcome)
        return failure(ErrorKind.INTERRUPTED, "PF-CHILD-CANCEL", "cancelled")

    monkeypatch.setattr(module, "execute", native)
    thread = threading.Thread(
        target=lambda: results.append(
            module.execute_leased(ledger, "produce", lease, "mesh.props.crate.v1", {}, 42)
        )
    )
    thread.start()
    for _ in range(120):
        marker = tmp_path / "child/child-started.txt"
        if marker.is_file() and marker.read_text() == "running":
            break
        time.sleep(0.025)
    else:
        pytest.fail("Owned child never reached running state")
    ledger.cancel("produce")
    thread.join(5)
    assert not thread.is_alive()
    assert outcomes[0].pid is not None and outcomes[0].reason == "cancelled"
    assert results[0].exit_code == 9


@pytest.mark.parametrize("job", ["production", "integration"])
def test_real_process_death_after_operation_before_coordinator_commit(tmp_path, monkeypatch, job):
    import os
    import subprocess
    import sys
    from pathlib import Path

    import polyforge.capabilities.dispatch as module
    from polyforge.workforce.operations import operation_context

    code = """import sys,os
from pathlib import Path
import polyforge.capabilities.dispatch as d
from polyforge.workforce.operations import operation_context
from polyforge.contracts.results import Result
p=Path(sys.argv[1]);job=sys.argv[2]
def native(identifier,inputs,context):
 (p/'runs'/'completed').mkdir(parents=True)
 (p/'runs'/'completed'/'output.json').write_text('{\"status\":\"PASS\"}')
 return Result(run_id='completed',evidence_paths=['runs/completed/output.json'])
d._execute=native
d.execute('contract.capability.validate.v1',{},operation_context(p,'crash_task',job,42,None))
os._exit(9)
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    child = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path), job], env=env, capture_output=True, timeout=20
    )
    assert child.returncode == 9, child.stderr

    def duplicate(*args):
        raise AssertionError("Native mutation repeated after completed operation")

    monkeypatch.setattr(module, "_execute", duplicate)
    result = module.execute(
        "contract.capability.validate.v1",
        {},
        operation_context(tmp_path, "crash_task", job, 42, None),
    )
    assert result.status == "PASS"
