"""Initialize new managed workspaces and query durable state without opening editors."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from uuid import uuid4

from polyforge.contracts.results import Result
from polyforge.contracts.validation import InputError
from polyforge.runner.state import RunJournal, atomic_json
from polyforge.security.paths import WorkspacePolicy

DEFAULT_TOML = """[tools]
blender_executable = ""
unity_executable = ""

[execution]
max_parallel_blender = 2
max_parallel_unity = 1
blender_timeout_seconds = 600
unity_timeout_seconds = 1800
retry_limit = 2

[security]
allow_network = false
allow_outside_workspace = false
require_approval_for_download = true
mode = "TRUSTED_LOCAL"

[visual_audit]
mode = "manual_or_host_vision"
preview_resolution = 512
"""


def init_workspace(target: Path, template: str, *, dry_run: bool = False) -> Result:
    """Create only a new explicitly named directory; never overwrite existing data."""
    if template != "simple_arena":
        raise InputError("Only the simple_arena template is available")
    if ".." in target.parts:
        raise InputError("Workspace initialization cannot use parent traversal")
    target = target.absolute()
    parent = WorkspacePolicy(target.parent)
    target = parent.path(target)
    if target.exists():
        raise InputError("Initialization requires a new directory; existing paths are preserved")
    planned = ["brief.md", "game_manifest.json", "polyforge.toml", ".polyforge/workspace.json"]
    # Read and validate bundled inputs before creating any destination.
    brief = files("polyforge").joinpath("data/arena_brief.md").read_text("utf-8")
    manifest = files("polyforge").joinpath("data/arena_manifest.json").read_text("utf-8")
    recipes = json.loads(files("polyforge").joinpath("data/arena_recipes.json").read_text("utf-8"))
    planned.extend(f"recipes/{identifier}.json" for identifier in recipes)
    if dry_run:
        return Result(data={"workspace": str(target), "planned_writes": planned, "dry_run": True})
    target.mkdir(exist_ok=False)
    policy = WorkspacePolicy(target)
    for name, content in (
        ("brief.md", brief),
        ("game_manifest.json", manifest),
        ("polyforge.toml", DEFAULT_TOML),
    ):
        policy.path(name).write_text(content, encoding="utf-8", newline="\n")
    for identifier, recipe in recipes.items():
        atomic_json(policy, f"recipes/{identifier}.json", recipe)
    atomic_json(
        policy,
        ".polyforge/workspace.json",
        {
            "schema_version": "1.0.0",
            "workspace_id": uuid4().hex,
            "security_scope": "TRUSTED_LOCAL",
            "trusted_local_approved": True,
            "isolation_verified": False,
            "template": template,
        },
    )
    return Result(
        data={
            "workspace": str(target),
            "created": planned,
            "manifest_validation": "NOT_RUN",
            "security_scope": "TRUSTED_LOCAL",
            "isolation_verified": False,
        },
        diagnostics=[
            {
                "code": "PF-TRUST-LOCAL",
                "message": "Local code runs with your account privileges; untrusted plugins denied",
            }
        ],
    )


def status_workspace(root: Path) -> Result:
    """Read journal state without creating locks, directories, or inferred success."""
    policy = WorkspacePolicy(root)
    runs = policy.path("runs")
    snapshots = []
    if runs.exists():
        for path in sorted(runs.iterdir()):
            policy.path(path)
            if path.is_dir() and policy.path(path / "events.jsonl").is_file():
                snapshots.append(RunJournal(policy, path.name).read())
    return Result(data={"runs": snapshots})


def report_run(root: Path, run_id: str) -> Result:
    """Return saved facts; a successful report query does not pass its evaluated run."""
    snapshot = RunJournal(WorkspacePolicy(root), run_id).read()
    return Result(
        run_id=run_id,
        data={
            "state": snapshot,
            "evaluated_run_status": "FAIL"
            if any(stage["status"] == "failed" for stage in snapshot["stages"].values())
            else "NOT_RUN",
        },
    )
