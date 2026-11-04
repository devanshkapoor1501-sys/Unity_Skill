# Phase 11 standalone profiling review and fix round

## Confirmed findings before fixes

1. P1: terminal resource peaks were lost (metrics.py original lines 124-126, processes.py original lines 172-193). The runner waited before final observation, and observation skipped exited processes. Mocked probe: live peak 536870912 bytes, terminal peak 3221225472 bytes, then exit. Recorded peak remained 536870912 and the scorer returned PASS.
2. P2: final fatal observations did not fail the outcome (processes.py original lines 189-196, performance.py original lines 148-157). A mocked normal run detected birth identity change only in finish: observer fatal=True, identity CHANGED, error recorded, outcome reason exit, score PASS.
3. P2: malformed process/hardware fields passed (performance.py original lines 105-112 and 148-157). Return code false, CPU/GPU/driver arrays/objects, CPU count true, RAM -1 scored PASS. Float/bool aliases for integer profile fields also passed.

Pre-fix focused performance file: 75 passed in 14.95s. Review probes mocked process/native API boundaries. The receipts provide trusted-local hash integrity, not authentication against a malicious workspace owner. No native acceptance was inferred.

## Implemented changes

- polyforge/runner/metrics.py: ProcessCounters opens one native process handle, verifies creation time, retains it for live/final RSS and CPU reads, and closes it on constructor failure and observer finalization. The existing one-shot process_counters API closes its own handle. Final reads neither reopen by PID nor require the process to remain alive. Fatal state is persisted.
- polyforge/runner/processes.py: fatal failure discovered by finish changes an otherwise successful exit to observation_failure.
- polyforge/unity/performance.py: validates PID, bounded positive Windows FILETIME birth token, bound identity, native resource source, explicit nonfatal/error-free observation, integer exit code, typed nonempty hardware names, positive integer CPU/RAM values, and integer resolution/pacing/frame counts. Unknown CPU stays None; GPU utilization stays UNKNOWN.
- tests/test_phase11_performance.py: covers retained-handle terminal RSS/CPU, final memory/birth errors, cancellation/interruption/start/launch/write cleanup, malformed hardware/process/scalar evidence. Existing observer policy tests now mock the retained reader boundary. The old post-read PID-requery test now asserts malformed readiness cannot erase a snapshot from a birth-bound handle; separate tests verify that handle's creation token directly.

TDD evidence: 18 new resource/shape cases failed before fixes then passed; 2 final failure propagation cases failed before runner fix then passed; 5 integer aliases failed before validation then passed; 2 malformed birth tokens failed before their bounded guard. Lifecycle tests assert one native handle opened and closed, including failure paths.

## Verification and limits

Final focused run: 138 passed in 31.21s across tests/test_phase11_performance.py, tests/test_phase1_runner.py, tests/test_phase1_review.py, tests/test_phase1_failures.py, tests/test_phase7_review.py. Ruff passes all four assigned files. Mypy passes all three assigned source modules. Targeted git diff --check passes.

Only bounded owned Python subprocess tests and mocked Win32 API tests were executed. No Unity/native player, full suite, C# changes, source outside the four assigned files, or commit. Native focus/rendering gates were not weakened. Parent/root owns native validation and independent final review. Since the reviewer implemented the fixes, this report is not independent approval of those fixes.
