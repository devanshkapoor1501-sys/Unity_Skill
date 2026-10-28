# Phase 7 — bounded workforce and robot animation

**Phase acceptance: PASS. Game acceptance: PARTIAL.** The required Phase 7
development gates passed on Windows. Protected evaluation, verified native host
delegation, OS sandbox enforcement and release profiling remain unexecuted.
Phase 8 has not been started.

Authority is the supplied v5.1 blueprint, Section 12 Phase 7, Chapters 16–18 and
Appendix G. Its SHA256 is
`8f186fa13ce3fc085cab96ee5991dce2e85dde36277f2c6c631f7e8d5a9331d6`.
The accepted starting commit was
`ee490d60abd36cdc407b3a7f8d7cff2a18bba243`; the implementation branch is
`codex/polyforge-phase-7`. Both source documents are preserved. The kickoff
[baseline inventory](v5_1_baseline.json) records source hashes, schema/stage
interfaces, installed tools, 200 passing Python tests and the actually executed
arena baseline `game-check-c9766313637d42af`.

## Delivered behavior

- Added typed task, job, handoff and review contracts around the existing S0–S5
  engine. Explicit task classification preserves the brief and feature IDs.
  Explanation and mesh-only tasks avoid Unity; supported complete-game requests
  retain S0–S5. Unsupported execution remains visibly REVIEW/NOT_RUN.
- Added the four minimum animation roles, permissions, discovery, dependency
  routing and a sequential coordinator. Native host delegation is UNAVAILABLE;
  role identity is DIFFERENT_ROLE_SAME_HOST, without protected evaluator authority.
- Added asset leases with tokens, process birth identity, TTL and heartbeat;
  cancellation fences publication and reaches the owned subprocess. Stable
  operation identities, native completion inventories and atomic result receipts
  bridge completion before coordinator commit. Resume validates source/input and
  output hashes rather than trusting a prior VERIFIED label.
- Added one parameterized rigid mechanical robot skeleton family, 19 named bones,
  rigid skin weights and preserved socket bindings. Blender uses explicit slotted
  Idle/Walk actions and channelbags, five sampled frames per one-second action,
  reopened editable source, FBX clips and four rendered pose views.
- Added native Unity Generic-rig import, an in-place two-state AnimatorController,
  prefab and separate AnimationArena scene. Actual imported skin motion and the
  enemy's Walk/Idle behavior are checked in PlayMode. Original PlayableArena
  bytes remain unchanged.
- Added six workforce commands and three registered capabilities through the
  existing command registry/shared dispatch. Updated the portable skill and the
  plain-language README. Packaged roles in the source distribution and schemas,
  animation worker and Unity resources in the wheel.

The existing registry, runner, journal, workspace policy, static geometry worker
and native Unity package were extended rather than duplicated. Thin interfaces
carry cancellation and durable operation identity. The guarded package upgrade
now records the exact applied source baseline, including rollback scope for its
ownership pointer; user edits continue to block automatic replacement. New
schemas remain in the existing `polyforge/contracts/` package, and tests follow
the existing flat `tests/test_*.py` layout. No new dependency was introduced.

## Executed checks

Python **3.12.14**, Blender **5.2.2 LTS**, Unity **6000.6.3f1**, URP **17.6.0**,
Input System **1.19.0** and Test Framework **1.8.0** were used. Windows 11 is the
executed platform. Linux typing analysis is static analysis, not a Linux native
application test. Commands below ran from the repository root with `TEMP` and
`TMP` pointing to the existing workspace `.tmp` directory.

| Gate | Exact command or retained invocation | Exit and observed result |
| --- | --- | --- |
| Python/security/contracts | `.venv/Scripts/python.exe -m pytest --cov --cov-report=term-missing --cov-report=json:.tmp/phase7/coverage-final.json --junitxml=.tmp/phase7/tests-final.xml` | 0; **243 passed**, 12 application-marked tests deselected; **95.78%** measured branch-enabled coverage, 90% threshold retained |
| Ruff | `.venv/Scripts/python.exe -m ruff check .` and `-m ruff format --check .` | Both 0; checks passed, 98 files formatted |
| Types | `.venv/Scripts/python.exe -m mypy` and `-m mypy --platform linux` | Both 0; 73 source files each |
| Command docs | `.venv/Scripts/python.exe -m tools.generate_cli_docs --check` | 0; generated documentation/fixtures current |
| Dependencies/build | `.venv/Scripts/python.exe -m pip check` and `-m build --no-isolation` | Both 0; wheel and source distribution built |
| Old Blender gates | `.venv/Scripts/python.exe -m pytest tests/test_phase3_blender.py tests/test_phase4_blender.py -m blender -q --basetemp=.tmp/phase7/blender-regression --junitxml=.tmp/phase7/blender-regression.xml` | 0; **9 passed** |
| Four-role animation | `.venv/Scripts/python.exe .tmp/phase7/run-workforce-animation.py` | 0; `task_f39a98b5dae1a230_17082ae4` PASS |
| Single-mode comparison | `.venv/Scripts/python.exe .tmp/phase7/run-single-animation.py` | 0; `task_f39a98b5dae1a230_17082ae4_single` PASS |
| Non-robot reuse | `.venv/Scripts/python.exe .tmp/phase7/run-nonrobot.py` | 0; `task_1db632c376286d22_1100f752` PASS; exact candidate reused on resume, no Unity job |
| Native completion recovery | `.venv/Scripts/python.exe .tmp/phase7/prove-recovery.py` | 0; unchanged resume, stale-controller rejection, Blender no-relaunch and Unity no-second-build checks passed |
| Existing native regressions | `.venv/Scripts/python.exe .tmp/phase7/regression-native.py` | 0; **17 static Editor**, **1 arena Editor**, **12 arena PlayMode**, public gameplay oracles and collision/restart mutants passed |
| Fresh wheel | `.venv/Scripts/python.exe .tmp/phase7/install.py` | 0; eight isolated install/help/catalog/init/dry-run/resource checks passed; package install used `--no-index --find-links .tmp/wheelhouse` |
| Installed command examples | `.venv/Scripts/python.exe .tmp/phase7/installed-workforce.py` | 0; actual wheel CLI plan/run/status/review and no-write dry run passed with a real Blender crate |

Every animation arm executed **five Editor tests and two PlayMode tests**, with
exact test identities parsed from XML. The three physical Editor fault cases
alter imported bone mapping, skin weights and Animator transitions respectively.
The missing-transition fixture has valid clips, isolating the transition defect.
PlayMode measures actual baked thigh-skin displacement, bone rotation and root
position; it also observes patrol-driven Walk and terminal-state Idle. The
sampled Blender skin/socket error is below 0.0001m. The test tolerances were
retained while correcting an initially mistaken body-mesh selection.

Single and four-role paths produced identical sampled motion and matching native
GUID/clip bindings, with no duplicate semantic IDs or original-scene changes.
This is deterministic engine-workflow parity, not a model-quality, speed or
parallel-agent benchmark. See [parity](phase-7-evidence/parity.json).

The native Unity command arrays, tool ownership, exit codes, timeouts and raw logs
are retained in each run's `process.json`/stdout files. New Blender invocations
use background/factory-startup/disabled-autoexec and one thread. Unity invocations
use batch mode, two job workers, bounded owned Windows processes and separate
test filters. [Quality commands](phase-7-evidence/quality/commands.json),
[installation commands](phase-7-evidence/install/commands.json) and
[installed workforce commands](phase-7-evidence/installed-workforce/commands.json)
retain full arguments and exit codes. The small execution scripts are copied to
`phase-7-evidence/scripts/` so their exact inputs remain reviewable.

## Negative checks, recovery and review

Wrong mapping, disconnected limbs, root drift, missing transitions, candidate
substitution, forged review identity, changed brief/manifest, schema/code changes,
unsafe paths and stale completed outputs fail their corresponding checks.
Real owned-process cancellation and process death are exercised; an expired dead
lease is reclaimed once and an active owner cannot be displaced by expiry alone.
Production/integration receipt-boundary crash tests use a deterministic native
backend and actual coordinator process death. They do not represent killing the
Unity Editor halfway through an arbitrary asset rewrite.

An actual completed Blender output was recovered with launching disabled. An
actual completed Unity integration was recovered with asset-build launch denied;
only its two native test runs executed. Removing the generated controller made
resume fail with contract exit 6; restoring its exact bytes restored the fixture.
See [recovery proof](phase-7-evidence/recovery-proof.json).

One fresh whole-phase review found six Important defects, all fixed in one tested
correction pass. Two initially Minor canonical-ID/fixture issues were treated as
Important and fixed. Initial RED outputs are retained, including a real expected
Unity compile failure while the animation driver was absent. Two additional
failing tests exposed incomplete implementation fingerprint coverage and passed
after the full resource inventory replaced the selected file list. No failed
check was turned into an ignored or passing gate. See
[review resolution](phase-7-review.md).

Three rendered source views were visually inspected for complete silhouette,
attached limbs and distinct walking offsets. This is an agent pose preview,
not a protected artistic assessment or a new manual player review. Phase 6's
user-confirmed manual play evidence remains in its original report.

## Artifacts and limits

[Evidence index](phase-7-evidence/index.json) hashes the retained native source,
FBX, motion samples, views, candidate/review/job records, completion receipts,
test XML and application logs. The editable native project source archive omits
Library/Temp caches and player binaries. [Workforce evidence](workforce_evidence.jsonl),
[minimal knowledge coverage](knowledge_coverage.json) and
[public acceptance oracle](acceptance_oracle.json) distinguish execution, review
and game acceptance. The empty experimental-action log accurately records that
no unfamiliar generated code was executed.

The generic system skill validator could not run because PyYAML is absent; it
also predates the existing `compatibility` field. This is recorded as BLOCKED,
with a narrower frontmatter/local-reference check passing. No new download was
performed to conceal this limit. Full skill-format and Codex/alternative-host
qualification remain Phase 10. Installed Blender's official `anim_utils.py` and
actual API probes established slot/channelbag compatibility; remote Blender API
documentation retrieval failed and is not claimed as successful verification.

TRUSTED_LOCAL is explicit. No OS isolation, independently controlled hidden
evaluation, humanoid/face/retargeting support, advanced textures or full
cross-application rollback is claimed. Native shutdown allocation warnings
remain in raw logs; profiling was not performed. Phase 7 did not rebuild a new
standalone player; the separate new animation fixture is qualified by native
Editor/PlayMode checks. Phase 6's existing standalone evidence is preserved.

**Next gate: Phase 8**, only after a separate start instruction: specialist
asset/material handoffs and the original six-frame controllable 2D pipeline.
This phase is prepared as a local commit; remote publication is a separate step.
