"""Single versioned CLI grammar used by argparse, docs, and invocation fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CONTRACT_VERSION = "1.0.0"
Option = tuple[tuple[str, ...], dict[str, Any]]
WORKSPACE: Option = (("--workspace",), {"required": True, "metavar": "PATH"})
RUN_ID: Option = (("--run-id",), {"required": True, "metavar": "ID"})
DRY_RUN: Option = (("--dry-run",), {"action": "store_true"})


@dataclass(frozen=True)
class CommandSpec:
    """Public syntax and truthful availability for one leaf command."""

    path: tuple[str, ...]
    help: str
    options: tuple[Option, ...] = ()
    implemented: bool = False
    phase: int = 1
    example: tuple[str, ...] = ()


COMMANDS = (
    CommandSpec(
        ("doctor",),
        "Probe local tools and execution policies",
        (
            (("--config",), {"metavar": "PATH"}),
            (("--workspace",), {"default": ".", "metavar": "PATH"}),
            (("--project",), {"metavar": "PATH"}),
            DRY_RUN,
        ),
        implemented=True,
        example=("doctor", "--json"),
    ),
    CommandSpec(
        ("init",),
        "Initialize a new managed workspace",
        ((("path",), {}), (("--template",), {"default": "simple_arena"}), DRY_RUN),
        implemented=True,
        example=("init", "workspace/arena_demo", "--template", "simple_arena", "--json"),
    ),
    CommandSpec(
        ("validate",),
        "Validate a game manifest",
        (WORKSPACE,),
        phase=2,
        implemented=True,
        example=("validate", "--workspace", "workspace/arena_demo", "--json"),
    ),
    CommandSpec(
        ("plan",),
        "Plan dependency stages without launching tools",
        (WORKSPACE, DRY_RUN),
        phase=2,
        implemented=True,
        example=("plan", "--workspace", "workspace/arena_demo", "--dry-run", "--json"),
    ),
    CommandSpec(
        ("build",),
        "Build eligible stages of a managed workspace",
        (
            WORKSPACE,
            (("--through",), {"choices": [f"S{i}" for i in range(6)]}),
            (("--only",), {"metavar": "ASSET_ID"}),
            (("--standalone",), {"action": "store_true"}),
            DRY_RUN,
            (
                ("--allow-package-downloads",),
                {
                    "action": "store_true",
                    "help": "Authorize Unity package resolution for this managed workspace",
                },
            ),
        ),
        phase=3,
        implemented=True,
        example=("build", "--workspace", "workspace/arena_demo", "--through", "S2", "--json"),
    ),
    CommandSpec(
        ("audit",),
        "Audit a generated asset",
        (WORKSPACE, (("--asset",), {"required": True}), DRY_RUN),
        implemented=True,
        phase=4,
        example=("audit", "--workspace", "workspace/arena_demo", "--asset", "robot_a", "--json"),
    ),
    CommandSpec(
        ("verify",),
        "Execute distinct integration and game verification gates",
        (WORKSPACE,),
        phase=6,
        implemented=True,
        example=("verify", "--workspace", "workspace/arena_demo", "--json"),
    ),
    CommandSpec(
        ("status",),
        "Read recorded run state",
        (WORKSPACE,),
        implemented=True,
        example=("status", "--workspace", "workspace/arena_demo", "--json"),
    ),
    CommandSpec(
        ("resume",),
        "Resume a recorded run",
        (WORKSPACE, RUN_ID),
        phase=9,
        example=("resume", "--workspace", "workspace/arena_demo", "--run-id", "example", "--json"),
    ),
    CommandSpec(
        ("report",),
        "Report one recorded run",
        (WORKSPACE, RUN_ID),
        implemented=True,
        example=("report", "--workspace", "workspace/arena_demo", "--run-id", "example", "--json"),
    ),
    CommandSpec(
        ("clean",),
        "Preview owned generated-file cleanup",
        (WORKSPACE, DRY_RUN, (("--confirm",), {"action": "store_true"})),
        phase=11,
        example=("clean", "--workspace", "workspace/arena_demo", "--dry-run", "--json"),
    ),
    CommandSpec(
        ("capability", "list"),
        "List implemented model-free capabilities",
        implemented=True,
        phase=0,
        example=("capability", "list", "--json"),
    ),
    CommandSpec(
        ("capability", "show"),
        "Show a capability contract",
        ((("id",), {}),),
        implemented=True,
        phase=0,
        example=("capability", "show", "contract.capability.validate.v1", "--json"),
    ),
    CommandSpec(
        ("capability", "run"),
        "Run a validated capability",
        ((("id",), {}), (("--input",), {"required": True}), WORKSPACE, DRY_RUN),
        implemented=True,
        phase=0,
        example=(
            "capability",
            "run",
            "contract.capability.validate.v1",
            "--input",
            "input.json",
            "--workspace",
            "workspace/arena_demo",
            "--dry-run",
            "--json",
        ),
    ),
    CommandSpec(
        ("compile-contract",),
        "Compile the semantic scene contract",
        ((("--manifest",), {"required": True}), DRY_RUN),
        phase=2,
        implemented=True,
        example=(
            "compile-contract",
            "--manifest",
            "workspace/arena_demo/game_manifest.json",
            "--json",
        ),
    ),
    CommandSpec(
        ("reconcile",),
        "Compare source and imported semantic bindings",
        (WORKSPACE, (("--strict",), {"action": "store_true"})),
        implemented=True,
        phase=5,
        example=("reconcile", "--workspace", "workspace/arena_demo", "--strict", "--json"),
    ),
    CommandSpec(
        ("scenario", "run"),
        "Execute a declarative scenario suite",
        (WORKSPACE, (("--suite",), {"required": True})),
        phase=6,
        implemented=True,
        example=(
            "scenario",
            "run",
            "--workspace",
            "workspace/arena_demo",
            "--suite",
            "core_gameplay",
            "--json",
        ),
    ),
    CommandSpec(
        ("diagnose",),
        "Diagnose structured run evidence",
        (WORKSPACE, (("--evidence-dir",), {"required": True})),
        implemented=True,
        phase=5,
        example=(
            "diagnose",
            "--workspace",
            "workspace/arena_demo",
            "--evidence-dir",
            "runs/example",
            "--json",
        ),
    ),
    CommandSpec(
        ("repair", "plan"),
        "Preview a bounded managed repair",
        (WORKSPACE, (("--issue",), {"required": True})),
        implemented=True,
        phase=5,
        example=(
            "repair",
            "plan",
            "--workspace",
            "workspace/arena_demo",
            "--issue",
            "ISSUE-001",
            "--json",
        ),
    ),
    CommandSpec(
        ("repair", "apply"),
        "Apply an approved repair transaction",
        (
            WORKSPACE,
            (("--plan",), {"required": True}),
            (("--approved",), {"action": "store_true", "required": True}),
        ),
        phase=5,
        implemented=True,
        example=(
            "repair",
            "apply",
            "--workspace",
            "workspace/arena_demo",
            "--plan",
            "repair.json",
            "--approved",
            "--json",
        ),
    ),
    CommandSpec(
        ("repair", "rollback"),
        "Restore and reverify a repair transaction",
        (WORKSPACE, (("--transaction-id",), {"required": True})),
        phase=9,
        example=(
            "repair",
            "rollback",
            "--workspace",
            "workspace/arena_demo",
            "--transaction-id",
            "tx-example",
            "--json",
        ),
    ),
    CommandSpec(
        ("benchmark", "run"),
        "Run a budgeted benchmark arm",
        (
            (("--suite",), {"required": True}),
            (("--arm",), {"choices": ["A", "B", "C", "D"], "required": True}),
            (("--output",), {"required": True}),
            DRY_RUN,
        ),
        phase=6,
        example=(
            "benchmark",
            "run",
            "--suite",
            "benchmark_core",
            "--arm",
            "D",
            "--output",
            "workspace/benchmarks",
            "--dry-run",
            "--json",
        ),
    ),
    CommandSpec(
        ("benchmark", "report"),
        "Report stratified benchmark outcomes",
        ((("--run",), {"required": True}),),
        phase=6,
        example=("benchmark", "report", "--run", "benchmark-example", "--format", "json"),
    ),
    CommandSpec(
        ("inspect-project",),
        "Statically inspect an original project without opening Unity",
        (
            (("--project",), {"required": True}),
            (("--read-only",), {"action": "store_true", "required": True}),
        ),
        phase=11,
        example=(
            "inspect-project",
            "--project",
            "workspace/existing_project",
            "--read-only",
            "--json",
        ),
    ),
    CommandSpec(
        ("mcp", "serve"),
        "Serve bounded capability tools through optional stdio MCP",
        ((("--transport",), {"choices": ["stdio"], "default": "stdio"}),),
        phase=10,
        example=("mcp", "serve", "--transport", "stdio"),
    ),
)
