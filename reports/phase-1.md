# Phase 1 — execution and policy foundation

**Phase status: PASS. Game status: PARTIAL. Phase 2 and later: NOT_RUN.**

Implemented and verified the local runtime infrastructure. Stop at this phase
boundary; no Blender geometry or Unity game project has been generated.

## Actual changes

- Bounded typed TOML config with explicit binary overrides, safe execution defaults,
  retry limits, and denial of network/outside-root/untrusted settings.
- Trusted-local WorkspacePolicy rejects traversal, drive-relative/UNC escapes,
  reserved Windows names, alternate streams, symlinks/junctions and reparse paths.
- Real shell-free worker runner: explicit binary allowlists, minimal environment,
  credential-safe byte-bounded logs, timeout/cancellation and owned-tree cleanup.
  Infinite/NaN timeouts are rejected before any filesystem changes or launch.
  Windows launches suspend before Job Object assignment and resume only after
  memory/process/kill-on-close limits are configured.
- OS-exclusive persistent locks verify PID/host/birth identity before reclaiming
  a stale owner. Foreign/ambiguous/live owners stay blocked. Project-specific Unity
  locks share one physical location even under nested authorized workspace roots.
- Atomic JSON replacement plus fsync; two bounded retries handle transient Windows
  sharing denials. Permanent denial preserves the old state file and durable event.
- Run journals persist complete ordered state snapshots before updating the cache.
  Interrupted cache writes replay from events; partial tails are recoverable;
  corrupt complete events fail explicitly. Passed stages require real nonempty
  evidence. Stage attempts respect the configured retry budget.
- Implemented CLI init/doctor/status/report. New workspace init refuses overwrites;
  doctor dry-run and invalid inputs create nothing. Status/report read journal
  facts without inferring gameplay success. Existing command examples stay tested.
- Doctor honors overrides, then conventional installations, then PATH. It probes
  Blender --version and Unity -version without opening any original Unity project,
  saves structured reports even for missing dependencies, and records configuration
  digest, versions, source revision, CPU/thread/RAM data, limits and isolation scope.
- Optional original-project readiness reads only known version/package/lock files.
  Unity lock, package readiness, missing tools, probe failure, policy denial and
  unavailable license/rendering evidence remain distinguishable.

Main additions: polyforge/config.py, doctor.py, workspace.py; runner/{ownership,
processes,locks,state}.py; security/policy.py; bundled init templates; five Phase 1
test modules. Updated CLI registry, docs, skill guidance and packaging resources.

## Verification

| Check | Actual result | Evidence |
| --- | --- | --- |
| Full pytest suite, no skipped junction test | PASS: 66 tests | phase-1-evidence/pytest.txt, python-tests.xml |
| Security/contracts statement + branch coverage | PASS: 97.79%, requirement >=90% unchanged | phase-1-evidence/coverage.json |
| Ruff check and format check | PASS | phase-1-evidence/ruff.txt, format.txt |
| Strict mypy, Windows and Linux target modes | PASS: 25 source files | phase-1-evidence/mypy.txt, mypy-linux.txt |
| Generated CLI docs/examples consistency | PASS | phase-1-evidence/cli-docs.txt |
| Dependency consistency | PASS | phase-1-evidence/pip-check.txt |
| Wheel/source archive builds | PASS | phase-1-evidence/build.txt |
| Fresh editable/wheel offline installs and installed CLI commands | PASS | phase-1-evidence/fresh-installs.json |
| Actual Blender version probe | PASS: 5.2.2, exit 0, owned Windows job | phase-1-evidence/application-probes/ |
| Actual Unity Editor version probe | PASS: 6000.6.3f1, exit 0, owned Windows job | phase-1-evidence/application-probes/ |
| Missing dependencies / invalid descriptor / future build | Expected nonzero structured outcomes | phase-1-evidence/verification.json and tests |
| Independent review regressions | PASS; no unresolved findings | review-phase-1.md |

Exact executed argument arrays, expected/actual exits, log paths and timings are
in phase-1-evidence/verification.json. Python 3.12.14 and the existing locked
development dependencies were reused; no new downloads were needed.

The full suite required access to create a disposable Windows junction. The
default sandbox denied fixture creation; the same actual test passed with that
access, then the complete suite ran with it. Nothing was skipped or weakened.

## Preserved failures and scope decisions

- Initial real doctor probe found the unrelated generic Unity CLI on PATH; its
  -version probe failed. That failed run, logs and stage state are retained beside
  successful runs in the application-probes evidence tree. Discovery precedence
  was corrected and covered by a failing-then-passing regression.
- A transient Windows/OneDrive state replacement denial was observed. Tests now
  prove success after two transient failures and safe failure on permanent denial.
- Manifest validation stays Phase 2, resolving the older Phase 1 deliverable summary
  against the approved implementation sequence. No partial schema validator is
  advertised. CLI producer resume scheduling stays Phase 3; library state recovery
  and retry semantics are already executed and tested.
- Basic RAM inventory is now measured through the Windows API; GPU, real rendering,
  runtime performance and complete target-device profiling remain NOT_RUN.
- The source revision recorded during pre-commit verification is Phase 0 HEAD;
  Phase 1 working-tree changes are represented by this commit and its saved tests.

## Security and later gates

The supported development profile remains TRUSTED_LOCAL, isolation_verified=false.
Job Objects are resource and ownership controls, not filesystem/network isolation.
Network requests and downloads are disabled by engine policy; ambient malicious
plugin egress is not contained. SANDBOXED_UNTRUSTED remains denied until actual
OS-level denial probes qualify a later execution profile.

License activation is NOT_RUN: version output cannot establish it. Project import,
graphics rendering, EditMode/PlayMode, standalone builds, hidden evaluator tests,
full original-project hash inventory and comparative benchmarks are later gates.
POSIX type checking passed; POSIX runtime/memory-limit enforcement and remote CI
were not executed here. None are presented as passing integration results.

Next: Phase 2 semantic manifest/intent compilation, supported-feature reporting,
scene contracts, dependency DAGs and content-hash invalidation. No public release,
remote tag or deployment was performed.
