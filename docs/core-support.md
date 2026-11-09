# Core support and remaining expertise

PolyForge is a portable, model-neutral Blender/Unity tool-competency Agent Skill
backed by the existing local capability engine. Preserve the user's requested
task: explanation, inspection, asset creation/editing, animation, scene or
component work, diagnostics, testing, or export/import. Build a game only when
explicitly requested. Existing arena, robot and platformer fixtures remain
regressions; they do not establish general tool mastery.

Historical Phases 0–10 retain their audited implementation evidence. Phase 11
is a technical checkpoint; stable CORE v1.0 release remains **BLOCKED**.
Phase 12's v7 technical exit is **COMPLETE**, verified in its declared Blender/Unity
workflow. Artistic qualification remains REVIEW; independent equal-tool trials
belong to the separately gated Phase 13. Future planning follows v7.1; see
[the implementation sequence](implementation-plan.md) for authority and gates.

Use `polyforge capability list --json` and `capability show ID --json` to inspect
the versioned executable contract. Knowledge routing proposes relevant tools
and roles; it does not prove that every requirement in a prompt is supported.

| Area | Current bounded support | Remaining work |
| --- | --- | --- |
| Asset modeling | Static recipes plus [room kits, vehicles, mechanical props, organic practice and typed composition](modeling.md) with editable sources and separate topology checks | Freeform extrusion, decals, sculpt/retopo, broader Geometry Nodes and evaluator-owned transfer |
| Materials | Declared simple material/texture handoffs and native import checks | Selected Blender UV/material work in conditional Phase 15; Unity material/rendering work in conditional Phase 16; independent visual review required |
| Animation | Original modular robot rig, Idle/Walk, Unity bindings and six-frame sprite workflow | Selected Blender/Unity competencies in conditional Phases 15/16 and separately funded cross-tool animation lane in Phase 17 |
| Gameplay | Original 3D survival arena and approved-sprite 2D checkpoint course, with explicit physical oracles and faults | Selected Unity component/physics/AI/UI work in conditional Phase 16; optional gameplay-systems lane in Phase 17 |
| Worlds | Managed prototype scene construction and native bindings | Selected scene, lighting, audio and profiling competencies in conditional Phases 15/16; cross-tool integration in Phase 17 |
| Generalist orchestration | Task-selected role graph, frozen handoffs, ownership, review, resource admission and sequential execution | Task-first versioned knowledge/routing in conditional Phase 14; cross-tool transfer and actual host delegation qualification in Phase 17 |
| Existing projects | Bounded static inventory, hashes/mtimes, requested/resolved package versions, GUID diagnostics and source syntax analysis | Compilation/runtime compatibility and safe approved changes require separate native evidence |
| Measurement | Declared rendered-loop standalone profile and local-mode measurements | Codex-run Phase 13 pilot with a frozen verifier rubric, matched tools and native receipts |

The [Phase 12 checkpoint](../reports/phase-12.md) reports Unity PASS for eight
main/LOD FBXs from four parameterized families; its coolant-valve composition
was Unity NOT_RUN. The [v7 repair](../reports/phase-12-v7.md) reproduced the
outlet reflection, then passed all twelve family/composition main/LOD imports,
ten applicable reflection mutants and twenty-four transformed-parent cases.
Material triangle assignments, source hashes, GUIDs and metadata were checked.
This qualifies the tested handoff and versions, not arbitrary exports or
independent unseen transfer.

Knowledge/reference coverage, native execution and independent transfer are
separate claims. v7 calls for REFERENCE_ONLY, VERSION_PROBED, EXPERIMENTAL,
VERIFIED_IN_WORKFLOW, INDEPENDENTLY_ACCEPTED, ASSISTED, UNSUPPORTED and BLOCKED
support records; these are planning vocabulary, not a claim that the current
schemas implement the full competency registry. Invocation results retain
their separate PASS/FAIL/BLOCKED/NOT_RUN/REVIEW meanings.

Phase 13 preparation has recorded the trial cap and decision rules. V7.1 uses
a separate Codex verifier for internal trials, and requires frozen cases and
C/D parity before paired execution. Phases 14–18 remain conditional and individually
scoped. Phase 18 is a scope-honest release audit, with stable claims restricted
to accepted task classes. Animation and gameplay may both have reference
coverage while executable modules are separately qualified.

The [Phase 13 charter](plans/2026-11-09-phase-13-pilot-charter.md)
records the owner terms, candidate preflight, and evaluator protocol.
Trial status is NOT RUN.

Networking, multiplayer, production save systems, arbitrary mechanics, broad
character rigs, unrestricted sculpt artistry and universal package/API
compatibility are not implemented merely because references discuss them.
GUI-only and visually subjective work needs an explicit assisted/manual path
and appropriate evidence.

The engine does not own a model provider or an external evaluator. Different
local role names are not independent model identities. Missing host delegation,
hidden evaluation, required visual review or hardware measurements remain
visible gaps. A successful operation is separate from independently accepted
completion of the user's task.

For unknown work, preserve the original requirements, select versioned official
references, propose a bounded disposable probe, test positive/negative and
transfer cases, and promote a reusable capability only when its evidence
supports it. Never replace an unfamiliar request with an available template.

Static inspection reads a present `Packages/packages-lock.json` as bounded data,
including transitive resolved versions. A missing lock is `NOT_AVAILABLE`;
malformed JSON or missing version values are rejected. This observes recorded
resolution, without downloading packages or verifying compatibility. See
[Unity's lock-file documentation](https://docs.unity.com/en-us/engine/6000.5/manual/packages-list/dependencies-lp/upm-conflicts-auto).

See [worker architecture](worker-architecture.md),
[approved phases](implementation-plan.md), [knowledge routing](knowledge.md),
[security policy](../SECURITY.md) and [Phase 11 evidence](../reports/phase-11.md).
