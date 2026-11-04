# Phase 11 inspection / benchmark boundary review

Date: 2026-11-01. Read-only source review of current uncommitted Phase 11 slices on `codex/polyforge-phase-11`.

Verdict: request changes for four confirmed correctness/resource-boundary gaps below. No runtime source, scoped product tests, native project, commit or push was changed. Review-only fixtures are under `.tmp/phase11/boundary-final-review/`.

## Confirmed findings

1. **[P2] Bound metadata reads at the actual read, not only at inventory time.** `polyforge/inspection.py:112-116` uses the inventory size to permit metadata analysis, then calls unbounded `Path.read_bytes()`. If a serialized asset grows after inventory, it is fully loaded before the hash mismatch is rejected. The reproduction grows `Assets/Thing.mat` from 10 bytes to 2,097,152 bytes immediately after the initial inventory, calls `inspect_project(..., max_file_bytes=1_048_576)`, and observes a complete 2,097,152-byte metadata read. The eventual InputError is correct, but occurs after bypassing both the advertised 1 MiB metadata read limit and caller's 1 MiB file budget. An arbitrarily larger concurrent file can consume memory first. Use a bounded read of at most the effective metadata/file limit plus one byte, then reject size/identity/digest mismatch. Repro: `test_metadata_read_stays_bounded_after_inventory_race`.

2. **[P2] Apply directory limits while discovering children.** `polyforge/inspection.py:31-40` checks the directory count only when popping a directory from `pending`, while a single `scandir` queues every child directory first. With `max_files=2`, a root containing 20 empty subdirectories consumes all 20 entries and queues all 20 before rejecting. Thus the nominal directory budget does not bound directory enumeration work or pending-list memory on a wide project tree. Check discovered directories (visited plus queued), or an explicit total entry budget, before appending each child. Repro: `test_wide_directory_inventory_stops_at_declared_budget` (20 entries observed where at most 2 were expected under this limit).

3. **[P2] Validate retry observations with the other integer counters.** `polyforge/benchmark/metrics.py:42-51` validates tokens/tool_calls/interventions but omits `retries`; `polyforge/benchmark/runner.py:57-66` then accepts a negative retry value as below the declared cap. A trusted protocol adapter reporting `tokens=1`, `tool_calls=1`, `retries=-1` under a frozen retries budget of zero gets a FINISHED PASS, `task_success=True`, and accepted-game numerator 1. This is a malformed usage observation, independently of the expressly declared/unauthenticated evaluator boundary. Add retries to finite, nonnegative integer validation; retain malformed observations as a failed adapter attempt rather than valid success. Repro: `test_invalid_retry_observation_cannot_be_accepted[-1]`. The 0.5/True cases in the scratch parametrization pass because budget zero separately rejects their positive values, not because retry types are validated.

4. **[P2] Measure elapsed time through the successful evaluation boundary.** `polyforge/benchmark/runner.py:60` freezes `duration_seconds` before `evaluator.grade()` at line 85, and the success path returns at line 102 without updating it. A deterministic monotonic-clock reproduction runs generation until t=0.1, completes successful grading at t=10.0, and reports an accepted attempt duration of 0.1 seconds. Failed evaluator/timeout exceptions instead reach line 124 and include grading time, so successful and failed attempt distributions are also inconsistent. This understates the promised time-to-accepted / accepted-only durations and cost/time comparisons. If grading is intentionally outside the producer wall deadline, document/report separate generation and evaluation times; still record total observed time through acceptance consistently. The existing 1-second budget also does not observe this successful evaluation delay; whether that delay should fail the producer budget is a separate policy decision. Repro: `test_duration_includes_time_until_acceptance`.

## Reproduction and verification

Scratch tests: `.tmp/phase11/boundary-final-review/test_boundary_review.py`.

Command (workspace root):

```powershell
.venv/Scripts/python.exe -m pytest .tmp/phase11/boundary-final-review/test_boundary_review.py --no-cov -q --basetemp=.tmp/phase11/boundary-final-review/fixtures
```

Observed: **4 failed, 2 passed in 2.52s**, corresponding to the four findings. No full suite or native process was run. Fixtures import existing public test helpers only to construct a configured public suite and explicitly artificial adapters; these are fault reproductions, not model benchmark trials or independent evaluator evidence.

## Review coverage and limits

Reviewed `polyforge/inspection.py`, its scoped tests, `polyforge/benchmark/{tasks,metrics,analysis,runner}.py`, `tests/test_phase11_benchmark.py`, the Tree-sitter dependency line in `pyproject.toml`, current Phase 11 design, and relevant blueprint sections 863, 875-878, 1199-1226 and 1443-1529.

The implementation explicitly preserves the trusted injected-Python protocol boundary, declared evaluator/provider identity limits, no source execution, static C# CST/Python AST parsing, unknown semantic compatibility, separate six-class metrics and complete-game denominators, frozen suite/brief/configuration digests, HTML escaping, and imported acceptance marked DECLARED_NOT_AUTHENTICATED. Current checkpoint recovery verifies committed byte-prefix hashes, retains uncommitted STARTED execution as censored, refuses credit for uncommitted FINISHED success, and marks recovery REVIEW. No new confirmed issue was found in those mechanisms during this pass.

Existing reported 95 benchmark / 42 inspection passing checks and coverage were not rerun here; those results belong to the slice implementers. This review did not assess independent held-out evaluation, provider authentication, OS isolation, native project correctness, generalized arbitrary-game capability, or other concurrently edited Phase 11 files. No such unavailable evidence is demanded before these reversible tooling corrections.

## Scoped fix re-review — 2026-11-01

**Disposition: all four reported P2 product issues resolved. No new load-bearing finding within this scoped re-review.**

Inspected only the changed inventory-discovery / metadata-read boundary, retry counter validation, final elapsed-time / wall-budget path, and directly related regression tests. Directory discovery increments/checks its budget before enqueueing each child. Serialized metadata now uses `open("rb").read(1_048_577)` and rejects size/digest mismatch. Retries participate in finite, nonnegative integer validation. A `finally` block records complete execution-plus-evaluation elapsed time on every exit and removes success / sets censored failure on an end-to-end wall overrun.

Original six-case scratch file rerun unchanged, with fresh `recheck-fixtures` basetemp: **5 passed, 1 scratch-test failure in 2.01s**. The sole failure is an obsolete implementation-specific spy: `test_metadata_read_stays_bounded_after_inventory_race` wraps `Path.read_bytes`, an API the fix correctly removed. The expected changed-before-metadata InputError occurs, but its spy captures no calls and `max([])` raises ValueError. This is not a remaining product defect. The original scratch file remains unchanged as requested.

Verified the replacement bounded read with the added regression that spies on actual stream consumption, plus the discovery and neighboring retry/evaluation-boundary tests:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_phase11_inspection.py tests/test_phase11_benchmark.py --no-cov -q -k 'growing_metadata_cannot_exceed_static_read_budget or wide_directory_scan_rejects_at_discovery_budget or retry_observations_require_bounded_nonnegative_integers or huge_retry_integer_is_a_typed_observation_error or malformed_adapter_retries_are_failed_attempts or attempt_elapsed_time_and_wall_budget_include_evaluation' --basetemp=.tmp/phase11/boundary-final-review/fix-regressions
```

Observed: **27 passed, 137 deselected in 8.40s**. This includes negative/boolean/fractional/nonfinite/oversized retry observations and evaluator accepted/rejected/blocked/timeout/exception exits both within and beyond the wall limit. The bounded metadata probe confirms actual consumption never exceeds 1,048,577 bytes after the growth race. No native run, full suite, runtime source edit or scoped test edit occurred during re-review; only this report appendix was written.
