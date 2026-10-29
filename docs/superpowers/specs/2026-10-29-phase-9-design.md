# Phase 9: supervision, diagnosis and verified recovery

Status: approved by the user and implemented. Qualification and limits are
recorded in [the Phase 9 report](../../../reports/phase-9.md).

## Authority and intended outcome

Implement only Phase 9 of the approved root v5.1 blueprint, Section 12,
Chapters 16–18 and Appendix E.2. Retain the original v4 Phase 9 functional
gates, including twelve cross-application defects. Baseline is commit
`78f67b32b00f7f8dea57f7ce7acf08185d00c3aa`; Phases 0–8 remain intact.

The outcome is an inspectable production/review/recovery path: corrupt or
unapproved candidates cannot enter Unity; a supervisor cannot overrule a
failed gameplay oracle; managed repairs either pass their declared checks or
restore the observed pre-repair application state. A failed restore is explicit
and blocks further automatic changes. Phase 10 host packaging is out of scope.

## Existing implementation and gaps

- `workforce/workers.py` seals artifact hashes and reruns registered technical
  inspection before accepting its receipt. Phase 9 must preserve this property.
- `workforce/permissions.py` gives inspectors no candidate writes. These are
  engine authorization rules, not an OS sandbox or hidden evaluator boundary.
- `unity/repairs.py` handles eight static-binding categories, with two attempts
  per recorded symptom. These categories are not the eight cross-tool
  playbooks required by Phase 9.
- `unity/transactions.py` snapshots a fixed managed subset. It does not yet
  capture all registered Blender sources, sidecars and gameplay inputs, or
  expose crash-resumable application-aware rollback through the CLI.
- Static recovery reimports through `PolyForgeBuilder.ReimportBatch` and checks
  native bindings. It does not rerun gameplay or reconstruct after a crash
  between byte restoration and reimport.
- The arena independently checks seven scenarios, keyboard controls and two
  injected mutants. Four additional independently scored mutants are needed.
- `resume` and `repair rollback` are advertised as unimplemented Phase 9
  commands. Their final behavior must be explicit and tested.

## Approach

Extend these existing flows. Use the standard library, current JSON Schema
validation, registered Blender workers and native Unity APIs. Do not add a
second scheduler, arbitrary patch executor, model SDK or dependency.

Alternative: a separate generic repair service would duplicate leases,
subprocess ownership and workspace policy. Alternative: label-only review
reports would be smaller but would not enforce promotion. Both are rejected.

## 1. Review board and promotion

Add a small `polyforge/review` package and versioned request/receipt schemas.
The board runs brief-compliance, asset/animation, Unity-import, gameplay and
performance checks appropriate to the task. A release supervisor consolidates
these results; it cannot alter an inspector's evidence or verdict.

Each review binds the exact candidate digest, revision, frozen original brief,
approved amendments and evidence-file hashes. Record `authored_by`,
`reviewed_by`, `evaluator_owner`, tool identity, read/write scope, applicable
gate, verdict and unresolved risks. Reviewers cannot author their candidate or
grant themselves additional authority through request metadata.

Keep three approvals separate:

1. Technical: registered checks execute successfully against the sealed bytes.
2. Subjective: an explicitly supplied human decision binds this revision and
   scope. Missing required approval remains REVIEW; an assistant role or a
   screenshot cannot silently create human approval.
3. Gameplay: tests and original-brief requirements have their own veto. Same-host
   public checks remain identified as PUBLIC_DEVELOPMENT. A separately owned
   hidden evaluator remains EXTERNAL_NOT_SUPPLIED until actually available.

Promotion records are engine-generated attestations tied to recomputed checks,
not cryptographic proof of an external identity. Caller-authored `APPROVED`
JSON is insufficient. Rejected, changed, missing, stale or incomplete evidence
denies promotion before the importer writes. Apply this gate to model/material,
animation and sprite integration; retain existing command compatibility.

Inspectors read only declared sealed candidate/evidence paths through bounded
read interfaces. Evaluator-only paths are denied by engine policy. Reports
explicitly disclose that same-user local code is not physically isolated.

## 2. Brief-derived public acceptance

Freeze the original brief separately from the generator manifest. Use explicit
typed traceability rows: original phrase → required feature → semantic artifact
ID → native component/reference → named public oracle → hashed evidence.
Approved amendments are append-only records bound to the original brief.

For the supported arena, retain the original WASD, collision, patrol, health,
damage, thirty-second objective and R-restart obligations even if a modified
manifest omits one. Missing mechanics yield PARTIAL/REJECTED, never ACCEPTED.
Unknown prose or unsupported requirements require review rather than invented
natural-language understanding. A valid XML PASS must contain the exact test
identities and be accompanied by actual scored telemetry. Empty/fake PASS,
misleading clip names and supervisor approval do not satisfy these checks.

## 3. Forensic diagnosis and bounded repair routing

Extend diagnostics using eight typed playbooks:

| Playbook | Evidence and bounded action |
| --- | --- |
| GUID/reference | Observed native mappings; rebuild registered managed wiring |
| FBX axes/scale | Saved-source/export metrics versus imported dimensions; rebuild with registered export/import settings |
| Geometry | Actual geometry diagnostics; regenerate from a validated recipe |
| Unity API | Exact compiler version/message, package and assembly context; propose a reviewed registered correction or BLOCKED |
| Missing component | Native object/component observations; rebuild managed prefab/scene wiring |
| Sprite curve | Observed sprite local IDs and PPtr curve; rebuild through the registered sprite importer |
| Animation slot | Actual action-slot/channelbag and motion evidence; rebuild through the registered slotted-animation worker |
| Worker timeout | Owned process evidence and budget; bounded retry only when safe, otherwise escalate |

Structured results take precedence over log heuristics. Classify missing tool,
contract violation, exporter/importer discrepancy, runtime mismatch, gameplay
failure and subjective review in that order. Generic null-reference text cannot
establish a unique root cause. Novel API/context/mode, Editor/runtime assembly,
domain-reload and missing-package failures remain distinct hypotheses with
falsifying checks. Do not auto-install packages or execute generated patches.

Each issue records evidence-DAG links, affected stable IDs, ranked hypotheses,
confidence, exact sanitized command/version/log excerpts, original specialist,
candidate revision, rejected alternatives, proposed changed paths, risk and
verification/rollback route. Record semantic before/after references alongside
byte hashes. Unknown/ambiguous causes produce a proposal or BLOCKED result.

Repairs use only registered actions in approved managed scope. Two proposals
per unique symptom maximum; repeating the same failed signature escalates to
the supervisor/user. Count failures durably across crash/resume. A plan cannot
authorize a different symptom, candidate, manifest, file set or arbitrary code.

## 4. Transaction and recovery

Extend `ManagedTransaction` and existing repair dispatch. Use one physical
project lock and the existing idle-Editor check for all project mutation paths.
Before mutation, compute the affected registered dependency closure and
snapshot managed manifest/recipes, Blender sources/exports/sidecars, generated
Unity assets and metadata, packages/settings, game/animation/sprite inputs and
provenance. Exclude arbitrary user files and Unity Library caches.

Record a snapshot manifest with exact hashes and immutable pre-repair native
bindings, semantic IDs, object counts, imported reference identities and scored
scenario results. Validate the entire snapshot before any restore write.

Journal states are PREPARED → APPLIED → VERIFYING → COMMITTED, or
ROLLING_BACK → ROLLED_BACK / ROLLBACK_FAILED. Keep compatibility when reading
older Phase 5 transactions without claiming that their static-only proof is a
complete Phase 9 proof.

After apply: invalidate affected owned cache entries, reimport through native
Unity APIs, and run targeted plus declared broad regression checks. Commit only
when measured checks improve the intended symptom without new regressions.
Record a minimal diff, path risk and before/after hashes/references.

After failure: restore registered source bytes, reimport from restored inputs,
rerun static bindings and the applicable original gameplay/animation/sprite
checks. Identity strings, GUIDs and counts compare exactly; existing 0.1 mm /
1 ppm numerical and scenario-specific physics tolerances remain explicit.
Matching bytes alone never prove restoration. A stale cache or crash between
restoration and reimport resumes in ROLLING_BACK and repeats the native proof.

`repair rollback --transaction-id` executes this recovery. `resume --run-id`
supports recoverable recorded transactions and registered stage/worker inputs;
it must reject unknown, stale, unsafe or unsupported run types with a precise
outcome rather than imply general resumption. Do not rerun committed side
effects without validating durable receipts. ROLLBACK_FAILED quarantines the
affected transaction/project from further automatic mutation until explicit
successful recovery, preserving forensic evidence.

## 5. Qualification fixtures

Keep the existing collision and restart mutants. Add win-condition, damage,
patrol/navigation and input mutants, with separate native test identities and
independently scored observed traces. An executed faulty trace must fail the
corresponding oracle; missing/malformed mutant telemetry is a failed gate, not
a killed mutant. Preserve nominal traces and all negative verdicts.

The twelve-defect pack covers stale GUID, wrong axes/scale, degenerate geometry,
Unity API mismatch, missing component, wrong sprite curve, broken action slot,
owned timeout/crash, swapped material, misleading clip, missing required
mechanic, and misleading PASS evidence. Record detection separately from
validated repair; unsupported automatic repair stays explicitly BLOCKED.

Additional tests cover attractive-but-wrong gameplay, supervisor/verifier veto,
reviewer self-approval/write denial, hidden-path denial, stale review receipts,
attempt exhaustion, concurrent write races, crash recovery, corrupted snapshot,
stale import cache, package/assembly/context diagnostics and original-project
non-mutation. Native rollback must demonstrate both restored success and
ROLLBACK_FAILED when invariant restoration cannot be proved.

## Delivery and quality bar

Run unchanged Python and Phase 6 native baselines before product changes.
Write failing boundary/recovery tests first, then implement in small slices.
Keep the existing >=90% contract/security coverage gate and include the new
trust/approval contracts. Run old/new offline tests, real Blender and native
Unity static/arena/animation/sprite regressions, lint/format, strict Windows and
Linux target types, CLI docs, package builds and fresh offline install checks.
Use one fresh whole-phase code review and verify all required fixes.

Keep an execution ledger and `reports/phase-9.md`, raw command logs, immutable
negative fixtures, candidate/review/repair journals and a hash-indexed evidence
bundle. Update public claims only to executed support. Report operation, test
and game status separately. No hidden-evaluator, aesthetic, standalone,
performance, host-delegation or OS-sandbox PASS without its own real evidence.

Implementation stays in the user-selected checkout on a Phase 9 feature branch;
do not create a large duplicate Unity worktree. Git changes need the current
environment's approval mechanism. Publication is covered by the existing user
instruction to commit/push completed phases and verify GitHub CI, but occurs
only after local qualification. Stop at Phase 9's acceptance boundary.
