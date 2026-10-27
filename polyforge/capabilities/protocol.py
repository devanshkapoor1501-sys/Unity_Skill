"""Shared typed capability interface, independent of models and host tools."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from polyforge.contracts.results import ErrorKind, Result
from polyforge.contracts.validation import InputError


@dataclass(frozen=True)
class RunContext:
    """Authorized execution context. Untrusted execution requires verified OS isolation."""

    workspace: Path
    seed: int = 42
    dry_run: bool = False
    timeout_seconds: int = 600
    max_output_bytes: int = 10_485_760
    retry_limit: int = 2
    transaction_id: str | None = None
    operation_id: str | None = None
    run_id: str | None = None
    allow_network: bool = False
    security_scope: str = "TRUSTED_LOCAL"
    isolation_verified: bool = False
    artifact_registry: dict[str, Any] = field(default_factory=dict)
    lock_path: Path | None = None
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("polyforge"))

    def __post_init__(self) -> None:
        if self.security_scope != "TRUSTED_LOCAL" or self.isolation_verified:
            raise InputError(
                "OS-enforced isolation is not implemented; untrusted execution denied",
                kind=ErrorKind.POLICY_DENIED,
                code="PF-POLICY-ISOLATION",
            )
        if self.allow_network:
            raise InputError(
                "Core capabilities do not permit network access",
                kind=ErrorKind.POLICY_DENIED,
                code="PF-POLICY-NETWORK",
            )
        if self.timeout_seconds <= 0 or self.max_output_bytes <= 0 or self.retry_limit < 0:
            raise InputError("Execution budgets must be positive; retries must be nonnegative")


@runtime_checkable
class Capability(Protocol):
    """Every concrete capability validates typed inputs and returns structured evidence."""

    def execute(self, inputs: dict[str, Any], context: RunContext) -> Result:
        """Execute a bounded operation, or describe it without side effects."""
        ...
