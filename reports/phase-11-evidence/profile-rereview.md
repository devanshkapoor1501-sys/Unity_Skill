# Phase 11 independent performance re-review

Read-only source review of `polyforge/runner/{metrics,processes}.py`, `polyforge/unity/performance.py`, and `tests/test_phase11_performance.py`. No source edits, full-suite run, commit, Unity/native launch, or demo/project/process manipulation. Scratch probes and this report are the only authored files.

## Confirmed findings

1. **P2 — Freeze the registered payload identity rather than a later fresh snapshot.** `performance.py:398-414` validates `_registered_player` before acquiring the project lock and later computes independent executable/package fingerprints. An executable or DLL changed between successful registration validation and fingerprint capture becomes the accepted baseline. Checks at lines 441 and 507 compare with that changed baseline, so they never detect its difference from the registered build. Deterministic probe wraps `_registered_player`, allows its real validation to finish, then changes `UnityPlayer.dll`; only the process boundary is mocked. All three profile samples run and the result is `PASS`, although calling the original `_registered_player` afterward rejects the payload. This is a concrete validation-to-freeze race, not a claim of authentication against a malicious workspace owner. Acquire the project lock before provenance validation/freeze, and obtain or cross-check frozen records against the exact payload that passed registration instead of blessing a subsequent independent snapshot. Add the boundary regression before freezing sources.

2. **P2 — Linux type-check qualification currently fails for the retained-counter implementation.** Root-supplied fresh `.tmp/phase11/final-types-linux.txt`, inspected during this review, reports 12 errors in `metrics.py:59-80` across 112 checked modules: instance attributes inferred only inside the Windows constructor branch become unavailable on Linux, and `ct.get_last_error` is unavailable in Linux ctypes stubs. Declare the instance state outside platform-pruned initialization / use an appropriately typed native API boundary, keeping the non-Windows runtime failure explicit. This reviewer did not run Linux mypy; the evidence is root's saved qualification output, not the Windows focused-test result.

## Resolved prior findings

- Retained process handle is opened once, checks expected creation token before observation, supplies live and final peak RSS/CPU without reopening by PID or requiring liveness, and closes on constructor failure or observer finalization.
- Final fatal observation converts an otherwise successful process outcome to `observation_failure`; scorer also requires explicit `fatal=False`, no errors, bound identity, native RSS source, valid PID/birth token, and integer zero exit code.
- Hardware/process/scalar malformed values in the reviewed tests are rejected. Missing CPU remains unknown, and GPU utilization remains `UNKNOWN`.
- Exactly three complete rendered samples are required, each with positive finite frame intervals covering the measured window, declared quality/resolution/pacing, focus, activity, readiness and RSS evidence. The reviewed validation does not introduce fake/zero measurements or permit failed samples to be discarded.

## Output-path and platform limits

- Ready reads revalidate the workspace path at use, and final artifact enumeration revalidates discovered paths. Evidence loading at `performance.py:481` directly opens a path validated before launch; a child-created link could therefore be read before final artifact enumeration rejects it. No link-based successful PASS was demonstrated, and no extra confirmed priority finding is claimed here. A point-of-use `policy.path(evidence)` would align this read with the existing ready-sidecar check.
- Malformed ready JSON can leave `observer.fatal=False` while recording errors; the scorer still rejects it. The narrow scratch probe confirms this scorer-vs-runner distinction. Fatal state propagation itself is covered and passes.
- Unsupported counter hosts fail explicitly instead of reporting fabricated counters. Real Windows terminal-counter behavior remains a native qualification responsibility; mocked tests do not establish that native acceptance.

## Verification

- `.venv/Scripts/python.exe -m pytest tests/test_phase11_performance.py --no-cov --basetemp .tmp/phase11/profile-rereview/pytest -q -o cache_dir=.tmp/phase11/profile-rereview/cache`: **107 passed in 16.23s**.
- Scratch `.tmp/phase11/profile-rereview/test_review_probes.py`: **2 passed in 2.98s**, reproducing acceptance of the registration/freeze mutation and the nonfatal malformed-ready error behavior. These are isolated scratch probes, not repository test changes.
- Initial `python` resolved to an unusable Windows App alias. An initial test invocation also lacked the parent scratch directory (74 passed / 33 temp-fixture setup errors); after creating the owned parent scratch directory, the complete focused run above passed.

Verdict: request changes for the confirmed race and Linux typing qualification failure. Existing retained-handle, fatal propagation, and evidence-shape fixes otherwise survived this narrow independent re-review. Root's full-suite source freeze was respected.
