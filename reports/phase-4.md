# Phase 4 — static audit and export

**Phase status: PASS. Game: PARTIAL. Phases 5–11: NOT_RUN.**

Added real Blender audit rendering and static FBX/material interchange. Actual
Unity import, artistic acceptance and Phase 5–11 game/release gates remain NOT_RUN.

## Changes

- Fixed front/side/top/iso orthographic cameras, deterministic framing, CPU Cycles
  lighting/seed/sample configuration and transparent RGBA8 PNGs. The host checks
  actual chunks, CRCs, bounded decompression, scanline filters, foreground alpha,
  color variation and unclipped image bounds independently of worker claims.
- Module-level preflight for reversed primitive normals, nonuniform/reflected
  scale, orientation, UVs, degeneracy, material slots and socket/parent bindings.
  Static export refuses armatures rather than applying static transforms to rigs.
- Selected tagged root/mesh/socket FBX export with explicit axes, meter scale,
  custom properties and disabled animation. Material sidecars preserve linear
  base color, metallic, roughness and per-module assignments. Handoff and binding
  files retain stable IDs, dimensions, sockets, geometry hashes and actual file
  hashes. Managed summaries preserve collider intent with validation NOT_RUN.
- Source-side FBX import in a fresh Blender scene verifies asymmetric dimensions,
  front socket, module IDs and used material IDs. Unused palette entries stay in
  editable source/sidecar without being required in FBX. This is explicitly
  BLENDER_FBX_ROUNDTRIP, not a Unity test.
- Working S3 build, saved-source audit CLI and audit.static.multiview.v1 catalog
  operation. Audit verifies registered source hashes and copies source bytes into
  a fresh run. Invalid input and dry runs write nothing. S4/S5 remain NOT_RUN/5.
- HTML view bundles retain visual_review_status REVIEW, while Unity/physics
  evidence stays NOT_RUN. Config/extension/cache paths are redirected to owned
  temporary directories. TRUSTED_LOCAL and isolation_verified=false stay explicit.

## Verification

| Gate | Actual result | Evidence under phase-4-evidence/ |
| --- | --- | --- |
| Separate Blender application gate | PASS: 9 tests, 0 failures/errors/skips | blender-tests.txt, blender-tests.xml, blender-verification.json |
| Three golden fixture audits | PASS: 12 nonblank 512×512 views, independent alpha/framing checks and repeated metadata | golden/index.json and retained run trees |
| Existing source audit | PASS: byte-identical source copy, original SHA-256 unchanged; pure dry run | actual application test and cli-verification.json |
| Six real fault categories | PASS: reversed_normals, nonuniform_scale, missing_uv, orientation, absent_socket, material detected with module origins | audit-faults.json |
| Managed CLI workflow | PASS: 7 commands with expected exits, source hashes, material values and S4 rejection | cli-verification.json and cli-*.json |
| Offline Python suite | PASS: 118 tests, 0 failures/errors/skips; 9 application tests deliberately deselected | pytest.txt, python-tests.xml |
| Security/contracts/recipe coverage | PASS: 95.74% combined, 96.97% statements, 92.86% branches; PNG module 100% | coverage.json |
| Ruff, format, strict Windows/Linux-target mypy | PASS, final command records retained | ruff.txt, format.txt, mypy*.txt |
| CLI examples/registry and dependency consistency | PASS, exit 0 | cli-docs.txt, pip-check.txt |
| Wheel/source archive and packaged resources | PASS, exit 0; final inventory/hashes retained | build.txt, package-artifacts.json |
| Fresh offline editable/wheel installs | PASS: 32 commands, all exit 0, including installed-wheel S3 execution | fresh-installs.json |
| Independent review | Three findings reproduced and fixed; malformed metadata also handled | review-phase-4.md |

Exact argv arrays, expected/actual exits, elapsed times and logs are in
verification.json, blender-verification.json, cli-verification.json and
fresh-installs.json. Primary acceptance commands are:

```powershell
$env:TEMP = Join-Path (Get-Location) '.tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m pytest --cov --cov-report=term-missing --cov-report=json:reports/phase-4-evidence/coverage.json --junitxml=reports/phase-4-evidence/python-tests.xml
.\.venv\Scripts\python.exe -m pytest tests/test_phase3_blender.py tests/test_phase4_blender.py -m blender -o addopts=-ra --junitxml=reports/phase-4-evidence/blender-tests.xml
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m mypy
.\.venv\Scripts\python.exe -m mypy --platform linux
.\.venv\Scripts\python.exe -m tools.generate_cli_docs --check
.\.venv\Scripts\python.exe -m build --no-isolation
.\.venv\Scripts\python.exe -m pip check
```

The actual Windows junction fixture runs with the access needed to create it;
no skip replaces that test. Default pytest deliberately deselects the nine real
application tests, which are executed separately and counted from their own XML.
Linux typing is not Linux runtime qualification. No threshold is lowered.

## Reproducible artifacts and versions

Golden assets are the modular robot, crate and asymmetric orientation arrows.
Each retained run has the editable source, four images, FBX, material/handoff and
roundtrip reports, logical mesh data, view checks, review page, immutable job,
process logs, journals and artifact SHA-256 inventory. The binding index connects
source identity to actual FBX/image bytes. Hash verification covers captured files
and Git attributes preserve raw vendor bytes. Binary .blend and FBX hashes may
differ between runs; logical geometry and export metadata are the repeatability
claim. Artistic image perfection is never inferred from reproducible settings.

Host Python 3.12.14 and Blender 5.2.2 LTS (embedded Python 3.13.13) were used.
Blender build d13f752e3b9c and actual executable/worker SHA-256 are retained per run.
Existing dependencies remain jsonschema 4.25.1, pytest 8.4.2, pytest-cov 6.3.0,
Ruff 0.13.3, mypy 1.18.2, build 1.3.0, setuptools 80.9.0 and wheel 0.45.1.
No new downloads or hosted services were used. Package stays unreleased 0.0.1.
Unity 6000.6.3f1 is a future integration target; no Unity process is launched.

## Findings and limitations

[Independent review](review-phase-4.md) found failed-S3 source selection,
preview-size validation after publication and unused-palette rejection. Each has
failing-then-passing regressions. Null/invalid run metadata now produces typed
errors. Host checks also reject changed sidecar values, material/socket bindings,
synthetic axis/unit faults, corrupted PNGs and changed source hashes.

An initial offline run still expected S3 to be unavailable; its future-stage
fixture now exercises S4. Another run exposed a README example requiring an
initialized workspace; that example is documented with the Windows setup flow
and the command-doc regression passes. The latter failure is preserved in
pytest-doc-example-failure.txt and verification-doc-example-failure.json. Early
Blender extension-cache access warnings are absent from final golden logs after
temporary-path redirection.

Current limits:

- CPU audit checks visibility/framing only. Human artistic review remains REVIEW.
- FBX roundtrip is Blender-only. Intended Unity settings (scale 1, useFileScale,
  bakeAxisConversion false) must be tested in the native Phase 5 importer.
- Material color/metallic/roughness work. S3 texture interchange explicitly returns
  NOT_RUN/5 before writes; arbitrary texture/plugin assets are not silently used.
- Normal diagnostics apply to the supported convex primitive modules. Advanced
  concave modeling, animation/rig export and arbitrary external projects are outside
  this phase. Armatures are rejected.
- OS sandbox enforcement, gameplay, collider physics, EditMode/PlayMode, standalone
  playability, profiling and external hidden qualification remain unavailable.
- Builds create fresh evidence; no producer cache/resume/repair claim is made.
- Original blueprint SHA-256 remains
  9d92fea8880b03b6d00e0bbe69b6fb8c1bf3f22f4c1ff16c1de7ae1f42970505.

Next gate: Phase 5 must import these exact exports through native Unity Editor
APIs, build materials/prefabs/scenes, prove scale/orientation, stable GUIDs and
object counts across repeated builds, and execute compilation/EditMode plus
managed rollback checks. Stop at the Phase 4 boundary.
