# Development and local tool setup

For contributors and assistants preparing the local build tools. For the user overview and skill installation, see [PolyForge](../README.md).

A portable agent skill backed by a local, model-independent Blender-to-Unity
capability engine. Apache-2.0. Final Codex/Claude installation and optional MCP
host qualification are scheduled for Phase 10.

**Current implementation: Phase 6 playable arena; manual play review passed.** Discovery, descriptor and
manifest validation, scene/feature compilation, and dependency planning work
without a model, Blender, or Unity. Workspace init, doctor, status and report
are implemented. Five headless Blender recipes and managed S0–S2 builds generate
editable sources and checked geometry. S3 audits/exports static assets; S4 builds
a managed URP project with native prefabs, materials, two static scene layouts,
observed semantic bindings and executed EditMode tests. Native binding diagnosis
and bounded repair are available. S5 adds movement, patrol, health, survival,
restart, declarative scenarios and actual Windows build/smoke. Full cross-app
recovery, benchmark trials and MCP remain future gates. See the phase reports.
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
after installation. The fixture validates example metadata; it does not execute
asset generation.

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
compilation reports development intent, and S5 separately records executed
feature evidence. Synthetic handoff checks and scenario validation do not execute
application tests.
See [manifest and planning rules](manifests.md) for publication, frozen-brief
and cache behavior. Pure catalog capabilities return contracts without files;
the normal compile/plan CLI commands publish derived JSON in the workspace.
Blender capabilities are execution operations: they create unique run directories,
logs, source.blend, metrics.json and logical-geometry.json. Use --dry-run for
zero writes. Build through S3 adds four transparent views, geometric diagnostics,
FBX, material and coordinate sidecars, and a visual-review bundle. Requesting
S4 creates the native Unity project and runs separate static EditMode gates;
S5 now constructs and verifies the bounded survival arena. Use
`polyforge build --workspace ROOT --through S5 --standalone --json` for actual
Windows player build/smoke, or omit `--standalone` for Editor-only checks.
`polyforge verify --workspace ROOT --json` and
`polyforge scenario run --workspace ROOT --suite core_gameplay --json` rerun
the native and independent public development checks. Visual quality stays
REVIEW; game acceptance stays PARTIAL. See [the arena guide](arena.md).

```powershell
.\.venv\Scripts\polyforge.exe build --workspace workspace/arena_demo --through S3 --dry-run --json
.\.venv\Scripts\polyforge.exe build --workspace workspace/arena_demo --through S3 --json
.\.venv\Scripts\polyforge.exe audit --workspace workspace/arena_demo --asset robot_a --dry-run --json
.\.venv\Scripts\polyforge.exe audit --workspace workspace/arena_demo --asset robot_a --json
.\.venv\Scripts\polyforge.exe build --workspace workspace/arena_demo --through S4 --allow-package-downloads --json
```

The real Blender gate is separate from offline Python tests:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_phase3_blender.py -m blender -o addopts=-ra
.\.venv\Scripts\python.exe -m pytest tests/test_phase4_blender.py -m blender -o addopts=-ra
.\.venv\Scripts\python.exe -m pytest tests/test_phase5_unity.py -m unity -o addopts=-ra
```

It requires installed Blender 5.2.2 and fails when the dependency is unavailable.
Default pytest excludes Blender and Unity application gates explicitly. See
[recipe contracts](recipes.md) for parameters, coordinate spaces and limits.
See [native Unity integration](unity-integration.md) for authorization,
handedness, binding evidence and minimal repair limits.

## Ownership and next delivery

- `polyforge/`: trusted engine, bundled contracts, and implemented catalog.
- `unity_package/`: separate UPM Editor/runtime/test assemblies and native APIs.
- `capabilities/`: future reviewed recipe data; fixtures are not advertised tools.
- `examples/`: original briefs and requested design contracts.
- `benchmarks/`: public development tasks and evaluator interfaces, never holdouts.
- `.agents/skills/polyforge/`: portable host-facing instructions.
- `workspace/`: ignored generated projects, run logs, caches, and artifacts.
- `reports/`: exact phase evidence and limitations.

See [architecture](architecture.md), [CLI contract](cli.md),
[security](../SECURITY.md), and [execution plan](implementation-plan.md).
Phase 7 adds bounded worker contracts and robot Idle/Walk animation; see the
[workforce workflow](workforce.md) and [Phase 7 evidence](../reports/phase-7.md).
Phase 8 adds [asset/material handoffs and the bounded 2D workflow](asset-workflow.md),
with separate technical, visual and game acceptance evidence.
The reviewed v5.1 roadmap keeps broader asset, texture, 2D and host integration
work in later phases; see [the implementation sequence](implementation-plan.md).
Phases stop at their acceptance
boundaries. The source blueprint remains unchanged.
