# Phase 2 — contracts and planning

**Phase status: PASS. Game status: PARTIAL. Phases 3–11: NOT_RUN.**

This phase delivers model-free validation, deterministic contracts and planning.
Blender/Unity producers and all Phase 3–11 integration gates remain NOT_RUN.

## Changes

- Strict bundled v1 manifest, recipe and scenario schemas; finite canonical JSON,
  explicit major-version rejection, bounded inputs, global semantic IDs, safe
  workspace-relative paths, cross-references and cycle detection.
- Deterministic scene graph with material/socket/actor/animation bindings,
  coordinate basis and bounds; source-span feature provenance, blocked/unsupported
  classification, typed composition ports and requirement coverage. Generator
  intent is DEVELOPMENT_ONLY and independent evaluator status stays NOT_RUN.
- S0–S5 task DAG with stable IDs, scoped local/transitive hashes, invalidation,
  artifact-hash cache checks and explicit execution NOT_RUN. Unchanged inputs
  alone never count as completed work. Duration estimates remain NOT_MEASURED.
- Separate pure handoff invariant engine with evidence graphs and bounded scenario
  validation. Synthetic agreement cannot claim real Blender or Unity execution.
- Working CLI validate, compile-contract and plan; three additional pure catalog
  capabilities. Normal compile/plan publishes derived JSON, freezes the brief and
  writes an atomic artifact inventory under a planning lock. Invalid input and dry
  runs write nothing, including locks. Input/output overlaps are rejected.
- Init bundles three typed recipe declarations and source annotations, preserving
  LF source offsets on Windows. These declarations are not registered producers.
- Ten named good/bad contract fixtures, public developer-owned stealth/dungeon
  probes, additional boundary tests, command examples, API documentation and skill
  guidance. No external hidden fixtures or acceptance rubrics were created.

## Verification

| Gate | Actual result | Evidence in phase-2-evidence/ |
| --- | --- | --- |
| Full Python suite | PASS: 94 tests, 0 failures/errors/skips | pytest.txt, python-tests.xml |
| Security/contracts coverage | PASS: 96.31% combined, 97.33% statements, 93.57% branches | coverage.json |
| Ruff and format | PASS, exit 0 | ruff.txt, format.txt |
| Strict mypy, Windows/Linux targets | PASS: 39 source files, exit 0 | mypy.txt, mypy-linux.txt |
| CLI documentation/examples | PASS, exit 0 | cli-docs.txt |
| Dependency consistency | PASS, exit 0 | pip-check.txt |
| Wheel/source builds and resource inventory | PASS, exit 0 | build.txt, package-artifacts.json |
| Fresh offline editable and wheel installs | PASS: 19 commands, all exit 0; wheel imported from its new venv | fresh-installs.json |
| CLI workflow and actual XML count check | PASS: 7 commands, all exit 0; zero-write dry runs and preserved source hashes | phase-smoke.json |
| Repeated plans | PASS: no affected tasks, no false cache hits | smoke-repeat-plan.json |
| Scoped material invalidation | PASS: geometry/export/runtime task hashes preserved | material-invalidation.json |
| Synthetic handoff | PASS agreement, FAIL for injected scale/socket/binding defects; application NOT_RUN | synthetic-handoff.json |
| Invalid descriptor / future build | Expected exits 2 / 5 | negative-descriptor.txt, future-build.txt |

Exact argument arrays, exits, timings and logs are in
[verification.json](phase-2-evidence/verification.json). Fresh-install commands are
in fresh-installs.json and CLI smoke commands in phase-smoke.json in the same folder.

The executed development command family is:

```powershell
$env:TEMP = Join-Path (Get-Location) '.tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m mypy --platform linux
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=term-missing --cov-report=json:reports/phase-2-evidence/coverage.json --junitxml=reports/phase-2-evidence/python-tests.xml
.\.venv\Scripts\python.exe -m tools.generate_cli_docs --check
.\.venv\Scripts\python.exe -m build --no-isolation
.\.venv\Scripts\python.exe -m pip check
```

Full pytest includes the actual disposable Windows junction fixture, using the
access necessary to create it. No skip or weakened gate substitutes for that test.
Linux-target mypy checks types only; it does not claim Linux runtime qualification.

Python 3.12.14, jsonschema 4.25.1, pytest 8.4.2, pytest-cov 6.3.0, Ruff 0.13.3,
mypy 1.18.2, build 1.3.0, setuptools 80.9.0 and wheel 0.45.1 were reused locally.
Engine version remains unreleased 0.0.1; contract major is 1. No new downloads.
Pinned Blender 5.2.2 and Unity 6000.6.3f1 version evidence remains in Phase 1;
this phase invokes neither application.

## Artifacts and review

Evidence includes JUnit XML, coverage JSON, command logs, fresh offline install
logs, sample compiled scene/feature/coverage JSON, plan and committed inventory,
material invalidation and synthetic handoff results. Packaging creates a local
wheel and source archive in ignored dist/; no remote publication occurred.

[Independent review](review-phase-2.md) identified input/output overwrites and
missing appearance dependencies for sprite bakes. Both findings were reproduced
with failing regressions and fixed. Further regressions prove complete input
identity, frozen-brief mismatch refusal, correct Windows source excerpts,
malformed handoff refusal and rig-to-bake invalidation. No required finding is
deferred.

## Limits and next gate

- Known gameplay interfaces are BLOCKED; unknown features are UNSUPPORTED. All
  supplied arena requirements remain unimplemented/unverified and game PARTIAL.
- Source spans establish traceability. Unannotated/alphanumeric uncovered text
  remains unresolved; this is not natural-language completeness or evaluator
  approval. The brief freeze is development-owned, not protected qualification.
- No executable recipe workers, images, FBX, imported prefabs, gameplay, real
  application test XML, player build, manual play or hidden evaluation exists yet.
- Cache metadata is trusted-local evidence, not protected acceptance. Future
  workers must include actual executable/toolchain and validator versions. No
  producer currently writes eligible cache records.
- Per-file publication is atomic; a failed multi-file transaction can retain a
  PREPARING marker. Consumers must require the COMMITTED artifact inventory.
  Formal cross-application repair transactions are a later phase.
- TRUSTED_LOCAL remains disclosed with isolation_verified=false. Untrusted
  sandbox execution, platform qualification and measured runtime estimates remain
  unavailable; none becomes PASS from pure contract checks.

Next: Phase 3 must generate three real Blender golden fixtures, register five
working recipes, demonstrate parameterized reuse and reject invalid geometry/
expansion limits on the pinned toolchain. Stop at the Phase 2 boundary.

Original DOCX SHA-256 remains
`9d92fea8880b03b6d00e0bbe69b6fb8c1bf3f22f4c1ff16c1de7ae1f42970505`.
