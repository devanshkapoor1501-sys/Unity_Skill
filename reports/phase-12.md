# Phase 12 advanced modeling

Phase 12 development is active under the user's sequencing amendment. Main
`941717b` passed [workflow 41877839001](https://github.com/devanshkapoor1501-sys/Unity_Skill/actions/runs/41877839001),
the technical Phase 11 checkpoint. Phase 11 stable release qualification remains
blocked by missing evaluator, benchmark and approval evidence.

This checkpoint implements four parameterized Blender families and a typed
composition capability. It adds specialist routing, an editable `.blend` with
its modifier stacks, evaluated FBX exports, a reduced detail export, four
inspection views and separate Blender inspection. The CLI capability preview
returns the compiled plan without writes. The workforce route checks the sealed
candidate and holds promotion at `REVIEW` until a separate artistic approval.

| Capability case | Dimensions (m) | Main polygons | LOD polygons | Blender geometry | Unity import |
| --- | --- | ---: | ---: | --- | --- |
| Room kit | 4 × 3 × 5 | 486 | 54 | PASS | PASS |
| Vehicle | 3 × 2 × 6 | 352 | 96 | PASS | PASS |
| Mechanical prop | 2 × 1 × 3 | 362 | 88 | PASS | PASS |
| Organic practice | 2 × 3 × 1 | 8,488 | 632 | PASS | PASS |
| Coolant valve composition | 3 × 2 × 2 envelope | 2,126 | 198 | PASS | NOT_RUN |

Blender 5.2.2 produced the five cases on Windows. The valve combines a Geometry
Nodes mounting base, Boolean bore, editable curve and subdivided handle with a
new socket. This is a public development transfer case. Unity 6000.6.3f1
imported each family's main and LOD FBX in an isolated managed project. An Editor
probe checked mesh inventory, UVs, bounds within 5 mm, socket positions and GUID
stability across forced reimports. The evidence index records SHA-256 hashes
and links the editable sources, FBXs, plans, inspection views and measurements.
[Native evidence](phase-12-evidence/index.json) · [Unity import log](phase-12-evidence/unity-import.txt)

The separate native inspector reopened source files with script execution
disabled. It checked object identities, source sizes and controls, modifiers,
material slots, pivot and sockets, polygon counts, finite UVs, degenerate faces,
edge manifoldness and coherent winding. Scratch copies with a displaced pivot,
a moved socket, an open mesh and a fully reversed mesh were rejected. The open
mesh reported four nonmanifold edges. Source hashes matched before and after inspection. Recovery
revalidated all nine required files and rejected a modified FBX. A fixed scratch
API probe verified a data-only mesh validation case and operator polling with
and without an active object. [Scratch probe](phase-12-evidence/scratch-probe.json)

An early Blender run found that Decimate's ratio counted triangles while the
contract measured polygons. A second run exposed nonmanifold edges on a vehicle
LOD after collapse. The producer now builds lower resolution primitives,
retains per-face materials, and runs the same independent topology and ratio
checks on the result. A review also found that recovery could accept an empty
inventory. Recovery now requires a complete journal, the fixed artifact list,
byte hashes and report/source/provenance bindings. A second process checks the
assets, and the review board discloses that the two roles share a host.

Follow-up native probes found that Blender purged unused palette slots and that
the winding audit rejected Solidify's inner cavity. The saved palette now keeps
all declared slots. The inspector only accepts an inward shell when it is
contained in one outward solid with no detected surface intersections or
nested cavities. Mirror and Solidify passed through the capability entry point
with one bound material, while a reversed mesh still failed the audit.

The added registry entries increased reference validation cost. Loading the
validated registry once per call reduced a local 20-iteration warm measurement
from 424 ms to 41 ms per catalog validation. The curated cards still reject any
capability ID outside the registered set.

| Requirement | Checkpoint evidence |
| --- | --- |
| 12.1–12.5 | Specialty inventory, four Blender workflows, expert routing, editable source, technical audits and eight Unity imports |
| 12.6, 12.11 | Public coolant valve composition passed. Evaluator-owned unseen transfer remains BLOCKED |
| 12.7–12.10 | Concept guide and typed routing. Scratch API probe passed. Sculpt, retopology, text, Grease Pencil and simulation remain assisted |
| 12.12 | Positive and negative modeling cases plus one public transfer. Full independent coverage across all required Blender domains remains open |
| 12.13–12.14 | Preserved modifier stacks, basis, bounds, budgets, normals, sockets and topology verified. Arbitrary intersection tests and artistic silhouette remain limited or REVIEW |

The LOD generator can reject a ratio it cannot meet while preserving the shape.
UV checks establish finite coordinates and valid material indices. UV layout
quality, exact self intersections, decals and sculpted topology are outside
this executable scope. `DISALLOW` uses conservative bounding boxes. Assembly
contact is explicit in the plan. The numeric audit and source hashes leave
artistic approval at `REVIEW` for every retained model.

Skills selected were the repo's PolyForge skill for supported tool and asset
contracts, the installed Agent Team and parallel dispatch workflows for bounded
compiler and inspector lanes, and the testing, debugging, Git and verification
workflows for repository checks. Native agents implemented the compiler and
inspector, verified official Blender APIs, and started workforce and knowledge
routing. The coordinator completed integration and recovery fixes. PolyForge
itself ran the specialist workflow in its supported local sequential mode.

```console
python -m pytest --cov --cov-report=json
python -m pytest tests/test_phase12_native.py -m "blender or unity"
python -m pytest tests/test_phase3_blender.py tests/test_phase4_blender.py -m blender
python -m ruff check .
python -m ruff format --check polyforge tools tests
python -m mypy
python -m tools.generate_cli_docs --check
python -m tools.reproducible_build --outdir dist/release-a --epoch 1793318400
```

Local Windows Python 3.12.14 regression passed 1,425 tests with 18 native
tests deselected, 94.08% combined coverage and 91.15% branch coverage. The final
Phase 12 Blender suite passed all five tests. The eight final FBXs passed the
Unity import probe in the disposable project. Nine earlier Blender tests passed
alongside the initial workforce run. Ruff, formatting, Windows/Linux mypy, CLI
documentation and two identical package builds passed.

The two v1 games passed their native regressions on Unity 6000.6.3f1. The arena
passed 1 Edit Mode test, 18 Play Mode tests, the standalone build and player
smoke. The checkpoint course passed 2 Edit Mode tests, 24 Play Mode tests,
standalone build, player smoke and standalone gameplay. Both remain `PARTIAL`
pending separate acceptance. [v1 native regression](phase-12-evidence/v1-native-regression.json)

The commit and its Actions run identify this development checkpoint on the
authorized main branch. Local tests and the remote CI matrix are separate.
See the [phase plan](../docs/plans/2026-11-06-phase-12.md) and
[modeling guide](../docs/modeling.md). The Phase 12 exit gate remains open for
independent transfer and remaining qualification. Phase 13 is pending.
