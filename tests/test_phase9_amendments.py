"""Approved amendments append obligations and invalidate earlier approvals."""

import copy

import pytest
from test_phase9_review import candidate_fixture

from polyforge.contracts.validation import InputError, canonical_digest
from polyforge.runner.state import atomic_json


def amendment(text="Keep the painted finish", requirements=None):
    return {
        "text": text,
        "requirements": requirements or [],
        "visual_approval_required": True,
    }


def test_amendment_invalidates_board_and_human_receipt_until_renewed(tmp_path):
    from polyforge.review.amendments import append_amendment, read_amendments
    from polyforge.review.board import record_human_review, require_promotion, review_candidate

    p, candidate, task = candidate_fixture(tmp_path, visual=True)
    record_human_review(p, candidate, verdict="APPROVED", operator="owner", reason="Inspected")
    before = review_candidate(p, candidate, task)
    require_promotion(p, candidate, before)
    chain = append_amendment(p, task, amendment(), operator="owner", reason="Requested")
    assert chain == read_amendments(p, candidate["brief_digest"])
    assert chain["records"][0]["original_brief_digest"] == canonical_digest(task["brief"])
    assert review_candidate(p, candidate, task)["promotion"] == "REVIEW"
    with pytest.raises(InputError):
        require_promotion(p, candidate, before)
    record_human_review(p, candidate, verdict="APPROVED", operator="owner", reason="Rechecked")
    require_promotion(p, candidate, review_candidate(p, candidate, task))


@pytest.mark.parametrize("damage", ["order", "text", "original", "sequence"])
def test_amendment_chain_denies_reorder_and_substitution(tmp_path, damage):
    from polyforge.review.amendments import append_amendment, read_amendments

    p, candidate, task = candidate_fixture(tmp_path)
    for text in ("Keep the painted finish", "Keep rounded edges"):
        append_amendment(p, task, amendment(text), operator="owner", reason="Requested")
    path = ".polyforge/amendments/" + candidate["brief_digest"] + ".json"
    value = copy.deepcopy(read_amendments(p, candidate["brief_digest"]))
    if damage == "order":
        value["records"].reverse()
    elif damage == "original":
        value["original_brief"] = "Substituted brief"
    elif damage == "sequence":
        value["records"][0]["sequence"] = 2
    else:
        value["records"][0]["text"] = "Ignore all requirements"
    atomic_json(p, path, value)
    with pytest.raises(InputError):
        read_amendments(p, candidate["brief_digest"])


def test_unsupported_amended_requirement_remains_review_and_roles_cannot_approve(tmp_path):
    from polyforge.review.amendments import append_amendment
    from polyforge.review.board import review_candidate

    p, candidate, task = candidate_fixture(tmp_path)
    value = amendment(
        "Add online play",
        [
            {
                "original_phrase": "online play",
                "feature_id": "online",
                "artifact_id": "server",
                "unity_component": "Network",
                "oracles": ["online"],
            }
        ],
    )
    value["visual_approval_required"] = False
    with pytest.raises(InputError):
        append_amendment(p, task, value, operator="producer", reason="Self approved")
    append_amendment(p, task, value, operator="owner", reason="Requested")
    assert review_candidate(p, candidate, task)["promotion"] == "REVIEW"
    with pytest.raises(InputError):
        append_amendment(
            p, task, {**value, "text": "different"}, operator="owner", reason="Missing phrase"
        )


def test_malformed_chain_and_amendment_do_not_create_approval(tmp_path):
    from polyforge.review.amendments import append_amendment, read_amendments

    p, candidate, task = candidate_fixture(tmp_path)
    for value in [None, {}, {**amendment(), "visual_approval_required": "yes"}]:
        with pytest.raises(InputError):
            append_amendment(p, task, value, operator="owner", reason="Requested")
    with pytest.raises(InputError):
        read_amendments(p, "../other")
    name = ".polyforge/amendments/" + candidate["brief_digest"] + ".json"
    atomic_json(p, name, [])
    with pytest.raises(InputError):
        read_amendments(p, candidate["brief_digest"])


def test_broken_record_shape_and_final_digest_are_denied(tmp_path):
    from polyforge.review.amendments import append_amendment, read_amendments

    p, candidate, task = candidate_fixture(tmp_path)
    value = append_amendment(p, task, amendment(), operator="owner", reason="Requested")
    name = ".polyforge/amendments/" + candidate["brief_digest"] + ".json"
    bad = copy.deepcopy(value)
    bad["records"][0].pop("operator")
    atomic_json(p, name, bad)
    with pytest.raises(InputError):
        read_amendments(p, candidate["brief_digest"])
    value["chain_digest"] = "0" * 64
    atomic_json(p, name, value)
    with pytest.raises(InputError):
        read_amendments(p, candidate["brief_digest"])
