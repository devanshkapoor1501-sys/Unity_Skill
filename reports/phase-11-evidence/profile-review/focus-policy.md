# Explicit focus-tolerant profile implementation

Authority: coordinator's explicit instruction following .tmp/phase11/focus-policy-review.md. This changes the previous implementation-added foreground rejection, not the numerical, sampling, identity or workload gates. C# was edited only after coordinator released its native source freeze.

## Contract and implementation

- DEFAULT_PROFILE and profiles/windows-arena.json declare focus_policy=OBSERVE_CONTINUOUS_BACKGROUND_ENABLED, renderer_observation=UNITY_END_OF_FRAME, and run_in_background=true. Current canonical DEFAULT_PROFILE digest: ea2ac506b6cf1e51c220f968ad4772d4bc29c739b4e1fd30200935a7c8b3ff2b.
- Every fresh native request includes these settings; StandaloneProfile requires them and writes them into its evidence. Missing legacy fields fail scoring. No saved native attempts were changed or rescored.
- Readiness no longer requires focus. Focus loss no longer aborts, pauses, resets, restarts, clears or filters measurement. All positive finite end-of-frame intervals remain in one continuous post-warmup window. If callback progress stops then resumes, the full wall-clock gap remains in the next interval. Existing timeout/incomplete/window/threshold checks remain.
- During measurement, focused_frames and unfocused_frames classify each interval using focus at its closing observation. focus_changes counts changes from the measurement-start state through subsequent closing observations. focused means every measured closing state was focused. These are not timestamped focus-callback events, and cannot describe transitions that occurred inside an interval.
- Scoring accepts focused, mixed and all-unfocused complete groups under the explicit policy. Counts must be exact nonnegative integers <=1000000, sum to frames_recorded, satisfy changes<=frames, and agree with the aggregate boolean. Invalid policy/background/source/counts and legacy metadata fail.
- Request/runtime, evidence and reports identify the end-of-frame telemetry source. GPU presentation stays NOT_MEASURED; GPU utilization stays UNKNOWN. Report/native metadata explicitly limits the data to CPU wall-clock observations: no independent GPU execution or physical display presentation timing, visibility, occlusion or whole-interval focus claim.
- Numerical gates stay median FPS>=30, p95<=50ms, RSS<=2147483648, readiness<=30s, 1280x720 PC, vSync0/target-1, 10s warmup and three complete 60s measurements. Native code also continuously checks resolution/quality/pacing/background policy. Editor/batch/nographics/Null-device and workload/camera/process ownership/provenance checks remain.

## Verification

TDD: 22 new policy/metadata cases failed before implementation; all 24 focused cases passed afterward. Existing focused=False with all-focused counts still fails as contradictory. Slow unfocused intervals still fail the unchanged FPS threshold.

Final owned run: 166 passed in 45.92s across test_phase11_performance.py plus Phase 1 runner/review/failures and Phase 7 review. Dedicated branch-aware coverage: performance.py 92%, runner/metrics.py 97%, combined 93.39% (required 90%). Coverage artifact: .tmp/phase11/profile-review/focus-coverage.xml.

Ruff passes performance.py and the owned test file. Mypy passes the three owned profiling/runner modules for --platform linux and --platform win32. StandaloneProfile.cs parses without C# syntax errors using tree-sitter; that is not compilation or runtime validation. Its draft patch is preserved at .tmp/phase11/focus-policy-native.patch and matches the applied source.

No Unity/native launch, full suite or commit was performed here. No other C#/platformer/oracle/bridge source changed. Parent/root owns fresh rebuild and three real measurements, independent code review, native transition-path verification, and reporting. No native PASS is asserted by this implementation report.
