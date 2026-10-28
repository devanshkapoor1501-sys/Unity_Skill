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
from polyforge.capabilities.registry import ManifestCapability, RegistryValidator, catalog, lookup
from polyforge.commands import COMMANDS, CommandSpec
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, load_json
from polyforge.security.paths import workspace_input
from polyforge.security.policy import redact


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
    if spec.path == ("build",):
        from polyforge.blender.build import build_assets

        return build_assets(
            Path(args.workspace),
            through=args.through,
            only=args.only,
            dry_run=args.dry_run,
            allow_package_downloads=args.allow_package_downloads,
            standalone=args.standalone,
        )
    if spec.path == ("audit",):
        from polyforge.blender.audit import audit_asset

        return audit_asset(Path(args.workspace), args.asset, dry_run=args.dry_run)
    if spec.path in {("verify",), ("scenario", "run")}:
        from polyforge.unity.game import verify_game

        if spec.path == ("scenario", "run") and args.suite != "core_gameplay":
            raise InputError("Phase6 executes the bounded core_gameplay declarative suite")
        return verify_game(Path(args.workspace))
    if spec.path in {("reconcile",), ("diagnose",), ("repair", "plan"), ("repair", "apply")}:
        from polyforge.unity.repairs import diagnose, reconcile_workspace, repair_apply, repair_plan

        workspace = Path(args.workspace)
        if spec.path == ("reconcile",):
            return reconcile_workspace(workspace)
        if spec.path == ("diagnose",):
            return diagnose(workspace, args.evidence_dir)
        if spec.path == ("repair", "plan"):
            return repair_plan(workspace, args.issue)
        return repair_apply(workspace, args.plan)
    if spec.path in {("validate",), ("plan",), ("compile-contract",)}:
        from polyforge.compiler.commands import manifest_command

        path = (
            Path(args.manifest)
            if spec.path == ("compile-contract",)
            else Path(args.workspace) / "game_manifest.json"
        )
        return manifest_command(path, spec.path[0], dry_run=getattr(args, "dry_run", False))
    if spec.path == ("doctor",):
        from polyforge.doctor import doctor

        return doctor(
            Path(args.workspace),
            config_path=Path(args.config) if args.config else None,
            project=Path(args.project) if args.project else None,
            dry_run=args.dry_run,
        )
    if spec.path == ("init",):
        from polyforge.workspace import init_workspace

        return init_workspace(Path(args.path), args.template, dry_run=args.dry_run)
    if spec.path == ("status",):
        from polyforge.workspace import status_workspace

        return status_workspace(Path(args.workspace))
    if spec.path == ("report",):
        from polyforge.workspace import report_run

        return report_run(Path(args.workspace), args.run_id)
    lookup(args.id)
    path = workspace_input(Path(args.workspace), Path(args.input))
    inputs = load_json(path)
    context = RunContext(workspace=Path(args.workspace), dry_run=args.dry_run)
    if args.id == "unity.game.arena.v1":
        from polyforge.blender.build import build_assets
        from polyforge.contracts.validation import validate_schema

        validate_schema(inputs, "game_build.schema.json")
        return build_assets(
            context.workspace,
            through="S5",
            dry_run=context.dry_run,
            allow_package_downloads=inputs.get("allow_package_downloads", False),
            standalone=inputs.get("standalone", False),
        )
    if args.id == "unity.scene.static.v1":
        from polyforge.blender.build import build_assets
        from polyforge.contracts.validation import validate_schema

        validate_schema(inputs, "unity_build.schema.json")
        return build_assets(
            context.workspace,
            through="S4",
            dry_run=context.dry_run,
            allow_package_downloads=inputs.get("allow_package_downloads", False),
        )
    if args.id == "audit.static.multiview.v1":
        from polyforge.blender.audit import audit_asset
        from polyforge.contracts.validation import validate_schema

        validate_schema(inputs, "audit_request.schema.json")
        return audit_asset(context.workspace, inputs["asset_id"], dry_run=context.dry_run)
    if args.id == "contract.capability.validate.v1":
        return RegistryValidator().execute(inputs, context)
    from polyforge.blender.adapter import BlenderCapability
    from polyforge.blender.recipes import RECIPES

    if args.id in RECIPES.values():
        kind = next(key for key, value in RECIPES.items() if value == args.id)
        return BlenderCapability(kind).execute(inputs, context)
    operation = {
        "contract.manifest.validate.v1": "validate",
        "contract.scene.compile.v1": "compile",
        "plan.scene.v1": "plan",
    }[args.id]
    return ManifestCapability(operation).execute(inputs, context)


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
        result = failure(exc.kind, exc.code, redact(str(exc)))
    except OSError as exc:
        result = failure(ErrorKind.PRODUCER_FAILURE, "PF-IO-FAILURE", redact(str(exc)))
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
