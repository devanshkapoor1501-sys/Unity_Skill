# PolyForge approved implementation sequence

Authority: PolyForge_v5_1_Expert_MultiWorker_Logic_Hardened_Blueprint.docx,
reviewed at the user's request on 2026-10-28. SHA256:
8f186fa13ce3fc085cab96ee5991dce2e85dde36277f2c6c631f7e8d5a9331d6.
Section 12 preserves the approved v4 Phase 0â€“6 work orders unchanged; their
paragraph comparison is recorded in the Phase 6 evidence. The v4 source remains
archived byte-for-byte in docs/source and available in Git history. The original research document was not supplied.

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
| 7 | Workforce contracts, classification, discovery, role/authority boundaries, leases; original robot rig, Idle/Walk and Animator | Baseline/migration inventory, sequential-role parity, non-robot orchestration, real animation/binding tests |
| 8 | Specialist asset/texture handoffs; original six-frame sprite pipeline | Role permissions, handoff inspection, alpha/pivots and real controllable 2D tests |
| 9 | Supervision, human review, eight repairs, cross-app rollback, 12 recipes | Twelve faults, six mutants, authority/misleading-test challenges, race/crash/cache recovery |
| 10 | Expert skill/reference routing, two host guides and optional bounded MCP | Skill/knowledge/permissions tests, actual host evidence, fake MCP identity/cancellation |
| 11 | Core v1.0, second genre, evaluator, benchmarks, profiling, static inspection | Original release gates plus multi-worker safety, parity and accurate core-only claims |
| 12 | Advanced Blender modeling, topology, sculpt and procedural geometry | Section-12/v5.1 per-domain good/bad and transfer fixtures |
| 13 | PBR materials, UV, texturing, rendering and visual consistency | Versioned source/channel provenance and separate technical/aesthetic review |
| 14 | Characters, creatures and advanced rigging/animation | Rig-family limits, independent deformation/motion and transfer evidence |
| 15 | Advanced Unity C#, gameplay, physics, AI, UI and architecture | Mechanic-specific runtime, negative and existing-project tests |
| 16 | Worlds, levels, lighting, audio, performance and integration | Editable integration, measured hardware/profile and independent visual review |
| 17 | Generalist production orchestra and expert v2 release | Separately controlled holdouts, frozen competency denominators and explicit domain gaps |

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

Before Phase 7, read Section 12, Chapters 16â€“18 and Appendices E/G together.
The expanded roadmap introduces no implemented commands or expertise claims by
itself. Workers may run sequentially; actual subagents and independent evaluator
ownership require distinct evidence. Phase 6 remains one bounded arena fixture.
