"""Versioned task, candidate and review boundaries."""

from typing import Any

from polyforge.contracts.validation import InputError, canonical_digest, validate_schema


def validate_review(review: dict[str, Any]) -> None:
    validate_schema(review, "review_verdict.schema.json")
    if review["producer_id"] == review["reviewer_id"]:
        raise InputError("A producer cannot approve its own candidate")
    if any(".." in p.replace("\\", "/").split("/") for p in review["evidence"]):
        raise InputError("Review evidence cannot escape its workspace")


def validate_task(value: dict[str, Any]) -> str:
    validate_schema(value, "workforce_task.schema.json")
    if not value["brief"].strip():
        raise InputError("Task brief cannot be blank")
    return canonical_digest(value)
