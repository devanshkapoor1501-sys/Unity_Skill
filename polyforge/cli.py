"""Portable CLI driven by a single authoritative command registry."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any, Never

from polyforge import __version__
from polyforge.capabilities.protocol import RunContext
from polyforge.capabilities.registry import RegistryValidator, catalog, lookup
from polyforge.commands import COMMANDS, CommandSpec
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, load_json
from polyforge.security.paths import workspace_input


class Parser(argparse.ArgumentParser):
    """Keep parser failures inside the same JSON/exit contract as execution errors."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs["allow_abbrev"] = False
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> Never:
        raise InputError(message, code="PF-INPUT-CLI")


def build_parser() -> argparse.ArgumentParser:
    """Build help and accepted syntax directly from the public command contract."""
    root = Parser(prog="polyforge", description="Local Blender-to-Unity capability engine")
    root.add_argument("--version", action="version", version=f"polyforge {__version__}")
    groups: dict[tuple[str, ...], Any] = {(): root.add_subparsers(required=True)}
    for spec in COMMANDS:
        prefix: tuple[str, ...] = ()
        for name in spec.path[:-1]:
            next_prefix = (*prefix, name)
            if next_prefix not in groups:
                parent = groups[prefix].add_parser(name, help=f"{name} operations")
                groups[next_prefix] = parent.add_subparsers(required=True)
            prefix = next_prefix
        availability = "" if spec.implemented else f" [NOT IMPLEMENTED; Phase {spec.phase}]"
        parser = groups[prefix].add_parser(
            spec.path[-1], help=spec.help + availability, description=spec.help + availability
        )
        for flags, kwargs in spec.options:
            parser.add_argument(*flags, **kwargs)
        parser.add_argument("--json", action="store_true", help="Emit the versioned JSON result")
        formats = (
            ["human", "json", "html"] if spec.path == ("benchmark", "report") else ["human", "json"]
        )
        parser.add_argument("--format", choices=formats, default="human")
        parser.set_defaults(spec=spec)
    return root


def dispatch(args: argparse.Namespace) -> Result:
    """Dispatch only implemented capabilities; placeholders never claim tool success."""
    spec: CommandSpec = args.spec
    if not spec.implemented:
        return failure(
            ErrorKind.PRODUCER_FAILURE,
            "PF-CAPABILITY-NOT-IMPLEMENTED",
            f"{' '.join(spec.path)} is planned for Phase {spec.phase}; no work was run",
            status="NOT_RUN",
        )
    if spec.path == ("capability", "list"):
        return Result(data={"capabilities": catalog()})
    if spec.path == ("capability", "show"):
        return Result(data={"capability": lookup(args.id)})
    lookup(args.id)
    path = workspace_input(Path(args.workspace), Path(args.input))
    inputs = load_json(path)
    context = RunContext(workspace=Path(args.workspace), dry_run=args.dry_run)
    return RegistryValidator().execute(inputs, context)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with structured, nonzero failures and no implicit model access."""
    values = list(sys.argv[1:] if argv is None else argv)
    json_output = (
        "--json" in values
        or "--format=json" in values
        or any(values[i : i + 2] == ["--format", "json"] for i in range(len(values)))
    )
    started = time.monotonic()
    try:
        args = build_parser().parse_args(values)
        json_output = args.json or args.format == "json"
        result = dispatch(args)
    except InputError as exc:
        result = failure(exc.kind, exc.code, str(exc))
    except KeyboardInterrupt:
        result = failure(ErrorKind.INTERRUPTED, "PF-RUN-INTERRUPTED", "Operation interrupted")
    result = replace(result, duration_ms=round((time.monotonic() - started) * 1000, 3))
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=True, allow_nan=False))
    else:
        print(f"{result.status}: operation; game={result.game_status}")
        for diagnostic in result.diagnostics:
            print(f"{diagnostic['code']}: {diagnostic['message']}")
        if result.data:
            print(json.dumps(result.data, indent=2, ensure_ascii=True, allow_nan=False))
    return result.exit_code
