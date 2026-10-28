# Phase 6 — playable 3D arena

Date: 2026-10-28. **Phase acceptance: PASS. Game acceptance: PARTIAL.**
All Phase 6 development gates, Windows player build/smoke and user manual play
review passed. This is not release, performance, sandbox or hidden qualification.

## Authority and changes

At the user's request, reviewed the supplied v5.1 blueprint, SHA256
`8f186fa13ce3fc085cab96ee5991dce2e85dde36277f2c6c631f7e8d5a9331d6`.
Its Section-12 Phase 0–6 paragraphs match v4 unchanged; see
[comparison](phase-6-evidence/v5.1-phase-comparison.json).
The original v4 document is preserved byte-for-byte in `docs/source`, with its
original SHA256 `9d92fea8880b03b6d00e0bbe69b6fb8c1bf3f22f4c1ff16c1de7ae1f42970505`.
The implementation sequence now reflects the expanded Phase 7–17 roadmap.

- Added reusable movement/input, health, patrol/contact damage, survival/failure,
  restart, HUD and development performance instrumentation.
- Built a separate native PlayableArena scene from generated Blender assets,
  including an editable wall source. Preserved the existing static scene gates.
- Added seven declarative behavior scenarios, actual Input System W/R cases,
  collision/restart mutants and independent Python observation oracles.
- Added S5, verify, core_gameplay scenario execution and unity.game.arena.v1.
  Dry-run and invalid-input preflight remain model-free and side-effect-free.
- Added loaded scene/request identity checks, per-enemy patrol requirements,
  malformed telemetry rejection, feature provenance and immutable run hashes.
- Added guarded owned-package upgrades against hash-verified previous bytes,
  retained native meta/GUIDs, editable project archives and transaction journals.
- Prepared twelve public development benchmark briefs and a pinned sample
  performance profile. Benchmark trials and profiling remain NOT_RUN.

## Versions and executed commands

Python 3.12.14, Blender 5.2.2 LTS build d13f752e3b9c, Unity 6000.6.3f1.
URP 17.6.0, Input System 1.19.0, Test Framework 1.8.0.
Commands ran from the repository root unless the recorded cwd says otherwise.
TEMP/TMP used the workspace-local `.tmp` directory. Windows link tests used
actual local junction/hardlink permission; no executed test was skipped.

| Command / gate | Exit | Outcome |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m ruff check .` | 0 | PASS |
| `.venv/Scripts/python.exe -m ruff format --check .` | 0 | PASS |
| `.venv/Scripts/python.exe -m mypy` | 0 | PASS; 57 source files |
| `.venv/Scripts/python.exe -m mypy --platform linux` | 0 | PASS |
| `.venv/Scripts/python.exe -m tools.generate_cli_docs --check` | 0 | PASS |
| `.venv/Scripts/python.exe -m pip check` | 0 | PASS |
| `.venv/Scripts/python.exe -m pytest --cov --cov-report=term-missing --cov-report=json:.tmp/phase6/coverage-final.json --junitxml=.tmp/phase6/tests-final.xml` | 0 | 199 passed; 12 application cases separately deselected |
| `.venv/Scripts/python.exe -m build --no-isolation` | 0 | wheel and source archive built |
| `.venv/Scripts/python.exe -m polyforge build --workspace .tmp/phase6/arena --through S5 --standalone --json` | 0 | static/native/game/player gates PASS |
| `.tmp/phase6/fresh-wheel/Scripts/python.exe -I -m polyforge verify --workspace .tmp/phase6/arena --json` | 0 | fresh installed wheel: native checks/oracles PASS |

[Quality commands](phase-6-evidence/quality/commands.json) and
[isolated installation commands](phase-6-evidence/install/commands.json) retain
exact absolute arguments, cwd, durations and exit codes. Eight fresh-install
checks used `--no-index`, the local wheelhouse and Python `-I`: install, pip check,
help/discovery, init, S5 dry-run and packaged native-resource equality checks.
No additional dependency download or model service was required.

Final expanded branch coverage: **94.99%**, with the unchanged 90% threshold.
New public oracle coverage is 91.41%; upgrade provenance guard coverage is 98.48%.
See [raw offline output](phase-6-evidence/offline-final.txt),
[XML](phase-6-evidence/tests-final.xml) and
[coverage](phase-6-evidence/coverage-final.json).

## Native evidence

Final static run: `unity-59d216e5c1784e1b` — native compilation, reconciliation
and all seventeen static EditMode tests PASS.
Game build: `game-build-5bccbde03d0848ac`.
Game verification: `game-check-d9ccc8eca7304c16` — one game EditMode test and
twelve PlayMode tests PASS, with exact expected test identities parsed from XML.
Installed wheel verification: `game-check-7c27c191aea94151` repeats both game
suites and independent public scoring successfully.

The seven observed behaviors are movement, blocking walls, every enemy's patrol,
contact health loss, zero-health failure, thirty-second survival and restart of
player/enemies/health/time. W/R cases exercise the actual Input System adapter.
Both required mutants emit valid observed regressions and are detected. Missing
or malformed evidence fails validation before any mutant verdict is inverted.

The real Windows Mono player built successfully and its owned smoke process
exited 0 after 150 fixed frames, observing startup and enemy motion. The executable
and dependencies remain locally below the final run's `player` directory;
[player inventory](phase-6-evidence/player-inventory.json) records hashes.
No player binary is committed. Editable source and Unity project archives,
bindings, raw process logs, XML, scenario traces and oracle verdicts are included
under [the evidence index](phase-6-evidence/index.json).
Disposable compiler `tmp` caches and player binaries are excluded from that
portable evidence selection; original per-run registries remain unchanged.

## Manual review and fixes

Initial interactive review was BLOCKED by the Windows lock screen. A subsequent
Computer Use attempt was stopped with Escape; the user explicitly resumed work.
After unlocking, the agent observed the rendered arena/HUD, movement and health
decreasing to 75. The user then played the final build and confirmed:
**“All listed play checks passed”**, covering WASD, wall collision, patrol/damage,
win/failure and R restart. See [manual review](phase-6-evidence/manual-review.json)
and [observed health screenshot](phase-6-evidence/interactive/health-damage.png).

Real regressions were retained: keyboard movement initially failed due headless
focus routing; a test-only focus configuration resolved it. R initially failed
because fixed-step polling missed the input edge; queued onAfterUpdate restart
events resolved it and the dedicated real-key test passed.

The one fresh whole-phase review identified four Important defects, all fixed
in one RED→GREEN pass. Native wrong-identity evidence passed before the fix and
was rejected after it; pure negative fixtures reject malformed mutants, one
frozen enemy among moving enemies, stale saved requests and false optional-feature
implementation claims. See [review resolution](phase-6-review.md).

## Limits and next gate

This phase supports one bounded 3D WASD/R thirty-second arena fixture. It does
not imply general genre support. Mandatory unsupported requests fail before
generation; optional unsupported features remain visibly unimplemented.
Fixed 0.02s steps allow three extra scheduled frames, 0.1m horizontal positional
tolerance and 0.06s win-time tolerance, without binary physics determinism claims.

TRUSTED_LOCAL remains disclosed, with Unity using the existing activation
profile. Sandbox enforcement, external hidden evaluation, second-genre reuse,
the remaining four release mutants and full cross-application crash recovery
remain later gates. No protected evaluator data is supplied or stored here.

The smoke used Null Device and reported 1422×693, with unavailable RSS represented
as zero by the runtime API. Those observations are **not** valid rendered profile
measurements. The requested 1280×720, 10-second warmup, three 60-second samples and
performance targets remain NOT_RUN. Native shutdown allocation warnings remain
in raw logs; they are not a measured performance or leak-free claim.

Benchmark inventory has four asset, two animation/import, three mechanic, two
repair and one complete 2D task. All A/B/C/D trials, MCP parity and accepted-game
metrics are NOT_RUN; independent scoring must be frozen before eligible trials.

Stop at this boundary. Phase 7 kickoff must inventory the actual repository and
toolchain, write the v5 baseline/migration evidence, then implement the expanded
workforce/discovery/authority contracts alongside the original robot animation
gates. No Phase 7 capability is advertised as implemented.
