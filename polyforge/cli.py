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
from polyforge.capabilities.registry import catalog, lookup
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
    if spec.path[0] == "knowledge":
        from polyforge.knowledge.catalog import catalog_cards
        from polyforge.security.paths import WorkspacePolicy

        if spec.path[-1] == "list":
            return Result(
                data={
                    "knowledge_cards": catalog_cards(),
                    "execution_status": "NOT_RUN",
                    "network": "DISABLED",
                }
            )
        if spec.path[-1] == "probe":
            from polyforge.knowledge.probes import probe_tool

            return probe_tool(Path(args.workspace), args.tool, dry_run=args.dry_run)
        if spec.path[-1] == "availability":
            from polyforge.knowledge.availability import availability_snapshot, probe_host

            policy = WorkspacePolicy(Path(args.workspace))
            snapshot = availability_snapshot(policy, args.project)
            if args.host:
                snapshot["hosts"][args.host].update(
                    {"status": "NOT_RUN"} if args.dry_run else probe_host(policy, args.host)
                )
            return Result(data={"availability": snapshot, "dry_run": args.dry_run})
        from polyforge.knowledge.router import route_reference

        policy = WorkspacePolicy(Path(args.workspace))
        route = route_reference(policy, load_json(policy.path(args.request)))
        return Result(
            status=route["status"],
            exit_code=0 if route["status"] == "PASS" else 3 if route["status"] == "BLOCKED" else 4,
            data={"reference_route": route},
        )
    if spec.path in {("resume",), ("repair", "rollback")}:
        from polyforge.unity.recovery import repair_rollback, resume_run

        if spec.path == ("resume",):
            return resume_run(Path(args.workspace), args.run_id)
        return repair_rollback(Path(args.workspace), args.transaction_id)
    if spec.path in {("repair", "inspect"), ("repair", "propose")}:
        from polyforge.repairs.diagnostics import diagnose_evidence, plan_repair
        from polyforge.security.paths import WorkspacePolicy

        policy = WorkspacePolicy(Path(args.workspace))
        if spec.path[-1] == "inspect":
            return Result(
                data={"diagnosis": diagnose_evidence(load_json(policy.path(args.evidence)))}
            )
        return Result(
            data={"proposal": plan_repair(policy, load_json(policy.path(args.diagnosis)))}
        )
    if spec.path[0] == "review":
        from polyforge.review.board import record_human_review, review_candidate
        from polyforge.security.paths import WorkspacePolicy

        policy = WorkspacePolicy(Path(args.workspace))
        if spec.path[-1] == "sprite-source":
            from polyforge.review.sprite_source import review_sprite_source

            review = review_sprite_source(policy, load_json(policy.path(args.input)))
            return Result(
                status="PASS" if review["promotion"] == "APPROVED" else "REVIEW",
                exit_code=0 if review["promotion"] == "APPROVED" else 4,
                data={"source_review": review},
            )
        if spec.path[-1] == "amend":
            from polyforge.review.amendments import append_amendment

            return Result(
                data={
                    "amendments": append_amendment(
                        policy,
                        load_json(policy.path(args.task)),
                        load_json(policy.path(args.amendment)),
                        operator=args.operator,
                        reason=args.reason,
                    )
                }
            )
        candidate = load_json(policy.path(args.candidate))
        if spec.path[-1] == "human":
            receipt = record_human_review(
                policy, candidate, verdict=args.verdict, operator=args.operator, reason=args.reason
            )
            return Result(data={"human_review": receipt})
        board = review_candidate(policy, candidate, load_json(policy.path(args.task)))
        approved = board["promotion"] == "APPROVED"
        return Result(
            status="PASS" if approved else "REVIEW",
            exit_code=0 if approved else 4,
            data={"review": board},
        )
    if spec.path[0] == "workforce":
        from polyforge.workforce.cli import dispatch as workforce_dispatch

        return workforce_dispatch(args)
    if spec.path == ("inspect-project",):
        from polyforge.inspection import inspect_project

        return inspect_project(Path(args.project))
    if spec.path == ("platformer", "build"):
        from polyforge.security.paths import WorkspacePolicy
        from polyforge.unity.platformer import build_platformer

        policy = WorkspacePolicy(Path(args.workspace))
        inputs = load_json(policy.path(args.input))
        if not isinstance(inputs, dict):
            raise InputError("Platformer input must be a JSON object")
        return build_platformer(
            policy.root,
            inputs,
            dry_run=args.dry_run,
            standalone=args.standalone or inputs.get("standalone", False),
        )
    if spec.path == ("profile-player",):
        from polyforge.unity.performance import profile_player

        return profile_player(Path(args.workspace), Path(args.player), dry_run=args.dry_run)
    if spec.path == ("benchmark", "run"):
        from importlib.resources import files

        from polyforge.benchmark.runner import run_suite
        from polyforge.benchmark.tasks import load_suite

        suite_path = (
            Path(str(files("polyforge").joinpath("data/benchmark-core/suite.json")))
            if args.suite == "benchmark_core"
            else Path(args.suite)
        )
        return run_suite(load_suite(suite_path), args.arm, Path(args.output), dry_run=args.dry_run)
    if spec.path == ("benchmark", "report"):
        from polyforge.benchmark.analysis import report_run as benchmark_report

        return benchmark_report(Path(args.run))
    if spec.path == ("clean",):
        from polyforge.cleanup import clean_workspace

        return clean_workspace(Path(args.workspace), dry_run=args.dry_run, confirm=args.confirm)
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
    from polyforge.capabilities.dispatch import execute

    return execute(args.id, inputs, context)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI with structured, nonzero failures and no implicit model access."""
    values = list(sys.argv[1:] if argv is None else argv)
    json_output = (
        "--json" in values
        or "--format=json" in values
        or any(values[i : i + 2] == ["--format", "json"] for i in range(len(values)))
    )
    started = time.monotonic()
    formatted_report: str | None = None
    try:
        args = build_parser().parse_args(values)
        if args.spec.path == ("mcp", "serve"):
            from polyforge.host.stdio import serve

            return serve(args.workspace)
        json_output = args.json or args.format == "json"
        result = dispatch(args)
        if args.spec.path == ("benchmark", "report") and not json_output:
            key = "report_html" if args.format == "html" else "report_human"
            formatted_report = result.data.get(key)
    except InputError as exc:
        result = failure(exc.kind, exc.code, redact(str(exc)))
    except OSError as exc:
        result = failure(ErrorKind.PRODUCER_FAILURE, "PF-IO-FAILURE", redact(str(exc)))
    except KeyboardInterrupt:
        result = failure(ErrorKind.INTERRUPTED, "PF-RUN-INTERRUPTED", "Operation interrupted")
    result = replace(result, duration_ms=round((time.monotonic() - started) * 1000, 3))
    if json_output:
        print(json.dumps(result.to_dict(), ensure_ascii=True, allow_nan=False))
    elif formatted_report is not None:
        print(formatted_report)
    else:
        print(f"{result.status}: operation; game={result.game_status}")
        for diagnostic in result.diagnostics:
            print(f"{diagnostic['code']}: {diagnostic['message']}")
        if result.data:
            print(json.dumps(result.data, indent=2, ensure_ascii=True, allow_nan=False))
    return result.exit_code
