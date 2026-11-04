"""Offline, escaped reports over preserved benchmark ledgers."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import Any

from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.security.paths import WorkspacePolicy

from .metrics import summarize, validate_record

_IDENTITY_FIELDS = (
    "schema_version",
    "run_id",
    "attempt_id",
    "arm",
    "task_id",
    "task_type",
    "original_brief_sha256",
    "rubric_sha256",
    "task_success_schema",
    "suite_digest",
    "configuration_digest",
    "execution_metadata",
    "budgets",
    "seed",
    "comparison_status",
    "genre",
    "platform",
    "complexity",
    "executed",
    "eligible",
)


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, child in pairs:
        if key in value:
            raise InputError("Duplicate benchmark JSON field")
        value[key] = child
    return value


def _constant(value: str) -> None:
    raise InputError(f"Non-finite benchmark JSON number: {value}")


def _read(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any] | None, bool]:
    root = path if path.is_dir() else path.absolute().parent
    policy = WorkspacePolicy(root)
    ledger = policy.path("ledger.jsonl" if path.is_dir() or path.name == "run.json" else path.name)
    with ledger.open("rb") as stream:
        raw = stream.read(33554433)
    if len(raw) > 33554432:
        raise InputError("Benchmark ledger exceeds its 32 MiB report limit")
    manifest_path = policy.path("run.json")
    manifest = load_json(manifest_path) if manifest_path.is_file() else None
    committed_bytes = len(raw)
    recovered = False
    if manifest is not None:
        if not isinstance(manifest, dict):
            raise InputError("Invalid benchmark manifest")
        digest = canonical_digest(
            {key: value for key, value in manifest.items() if key != "manifest_digest"}
        )
        if manifest.get("manifest_digest") != digest:
            raise InputError("Benchmark manifest metadata digest mismatch")
        if hashlib.sha256(raw).hexdigest() != manifest.get("ledger_sha256"):
            checkpoint_bytes = manifest.get("ledger_bytes")
            if (
                type(checkpoint_bytes) is not int
                or not 0 <= checkpoint_bytes < len(raw)
                or (checkpoint_bytes and raw[checkpoint_bytes - 1 : checkpoint_bytes] != b"\n")
                or hashlib.sha256(raw[:checkpoint_bytes]).hexdigest()
                != manifest.get("ledger_sha256")
                or len(raw[checkpoint_bytes:].splitlines()) != 1
                or not raw.endswith(b"\n")
            ):
                raise InputError("Benchmark ledger hash mismatch")
            committed_bytes = checkpoint_bytes
            # A suffix is unauthenticated and cannot be distinguished from an append attack.
            # Retain only censored execution evidence and force a non-passing report.
            recovered = True
    rows: dict[str, dict[str, Any]] = {}
    lines = raw.splitlines(keepends=True)
    if len(lines) > 51200:
        raise InputError("Benchmark ledger exceeds its bounded event count")
    offset = 0
    for index, encoded_line in enumerate(lines):
        committed = offset < committed_bytes
        offset += len(encoded_line)
        line = encoded_line.rstrip(b"\r\n")
        if not line or len(line) > 1048576:
            raise InputError("Empty or oversized benchmark ledger event")
        value = json.loads(line.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
        validate_record(value)
        payload = {key: child for key, child in value.items() if key != "row_digest"}
        if "row_digest" in value and value["row_digest"] != canonical_digest(payload):
            raise InputError("Benchmark event metadata digest mismatch")
        if manifest is not None:
            if "row_digest" not in value:
                raise InputError("Recorded benchmark event lacks its metadata digest")
            if (
                value.get("configuration_digest") != manifest.get("configuration_digest")
                or value.get("run_id") != manifest.get("run_id")
                or value.get("arm") != manifest.get("arm")
            ):
                raise InputError("Benchmark event and manifest identity mismatch")
        key = value.get("attempt_id", "import_" + str(index))
        if not isinstance(key, str) or not key or len(key) > 256:
            raise InputError("Invalid benchmark attempt identity")
        event = value.get("event")
        if (
            event is not None
            and (not isinstance(event, str) or event not in {"STARTED", "FINISHED"})
        ) or (manifest and event is None):
            raise InputError("Unknown benchmark attempt event")
        previous = rows.get(key)
        if previous is not None:
            if previous.get("event") != "STARTED" or event != "FINISHED":
                raise InputError("Invalid or duplicate benchmark attempt transition")
            if any(previous.get(field) != value.get(field) for field in _IDENTITY_FIELDS):
                raise InputError("Benchmark attempt identity changed after STARTED")
        elif event == "FINISHED" and value["executed"]:
            raise InputError("Executed benchmark completion lacks its STARTED event")
        if event == "STARTED" and (
            not value["executed"]
            or not value["eligible"]
            or not value["censored"]
            or value["status"] != "NOT_RUN"
            or value["evaluation_status"] != "NOT_RUN"
            or value["task_success"]
            or value["game_status"] == "ACCEPTED"
        ):
            raise InputError("Invalid benchmark STARTED observation")
        if not committed and event == "FINISHED":
            if previous is None:
                raise InputError("Uncommitted completion lacks censored execution evidence")
            continue  # The committed STARTED event remains the only credited observation.
        rows[key] = value
    return list(rows.values()), manifest, recovered


def report_run(path: Path) -> Result:
    """Return JSON, human text and HTML as data; never write report outputs."""
    try:
        records, manifest, recovered = _read(path)
        summary = summarize(records)
        comparison = (
            manifest.get("comparison_status", "NON_ATTRIBUTABLE")
            if manifest
            else ("NON_ATTRIBUTABLE")
        )
        games = summary["accepted_game_rate"]
        human = [
            "Public development benchmark (exploratory)",
            f"Comparison: {comparison}; independent release qualification: BLOCKED",
            "Identity assurance: declared metadata; "
            "no provider or independent-ownership authentication",
            "Declared acceptance observations; "
            "evaluator identities and grades are not authenticated",
            f"Complete games: {games['numerator']}/{games['denominator']} ({games['status']})",
            "Cost: unknown observations are retained; no zero-cost assumption",
            "Elapsed attempt medians include failed/censored observations; "
            "accepted-only medians separate",
            "Superiority claim: UNSUPPORTED",
            "Required external holdouts and worker ablations: NOT_RUN unless separately evidenced",
        ]
        if recovered:
            human.append(
                "Uncommitted ledger suffix: REVIEW required; pending attempts stay censored"
            )
        for configuration in summary["by_configuration"]:
            human.append(
                f"Arm {configuration['arm']} configuration {configuration['configuration_digest']}"
            )
            for task_type, metric in configuration["by_task_type"].items():
                human.append(
                    f"  {task_type}: {metric['numerator']}/{metric['denominator']}; "
                    f"attempt median seconds={metric['median_attempt_seconds']}; "
                    f"accepted median seconds={metric['median_accepted_seconds']}; "
                    f"unknown cost={metric['unknown_cost_count']}; "
                    f"censored={metric['censored_count']}"
                )
        for row in records:
            human.append(
                f"{row['arm']} {row['task_id']}: {row['status']}; "
                f"evaluation={row['evaluation_status']}; executed={row['executed']}"
            )
        text = "\n".join(human) + "\n"
        rendered = (
            '<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            "<title>Public benchmark report</title><body><h1>Public benchmark report</h1><pre>"
            + html.escape(text, quote=True)
            + "</pre><details><summary>Complete observations</summary><pre>"
            + html.escape(
                json.dumps(
                    {"summary": summary, "records": records},
                    indent=2,
                    ensure_ascii=True,
                    allow_nan=False,
                ),
                quote=True,
            )
            + "</pre></details></body></html>"
        )
        return Result(
            status="REVIEW" if recovered else "PASS",
            exit_code=int(ErrorKind.POLICY_DENIED) if recovered else 0,
            error_code="PF-BENCHMARK-UNCOMMITTED-SUFFIX" if recovered else None,
            data={
                "summary": summary,
                "records": records,
                "comparison_status": comparison,
                "qualification_status": "BLOCKED",
                "acceptance_assurance": "DECLARED_NOT_AUTHENTICATED",
                "report_human": text,
                "report_html": rendered,
                "integrity_status": "UNCOMMITTED_SUFFIX_REVIEW_REQUIRED"
                if recovered
                else (
                    "LOCAL_DIGEST_VERIFIED_NOT_AUTHENTICATED"
                    if manifest
                    else "UNVERIFIED_IMPORTED_OBSERVATIONS"
                ),
            },
        )
    except InputError as exc:
        return failure(exc.kind, exc.code, str(exc))
    except (OSError, ValueError, RecursionError) as exc:
        return failure(ErrorKind.INVALID_INPUT, "PF-BENCHMARK-REPORT", str(exc))
