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

Phase 2 is next. No Blender geometry or Unity game project has been generated.
