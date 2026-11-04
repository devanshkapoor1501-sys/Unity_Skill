# Phase 11 final branch scoped re-review

Disposition: **both confirmed P2 findings from final-branch-review.md are resolved. No new actionable finding was confirmed in this scoped re-review.**

Read-only review of corrected package-resolution reporting, benchmark repetition scheduling, directly related tests, and the platformer EditMode inspection correction. No runtime/product test edits, Unity/Blender launches, full-suite execution, commits or pushes were performed. This report is the only new authored file; test runners used fresh owned scratch directories.

## Confirmed fixes

1. `polyforge/inspection.py` now bounded-loads a present `Packages/packages-lock.json` through the existing strict JSON reader (1 MiB plus sentinel, duplicate/nonfinite/nesting error handling). It reports requested manifest versions separately from `resolved_packages`, preserving transitive package versions. Missing lock evidence is explicitly `package_resolution=NOT_AVAILABLE`; present observed lock data is labeled `OBSERVED_LOCK_DATA_ONLY`. Invalid lock shape or missing/nonstring/blank resolved versions raise structured `InputError`. The original requested1.0/resolved1.1/transitive2.0 counterexample now passes its expected-output assertions. This is static metadata observation, not an assertion of installed/runtime compatibility.

2. `polyforge/benchmark/runner.py` now derives the default seed schedule from the frozen `runs_per_task_arm` count (deterministic seeds starting at 42). An explicitly supplied seed schedule must have exactly that count and remains subject to bounded integer/uniqueness checks before output creation. The bundled 12-task, five-repetition suite now plans 60 cases. Focused adapter fixtures explicitly declare their intended smaller repetition counts instead of silently overriding the suite.

3. The revised `unity_package/Tests/PlatformerEditor/PlatformerTests.cs` inspection test no longer calls `PlatformerBuilder.Build`. It opens the already delivered scene, verifies session input/scene bindings against the supplied request, retains its existing structural checks, and compares the final scene file hash to the initial scene hash. Source review confirms the specific rebuild call reported by root is absent. Native RED/GREEN execution and rollback qualification remain root's responsibility; this reviewer did not run native tests or claim their result.

## Fresh verification

Original reviewer regressions, unchanged:

```powershell
.venv/Scripts/python.exe -m pytest .tmp/phase11/final-branch-review/test_review_findings.py --no-cov -q --basetemp=.tmp/phase11/final-branch-review/rereview-pytest
```

Observed **2 passed in 0.82s**.

Direct fix regressions:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_phase11_inspection.py tests/test_phase11_benchmark.py --no-cov -q -k 'requested_and_resolved_package_versions_include_transitive_dependencies or malformed_resolved_package_metadata_is_rejected_without_writes or missing_package_lock_is_explicitly_unobserved or default_run_schedules_every_declared_repetition or explicit_seed_schedule_cannot_silently_omit_declared_repetitions' --basetemp=.tmp/phase11/final-branch-review/rereview-contracts
```

Observed **11 passed, 197 deselected in 6.19s**. This covers malformed lock variants, missing-lock evidence, resolved/transitive output, retained default repetitions, and rejection of partial explicit schedules without writes.

This scoped approval closes the two prior product findings; it does not replace final frozen full-suite/coverage/native/reproducible-build/install/CI evidence or resolve explicitly unavailable independent evaluator/model/holdout release requirements.

