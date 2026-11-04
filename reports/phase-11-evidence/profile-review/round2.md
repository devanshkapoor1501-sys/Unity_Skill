# Phase 11 profiling fix round 2

Assigned findings: registration-to-baseline payload race and Linux mypy failures from platform-pruned ctypes state.

## Changes

- performance._registered_player returns an explicitly typed pair: validated job and the exact validated payload record tuple. No later fresh inventory becomes the baseline.
- The executable SHA and build digest derive from those validated records. After acquiring the Unity project lock, current inventory must match that same tuple before creating profile files or launching a player. Existing before-sample and post-sample checks continue comparing against the validated digest. Dry run returns before lock acquisition or profile writes.
- Evidence loading now revalidates policy.path(evidence) at the read boundary and keeps the existing 32 MiB bound.
- ProcessCounters declares ctypes state at class scope, so Linux mypy does not lose attributes through constructor platform pruning. Typed callable lookup for Windows library/error APIs keeps runtime unavailability explicit. No type ignores, lint suppressions, or reduced checks.
- Fake Win32 test fixtures explicitly supply WinDLL and get_last_error even when those exports are absent on the host.

## TDD and verification

- Four race regressions failed against the prior implementation, then passed after the fix: replace registered DLL or executable immediately after successful registration returns, or while acquiring the project lock. Every case now raises InputError with zero launches and no profiles directory.
- Reproduced all 12 Linux mypy errors on the three assigned source modules before the ctypes fix. Both `--platform linux` and `--platform win32` now pass on those modules.
- Focused performance plus existing runner/review/failure tests: 142 passed in 39.83s across test_phase11_performance.py, test_phase1_runner.py, test_phase1_review.py, test_phase1_failures.py, test_phase7_review.py.
- Simulated Linux's absence of WinDLL/get_last_error: before the fixture correction, 5 failed / 8 setup errors / 1 passed; after correction, all 14 relevant native-boundary/terminal/lifecycle/unsupported-host tests passed in 0.84s. This simulated export absence is not an actual Linux runtime qualification.
- Ruff passes all four assigned files. Targeted git diff --check passes.

No full suite, Unity/native player launch, C#/platformer/oracle/bridge changes, or commit. Only assigned Python source/test files and this owned scratch report changed. Native rendering/focus rules remain unchanged. Parent owns fresh full-suite/native verification and independent final review; this is implementation evidence, not independent approval.
