# Static Blender recipes

Phase 3 implements robot, crate, wall, doorway and environment tile families.
The executable catalog lists their versioned IDs and shared request schema.
No model, MCP bridge, network or user-supplied Python is needed. Blender 5.2.2 is
required; its complete LTS label and build hash are retained separately.

```console
polyforge capability list --json
polyforge capability run mesh.robot.modular.v1 --input examples/static_recipes/robot.json --workspace . --dry-run --json
polyforge capability run mesh.robot.modular.v1 --input examples/static_recipes/robot.json --workspace . --json
polyforge build --workspace workspace/arena_demo --through S2 --dry-run --json
polyforge build --workspace workspace/arena_demo --through S2 --json
```

## Data and coordinates

Requests contain schema_version, asset_id, parameters.size_m and optional
max_polygons (default 25,000, hard maximum 100,000). Size is width, height, depth
in Unity XYZ meters. Doorway also accepts opening_width_m and opening_height_m;
the opening must leave at least 5% usable frame. Other parameters are rejected.
Context seed defaults to 42 and controls deterministic bevel variation.

Expansion produces bounded recipe JSON: modules, parent links, socket attachments,
materials, pivot and target bounds. Module locations, dimensions and socket
positions use canonical Unity coordinates. Child location is relative to its
parent center, or to the named attach_to socket on that parent. A socket's position
is local to its owning module and must lie on/in that module's box. Parent cycles,
missing references, duplicate IDs and excess bevels are invalid input.

The worker converts positions to Blender (x, -z, y), constructs primitives, fits
the assembly to the declared bounds, and bakes the fit into geometry. The root
stays at the base center with unit scale. Target fitting preserves proportions
under changes to requested width/height/depth; module/socket world positions in
metrics are authoritative after fitting. Semantic IDs remain full strings even
when human-facing Blender names require deterministic shortening.

Supported primitives are cube, beveled_box, sphere, cylinder and plane. Arrays
are limited to 256 modules, 128 sockets and 16 palette materials. Sphere/cylinder
tessellation and bevel segments are fixed and bounded. Plane faces are allowed
inside assemblies; a complete asset must have nonzero 3D bounds. The reviewed
JSON DSL cannot import scripts, arbitrary assets or unbounded expansion operators.

## Execution and evidence

The existing allowlisted process runner launches Blender in background with
factory settings, automatic scripts disabled, one thread and a Python error exit
code. Job/output paths are separate arguments. Workspaces serialize Blender
workers with a lock; configured concurrency may exceed the current effective
one-worker limit. Resource ownership and bounded logs do not claim OS isolation.

Each invocation creates a unique run directory with immutable input JSON,
executable/worker SHA-256, version-probe and generation logs, process outcomes,
stage journal, source.blend, metrics.json, logical-geometry.json and artifact
hashes. Declared palette materials are explicitly retained in editable sources.
The saved file is reopened with scripts disabled and measured again. The host
validates identities, bounds, base-center position, measured root pivot/units,
UV areas, face degeneracy, finite values, socket ordering, polygon budget and
logical payload digest before registering artifacts.

Logical hashes address world-space oriented faces with their UV bindings,
rounded to six decimal places, plus semantic hierarchy and socket positions.
Face storage order/cyclic starting corner do not affect the hash; reversed
winding does. Binary .blend bytes may differ, and their SHA-256 is stored
separately. Palette color is appearance, so it does not alter geometry hashes.
Logical outputs permit at most 32 MiB JSON; user input JSON remains capped at
1 MiB. The actual 128-sphere fixture exceeds 1 MiB within supported mesh budgets.

## Managed stages and limits

Build defaults to S2. S0 probes Blender; S1 publishes validated contracts; S2
generates selected assets in dependency order. --only includes its dependencies.
Every effective recipe, including size/material overrides and configuration,
validates before writes. Dry runs launch nothing. S3–S5 remain NOT_RUN/5.
Results distinguish successful source generation from game acceptance (PARTIAL)
and application gameplay tests (NOT_RUN).

Builds create fresh outputs rather than claim cache hits. Planner hashes and
artifact lookup remain available, but no producer cache is populated yet.
Generic resume/repair orchestration remains unavailable; fresh reruns retain
earlier evidence. Stage retry limits are not silently consumed by hidden retries.

Initial Phase 1/2 workspaces may carry placeholder robot declarations; replace
those explicitly using the current reviewed recipe data. Existing projects and
source files are never overwritten by generation. Rendering, visual review,
FBX/material interchange and actual Unity import begin in later phases.

## Verification and sources

Default pytest runs offline tests; the separately selected blender marker runs
actual generation, roundtrip, reproducibility, five-family/two-brief reuse,
large-payload and saved-source fault probes. Missing Blender fails that gate.
Public probes are development tests; no hidden evaluator acceptance is implied.

Official references: [Blender command-line arguments](https://docs.blender.org/manual/en/5.4/advanced/command_line/arguments.html)
and [mesh operators](https://docs.blender.org/api/dev/bpy.ops.mesh.html). These
reference APIs; compatibility evidence is from the locally pinned 5.2.2 runs,
not from assuming development documentation matches an installed binary.
