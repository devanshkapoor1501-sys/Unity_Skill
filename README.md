# PolyForge

A local, model-independent Blender-to-Unity capability engine. Apache-2.0.

**Current delivery: Phase 0 foundation.** Capability discovery and descriptor
validation work without a model, Blender, or Unity. Game generation, doctor,
planning, repair, benchmarks, and MCP are registered future commands and return
`NOT_RUN` with a nonzero exit code. No playable-game or sandbox claim is made.

## Windows setup

Use Python 3.11 or newer. Creating the virtual environment does not require a
network connection. The installation step downloads declared Python dependencies;
run it only when dependency downloads are allowed.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-build-isolation --no-deps -e .
.\.venv\Scripts\polyforge.exe --help
```

If the Windows sandbox's default temp directory is inaccessible, point `TEMP` and
`TMP` to an existing writable project-local directory before setup and tests.

## Working offline commands

The following commands execute without model credentials or network access
after installation. The fixture is example metadata; it does not make the robot
capability available in this release.

```console
polyforge capability list --json
polyforge capability show contract.capability.validate.v1 --json
polyforge capability run contract.capability.validate.v1 --input tests/fixtures/capability_valid.json --workspace . --json
polyforge capability run contract.capability.validate.v1 --input tests/fixtures/capability_valid.json --workspace . --dry-run --json
```

Normal execution and dry-run validation only read input files. Invalid input
returns exit 2; outside-workspace input returns exit 4. Neither writes artifacts.
`status=PASS` means descriptor validation succeeded; it does not mean a game was
tested. `evaluated_test_status=NOT_RUN` and `game_status=PARTIAL` remain explicit.

## Development checks

```powershell
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m tools.generate_cli_docs --check
.\.venv\Scripts\python.exe -m build --no-isolation
```

Security/contracts branch coverage must remain at least 90%. Integration tests
will be separate from offline tests. Missing tooling is not a passing result.

## Ownership and next delivery

- `polyforge/`: trusted engine, bundled contracts, and implemented catalog.
- `unity_package/`: future separate Editor/runtime tooling; no generated YAML.
- `capabilities/`: future reviewed recipe data; fixtures are not advertised tools.
- `examples/`: original briefs and requested design contracts.
- `benchmarks/`: public development tasks and evaluator interfaces, never holdouts.
- `.agents/skills/polyforge/`: portable host-facing instructions.
- `workspace/`: ignored generated projects, run logs, caches, and artifacts.
- `reports/`: exact phase evidence and limitations.

See [architecture](docs/architecture.md), [CLI contract](docs/cli.md),
[security](SECURITY.md), and [execution plan](docs/implementation-plan.md).
The next delivery is Phase 1: doctor, configuration, worker execution, locks,
state journals, and expanded workspace policy. Phases stop at their acceptance
boundaries. The source blueprint remains unchanged.
