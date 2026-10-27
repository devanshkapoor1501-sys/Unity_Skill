"""One public status and exit-code contract; game acceptance stays separate."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import IntEnum
from typing import Any

from polyforge import __version__


class ErrorKind(IntEnum):
    """Normative process exits from blueprint section 7.7."""

    INVALID_INPUT = 2
    MISSING_DEPENDENCY = 3
    POLICY_DENIED = 4
    PRODUCER_FAILURE = 5
    CONTRACT_FAILURE = 6
    TEST_FAILURE = 7
    RETRY_EXHAUSTED = 8
    INTERRUPTED = 9


STATUSES = frozenset({"PASS", "FAIL", "BLOCKED", "NOT_RUN", "REVIEW"})
GAME_STATUSES = frozenset({"ACCEPTED", "PARTIAL", "REJECTED"})


@dataclass(frozen=True)
class Result:
    """JSON-safe operation outcome, never inferred from application logs."""

    status: str = "PASS"
    exit_code: int = 0
    error_code: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    diagnostics: list[dict[str, Any]] = field(default_factory=list)
    operation_id: str | None = None
    run_id: str | None = None
    version: str = __version__
    contract_version: str = "1.0.0"
    input_digest: str | None = None
    artifact_ids: list[str] = field(default_factory=list)
    evidence_paths: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    duration_ms: float = 0
    rollback_id: str | None = None
    evaluated_test_status: str = "NOT_RUN"
    game_status: str = "PARTIAL"

    def __post_init__(self) -> None:
        if self.status not in STATUSES or self.evaluated_test_status not in STATUSES:
            raise ValueError("Unknown public status")
        if self.game_status not in GAME_STATUSES:
            raise ValueError("Unknown game acceptance state")
        if self.exit_code not in {0, *ErrorKind}:
            raise ValueError("Unknown process exit code")
        if (self.status == "PASS") != (self.exit_code == 0):
            raise ValueError("Only a successful operation may exit zero")
        if self.status == "BLOCKED" and self.exit_code not in {3, 4}:
            raise ValueError("BLOCKED requires missing dependency or policy denial")
        if self.status == "REVIEW" and self.exit_code != 4:
            raise ValueError("REVIEW requires policy denial")

    def to_dict(self) -> dict[str, Any]:
        """Return the stable wire envelope, separating execution and test state."""
        return {**asdict(self), "operation_status": self.status}


def failure(kind: ErrorKind, error_code: str, message: str, *, status: str | None = None) -> Result:
    """Translate typed errors through the one normative exit/status mapping."""
    if status is None:
        status = (
            "BLOCKED" if kind in {ErrorKind.MISSING_DEPENDENCY, ErrorKind.POLICY_DENIED} else "FAIL"
        )
    return Result(
        status=status,
        exit_code=int(kind),
        error_code=error_code,
        diagnostics=[{"code": error_code, "message": message}],
    )
