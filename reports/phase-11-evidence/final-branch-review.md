# Phase 11 final branch review

Read-only review against base `31827d134102650604aaa0998c0d06d6f4a579c3`, including tracked changes and untracked product/test files. Runtime/native sources remained frozen: no product/test edits, Unity/Blender launches, full-suite execution, commits or pushes were performed by this reviewer. Only this report and isolated scratch fixtures/probes were written.

## Verdict

Request changes for the two reproducible P2 findings below. No additional high-confidence P0/P1 defect was confirmed. This verdict concerns the implemented tooling; it is not approval of Phase 11 release qualification.

## Findings

1. **[P2] Inspect and expose resolved package versions, including transitive packages.** `polyforge/inspection.py:387-395` reads only `Packages/manifest.json`. The approved design explicitly requires requested/resolved version reporting. A project declaring direct package `com.example.direct=1.0.0`, with `packages-lock.json` recording direct resolution `1.1.0` and transitive `com.example.transitive=2.0.0`, returns PASS and reports only the requested direct version. Neither resolved version nor transitive package identity appears anywhere in the analysis; the lock only appears as an opaque inventory hash. Replacing the lock with invalid JSON also returns PASS without an incompleteness observation. Consequently inspection cannot distinguish requested constraints from the resolved dependency graph or report malformed resolution metadata. Parse a present lock through the same bounded non-executing data boundary, expose requested and resolved values distinctly, retain transitive dependencies, and mark missing/malformed resolution evidence explicitly rather than silently implying a complete version observation. Scratch regression: `test_static_inspection_reports_resolved_package_versions`.

2. **[P2] Honor the suite's declared repetitions in the default benchmark run.** `polyforge/benchmark/runner.py:154` defaults to the single seed `(42,)`, and lines 194/217/245 plan and emit only that seed; `runs_per_task_arm` is validated and frozen but never used by the runner. The bundled suite declares five repetitions per task at `polyforge/data/benchmark-core/suite.json:186`, yet the normal CLI/default API invocation plans only 12 cases instead of 60. The remaining 48 declared trials do not receive BLOCKED/NOT_RUN rows, so the suite's declared sampling plan and retained attempt inventory disagree even before adapters are available. Generate/freeze a deterministic default seed schedule of the declared length, or require an explicit correctly sized schedule; if a deliberate partial run is supported, preserve the missing planned repetitions and label the partial execution. Scratch regression: `test_default_suite_run_preserves_declared_repetition_count`.

## Reproduction

Command from workspace root:

```powershell
.venv/Scripts/python.exe -m pytest .tmp/phase11/final-branch-review/test_review_findings.py --no-cov -q --basetemp=.tmp/phase11/final-branch-review/pytest
```

Observed **2 failed in 1.29s**, both assertion failures reproducing the findings. These are scratch contract regressions, not modified repository tests. The accompanying `reproduce.py` confirms:

- Valid requested/resolved lock fixture: PASS, only `{"com.example.direct":"1.0.0"}` in `packages`, no resolved/transitive information.
- Malformed lock fixture: PASS with no lock diagnostic.
- Bundled suite: declared repetitions 5, task count 12, default planned cases 12, expected declared plan 60.

## Review evidence and limits

Reviewed the Phase 11 design/plan, implementation-plan authority, the tracked integration diff, and principal new inspection, benchmark orchestration/reporting/metrics/task contracts, platformer compiler/native runtime/tests/physical oracle, profiling/provenance/process-counter paths, workforce sealing/inspection/recovery, packaging helper/CI, support documentation and work-in-progress report. Prior independent scoped reviews were used as supporting evidence for already reviewed boundaries.

The registration report records all its archive/sealed-delivery findings resolved. Current performance code freezes the registered payload records and compares the current payload under the project lock; native counter state is explicitly declared for cross-platform typing, and evidence reads revalidate workspace paths. The inspection/benchmark boundary report records its bounded reads/discovery/retry/end-to-end timing findings resolved. No unchanged prior finding is repeated here.

Root reports the later full offline run at 1,133 passing cases with one stale catalog expectation subsequently passing its targeted correction, and 93.44% combined / 90.056% branch coverage. Those are root-supplied results, not rerun by this reviewer. Final frozen complete qualification, native recovery terminal evidence, package/install evidence and exact remote CI still require the coordinator's final evidence disposition.

`reports/phase-11.md` explicitly says IN_PROGRESS and identifies its earlier counts as distinct non-final runs; its remaining-work list is not a final release claim. Independent evaluator/model/hidden-holdout evidence remains explicitly BLOCKED/NOT_RUN; neither same-host roles nor availability ledgers establish stable core v1 or general game-production capability. No finding is raised merely because those external identities are unavailable.
