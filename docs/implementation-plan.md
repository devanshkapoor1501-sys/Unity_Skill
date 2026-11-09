# PolyForge implementation sequence and conditional v7 roadmap

Historical Phase 0–11 authority: PolyForge_v5_1_Expert_MultiWorker_Logic_Hardened_Blueprint.docx,
reviewed at the user's request on 2026-10-28. SHA256:
8f186fa13ce3fc085cab96ee5991dce2e85dde36277f2c6c631f7e8d5a9331d6.
Section 12 preserves the approved v4 Phase 0â€“6 work orders unchanged; their
paragraph comparison is recorded in the Phase 6 evidence. The v4 source remains
archived byte-for-byte in docs/source and available in Git history. The original research document was not supplied.

Future-facing authority (2026-11-08): the supplied
PolyForge_v7_0_Tool_Competency_Development_Blueprint_Phases_0-18.docx
(SHA-256 `a7dca4b3b534859879e435f82442f2f8667dbcdb5e5367ee125d5a3575fff29b`).
The local text extract, `.tmp/v7-blueprint.txt`, has SHA-256
`2f0d8dcc12a233ddd860bac417109eb0d498680aed018cac20c857ac00704333`.
v7 supersedes earlier future-facing mission, benchmarks, release proposals and
Phase 12–18 instructions. Historical Phase 0–11 work orders, evidence and open
gates remain preserved; older plans are archival rather than competing future
instructions. Source and actual tests determine implementation status; this
roadmap is not a test certificate or approval to execute every proposed phase.

## Global decisions

- Current product mission (v7): a portable, model-neutral Blender/Unity
  tool-competency Agent Skill backed by the existing local capability engine.
  Preserve the original user task, choose appropriate tools and verify the
  requested result. Games are explicit user workloads or regression fixtures;
  complete-game generation is not the default deliverable or a universal gate.
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
| 9 | Supervision, human review, eight repairs, cross-app rollback, 12 defect fixtures | Twelve faults, six mutants, authority/misleading-test challenges, race/crash/cache recovery |
| 10 | Expert skill/reference routing, two host guides and optional bounded MCP | Skill/knowledge/permissions tests, actual host evidence, fake MCP identity/cancellation |
| 11 | Core v1.0, second genre, evaluator, benchmarks, profiling, static inspection | Original release gates plus multi-worker safety, parity and accurate core-only claims |
| 12 | TECHNICAL EXIT COMPLETE: modeling/export/import repair verified in the recorded workflow | Real Unity reproduced and corrected the coolant outlet, rejected injected reflections, and verified main/LOD import, source integrity, rollback and regressions. Artistic review remains REVIEW. |
| 13 | NOT RUN: separately approved independent equal-tool pilot | Frozen charter, budget/deadline and evaluator; ten attempts across five pairs, tool parity, independent rubric, negatives, reuse and CONTINUE/NARROW/STOP/INCONCLUSIVE decision |
| 14 | CONDITIONAL: version-aware knowledge and task routing | Reuse existing catalog/router; additive competency records, task-first routes, exact version/source provenance, nonmutating read-only paths and honest coverage |
| 15 | CONDITIONAL: Blender competencies in separately budgeted submodules | One selected domain/version at a time; native positive/negative, unseen transfer, source reopen, independent review and existing-route regressions |
| 16 | CONDITIONAL: Unity competencies in separately budgeted submodules | One selected Editor/runtime domain; managed-project safety, correct assemblies/lifecycle, native EditMode/PlayMode as relevant, negatives and independent variations |
| 17 | CONDITIONAL: cross-tool composition and workflow evaluation | Coordinate/asset invariants, independent transfer and fault injection; optional animation and gameplay lanes separately funded/tested; real host evidence for concurrency claims |
| 18 | CONDITIONAL: scope-honest portable skill release and investment decision | Application/version/status coverage, scoped install/native/regression/security/license/provenance audits; SCOPED RELEASE/LABELED PREVIEW/KEEP PERSONAL TOOL/STOP INVESTING |

## Current status and future entry gates

[The Phase 0–10 audit](../reports/phases-0-10-audit.md) records 264 implemented
requirements and 17 permitted external/later blocks across 281 rows. These are
historical audited results, not fresh tests. [Phase 11](../reports/phase-11.md)
is a technical checkpoint with stable CORE v1.0 release **BLOCKED**; the later
user sequencing amendment allowed Phase 12 development without closing those
release gates. [The v7 reconciliation](../reports/phase-11-reconciliation-v7.md)
records reported versus newly witnessed evidence.

[Phase 12](../reports/phase-12-v7.md) has completed its v7 technical exit as
VERIFIED_IN_WORKFLOW for the recorded Blender 5.2.2 / Unity 6000.6.3f1 workflow.
The coolant outlet, main/LOD imports, material assignments, source hashes,
GUIDs, and arena/platformer regressions passed their recorded checks. Artistic
review remains REVIEW; extreme-ratio ridge attachment and fresh standalone/player
checks remain unqualified or NOT_RUN as stated in the report. This technical
completion does not close Phase 11's stable-release gates.

Phase 13 requires a separate owner-approved charter, resource budget/deadline,
independent evaluator and equal-tool arms. The v7 proposal is 16 focused hours
over seven days (up to six for Phase 12 and ten for Phase 13), five unseen paired
tasks, and a separately preapproved one-hour reuse check on days 8–14.
Proposed thresholds are at least 4/5 assisted outputs accepted, zero undetected
critical coordinate/socket defects, no worse acceptance than equal-tool Codex,
and at least 20% lower median time or 30% fewer manual corrections without
quality loss. The current charter records the owner’s go-ahead for the Phase 13
trial cap and decision rules. The separate reuse allocation is pending.
Stop on expired authority, budget/deadline overrun, unsafe original-project
mutation, missing evaluator, tool-parity failure or unrecovered critical
regression. Failed/inconclusive evidence does not authorize expansion.

Phases 14–18 are conditional proposals after a permitted Phase 13 decision and
separate scoped approval. Proposed caps are 12 hours for Phase 14, 12 hours for
the first Phase 15/16 submodule or Phase 17 lane, and eight hours for Phase 18
excluding separately approved external evaluation. Additional modules need
their own caps. Animation and gameplay remain knowledge domains together;
their executable lanes are optional, independently funded and verified.
No stable tag, universal expertise claim or automatic continuation follows
from this documentation update.

The [Phase 13 pilot charter](plans/2026-11-09-phase-13-pilot-charter.md)
records the owner terms, candidate preflight, and evaluator protocol. Trial
execution remains NOT RUN.

Support records must distinguish knowledge, native execution and independent
transfer: REFERENCE_ONLY, VERSION_PROBED, EXPERIMENTAL, VERIFIED_IN_WORKFLOW,
INDEPENDENTLY_ACCEPTED, ASSISTED, UNSUPPORTED and BLOCKED. These planned support
states are distinct from invocation PASS/FAIL/BLOCKED/NOT_RUN/REVIEW and do not
relabel historical results or imply a newly implemented schema.

## Preserved historical qualification and continuing safety

The historical gameplay/performance gates below apply to their original
fixtures and release scope. They do not impose a playable-game requirement on
every new tool task or replace the conditional v7 gates above.

Audit erratum (2026-10-30): the Phase 9 table originally said “12 recipes”. The
preserved v4 work order 9.8 requires “Fault-inject 12 cross-application cases”,
and v5.1 retains that defect gate. The table now reflects that requirement;
the twelve defect cases and separate detection/repair evidence remain required.

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
