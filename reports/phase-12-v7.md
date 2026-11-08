# Phase 12 v7 modeling handoff repair

Work date: 2026-11-08, Asia/Calcutta. Baseline HEAD:
`150b8dde4859f1f264f6af4243017406f6c2039c`, with pre-existing uncommitted work
preserved. This report covers the bounded v7 Phase 12 repair, not a stable
release or independently controlled qualification.

## Authority and prior progress

The user requested an assessment and continuation against the updated plan,
using native parallel agents where useful. The supplied v7 blueprint's SHA256
is `2f0d8dcc12a233ddd860bac417109eb0d498680aed018cac20c857ac00704333`.
Its first work order requires the coolant-valve coordinate repair before
considering Phase 13. See the [bounded work plan](../docs/plans/2026-11-08-phase-12-v7-repair.md)
and [Phase 11 reconciliation](phase-11-reconciliation-v7.md).

Phases 0–10 have historical bounded implementation/audit evidence. Phase 11
has a technical checkpoint; stable release remains **BLOCKED**. Phase 12 had
four families, typed compositions and Blender inspection, but its retained
Unity evidence covered eight family FBXs and excluded the coolant composition.
Reported earlier test counts are historical, not freshly witnessed results.

## Reproduction and correction

Real Unity 6000.6.3f1 reproduced the original outlet at
`(-0.90, 0.77, 0.35)` against the frozen `(0.90, 0.77, 0.35)` requirement.
The original source-to-FBX trace preserved Blender `(0.90, -0.35, 0.77)`;
the X reversal appeared at Unity's handedness conversion. The original failure
is retained with model-root/child local/world matrices, determinants and exact
expected/observed positions in [the native red receipt](phase-12-v7-evidence/red-unity-frames.json).
The unchanged coordinate tolerance is 5 mm. JSON observations use float32;
the serialization assertion allows 1 micrometre without changing that tolerance.

The modeling exporter now temporarily reflects the shared export hierarchy's
X scale, covering evaluated meshes and socket empties together. `finally`
restores the source scale before rendering/saving or propagating an error.
The canonical source root remains unit/identity. The old static-recipe Unity
prefab reflection belongs to a different pipeline and remains unchanged;
applying it again to these compensated modeling FBXs would reflect twice.

Stronger material checks exposed a second existing handoff defect: a Geometry
Nodes base declared `trim`, evaluated with a placeholder material and imported
as Unity `Lit`. Export copies now explicitly retain the source palette.
The [native failure](phase-12-v7-evidence/material-red-unity.json) and
[source/FBX trace](phase-12-v7-evidence/material-red-frame-trace.json) preserve it.
A Set Material node experiment failed the LOD's source-palette indexing and was
removed; its failure log is retained. Independent review then identified that
clearing mesh material slots also clears face indices. Native reproduction
showed the mechanical LOD changing from `{trim:12, base:192, accent:60}` source
triangles to `{trim:264}` in FBX. The final exporter saves/restores face indices
around palette replacement. [LOD red trace](phase-12-v7-evidence/lod-material-red.json).

The separate native source inspector now measures triangles per declared
material. Unity compares these counts against actual imported submeshes,
alongside exact material inventories, per-module bounds, aggregate bounds,
UVs, sockets, GUIDs and metadata hashes. Slot names alone are insufficient.

## Verification evidence

The bounded repair is **VERIFIED_IN_WORKFLOW** for Blender 5.2.2 and Unity
6000.6.3f1 on this Windows host. The coolant main and LOD sockets both imported
at `(0.899999976, 0.769999862, 0.350000083)`, within the unchanged 5 mm tolerance.
All four families and both compositions passed, including the previously
excluded coolant valve and inspection gantry. The complete
[evidence index](phase-12-v7-evidence/index.json) binds the sources, FBXs,
inspection reports, plans and preview images by SHA256.

| Executed check | Result | Evidence |
| --- | --- | --- |
| Full offline suite | 1,438 PASS; 20 native tests deselected | [Log](phase-12-v7-evidence/offline-final.txt) |
| Coverage gates | 94.10% combined; 91.19% branches | [Gate](phase-12-v7-evidence/coverage-gate.txt) |
| Phase 12 native Blender | 6 PASS; source hashes and export-failure rollback preserved | [Log](phase-12-v7-evidence/blender-final.txt), [frames](phase-12-v7-evidence/green-frame-trace.json) |
| Legacy Blender generation/export | 9 PASS | [Log](phase-12-v7-evidence/legacy-blender.txt) |
| Native Unity modeling handoff | 12 main/LOD imports PASS; 10 applicable reflection mutants rejected; 24 nested-parent cases PASS | [Receipt](phase-12-v7-evidence/unity-final.json), [command](phase-12-v7-evidence/unity-final.txt) |
| Arena compatibility | 1 EditMode + 18 PlayMode PASS; public oracles PASS | [Receipt](phase-12-v7-evidence/game-regressions.json) |
| Platformer compatibility | 2 EditMode + 24 PlayMode PASS; public oracles PASS | [Receipt](phase-12-v7-evidence/game-regressions.json) |
| Ruff, formatting, strict mypy, CLI documentation | PASS; mypy checked 119 source files | [Lint](phase-12-v7-evidence/lint-final.txt), [format](phase-12-v7-evidence/format-final.txt), [types](phase-12-v7-evidence/types-final.txt), [CLI](phase-12-v7-evidence/cli-docs.txt) |

Unity checks include positive/negative X sockets with nonzero Y/Z, asymmetric
per-module geometry, translated/rotated/nonuniform and mirrored nested parents,
main/LOD material slot and triangle assignments, stable GUIDs, identical `.meta`
hashes across forced reimport, and intact editable source hashes. A separate
Blender process forced real export failures and verified exact source-object
frame restoration and file hashes for all six cases. These public transfer
cases remain distinct from evaluator-owned unseen transfer.

Actual commands used the existing virtual environment; native binaries ran
through owned process policies. The Unity-only regression reused generated
assets and the disposable cached project rather than generating them again:

```powershell
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=json --cov-report=term-missing --basetemp .tmp/v7-final-offline
.\.venv\Scripts\python.exe -m tools.check_coverage
.\.venv\Scripts\python.exe -m pytest tests/test_phase12_native.py -m blender -x -vv --basetemp .tmp/v7d
.\.venv\Scripts\python.exe reports/phase-12-v7-evidence/reproduce_reflection.py
.\.venv\Scripts\python.exe reports/phase-12-v7-evidence/run_unity_import.py .tmp/v7d/phase12-blender0 .tmp/v7u
.\.venv\Scripts\python.exe -m pytest tests/test_phase3_blender.py tests/test_phase4_blender.py -m blender -q --basetemp .tmp/v7legacy
.\.venv\Scripts\python.exe reports/phase-12-v7-evidence/run_existing_games.py
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check polyforge tools tests
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m tools.generate_cli_docs --check
```

Already witnessed: baseline 217 focused Python passes; the first full suite
had 1,437 passes and one stale assisted-routing expectation. The current router
correctly withholds a crate candidate for a mixed sculpt request. That test
now requires no capability, assisted review and blocked discovery; the router
was preserved. Both affected test modules then passed all 32 cases.

The first restricted Unity startup crashed in its local service/system access;
it is not coordinate evidence. Unrestricted native execution used owned
processes, timeouts, project locks and disposable copies. Unity's initial
template resolution fetched its already pinned dependencies into the local
UPM cache; later runs reused copied caches. No new project dependency was adopted.
One diagnostic harness assertion initially compared serialized float32 values
exactly; it was corrected and rerun. Failed attempts remain separate from green
receipts, rather than being counted as passing tests.

Both retained game fixtures have freshly passed EditMode, PlayMode and public
behavior oracles in an independent ordinary copy. Original Assets, Packages
and ProjectSettings hashes matched before/after. Fresh standalone builds,
player smoke and manual gameplay were **NOT_RUN** in this repair; older records
remain historical. [Current game receipt](phase-12-v7-evidence/game-regressions.json).

## Scope and remaining gates

Production changes reuse `modeling_worker.py` and the independent
`modeling_inspector.py`. Existing capability IDs, schemas, CLI commands,
compiler inputs, workforce roles and old game fixtures remain available.
Tests extend the existing native probe and add a source/FBX trace helper.
Documentation reconciles the future roadmap through Phase 18 and explains
the distinct modeling/static export conventions.

Native Codex agents audited reports, traced the source, checked official
documentation, implemented the C# inspector, reconciled docs/tests and reviewed
the fix. The coordinator integrated changes and ran native verification.
These are actual host subagents and same-host development checks, not external
evaluator acceptance. OMX tmux Team was unavailable in this app surface.
The codebase graph connection failed; direct source inspection supplied evidence.

The user's continuation request authorized this local repair. It did not
activate v7's proposed 16-hour multi-day pilot or appoint an independent
evaluator. Measured elapsed time from the baseline freeze to evidence collection
was 3,737.84 seconds (62.3 minutes), including waits and review; earlier discovery
and final report preparation are outside that measurement. Exact timestamps
and artifact hashes are in the evidence index. Model billing, tokens/cost and per-process peak OS resources
are **UNKNOWN**; no performance advantage is claimed.

Completion reconciliation: v7 Section 7.4's Phase 12 technical exit is
**COMPLETE / VERIFIED_IN_WORKFLOW**. Independent equal-tool evaluation belongs
to Phase 13; the older PARTIAL label grouped separate future and artistic gates.
Artistic review remains **REVIEW** and Phase 11 stable release **BLOCKED**.
Phase 13 needs its charter, budget and evaluator decision; Phases 14–18 remain
conditional. No stable tag or direct-main merge is part of this publication.

The owner subsequently requested two visual corrections before pushing: seat
the cabin and expose organic details. They are implemented, with 21 regression
cases reproduced RED, 101 modeling tests GREEN, six native Blender tests and
twelve Unity imports passing again. A separate visual review confirmed cabin
contact at 1.00 m and visible crown/ridges. The [review](phase-12-v7-review.md)
retains appearance limitations, including unqualified extreme-ratio surface
attachment. Updated native receipts are
[Blender](phase-12-v7-evidence/visual-blender-final.txt),
[Unity](phase-12-v7-evidence/visual-unity-final.json) and
[frame rollback](phase-12-v7-evidence/visual-frame-trace.json).

The containing commit identifies the published changes; its branch/PR CI must
be observed separately. Recorded workspace-helper commands above depend on
ignored local caches. Fresh checkouts should run the canonical native test:
`python -m pytest tests/test_phase12_native.py -m "blender or unity"`.

Official references consulted: [Blender 5.2 FBX manual](https://docs.blender.org/manual/en/5.2/files/import_export/fbx_legacy.html),
[Unity 6000.6 axis conversion](https://docs.unity.com/en-us/engine/6000.6/script-reference/unityeditor/modelimporter/bakeaxisconversion),
[Blender 5.2.2 material implementation](https://raw.githubusercontent.com/blender/blender/v5.2.2/source/blender/blenkernel/intern/material.cc)
and [mesh material-index clearing](https://raw.githubusercontent.com/blender/blender/v5.2.2/source/blender/blenkernel/intern/mesh.cc).
Installed Blender's RNA probe confirmed space-transform defaults directly;
documentation alone was not treated as proof of the native mapping.
