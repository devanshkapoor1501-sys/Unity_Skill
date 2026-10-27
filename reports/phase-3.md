# Phase 3 — static semantic Blender assets

**Phase status: PASS. Game status: PARTIAL. Phases 4–11: NOT_RUN.**

Implemented five versioned static recipe families and managed asset generation.
No Phase 4 rendering/export, Unity integration or gameplay gate is claimed.

## Changes

- Added robot, crate, modular wall, doorway and environment-tile capabilities,
  typed requests and bounded primitive expansion. Robot parts, sockets and parent
  attachments are reusable data; doorway openings and asset dimensions are
  parameterized. Unknown parameters, cycles, dangling bindings, oversized arrays,
  invalid bevels and impossible openings fail before execution.
- Added the reviewed headless worker using JSON paths, background/factory startup,
  disabled automatic scripts and the existing allowlisted owned-process runner.
  Actual Blender version prechecks, resource budgets, sanitized logs and journals
  remain separate from source/geometry validation.
- Source files retain full semantic tags, editable materials/UVs, explicit parent
  hierarchy and a fitted base-center pivot. The worker saves/reopens .blend with
  scripts disabled, then measures actual bounds, root position, unit scale and
  mesh diagnostics. Host checks validate identities, sockets, UVs, budgets,
  coordinates and the independent logical artifact digest before registration.
- Logical geometry hashes address oriented face coordinates and UV bindings,
  quantized to six decimals. Storage indices and cyclic face starts do not alter
  logical identity; reversed winding does. Binary source hashes are recorded
  separately. Executable/worker hashes, actual build label and embedded Python
  version connect each artifact to its toolchain.
- CLI build supports S0 precheck, S1 contracts and S2 assets, --only with dependency
  closure, and zero-write dry runs. Effective material/size overrides and config
  validate before any publication. S3–S5 remain NOT_RUN/5. Five mesh catalog
  operations create fresh, isolated run outputs; four pure contracts/planning
  operations continue to work without Blender.

## Verification

| Gate | Actual result | Evidence under phase-3-evidence/ |
| --- | --- | --- |
| Offline Python suite | PASS: 107 tests; 4 application tests deliberately deselected, none skipped | pytest.txt, python-tests.xml |
| Security/contracts and recipe DSL coverage | PASS: 94.99% combined; 96.46% statements, 91.43% branches | coverage.json |
| Ruff and format | PASS, exit 0 | ruff.txt, format.txt |
| Strict mypy Windows/Linux targets | PASS: 44 source files, exit 0 | mypy.txt, mypy-linux.txt |
| CLI documentation/command grammar | PASS, exit 0 | cli-docs.txt |
| Dependency consistency and wheel/sdist builds | PASS, exit 0 | pip-check.txt, build.txt, package-artifacts.json |
| Fresh offline editable/wheel installs | PASS: 30 commands exit 0, including five recipe dry runs each and real installed-wheel generation | fresh-installs.json |
| Managed CLI smoke | PASS: 5 commands exit 0; source hashes/dry runs/material-only geometry identity checked | cli-verification.json |
| Real Blender application gate | PASS: 4 actual tests, 0 failures/errors/skips; all three golden types repeat and wall/door connectors align | blender-verification.json, blender-tests.xml |
| Missing/wrong dependency, invalid input and future stage | Structured exits 3, 2 and 5; truthful NOT_RUN/BLOCKED | tests/test_phase3_cli.py and verification.json |
| Independent review | Three findings reproduced and fixed | review-phase-3.md |

Exact commands, expected/actual exits and durations are retained in verification.json,
blender-verification.json, cli-verification.json and fresh-installs.json. Primary
reproduction commands are:

```powershell
$env:TEMP = Join-Path (Get-Location) '.tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=term-missing --cov-report=json:reports/phase-3-evidence/coverage.json --junitxml=reports/phase-3-evidence/python-tests.xml
.\.venv\Scripts\python.exe -m pytest tests/test_phase3_blender.py -m blender -o addopts=-ra --junitxml=reports/phase-3-evidence/blender-tests.xml
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m mypy --platform linux
.\.venv\Scripts\python.exe -m tools.generate_cli_docs --check
.\.venv\Scripts\python.exe -m build --no-isolation
.\.venv\Scripts\python.exe -m pip check
```

The offline suite ran with the access required to create the actual disposable
Windows junction fixture; that test was not skipped. Linux-target typing is not
Linux runtime qualification. Application XML is checked for the expected actual
test count and zero failures/errors/skips.
The unchanged 90% coverage gate now explicitly includes the new recipe contract
module (93.12% combined), in addition to contracts and security packages.

## Application artifacts

The golden index in phase-3-evidence/golden/index.json links actual editable
sources, normalized metrics, logical geometry, input snapshots, logs, stage
journals and artifact inventories for three fixture types. Raw bytes are preserved
so recorded hashes survive repository checkout. Earlier passing runs are retained.

| Fixture | Polygons | Vertices | Purpose |
| --- | ---: | ---: | --- |
| Modular robot | 1,084 | 1,100 | Semantic limbs, attached sockets, hierarchy and bounded bevels |
| Crate prop | 162 | 168 | Reusable beveled prop and braces |
| Asymmetric arrows | 164 | 170 | Unequal dimensions, marked up/front and source basis |

Other actual runs execute all five families, two briefs using the same robot
capability with different sizes/hashes, and 128 spheres producing 16,384 polygons
with a logical JSON payload over 1 MiB. Saved-source probes corrupt UVs, face
geometry, left/right sockets, budgets, root translation, mesh placement and units.
The managed CLI also checks a real material edit preserves the robot geometry hash.

## Versions and observed failures

Host Python 3.12.14; actual Blender 5.2.2 LTS, embedded Python 3.13.13. Per-run
metrics include Blender's actual build hash and the adapter records executable
and worker SHA-256. Existing locked packages were reused: jsonschema 4.25.1,
pytest 8.4.2, pytest-cov 6.3.0, Ruff 0.13.3, mypy 1.18.2, build 1.3.0,
setuptools 80.9.0 and wheel 0.45.1. No new downloads. Unity 6000.6.3f1 remains
the planning target; this phase never invokes Unity.

Observed failures led to verified fixes: numeric version vs LTS-label handling,
preserving editable palette resources during reload, canonical sphere face order,
missing-UV diagnostics, material/config override preflight, measured pivots and
bounded large-output reads. [Independent review](review-phase-3.md) records the
required findings; no required finding was deferred and no threshold was lowered.
The final source-archive refresh initially hit the host's inaccessible default
temp directory. Its failed log/exit are retained as sdist-refresh-initial.*;
the documented workspace-local TEMP/TMP settings produced a passing refresh.

## Limits and next gate

- TRUSTED_LOCAL remains explicit; OS isolation and malicious plugin containment
  are not provided. Missing Blender blocks the real gate rather than skipping it.
- Source generation PASS does not establish Unity binding, game playability,
  independent feature acceptance or release qualification. Game stays PARTIAL.
- UV projection is geometric and simple; no photorealism or texture-quality
  review is claimed. No renders, FBX, Unity imports, rig actions or sprites exist.
- Builds intentionally regenerate and preserve fresh run evidence. They do not
  populate the planner cache or claim a cache hit. Generic resume/repair is still
  NOT_RUN pending managed retry/repair work; its registry phase is now truthful.
- Early Phase 1/2 placeholder robot recipes need an explicit update to the current
  reviewed family data. User sources are not silently overwritten or migrated.
- The original blueprint is unchanged. SHA-256:
  9d92fea8880b03b6d00e0bbe69b6fb8c1bf3f22f4c1ff16c1de7ae1f42970505.

Next is Phase 4: four nonblank audit views, diagnostics, FBX/material metadata,
hashes and asymmetric orientation/export checks. Real Unity import remains a
separate Phase 5 gate. Stop at the Phase 3 boundary.
