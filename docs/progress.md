# Execution ledger — PolyForge approved implementation sequence

Plan: docs/implementation-plan.md. Spec: original corrected v4 blueprint at root.

## Rulings

- Work in the explicitly requested folder. It had no existing application or Git
  repository; initialize codex/polyforge-phase-0 rather than create a second checkout.
- Stop after Phase 0 as required by the approved phase-boundary rule. Later phases
  retain their plan and are not misrepresented as completed.
- Materialize functioning packages and owned root directories now; future adapters
  will be added with their phase tests rather than empty executable placeholders.
- Use one real offline metadata-validation capability for protocol acceptance;
  example robot descriptors do not enter the available capability catalog.
- Unimplemented commands return NOT_RUN/5, not PASS or a fake dependency result.
- Python dependency downloads explicitly approved in chat. Use project-local temp
  files because the execution sandbox's default temp path denied writes.
- Do not create hidden task identities locally: external evaluator ownership is
  required. The public arena fixture has an actual frozen brief hash and no rubric.

## Phase 0 work

- Tests written and observed failing before the runtime package existed.
- Foundation implemented: packaging, command grammar, schemas, model-free registry,
  typed context/result and evaluator interfaces, examples, docs, skill scaffold, CI.
- Initial dependency setup failed on temp permissions, then DNS/metadata failures.
  Known stable versions were provisioned from official PyPI and pinned with their
  resolved dependencies. pip check passes; no gate was waived.
- Initial full suite: 27 passed; contracts/security branch coverage 100%.
- Independent read-only review found decoder exceptions, option abbreviation/
  output-mode inconsistency, and regex end-anchor acceptance of trailing newlines.
  Each finding has a reproduced failing test and a passing focused regression.
  No review findings were deferred; future application execution was correctly
  excluded from this foundation review.
- Final suite: 33 passed; security/contracts statement and branch coverage 100%.
- Ruff check/format, strict mypy, CLI documentation, dependency consistency and
  wheel/sdist builds pass. Fresh isolated editable and wheel installations pass
  without network access, including actual console commands outside the checkout.
- Phase 0: complete. Evidence is in reports/phase-0.md and reports/evidence/.

## Phase 1 work

- User continued Phase 1. Existing branch/checkout reused; Phase 0 baseline had
  33 passing tests. No additional dependency downloads were needed.
- Config/path/policy, durable state/locks, native owned process runner, workspace
  init, doctor/status/report implemented in tested slices.
- Actual version probes passed for Blender 5.2.2 and Unity 6000.6.3f1. The initial
  Unity PATH candidate was a different CLI; conventional installed Editor roots
  now precede PATH and explicit overrides still win.
- Real worker tests cover secret env filtering, timeouts, cancellation, output
  caps and descendant cleanup. Real Windows junction rejection passed with the
  access needed to create a disposable test junction; the default sandbox denied
  junction creation. No test was skipped to satisfy the gate.
- Ruling: manifest validation is Phase 2 despite the older Phase 1 deliverable
  summary; CLI producer resume scheduling is Phase 3. Library journal recovery
  and retry budgets work now. Neither future command claims to have executed.
- Ruling: Windows Job Objects enforce resource/process ownership without claiming
  filesystem/network containment. Untrusted workflows stay denied. POSIX runtime
  and memory enforcement claims remain unverified on this Windows host.
- Independent review identified truncated/quoted credential redaction and invalid
  static project metadata. Failing regressions were added and fixes passed.
- Observed transient Windows atomic-replace denial now has two bounded retries
  and a permanent-denial regression preserving the old file and durable events.
- Phase 1 complete: full suite 66 passed, no skipped junction test; security/
  contracts coverage 97.79%. Ruff, format, strict Windows/Linux target mypy,
  package builds, dependency/CLI docs checks and fresh offline editable/wheel
  installs (including installed init and doctor dry-run) passed.
- Exact evidence is under reports/phase-1-evidence/ and reports/phase-1.md.
  No remote CI or public publication is implied.

## Phase 2 work

- User continued Phase 2. The existing checkout and installed dependencies were
  reused. No new network access, Blender worker or Unity project was required.
- Added strict v1 manifest/recipe/scenario schemas, canonical serialization,
  global IDs, reference/path/budget checks and deterministic dependency ordering.
- Added pure scene/feature/coverage compilation with source ranges, stable graph
  bindings and DEVELOPMENT_ONLY authority. Known future producers stay BLOCKED,
  unknown features UNSUPPORTED and every game PARTIAL. Public stealth/dungeon
  fixtures are development probes, never evaluator holdouts.
- Added S0–S5 DAGs with scoped local/transitive input hashes, artifact-verified
  cache lookup and explicit NOT_RUN execution. No measured seconds or completed
  producer output is invented. Material/texture edits preserve mesh/export and
  gameplay-code fingerprints; rig/appearance edits invalidate dependent bakes.
- CLI validate is read-only; compile-contract/plan publish under a planning lock
  with an original-brief freeze, atomic JSON and artifact hashes. Dry runs and
  invalid input write nothing. Pure catalog operations remain JSON-in/JSON-out.
- Synthetic handoff invariants produce evidence graphs and retain NOT_RUN
  application execution. Scenario and external evaluator interfaces stay separate.
- Ten named static good/bad manifest fixtures and additional adversarial tests
  cover unsafe paths, cycles, duplicate IDs, invalid numeric data, missing
  references, unsupported mandatory features, stale cache and frozen input edits.
- Independent review found input/output overwrites and omitted appearance
  dependencies for sprite bakes. Both were reproduced RED, fixed and verified
  GREEN. Input identity now covers recipe/brief/file inputs too. Windows LF
  initialization has a reproduced source-offset regression and verified fix.
- Ruling: source-range coverage is conservative traceability, not NLP completeness
  or evaluator acceptance. Future worker tool fingerprints and actual cache
  producers belong to their integration phases; no current cache evidence claims
  execution. Multi-file publication uses a COMMITTED inventory marker; failed
  PREPARING output is not a committed contract set.
- Acceptance evidence is in reports/phase-2.md and reports/phase-2-evidence/.
- Phase 2 complete: 94 tests passed with no skips; security/contracts coverage
  96.31% combined and 93.57% branches. Ruff, strict Windows/Linux target mypy,
  CLI documentation, dependency/package checks, fresh offline editable/wheel
  installs and a seven-command actual workspace smoke workflow all passed.

## Phase 3 work

- User continued Phase 3 on the existing branch and installed toolchain. No
  downloads or new runtime dependencies were needed.
- Added five reusable static families with bounded primitive DSL expansion,
  deterministic seed, parent/socket attachments, materials, UVs and base pivots.
- Added owned background Blender worker with pinned version precheck, actual
  editable source roundtrip, geometry diagnostics, logical payloads and artifact
  hashes. Source frames and socket spaces are explicit.
- Added CLI build through S0/S1/S2 and five executable mesh capabilities. All
  effective overrides/config validate before publication; invalid and dry runs
  write nothing. Later stages still return NOT_RUN. No game is accepted.
- Real golden/reuse tests passed after identifying LTS version-label suffixes,
  retained palette resources and nondeterministic sphere face ordering. Geometry
  hashes now canonicalize oriented face coordinates/UVs, preserving winding.
- Actual saved-source probes detect missing UV, collapsed faces, reversed sockets,
  polygon budget violations, translated roots, shifted geometry and changed units.
- Independent review found material override preflight, unmeasured pivots and a
  valid output exceeding the input JSON budget. Each has RED/GREEN regression
  evidence; logical output reads have a distinct bounded 32 MiB limit while user
  input JSON remains 1 MiB. Root/units and base bounds are measured after reload.
- Ruling: generic resume scheduling remains NOT_RUN until managed retry/repair
  transactions in Phase 9. The normative Phase 3 gate is static generation;
  earlier provisional CLI phase numbering is corrected rather than advertising
  unsafe partial resume. Existing library journal recovery remains functional.
- Ruling: builds generate fresh immutable run outputs and do not populate the
  planner cache. Logical repeatability is demonstrated by actual regeneration,
  not claimed from cache equality. Cross-app/game geometry features stay blocked
  until Unity binding evidence exists.
- Final phase verification is recorded in reports/phase-3.md and phase-3-evidence/.
- Phase 3 complete: 107 offline tests and 4 real Blender tests passed with no
  skips. Security/contracts plus recipe DSL coverage is 94.99% combined and
  91.43% branches, with the unchanged 90% gate extended to the new module. Ruff,
  typing, package/resource checks, fresh offline editable/wheel installs and real
  installed-wheel generation passed. Three golden fixture types repeat logically;
  wall/door connectors align; all seven saved-source fault probes are rejected.

## Phase 4 work

- User continued Phase 4 after uploading the completed Phase 0–3 history. Existing
  checkout and pinned dependencies were reused; no new downloads were required.
- Added fixed CPU audit cameras, transparent RGBA views, bounded independent PNG
  checks and a local review bundle. Artistic quality remains REVIEW.
- Added static geometry/transform/UV/material/socket diagnostics with module-level
  origins, selected FBX, material/handoff sidecars and Blender FBX roundtrip.
- Added managed saved-source audit, immutable copies, input/output artifact hashes
  and manifest export bindings. Config/effective recipes and preview limits
  validate before writes; S4/S5 remain unavailable.
- Independent review found failed-S3 source selection, preview budget preflight
  and unused palette/FBX mismatch. All have RED/GREEN regressions. Malformed
  metadata, pixel corruption, source hash changes and synthetic handoff defects
  are also checked. No required finding is deferred.
- Ruling: Blender FBX roundtrip validates source-side interchange only. Actual
  Unity axis/scale/material verification remains NOT_RUN until Phase 5. Intended
  importer settings are metadata, not a passing Unity claim. Collider intent is
  retained separately from unexecuted physics evidence.
- Ruling: palette sidecars retain unused editable materials; FBX checks require
  only used materials. Color/metallic/roughness are supported, while texture
  interchange requests explicitly remain NOT_RUN rather than silently ignored.
- Final acceptance evidence is recorded in reports/phase-4.md and phase-4-evidence/.
- Phase 4 complete: 118 offline tests and 9 actual Blender tests passed, with no
  skips in either executed gate. Coverage is 95.74% combined and 92.86% branches;
  the new PNG module is fully covered. Lint, format, strict typing, package/CLI
  checks and 32 fresh offline install commands passed, including installed-wheel
  S3 execution. Three golden assets retain twelve checked views and exact hashes.

Phase 5 is next: native Unity import and scene construction. Game remains PARTIAL.
