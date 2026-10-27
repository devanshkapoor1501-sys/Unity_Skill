"""Strict JSON loading and bundled, non-networked JSON Schema validation."""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from polyforge.contracts.results import ErrorKind


class InputError(ValueError):
    """Recoverable invalid input with a stable machine-readable category."""

    def __init__(
        self,
        message: str,
        *,
        kind: ErrorKind = ErrorKind.INVALID_INPUT,
        code: str = "PF-INPUT-CONTRACT",
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.code = code


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise InputError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise InputError(f"Non-finite JSON number: {value}")


def load_json(path: Path, *, max_bytes: int = 1_048_576) -> Any:
    """Read a bounded UTF-8 JSON document; reject duplicate fields and NaN."""
    if type(max_bytes) is not int or not 1 <= max_bytes <= 33_554_432:
        raise InputError("Invalid bounded JSON read budget")
    try:
        with path.open("rb") as stream:
            content = stream.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise InputError(f"Input exceeds the {max_bytes}-byte JSON limit")
        return json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (OSError, ValueError, RecursionError) as exc:
        raise InputError(f"Cannot read JSON input: {exc}") from exc


def canonical_digest(value: Any) -> str:
    """Hash semantic JSON, independent of indentation and object-key ordering."""
    try:
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise InputError(f"Input is not finite JSON: {exc}") from exc
    return hashlib.sha256(encoded).hexdigest()


def schema_document(name: str) -> dict[str, Any]:
    """Read a known packaged schema; never resolve user-provided URLs."""
    allowed = {
        "capability.schema.json",
        "result.schema.json",
        "benchmark_task.schema.json",
        "game_manifest.schema.json",
        "recipe.schema.json",
        "recipe_request.schema.json",
        "audit_request.schema.json",
        "scenario.schema.json",
    }
    if name not in allowed:
        raise InputError(f"Unknown bundled schema: {name}")
    value: dict[str, Any] = json.loads(
        files("polyforge.contracts").joinpath(name).read_text("utf-8")
    )
    return value


def validate_schema(value: Any, name: str) -> None:
    """Validate at the input boundary with actionable JSON field locations."""
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise InputError(
            "Install PolyForge's jsonschema dependency before validation",
            kind=ErrorKind.MISSING_DEPENDENCY,
            code="PF-DEPENDENCY-VALIDATOR",
        ) from exc
    canonical_digest(value)
    errors = sorted(
        Draft202012Validator(schema_document(name)).iter_errors(value),
        key=lambda error: str(list(error.absolute_path)),
    )
    if errors:
        error = errors[0]
        location = "$" + "".join(f"[{part}]" for part in error.absolute_path)
        raise InputError(f"{location}: {error.message}")
