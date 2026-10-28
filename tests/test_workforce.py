"""Phase 7 routing/authority tests run without Blender, Unity or model credentials."""

import copy

import pytest

from polyforge.contracts.validation import InputError


def request(task="CREATE_ASSET", **changes):
    return {
        "schema_version": "1.0.0",
        "brief": "Make a blue industrial crate; preserve editable source.",
        "task_class": task,
        "domain_tags": ["blender"],
        "feature_ids": ["editable_source"],
        "capability_id": "mesh.props.crate.v1",
        "input": {
            "schema_version": "1.0.0",
            "asset_id": "industrial_box",
            "parameters": {"size_m": [1, 1, 1]},
        },
        **changes,
    }


def test_minimal_routing_preserves_brief_and_never_forces_robot_or_unity():
    from polyforge.workforce.router import plan_task

    for task in ["EXPLAIN", "INSPECT", "CREATE_ASSET"]:
        value = request(task)
        plan = plan_task(value)
        assert plan["original_request"] == value
        assert "S4" not in plan["stages"]
        assert all("unity" not in j.get("capability_id", "") for j in plan["jobs"])
    full = plan_task(
        request(
            "BUILD_GAME", capability_id="unity.game.arena.v1", input={"schema_version": "1.0.0"}
        )
    )
    assert full["stages"] == ["S0", "S1", "S2", "S3", "S4", "S5"]
    assert plan_task(request("EXPLAIN"))["execution_status"] == "NOT_RUN"


@pytest.mark.parametrize("name", ["animation/adapter.py", "contracts/handoff.schema.json"])
def test_engine_identity_covers_adapter_and_contract_changes(tmp_path, monkeypatch, name):
    import shutil

    import polyforge.workforce.router as module

    original = module.files
    package = tmp_path / "polyforge"
    shutil.copytree(original("polyforge"), package, ignore=shutil.ignore_patterns("__pycache__"))
    target = package / name
    monkeypatch.setattr(
        module, "files", lambda key: package if key == "polyforge" else original(key)
    )
    before = module.engine_digest()
    target.write_text(target.read_text() + "\nchanged")
    assert module.engine_digest() != before


@pytest.mark.parametrize(
    "change",
    [
        {"task_class": "ARBITRARY"},
        {"capability_id": "shell.exec"},
        {"input": {"shell": "rm -r"}},
        {"brief": ""},
        {"domain_tags": []},
        {"seed": -1},
    ],
)
def test_invalid_task_rejected_before_any_work(change):
    from polyforge.workforce.router import plan_task

    with pytest.raises(InputError):
        plan_task(request(**change))


def test_permission_boundaries_and_claimed_host_independence_are_enforced(tmp_path):
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.workforce.permissions import authorize, execution_profile

    p = WorkspacePolicy(tmp_path)
    assert execution_profile("sequential")["independence"] == "DIFFERENT_ROLE_SAME_HOST"
    with pytest.raises(InputError):
        execution_profile("host")
    with pytest.raises(InputError):
        authorize(p, "animation_inspector", "write", "candidates/a/source.blend")
    with pytest.raises(InputError):
        authorize(p, "rig_animation_artist", "write", "UnityProject/x.cs")
    with pytest.raises(InputError):
        authorize(p, "rig_animation_artist", "write", "../outside")
    with pytest.raises(InputError):
        authorize(p, "rig_animation_artist", "tool", "shell.exec")
    assert authorize(p, "rig_animation_artist", "tool", "animation.robot.rig.v1")


def test_schema_rejects_self_review_and_unbound_candidate():
    from polyforge.workforce.models import validate_review

    review = {
        "schema_version": "1.0.0",
        "artifact_id": "candidate_a",
        "candidate_digest": "a" * 64,
        "producer_id": "artist",
        "reviewer_id": "inspector",
        "verdict": "APPROVED",
        "independence": "DIFFERENT_ROLE_SAME_HOST",
        "evidence": ["runs/check/report.json"],
    }
    validate_review(review)
    for changes in [
        {"reviewer_id": "artist"},
        {"candidate_digest": "bad"},
        {"independence": "SEPARATELY_CONTROLLED_EVALUATOR"},
    ]:
        with pytest.raises(InputError):
            validate_review({**copy.deepcopy(review), **changes})


def test_job_leases_fence_competing_writer_cancel_and_idempotent_commits(tmp_path):
    from polyforge.workforce.ledger import JobLedger

    ledger = JobLedger(tmp_path, "task_a")
    lease = ledger.claim("produce", "industrial_box", ttl=60)
    with pytest.raises(InputError):
        ledger.claim("other", "industrial_box", ttl=60)
    ledger.commit("produce", lease, {"status": "PASS", "artifact": "runs/source"})
    assert ledger.completed("produce")["artifact"] == "runs/source"
    assert ledger.claim("produce", "industrial_box", ttl=60) is None
    second = ledger.claim("other", "industrial_box", ttl=60)
    ledger.cancel("other")
    with pytest.raises(InputError):
        ledger.commit("other", second, {"status": "PASS"})
    with pytest.raises(InputError):
        ledger.commit("produce", lease, {"status": "FAIL"})


def test_dead_expired_owner_reclaimed_once_but_live_owner_is_not(tmp_path, monkeypatch):
    import polyforge.workforce.ledger as module
    from polyforge.workforce.ledger import JobLedger

    ledger = JobLedger(tmp_path, "task_a")
    old = ledger.claim("produce", "robot", ttl=1)
    monkeypatch.setattr(module.time, "time", lambda: 10**12)
    with pytest.raises(InputError):
        ledger.claim("replacement", "robot", ttl=1)
    monkeypatch.setattr(module, "process_identity", lambda pid: None)
    replacement = ledger.claim("replacement", "robot", ttl=1)
    with pytest.raises(InputError):
        ledger.commit("produce", old, {"status": "PASS"})
    ledger.commit("replacement", replacement, {"status": "PASS"})
    assert ledger.completed("replacement")["status"] == "PASS"


def test_dry_run_and_invalid_requests_cannot_create_ledger(tmp_path):
    from polyforge.workforce.orchestrator import run_task

    assert run_task(tmp_path, request(), dry_run=True).status == "PASS"
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(InputError):
        run_task(tmp_path, request(capability_id="shell.exec"))
    assert list(tmp_path.iterdir()) == []


def test_workforce_cli_and_discovery_use_the_existing_registry(tmp_path):
    from polyforge.cli import build_parser, dispatch

    result = dispatch(
        build_parser().parse_args(["workforce", "roles", "--workspace", str(tmp_path), "--json"])
    )
    assert "rig_animation_artist" in result.data["roles"]
    assert result.data["native_subagents"] == "UNAVAILABLE"
    assert list(tmp_path.iterdir()) == []


def test_candidate_changes_and_approval_substitution_are_rejected(tmp_path):
    import hashlib

    from polyforge.contracts.results import Result
    from polyforge.runner.state import atomic_json
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.workforce.workers import check_candidate, require_approval, seal_candidate

    p = WorkspacePolicy(tmp_path)
    p.mkdir("runs/mesh_a/asset")
    source = p.path("runs/mesh_a/asset/source.blend")
    source.write_bytes(b"BLENDER source")
    atomic_json(
        p,
        "runs/mesh_a/artifacts.json",
        {
            "artifacts": [
                {
                    "relative_path": "runs/mesh_a/asset/source.blend",
                    "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                }
            ]
        },
    )
    candidate = seal_candidate(p, Result(run_id="mesh_a"), "a" * 64)
    check_candidate(p, candidate)
    review = {
        "schema_version": "1.0.0",
        "artifact_id": candidate["artifact_id"],
        "candidate_digest": candidate["candidate_digest"],
        "producer_id": "producer",
        "reviewer_id": "inspector",
        "independence": "DIFFERENT_ROLE_SAME_HOST",
        "verdict": "APPROVED",
        "evidence": ["runs/mesh_a/artifacts.json"],
    }
    with pytest.raises(InputError):
        require_approval(p, candidate, review)
    with pytest.raises(InputError):
        require_approval(p, candidate, {**review, "candidate_digest": "b" * 64})
    with pytest.raises(InputError):
        require_approval(p, candidate, {**review, "verdict": "REVIEW"})
    source.write_bytes(b"changed")
    with pytest.raises(InputError):
        check_candidate(p, candidate)


def test_atomic_commit_recovers_crash_before_lease_release(tmp_path, monkeypatch):
    import polyforge.workforce.ledger as module
    from polyforge.workforce.ledger import JobLedger

    ledger = JobLedger(tmp_path, "task_a")
    lease = ledger.claim("produce", "robot")
    original = module.atomic_json

    def interrupted(policy, path, value):
        if value.get("released") is True:
            raise OSError("power loss after durable result")
        return original(policy, path, value)

    monkeypatch.setattr(module, "atomic_json", interrupted)
    with pytest.raises(OSError):
        ledger.commit("produce", lease, {"status": "PASS"})
    monkeypatch.setattr(module, "atomic_json", original)
    assert ledger.completed("produce") == {"status": "PASS"}
    assert ledger.claim("inspect", "robot") is not None


def test_cancelling_expired_job_cannot_release_replacement_owner(tmp_path, monkeypatch):
    import polyforge.workforce.ledger as module
    from polyforge.workforce.ledger import JobLedger

    ledger = JobLedger(tmp_path, "task_a")
    ledger.claim("old", "robot", ttl=1)
    monkeypatch.setattr(module.time, "time", lambda: 10**12)
    monkeypatch.setattr(module, "process_identity", lambda pid: None)
    replacement = ledger.claim("new", "robot", ttl=60)
    ledger.cancel("old")
    ledger.commit("new", replacement, {"status": "PASS"})


def test_repeated_owned_upgrades_use_committed_package_provenance(tmp_path):
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity.upgrade import sync_package

    p = WorkspacePolicy(tmp_path)
    sync_package(p, {"Runtime/New.cs": b"first"})
    sync_package(p, {"Runtime/New.cs": b"second"})
    assert (
        p.path("UnityProject/Packages/com.polyforge.engine/Runtime/New.cs").read_bytes()
        == b"second"
    )
    p.path("UnityProject/Packages/com.polyforge.engine/Runtime/New.cs").write_bytes(b"user change")
    with pytest.raises(InputError):
        sync_package(p, {"Runtime/New.cs": b"third"})


def test_explanation_only_needs_no_asset_recipe_or_unity_task():
    from polyforge.workforce.router import plan_task

    value = {
        "schema_version": "1.0.0",
        "brief": "Explain when to use a CharacterController.",
        "task_class": "EXPLAIN",
        "domain_tags": ["unity"],
        "feature_ids": [],
    }
    plan = plan_task(value)
    assert plan["jobs"] == []
    assert plan["original_request"] == value
    assert plan["execution_status"] == "NOT_RUN"


def test_animation_and_incompatible_task_routes_keep_explicit_scope():
    from polyforge.workforce.router import plan_task

    plan = plan_task(
        request(
            "ANIMATE",
            capability_id="animation.robot.rig.v1",
            domain_tags=["blender", "unity", "animation"],
        )
    )
    assert len(plan["jobs"]) == 4
    assert plan["stages"] == ["S0", "S1", "S2", "S3", "S4", "S5"]
    for value in [
        request("ANIMATE"),
        request("BUILD_GAME"),
        request(
            "CREATE_ASSET", capability_id="unity.game.arena.v1", input={"schema_version": "1.0.0"}
        ),
    ]:
        with pytest.raises(InputError):
            plan_task(value)
    value = request()
    del value["input"]
    with pytest.raises(InputError):
        plan_task(value)
    with pytest.raises(InputError):
        plan_task(request(brief="   "))


def test_review_evidence_traversal_and_unknown_role_are_denied(tmp_path):
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.workforce.models import validate_review
    from polyforge.workforce.permissions import authorize

    with pytest.raises(InputError):
        authorize(WorkspacePolicy(tmp_path), "invented", "read", "runs/a")
    review = {
        "schema_version": "1.0.0",
        "artifact_id": "candidate",
        "candidate_digest": "a" * 64,
        "producer_id": "producer",
        "reviewer_id": "inspector",
        "verdict": "APPROVED",
        "independence": "DIFFERENT_ROLE_SAME_HOST",
        "evidence": ["../outside"],
    }
    with pytest.raises(InputError):
        validate_review(review)


def test_job_ownership_heartbeat_corruption_and_terminal_states(tmp_path):
    from polyforge.runner.state import atomic_json
    from polyforge.workforce.ledger import JobLedger

    ledger = JobLedger(tmp_path, "task_a")
    with pytest.raises(InputError):
        JobLedger(tmp_path, "../bad")
    with pytest.raises(InputError):
        ledger.claim("job", "asset", ttl=0)
    lease = ledger.claim("job", "asset", ttl=30)
    with pytest.raises(InputError):
        ledger.heartbeat("job", lease, ttl=0)
    ledger.heartbeat("job", lease, ttl=60)
    with pytest.raises(InputError):
        ledger.commit("job", None, {"status": "PASS"})
    with pytest.raises(InputError):
        ledger.commit("job", {**lease, "token": "forged"}, {"status": "PASS"})
    ledger.commit("job", lease, {"status": "PASS"})
    with pytest.raises(InputError):
        ledger.cancel("job")
    state = __import__("json").loads(ledger.policy.path(ledger._state("job")).read_text())
    state["result"] = {"status": "FAIL"}
    atomic_json(ledger.policy, ledger._state("job"), state)
    with pytest.raises(InputError):
        ledger.completed("job")
    lease = ledger.claim("cancelled", "other_asset")
    ledger.cancel("cancelled")
    with pytest.raises(InputError):
        ledger.claim("cancelled", "other_asset")


def test_job_cancellation_reaches_the_owned_capability_process(tmp_path, monkeypatch):
    import threading

    import polyforge.workforce.orchestrator as module
    from polyforge.contracts.results import ErrorKind, failure
    from polyforge.workforce.ledger import JobLedger

    started = threading.Event()
    observed = threading.Event()

    def capability(identifier, inputs, context):
        started.set()
        if context.cancel.wait(5):
            observed.set()
        return failure(ErrorKind.INTERRUPTED, "PF-TEST-CANCEL", "cancelled")

    monkeypatch.setattr(module, "execute", capability)
    ledger = JobLedger(tmp_path, "cancel_task")
    lease = ledger.claim("produce", "crate")
    result = []
    thread = threading.Thread(
        target=lambda: result.append(
            module.execute_leased(ledger, "produce", lease, "mesh.props.crate.v1", {}, 42)
        )
    )
    thread.start()
    assert started.wait(2)
    ledger.cancel("produce")
    thread.join(3)
    assert not thread.is_alive() and observed.is_set()
    assert result[0].exit_code == 9
