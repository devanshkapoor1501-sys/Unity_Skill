# Manifest and planning contracts

Phase 2 accepts v1 JSON design manifests, typed parametric recipe declarations,
and bounded development scenarios. Unknown fields are rejected. Known v1 fields
may declare a newer minor version; new majors require an explicit migration.
No automatic migration or amendment workflow is implemented.

All declared assets, actors, materials, animations and sprite sheets have unique
semantic IDs. References must exist. Asset dependencies and recipe parents must
be acyclic. Spawn positions lie inside the declared centered XZ scene with
nonnegative Y. Dimensions are finite positive meters. Source paths use relative
POSIX spelling; traversal, drive paths, alternate streams, links and junctions
are rejected. Textures/atlases are fingerprinted inputs, not decoded images yet.
Recipe declarations are data, not executable code or completed geometry.

## Ownership and source evidence

Intent annotations identify required features, binding IDs, original source
ranges (Unicode character offsets), and generator-owned acceptance intent.
The compiler checks ranges and preserves exact source text. Initialized briefs
use LF consistently so Windows newline conversion cannot shift source offsets.
Missing annotations
or unreviewed brief text remain unresolved. This conservative check is not an
automatic natural-language completeness classifier. Counts describe supplied
annotations, not evaluator-confirmed feature completeness.

Known feature interfaces have a future phase and BLOCKED support state. Unknown
interfaces are UNSUPPORTED. Composition checks incompatible movement on a shared
binding and missing typed ports. Nothing is considered implemented or independently
verified at this phase. Successful compilation may report operation PASS with
game PARTIAL and evaluated_test_status NOT_RUN. Public stealth/dungeon fixtures
are developer-owned probes; external qualification holdouts remain external.

## Commands and persistence

```console
polyforge validate --workspace workspace/arena_demo --json
polyforge compile-contract --manifest workspace/arena_demo/game_manifest.json --dry-run --json
polyforge plan --workspace workspace/arena_demo --dry-run --json
polyforge plan --workspace workspace/arena_demo --json
polyforge capability run plan.scene.v1 --input game_manifest.json --workspace workspace/arena_demo --json
```

Validation and all dry runs write nothing, including locks. Invalid manifests,
recipes and previous-plan metadata fail before publication. Publication refuses
destinations that overlap manifest, brief, recipe or referenced file inputs,
including fixed metadata and lock destinations. Pure catalog
capabilities always return their contracts directly without writes.

Normal compile/plan commands publish scene_contract.json, feature_contract.json
and requirement_coverage.json; plan also publishes plan.json. Under a workspace
planning lock, original_prompt.txt is created exclusively with the original UTF-8
bytes. Its SHA-256 must match on later runs. This is a development freeze, not a
protected evaluator brief. brief-lock.json has no invented acceptance rubric.
planning-state.json records PREPARING then COMMITTED with hashes and lengths.
Atomic per-file replacement preserves recoverable evidence; a multi-file I/O
failure can leave PREPARING and must not be interpreted as a committed set.

## DAG and cache semantics

Stages are S0 precheck, S1 contracts, S2 model/appearance, S3 audit/export,
S4 Unity construction and S5 verification. Tasks carry stable IDs, sorted
dependencies, local and transitive input hashes, NOT_RUN execution, and relative
work estimates. Seconds remain null/NOT_MEASURED until producers are measured.
Mandatory blockers remain attached to the plan; planning never claims a game.

The manifest digest addresses its canonical JSON alone. Operation input identity
also includes canonical recipe digests, referenced file SHA-256 values and the
original brief SHA-256. The scene contract retains those fingerprints; published
artifact inventory entries refer to that complete input identity.

Material-only edits preserve geometry/export and gameplay-code fingerprints;
collider edits invalidate imports and verification; recipe/size/seed edits
invalidate affected geometry downstream. Texture/atlas bytes and rig animation
declarations participate in dependent fingerprints. Bakes depend on appearance
and rig declarations as well as geometry. A previous-plan comparison
includes removed task IDs. Scenario and evaluator execution remain separate gates.

Cache lookup requires matching input hash, PASS status, nonempty outputs,
validated metadata, contained paths and actual file length/SHA-256 agreement.
The trusted-local cache metadata is not evaluator evidence or an untrusted
security boundary. No build producers write eligible cache records yet. Future
workers must include their executable/toolchain fingerprints and validator
versions. Cache HIT never changes the planner's execution status to PASS.

## Synthetic handoff and scenarios

Handoff reports declare their basis, meters per unit, dimensions and semantic
material/socket/prefab bindings. The invariant engine normalizes Blender Z-up,
forward -Y to Unity Y-up, forward Z; dimensions use 2% relative/1 mm absolute
tolerance. It emits issues plus expected/source/imported evidence links. Reports
are synthetic until real adapters are supplied. PASS is payload agreement only.

Scenario JSON permits bounded move, wait, attack, interact and restart actions,
fixed ticks, expected events and explicit tolerances. Known actor/scene references
and schedule duration are checked. No scripts, eval, test runner or protected
rubric are generated or executed by this validator.
