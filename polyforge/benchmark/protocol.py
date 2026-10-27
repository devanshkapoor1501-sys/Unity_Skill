"""Interface boundaries for future baseline runners and independent evaluators."""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from polyforge.contracts.results import ErrorKind, Result, failure


@dataclass(frozen=True)
class EvaluationRequest:
    """References public brief identity and produced artifacts, never hidden answers."""

    task_id: str
    original_brief_sha256: str
    artifact_root: Path
    task_type: str


class BaselineRunner(Protocol):
    """A/B/C/D implementations must preserve the same declared execution budgets."""

    def run(self, task: EvaluationRequest, *, arm: str, seed: int) -> Result: ...


class AcceptanceEvaluator(Protocol):
    """Evaluate observed evidence in a separately owned environment."""

    def grade(self, request: EvaluationRequest) -> Result: ...


class UnavailableEvaluator:
    """Fail closed until an external evaluator supplies protected qualification."""

    def grade(self, request: EvaluationRequest) -> Result:
        return failure(
            ErrorKind.MISSING_DEPENDENCY,
            "PF-EVALUATOR-UNAVAILABLE",
            f"Independent evaluator unavailable for task {request.task_id}",
        )
