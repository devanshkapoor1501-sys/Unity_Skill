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

## Next phase

Phase 1 remains NOT_RUN. No Blender or Unity generation has been attempted.
