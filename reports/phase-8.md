# Phase 8 — inspected asset packages and a controllable 2D demo

**Phase acceptance: PASS for the bounded development scope below. Game acceptance:
PARTIAL.** The required asset handoffs, sprite bake and independent 2D fixture
executed successfully on Windows. Artistic approval remains REVIEW. Protected
evaluation, host qualification, OS isolation and release profiling remain open.
Phase 9 has not started.

Authority: the supplied v5.1 blueprint, Section 12 Phase 8, Chapters 16–18 and
Appendix G. Blueprint SHA256:
`8f186fa13ce3fc085cab96ee5991dce2e85dde36277f2c6c631f7e8d5a9331d6`.
Starting commit: `ba70092d860055c8b9f67cd157e4e3fcf9777bfa`.
Implementation branch: `codex/polyforge-phase-8`. The blueprint is preserved.

Phase 7 was pushed and verified before Phase 8 implementation began. Both its
branch run `40681944577` and [main run `40682278940`](https://github.com/devanshkapoor1501-sys/Unity_Skill/actions/runs/40682278940)
passed Windows Python 3.11, Windows Python 3.12 and Ubuntu Python 3.12 jobs.
Those results apply to Phase 7; this report does not claim remote Phase 8 CI.

## Delivered behavior

- Five specialist role definitions: Asset Architect, Modeler, UV/Material Artist,
  Asset Refiner and Asset Quality Inspector. Explicit AssetSpec inputs preserve
  the original brief, silhouette, dimensions, primitive family, polygon budget,
  UV0, palette, basic material targets, pivot, collider, licenses and rubric.
  The host supplies this interpretation; unrestricted natural-language asset
  design is not claimed.
- Versioned bundles bind editable geometry, logical geometry/UV source, material
  sidecars, FBX and measured geometry to the spec, original brief and revision.
  Missing sources, licenses, unsafe references or coordinate mismatches fail.
  Optional reference inputs are DATA_ONLY and cannot authorize actions.
- A bounded model → inspection → scoped material refinement → reinspection
  workflow retains both source revisions. Two distinct asset families completed
  it. Unrelated workflows overlap, including material planning; native Blender
  work is conservatively queued. Same-asset leases prevent conflicting writers.
  Role separation is DIFFERENT_ROLE_SAME_HOST, without evaluator independence.
- Exactly six transparent robot frames from the registered Phase 7 Walk source,
  a fixed camera, editable source and an untrimmed atlas. Independent PNG decoding
  checks real pixels, frame bounds, alpha, order, pivot and atlas consistency.
- Native Unity Sprite Data Provider slicing, imported sprite identities, an
  `m_Sprite` reference curve, a measured one-second looping clip, prefab and
  separate controllable SpriteArena scene. Rigidbody2D collision, injectable
  input, real keyboard input and input-handler cleanup execute in PlayMode.
- Direct supplied sprites use a Unity route without Blender discovery or
  generation. The current importer supports the demonstrated six-frame 128px
  format; the classifier does not impose Blender's robot-baking route on 2D
  tasks. Other sprite layouts remain unsupported by this capability.
- Three registered capabilities through the existing dispatch:
  `asset.package.build.v1`, `sprite.robot.bake.v1` and `sprite.unity.strip.v1`.
  Command registry/help remain shared. The skill, plain-language README,
  developer guide and executable asset examples describe this executed scope.

Basic URP Lit base color, metallic and roughness are supported, with
smoothness = 1 − roughness. Advanced image textures and procedural PBR remain
Phase 13. Single primitive LOD and generated UV0 do not imply arbitrary topology,
hand-painted UVs or general texture production.

## Executed checks

Executed toolchain: Python **3.12.14**, Blender **5.2.2 LTS**, Unity
**6000.6.3f1**, URP **17.6.0**, Input System **1.19.0**, Test Framework **1.8.0**,
and the Editor's built-in **2D Sprite 1.0.0**. Windows is the executed native
platform. Linux mypy analysis is not Linux application qualification.

Commands ran from the repository root. For Python tests/builds, `TEMP` and `TMP`
pointed to the existing workspace `.tmp` directory. Retained scripts are copied
under `phase-8-evidence/scripts/` with `.py.txt` suffixes; native `process.json`
files retain complete application arguments, versions, ownership and exit codes.

| Gate | Exact command or retained driver | Exit / observed result |
| --- | --- | --- |
| Python/security/contracts | `.venv/Scripts/python.exe -m pytest --cov --cov-report=term-missing --cov-report=json:.tmp/phase8/coverage-final.json --junitxml .tmp/phase8/tests-final.xml` | **0; 269 passed**, 12 application-marked tests deselected; **95.05%** branch-enabled configured coverage; 90% threshold retained |
| Final correction tests | `.venv/Scripts/python.exe -m pytest tests/test_assets.py tests/test_sprites.py tests/test_phase8_review.py tests/test_phase6_contracts.py tests/test_workforce.py --junitxml .tmp/phase8/review-green.xml` | **0; 87 passed**, after the final native test inventory update |
| Lint/format | `.venv/Scripts/python.exe -m ruff check .` and `-m ruff format --check .` | Both **0**; 110 Python files formatted |
| Types | `.venv/Scripts/python.exe -m mypy` and `-m mypy --platform linux` | Both **0**; 82 source files each |
| Command docs | `.venv/Scripts/python.exe -m tools.generate_cli_docs --check` | **0** |
| Dependencies/build | `.venv/Scripts/python.exe -m pip check` and `-m build --no-isolation` | Both **0**; wheel and source distribution built |
| Existing Blender gates | `.venv/Scripts/python.exe -m pytest -m blender --basetemp .tmp/phase8/blender-regression --junitxml .tmp/phase8/blender-regression.xml` | **0; 9 passed**, including repeated fixtures, export/audit and orientation checks |
| Concurrent distinct assets | `.venv/Scripts/python.exe .tmp/phase8/run-assets.py` | **0**; crate and wall complete separate retained revisions, overlapping workflow windows, one queued Blender worker |
| Blender sprite bake | `.venv/Scripts/python.exe .tmp/phase8/run-bake.py` | **0**; six real frames, atlas, editable source and independent pixel audit |
| Existing and fresh native 2D | `.venv/Scripts/python.exe .tmp/phase8/native-final.py` | **0**; each project executes **5 Editor + 4 PlayMode** tests; fresh coordinator passes with an unavailable Blender path |
| Final asset coordinator | `.venv/Scripts/python.exe .tmp/phase8/asset-final.py` | **0**; full sealed producer → inspector handoff passes |
| Robot animation regression | `.venv/Scripts/python.exe .tmp/phase8/animation-final.py` | **0; 5 Editor + 2 PlayMode** tests, including physical mapping/limb/transition faults |
| Static and playable arena regressions | `.venv/Scripts/python.exe .tmp/phase8/regression-native.py` | **0; 17 static Editor + 1 arena Editor + 12 arena PlayMode**; independent public oracles and collision/restart mutants pass |
| Fresh wheel installation | `.venv/Scripts/python.exe .tmp/phase8/install.py` | **0**; 11 install/help/catalog/roles/plan/resource checks; local wheelhouse, `--no-index`; schemas, Unity source/metadata and sdist skill/roles verified |
| Installed asset commands | `.venv/Scripts/python.exe .tmp/phase8/installed-workforce.py` | **0**; real Blender asset via installed CLI plan/run/status/review; dry-run inventory unchanged |
| Installed sprite/asset input admission | `.venv/Scripts/python.exe .tmp/phase8/installed-inputs.py` | **0** driver; valid dry runs return **0**, invalid input **2**, all three preserve the complete workspace file inventory |

[Quality command records](phase-8-evidence/quality/commands.json),
[install commands](phase-8-evidence/install/commands.json),
[installed workflow commands](phase-8-evidence/installed-workforce/commands.json)
and [zero-write checks](phase-8-evidence/installed-inputs/commands.json) retain
full arguments and outcomes. Asset contracts measured **95.08%**, sprite
contracts/pixel audits **100%**, path policy **95.88%**, and lock handling
**90.08%**. Native applications run as separate gates; a model-free Python pass
does not stand in for application evidence.

## Native evidence and observations

| Output | Native identity / evidence |
| --- | --- |
| Concurrent crate | `asset_fa45468955174ba18eabaecf1545b864` |
| Concurrent wall | `asset_4ac6efa41ceb4d6e886b23f76fc0f084` |
| Registered robot bake | `sprites-210b82c4c9fa44d1` |
| Final 2D integration into the existing project | `sprite-unity-16aa676ff41a4e4e` |
| Fresh direct-sprite coordinator | `task_27bd6f684c81a83a_b15bbf5c`, native `sprite-unity-op_db071558788500db67320ebe8553659a` |
| Final asset coordinator | `task_edcbddfd75193954_67c463f2` |
| Installed asset workflow | `task_edcbddfd75193954_135d3c54` |
| Existing arena check | `game-check-c468f4dec0cd4d81` |

Both asset families first received a material rejection and then technical
approval after one scoped palette refinement. The original source/review was
retained. The inspector compares frozen brief/spec hashes, measured dimensions,
triangles, UV geometry digest, complete semantic material assignments and source
license/dependencies. A technical approval cannot satisfy required visual review.

The bake samples Walk frames 1/5/9/13/17/21. Frames are 128×128 RGBA, atlas
768×128, pivot (0.5, 0.1), PPU 64, FPS 6, without trimming. Unity's final
object-reference key lasts one frame: six keys at 0 through 5/6 seconds produce
the measured one-second clip. The initially attempted seventh key produced
1.166667 seconds and failed the unchanged duration test.

Final native XML requires the exact expected identities and passing results;
empty, skipped, substituted or duplicate tests cannot pass. Two Editor tests
deliberately reject missing/reordered sprite curves. PlayMode observes all six
actual imported sprites, wraparound, movement, wall collision, real W input and
input disposal on destruction. An early input test created its keyboard before
changing Editor input settings, which reset the device; the fixture was corrected
to use the established settings-before-device order and retained its assertions.

Repeated existing-project builds retained **identical complete binding reports**,
including all six sprite local IDs and prefab/scene/clip GUIDs. Existing 3D scene
bytes were compared before/after. A fresh project's GUIDs are independent.
See [repeat identity evidence](phase-8-evidence/parity.json). The final driver's
first progress line still says “3 Play”; its actual parsed XML records **4**.

## Review, measurements and limits

One fresh whole-phase review found four Important and two Minor issues. All were
fixed, along with related provenance and fresh-package-baseline defects found
during verification. RED outputs and raw failed native XML remain in the evidence.
An Editor destruction assertion was moved to actual PlayMode lifecycle testing;
the Editor test still checks replacement, identical assignment and clearing.
No failed check was relabeled as passing. See [review resolution](phase-8-review.md).

The [exploratory handoff benchmark](phase-8-evidence/benchmark.json) ran one
workflow and direct-generation sample per asset type. Crate: 20.063s versus
10.093s, 9.970s overhead. Wall: 17.563s versus 8.875s, 8.688s overhead. Geometry
and final material targets matched. Workflow runs include rejection/refinement;
direct runs begin with the final palette. Sequential trial order, warm caches
and n=1 prevent speedup or general model-quality conclusions. This is not the
release four-arm benchmark.

The atlas and crate/wall source previews were visually inspected, with limited
agent confidence **0.8**. This is source preview review, not protected artistic
approval, a new manual player review or a rendered standalone measurement.
Artistic approval remains **REVIEW**. Phase 6's manual evidence is preserved.

No new Python or third-party sprite dependency was added. Fresh Unity projects
did resolve the previously authorized template packages from Unity's registry;
the 2D Sprite package itself is installed with the Editor. Network authorization
is required for both fresh and existing projects unless already recorded.
Managed package updates require a verifiable source baseline; unproven edits
remain denied. No unchecked adoption or permission bypass was added.

The generic system skill validator remains **BLOCKED** by missing PyYAML and an
older helper's compatibility-field support. The narrower frontmatter/local-link
check passed. Complete portable-host validation remains Phase 10. Official
installed Data Provider documentation and executed native probes support the
specific API use; no general cross-version compatibility claim is made.

[Evidence index](phase-8-evidence/index.json) hashes source files, revisions,
handoffs, journals, process logs, test XML, PNGs, metadata and measurements. Two
editable Unity source archives include Assets, Packages and ProjectSettings,
omitting Library/Temp/UserSettings caches and players. [Public acceptance](acceptance_oracle.json),
[workforce lineage](workforce_evidence.jsonl) and
[knowledge records](knowledge_coverage.json) retain the authority boundaries.

Only Windows Editor execution is qualified here. No Phase 8 standalone build,
player smoke, performance measurement, hidden evaluator result, host-subagent
qualification or sandbox enforcement is claimed. Full cross-application rollback
remains Phase 9. Skill/MCP host qualification remains Phase 10. Phase 8 is saved
locally; remote Phase 8 publication is not part of this acceptance claim.

**Next gate:** Phase 9 supervision, evidence-based diagnostics, eight repair
playbooks, complete transactional rollback/reimport, crash recovery and gameplay
mutation challenges. Stop at this boundary until requested.
