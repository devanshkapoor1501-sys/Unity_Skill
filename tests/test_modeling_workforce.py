"""Specialist routing and sealed independent modeling review contracts."""

import copy
import hashlib
import json

import pytest

from polyforge.blender.modeling import MODELING_CAPABILITIES, compile_modeling
from polyforge.contracts.results import Result
from polyforge.contracts.validation import InputError, canonical_digest
from polyforge.security.paths import WorkspacePolicy

SPECIALISTS = {
    "room_kit": "modeler_architecture",
    "vehicle": "modeler_hard_surface",
    "mechanical_prop": "modeler_hard_surface",
    "organic": "modeler_organic_retopo",
    "compose": "modeler_procedural",
}


def modeling_task(kind="compose"):
    inputs = {"schema_version": "1.0.0", "asset_id": "part", "parameters": {"size_m": [2, 2, 2]}}
    if kind == "compose":
        inputs.update(
            objects=[
                {
                    "id": "body",
                    "primitive": "box",
                    "size_m": [2, 2, 2],
                    "location": [0, 1, 0],
                    "rotation_deg": [0, 0, 0],
                    "material_id": "base",
                    "export": True,
                    "modifiers": [],
                }
            ],
            sockets=[{"id": "top", "position": [0, 2, 0]}],
            expected_bounds=True,
            overlap_policy="DISALLOW",
        )
    return {
        "schema_version": "1.0.0",
        "brief": "Preserve the requested editable modeling source.",
        "task_class": "CREATE_ASSET",
        "domain_tags": ["blender"],
        "feature_ids": ["editable_source"],
        "capability_id": MODELING_CAPABILITIES[kind],
        "input": inputs,
        "seed": 42,
    }


@pytest.mark.parametrize("kind", list(SPECIALISTS))
def test_modeling_routes_to_only_the_required_specialist_and_independent_inspector(kind):
    from polyforge.workforce.router import plan_task

    task = modeling_task(kind)
    before = copy.deepcopy(task)
    plan = plan_task(task)
    assert task == before and plan["original_request"] == task
    assert [j["role_id"] for j in plan["jobs"]] == [
        "asset_architect",
        SPECIALISTS[kind],
        "asset_inspector",
    ]
    assert plan["stages"] == ["S0", "S1", "S2", "S3"]
    assert plan["jobs"][1]["context"]["tool_allowlist"]
    assert task["capability_id"] in plan["jobs"][1]["context"]["tool_allowlist"]
    assert plan["jobs"][2]["context"]["tool_allowlist"] == ["artifact.candidate.inspect.v1"]
    assert all("unity" not in j["capability_id"] for j in plan["jobs"])


@pytest.mark.parametrize("kind", list(SPECIALISTS))
def test_specialists_have_only_relevant_production_tools_and_managed_write_scope(tmp_path, kind):
    from polyforge.workforce.permissions import authorize

    policy = WorkspacePolicy(tmp_path)
    role = SPECIALISTS[kind]
    assert authorize(policy, role, "tool", MODELING_CAPABILITIES[kind])
    assert authorize(policy, role, "write", "runs/owned/source.blend")
    for target in ["artifact.candidate.inspect.v1", "unity.game.arena.v1", "mesh.props.crate.v1"]:
        with pytest.raises(InputError):
            authorize(policy, role, "tool", target)
    for target in ["UnityProject/Assets/model.fbx", "workforce/approval.json"]:
        with pytest.raises(InputError):
            authorize(policy, role, "write", target)
    for capability in MODELING_CAPABILITIES.values():
        with pytest.raises(InputError):
            authorize(policy, "asset_inspector", "tool", capability)


def sealed_model(tmp_path):
    from test_modeling_inspection import fixture

    from polyforge.workforce.workers import seal_candidate

    task = modeling_task()
    plan = compile_modeling("compose", task["input"], seed=task["seed"])
    _, report = fixture()
    source = b"editable test source bytes"
    source_digest = hashlib.sha256(source).hexdigest()
    report.update(
        input_digest=plan["input_digest"],
        materials=plan["materials"],
        source_sha256_before=source_digest,
        source_sha256_after=source_digest,
    )
    provenance = {
        "schema_version": "1.0.0",
        "asset_id": "part",
        "input_digest": plan["input_digest"],
        "tool_version": "5.2.2",
        "editable_source": "source.blend",
        "source_sha256": source_digest,
        "export_policy": "EVALUATED_COPIES_SOURCE_MODIFIERS_PRESERVED",
        "coordinate_basis": {"up": "Z", "forward": "-Y", "meters_per_unit": 1},
        "artistic_status": "REVIEW",
    }
    prefix = "runs/model-test/asset/"
    values = {
        "source.blend": source,
        "asset.fbx": b"main export",
        "lod.fbx": b"lod export",
        "inspection.json": json.dumps(report).encode(),
        "provenance.json": json.dumps(provenance).encode(),
    }
    records = []
    for name, data in values.items():
        path = tmp_path / (prefix + name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        records.append({"relative_path": prefix + name, "sha256": hashlib.sha256(data).hexdigest()})
    registry = tmp_path / "runs/model-test/artifacts.json"
    registry.write_text(json.dumps({"artifacts": records}))
    policy = WorkspacePolicy(tmp_path)
    candidate = seal_candidate(policy, Result(run_id="model-test"), canonical_digest(task["brief"]))
    return policy, task, candidate, plan


def reseal(policy, candidate):
    for item in candidate["files"]:
        item["sha256"] = hashlib.sha256(policy.path(item["path"]).read_bytes()).hexdigest()
    candidate["candidate_digest"] = canonical_digest(
        {k: v for k, v in candidate.items() if k != "candidate_digest"}
    )


def test_modeling_inspection_revalidates_native_measurements_against_exact_compiled_request(
    tmp_path,
):
    from polyforge.workforce.workers import inspect_candidate

    policy, task, candidate, _ = sealed_model(tmp_path)
    before = {f["path"]: policy.path(f["path"]).read_bytes() for f in candidate["files"]}
    review = inspect_candidate(policy, candidate, task, technical_only=True)
    assert review["verdict"] == "APPROVED" and review["reviewer_id"] != candidate["producer_id"]
    assert review["request"] == task and review["candidate_digest"] == candidate["candidate_digest"]
    assert {f["path"]: policy.path(f["path"]).read_bytes() for f in candidate["files"]} == before


def test_modeling_review_holds_promotion_for_artistic_approval(tmp_path):
    from polyforge.review.board import require_promotion, review_candidate

    policy, task, candidate, _ = sealed_model(tmp_path)
    review = review_candidate(policy, candidate, task)
    assert review["technical"] == "APPROVED"
    assert review["subjective"] == review["promotion"] == "REVIEW"
    with pytest.raises(InputError, match="required approval"):
        require_promotion(policy, candidate, review)


@pytest.mark.parametrize(
    "name", ["source.blend", "asset.fbx", "lod.fbx", "inspection.json", "provenance.json"]
)
def test_modeling_inspection_requires_each_source_export_and_evidence_to_be_sealed(tmp_path, name):
    from polyforge.workforce.workers import inspect_candidate

    policy, task, candidate, _ = sealed_model(tmp_path)
    candidate["files"] = [f for f in candidate["files"] if not f["path"].endswith("/" + name)]
    reseal(policy, candidate)
    with pytest.raises(InputError):
        inspect_candidate(policy, candidate, task, technical_only=True)


@pytest.mark.parametrize(
    "name,key,value",
    [
        ("inspection.json", "source_sha256_before", "a" * 64),
        ("inspection.json", "source_sha256_after", "a" * 64),
        ("inspection.json", "input_digest", "a" * 64),
        ("inspection.json", "technical_status", "FAIL"),
        ("provenance.json", "source_sha256", "a" * 64),
        ("provenance.json", "input_digest", "a" * 64),
        ("provenance.json", "asset_id", "other"),
        ("provenance.json", "tool_version", "5.3.0"),
        ("provenance.json", "export_policy", "SOURCE_MODIFIERS_APPLIED"),
    ],
)
def test_valid_seal_cannot_hide_forged_source_or_provenance_bindings(tmp_path, name, key, value):
    from polyforge.workforce.workers import inspect_candidate

    policy, task, candidate, _ = sealed_model(tmp_path)
    path = policy.path("runs/model-test/asset/" + name)
    data = json.loads(path.read_text())
    data[key] = value
    path.write_text(json.dumps(data))
    reseal(policy, candidate)
    with pytest.raises(InputError):
        inspect_candidate(policy, candidate, task, technical_only=True)


def test_request_semantics_and_seed_cannot_change_after_modeling_production(tmp_path):
    from polyforge.workforce.workers import inspect_candidate

    policy, task, candidate, _ = sealed_model(tmp_path)
    for field, value in [
        ("seed", 43),
        ("input", {**task["input"], "parameters": {"size_m": [3, 3, 3]}}),
    ]:
        changed = {**task, field: value}
        with pytest.raises(InputError):
            inspect_candidate(policy, candidate, changed, technical_only=True)


def test_read_time_candidate_change_during_independent_validation_is_detected(
    tmp_path, monkeypatch
):
    import polyforge.blender.modeling_inspection as validator
    from polyforge.workforce.workers import inspect_candidate

    policy, task, candidate, _ = sealed_model(tmp_path)
    validate = validator.validate_modeling_report

    def changing_validate(plan, report):
        validate(plan, report)
        policy.path("runs/model-test/asset/source.blend").write_bytes(b"changed during review")

    monkeypatch.setattr(validator, "validate_modeling_report", changing_validate)
    with pytest.raises(InputError):
        inspect_candidate(policy, candidate, task, technical_only=True)
