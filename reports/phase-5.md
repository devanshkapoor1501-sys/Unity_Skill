# Phase 5 — native Unity integration

Date: 2026-10-28. Acceptance: **PASS for Windows Editor static integration**.
Game: **PARTIAL**. PlayMode, standalone, manual artistic review, sandbox
qualification and external hidden evaluation have not passed this phase.

## Changes

- Added a separate UPM package with Editor/runtime/test assemblies and packaged
  its C#, assembly definitions and native-generated meta files in the Python wheel.
- Bootstrap copies the installed pinned URP template into a new managed project,
  preserves native asset bytes, refuses unmanaged projects and checks package
  identity. No serialized scene/prefab YAML is edited as text.
- Added native FBX import, linear URP material mapping, fitted colliders, semantic
  prefabs and Arena/Training static layouts using shared templates.
- Added observed model/prefab GUIDs, semantic node local IDs/paths, socket positions,
  collider shapes/references, scene instance references/transforms, camera/light
  checks and independently checked Python reconciliation.
- Added S4, unity.scene.static.v1, reconcile, diagnose and bounded repair plan/apply.
  Input source SHA checks prevent same-bounds FBX replacement from passing.
- Material-only rebuilds reuse registered geometry and preserve FBX/C# hashes,
  GUIDs, hierarchy and scene counts. Invalid and dry inputs write nothing.
- Repairs resolve against recorded evidence, use internally derived symptom
  attempt keys, snapshot exact owned bytes and rebuild only the affected asset
  and dependent scenes. Verification permits unchanged unrelated faults; rollback
  compares real post-reimport observations with the actual pre-repair baseline.
- Extended coverage to Unity bootstrap/evidence/snapshot and FBX comparison modules.

## Versions and commands

Python 3.12.14; Blender 5.2.2 LTS, build d13f752e3b9c; Unity 6000.6.3f1.
Installed URP template com.unity.template.urp-blank 17.2.1 declares and resolves
URP 17.6.0, Input System 1.19.0 and Test Framework 1.8.0. Exact resolved package
locks and Unity version observations are preserved in native snapshots/reports.
Python dependency versions remain pinned in requirements-dev.lock.

Commands below ran from the repository root. The structured
[quality commands](phase-5-evidence/quality-commands.json),
[installation commands](phase-5-evidence/install-commands.json) and every native
process.json retain full arguments, paths, durations and exit codes.

| Gate / exact command | Exit | Result |
| --- | --- | --- |
| `.venv/Scripts/python.exe -m ruff check .` | 0 | PASS |
| `.venv/Scripts/python.exe -m ruff format --check .` | 0 | PASS |
| `.venv/Scripts/python.exe -m mypy` | 0 | PASS; 54 source files |
| `.venv/Scripts/python.exe -m mypy --platform linux` | 0 | PASS |
| `.venv/Scripts/python.exe -m tools.generate_cli_docs --check` | 0 | PASS |
| `.venv/Scripts/python.exe -m pip check` | 0 | PASS |
| `.venv/Scripts/python.exe -m pytest --cov --cov-report=term-missing --cov-report=json:.tmp/phase5/coverage-final.json --junitxml=.tmp/phase5/tests-final.xml` | 0 | 162 passed; 12 application cases deliberately deselected; no executed skips |
| `.venv/Scripts/python.exe -m pytest tests/test_phase3_blender.py tests/test_phase4_blender.py -m blender -q --basetemp=.tmp/phase5/blender-final --junitxml=.tmp/phase5/blender-final.xml` | 0 | 9 actual Blender cases passed |
| `.venv/Scripts/python.exe -m pytest tests/test_phase5_unity.py -m unity -q --basetemp=.tmp/phase5/integration-reviewed --junitxml=.tmp/phase5/unity-reviewed.xml` | 0 | 3 real end-to-end cases passed; 904.10 seconds |
| `.venv/Scripts/python.exe -m build --no-isolation` | 0 | wheel and source archive built |
| `.venv/Scripts/python.exe -m pip install --no-index --no-build-isolation --no-deps -e .` | 0 | editable metadata refreshed |
| `.tmp/phase5/fresh-wheel/Scripts/python.exe -I -m polyforge build --workspace .tmp/phase5/integration-reviewed/polyforge_phase50/arena --through S4 --json` | 0 | installed-wheel S4, all 17 native cases, complete editable native archive |

Final offline coverage: **95.28% combined**, with the unchanged 90% threshold.
Native evidence checks are 100% covered; bootstrap and snapshot modules each
exceed 90%. See [coverage](phase-5-evidence/coverage-final.json) and raw quality logs.
Windows junction/hardlink tests ran with actual local link-creation permission.
The initial sandbox-only junction creation denial was rerun successfully; the
test was not skipped or weakened.

Fresh wheel verification executed twelve recorded checks without network access,
outside source imports using Python `-I`: installation, dependency check, CLI
discovery, model-free S4 dry run, resource hash equality and actual native template
bootstrap. The subsequent installed-wheel S4 invoked real Unity. Package hashes
and [native resource inventory](phase-5-evidence/package-resource-check.json) are retained.

## Actual native evidence

The native gate requires exactly seventeen named passing EditMode cases. It
rejects empty, skipped, duplicate, stale or different test runs. Compilation,
builder execution and tests use separate owned invocations; tests omit `-quit`.
Native test failure exit 2 maps to public test failure exit 7.

The final first and material-only builds each executed all seventeen cases:
dimension/socket/binding agreement, linear material mapping, repeated GUID/local-ID
and count stability, scale/material/socket/component faults, missing prefab GUID,
changed material values, five collider faults and three saved-scene overrides.
The socket-free `.987654` metallic edge fixture also executed all seventeen cases.

The final installed-wheel run is unity-c529663969334e47. Its native-output.zip
contains Assets (including URP settings), Packages and ProjectSettings, excluding
Library. It is an editable Unity project snapshot. Blender editable sources,
FBX files, four-view evidence, input digests and hashes remain in the recorded S3
runs. The immutable report index verifies **581 retained evidence files**.

The full integration proves:

1. A fresh managed arena project compiles, imports three assets and opens both scenes.
2. Material-only rebuild preserves FBX bytes, C# bytes, GUIDs and object counts.
3. A robot scale fault and separate crate material fault are detected. The robot
   repair commits while reporting the unchanged crate fault. A real crate apply
   followed by an injected verifier rejection restores the faulty baseline and
   reports ROLLED_BACK, not ROLLBACK_FAILED. A separate healthy snapshot restores
   deliberately changed manifest/model bytes, forces Unity reimport and recovers
   the same GUIDs, scene counts and exact byte inventory (`bytes_match=true`).

The rejected repair correctly returns FAIL/6 while its enclosing acceptance test
passes because the failure and verified rollback were expected. This is not a
claim that the rejected repair succeeded.

## Rulings and limits

- Native activation requires existing Windows OS profile paths; credentials and
  licenses are never copied. UPM caches/requested logs stay in the workspace.
  Licensing services may write profile state. Cost: this remains TRUSTED_LOCAL,
  with no filesystem/egress containment claim; untrusted execution is disabled.
  Unity package downloads were explicitly authorized in chat, and workspace
  authorization persists for subsequent package resolution. Two Bee workers keep
  compilation within the unchanged 32-process Windows job limit.
- Actual Unity import reverses X relative to the semantic Blender coordinates.
  A measured nested-model reflection restores handedness; semantic/collider roots
  remain unit-scaled. Cost: animation families need their own later verification.
- FBX roundtrip uses 10 micrometres absolute / 1 ppm relative coordinate tolerance
  after a real 20m floor drifted by 3 micrometres. IDs stay exact. Cost: smaller
  numerical deviations are accepted; meaningful scale/binding faults still fail.
- The two-game-family foundation is two static layouts sharing prefab/binding
  templates. Cost: two complete accepted games are not claimed; gameplay begins
  in Phase 6. Optional texture interchange remains explicitly unsupported.
- Full cross-application crash/stale-cache/scenario restoration and public
  rollback/resume are Phase 9. This gate verifies managed static bytes and real
  reimport bindings only. Codex/Claude host installation qualification remains
  Phase 10; standalone profiling and external hidden qualification remain Phase 11.

Fresh independent review found six Important issues, no Critical or Minor issues.
All six have RED/GREEN regressions and the full reviewed application gate passed;
see [review resolution](phase-5-review.md). No required finding is deferred.

Next gate: Phase 6, playable arena, independent behavior scenarios, EditMode and
PlayMode XML, collision/restart mutants and concrete manual play review. User
authorized pushing this completed phase and then continuing into Phase 6.
