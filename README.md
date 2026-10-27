# PolyForge

A local, model-independent Blender-to-Unity capability engine. Apache-2.0.

**Current delivery: Phase 4 audit and export.** Discovery, descriptor and
manifest validation, scene/feature compilation, and dependency planning work
without a model, Blender, or Unity. Workspace init, doctor, status and report
are implemented. Five headless Blender recipes and managed S0–S2 builds generate
editable sources and checked geometry. Unity/game generation, repair, benchmarks and MCP remain future
commands and return `NOT_RUN`/5.
Trusted-local process protections do not claim untrusted OS containment.

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
polyforge doctor --dry-run --json
```

Descriptor execution and dry-run validation only read input files. Invalid input
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
The Windows junction test creates a disposable local junction. A restricted host
may require additional test execution access; do not skip it to pass the gate.

## Runtime setup and precheck

Create the parent directory first. Initialization refuses existing targets;
--dry-run writes nothing. The default template carries a development design
manifest, annotated original brief, and three declarative recipe inputs.

```powershell
New-Item -ItemType Directory -Force workspace
.\.venv\Scripts\polyforge.exe init workspace/arena_demo --json
.\.venv\Scripts\polyforge.exe doctor --workspace workspace/arena_demo --json
.\.venv\Scripts\polyforge.exe status --workspace workspace/arena_demo --json
.\.venv\Scripts\polyforge.exe validate --workspace workspace/arena_demo --json
.\.venv\Scripts\polyforge.exe plan --workspace workspace/arena_demo --dry-run --json
.\.venv\Scripts\polyforge.exe compile-contract --manifest workspace/arena_demo/game_manifest.json --json
.\.venv\Scripts\polyforge.exe plan --workspace workspace/arena_demo --json
.\.venv\Scripts\polyforge.exe build --workspace workspace/arena_demo --through S2 --dry-run --json
.\.venv\Scripts\polyforge.exe build --workspace workspace/arena_demo --through S2 --json
```

Doctor honors explicit TOML executable paths, then conventional installations,
then PATH. Unity's generic `unity` CLI can differ from the Editor. Probes use
`Blender --version` and `Unity -version`; original projects never open. Optional
`--project PATH` reads only known settings/packages/lock files statically.
Doctor saves doctor.json plus a durable run/log tree even for missing tools.
Version probes do not prove Unity activation, graphics rendering or gameplay.

The runner provides allowlisted binaries, minimal environments, redacted bounded
logs, timeouts/cancellation, owned process-tree cleanup and Windows job memory/
process limits. POSIX process-group cleanup is implemented; POSIX memory ceilings
are explicitly unverified. Locks use OS exclusion plus PID/host/birth metadata.
Journal replay recovers a cache interrupted after a durable append. Resume
scheduling stays unavailable until actual build producers exist.

Compilation preserves original source ranges and creates development-only scene,
feature and coverage contracts. Planning records S0–S5 task dependencies and
content hashes. Both operations can PASS while game status remains PARTIAL:
all requested gameplay producers are still BLOCKED or UNSUPPORTED. Synthetic
handoff checks and scenario validation do not execute application tests.
See [manifest and planning rules](docs/manifests.md) for publication, frozen-brief
and cache behavior. Pure catalog capabilities return contracts without files;
the normal compile/plan CLI commands publish derived JSON in the workspace.
Blender capabilities are execution operations: they create unique run directories,
logs, source.blend, metrics.json and logical-geometry.json. Use --dry-run for
zero writes. Build through S3 adds four transparent views, geometric diagnostics,
FBX, material and coordinate sidecars, and a visual-review bundle. Requesting
S4–S5 returns NOT_RUN/5. Visual quality remains REVIEW; Unity import stays NOT_RUN.

```powershell
.\.venv\Scripts\polyforge.exe build --workspace workspace/arena_demo --through S3 --dry-run --json
.\.venv\Scripts\polyforge.exe build --workspace workspace/arena_demo --through S3 --json
.\.venv\Scripts\polyforge.exe audit --workspace workspace/arena_demo --asset robot_a --dry-run --json
.\.venv\Scripts\polyforge.exe audit --workspace workspace/arena_demo --asset robot_a --json
```

The real Blender gate is separate from offline Python tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase3_blender.py -m blender -o addopts=-ra
.\.venv\Scripts\python.exe -m pytest tests/test_phase4_blender.py -m blender -o addopts=-ra
```

It requires installed Blender 5.2.2 and fails when the dependency is unavailable.
Default pytest excludes that application gate explicitly. See
[recipe contracts](docs/recipes.md) for parameters, coordinate spaces and limits.

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
The next delivery is Phase 5: native Unity import, materials, prefabs and scene construction.
Phases stop at their acceptance
boundaries. The source blueprint remains unchanged.
