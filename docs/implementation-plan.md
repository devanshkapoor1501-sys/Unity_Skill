# PolyForge approved implementation sequence

Authority: PolyForge_Codex_Implementation_Blueprint_v4_Logic_Corrected.docx in the
repository root. Preserve it. Its normative sections override illustrative older
examples. The original research document was not supplied.

## Global decisions

- One repository in the requested folder; native Python CLI and separate Unity package.
- Python 3.11+; local Python 3.12.14, Blender 5.2.2 LTS, Unity 6000.6.3f1.
- Installed URP template declares URP 17.6.0, Input System 1.19.0, Test Framework 1.8.0.
- Apache-2.0 for original source. Windows Editor/standalone first.
- Optional stdio MCP bridge and portable skill; no core model dependency.
- Runtime network off; dependency downloads require opt-in (Python setup approved in chat).
- Independent hidden qualification is external; no private evaluator material in this repo.
- Tool success never implies game acceptance; missing tests are NOT_RUN/BLOCKED.
- Dry-run and invalid inputs write nothing. No raw Unity serialized-YAML editing.
- Every phase writes an exact evidence report and stops at its acceptance boundary.

## Deliveries

| Phase | Deliverable | Exit evidence |
| --- | --- | --- |
| 0 | Packaging, CLI grammar, capability/result schemas, registry, test/CI/skill scaffold, benchmark interfaces | Fresh install, help/discovery, model-free fixtures, lint/types/coverage, zero-side-effect checks |
| 1 | Doctor, config, subprocess ownership, locks, atomic state/events, redaction and policy | Windows path/Unicode/junction tests, timeout/lock recovery, truthful trust mode |
| 2 | Manifest/intent compiler, semantic graph, support classification, DAG/cache and scenarios | Eight good/bad fixtures, unsafe-input rejection, material-only invalidation |
| 3 | Blender worker and five semantic recipes | Three real fixtures, parameterized reuse, geometry metrics, expansion-limit negatives |
| 4 | Four-view audit, FBX/material sidecars, axes and hashes | Nonblank views and reproducible export evidence; real Unity import awaits Phase 5 |
| 5 | Native Unity import/material/prefab/scene APIs, bindings and early repairs | Compilation/EditMode, stable GUID/counts on repeat build, scale/reference fault and rollback |
| 6 | Playable arena, input/health/patrol/timer/restart, independent public behavior harness | Five real PlayMode scenarios, two mutants, manual play; player claims need standalone smoke |
| 7 | One robot rig family, action slots/channelbags, Idle/Walk and Animator | Real Blender frame samples and Unity motion/bone/transition tests |
| 8 | Six-frame sprite baking, metadata, Unity slicing and flipbook | Alpha/framing/pivot/order checks and real controllable 2D PlayMode fixture |
| 9 | Eight repair playbooks, full cross-app journal/reimport/rollback, 12 recipes | Twelve faults, six mutants, wrong-manifest/misleading-test rejection, crash/cache recovery |
| 10 | Validated portable skill, two host guides and bounded stdio MCP bridge | CLI doctests, host evidence, fake MCP client, identity/cancellation, model-disabled operation |
| 11 | Second genre, external evaluator, benchmarks, profiling, static inspection, release package | Windows E2E, hidden qualification, tool-parity/category results, original hashes, performance/security evidence |

## Non-negotiable qualification

Maintain >=90% branch coverage for security/contracts. Separate Blender, Unity
compile, EditMode, PlayMode, player-build, manual and hidden-evaluator outcomes.
Cover blueprint T01-T12. Detect collision/restart/win/damage/navigation/input
mutants. Frozen seeds/steps require declared tolerances, not binary physics claims.

Default profile: Windows player, 1280x720, declared quality, 10-second warmup,
three 60-second measurements; target median >=30 FPS, P95 frame <=50ms,
peak RSS <=2GB, load <=30s. Obtain actual hardware and measurements first.

Use TRUSTED_LOCAL with disclosure until actual OS denial probes qualify a
Windows Sandbox execution profile. Unsupported profiles deny untrusted inputs.
Never open original projects in Unity for inspection: static scan or cloned
runtime copy with complete before/after original hashes.

Prepare artifacts locally. Public publishing, remote tags and deployment are
separate actions. Unavailable external checks prevent full release claims but
must not be concealed by passing development checks.
