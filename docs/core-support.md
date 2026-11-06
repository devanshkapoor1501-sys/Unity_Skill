# Core support and remaining expertise

This is a portable skill and local capability engine under Phase 11
qualification. Example objects and games teach tool use, worker handoffs and
verification. They are not a substitute for the user's requested game and do
not demonstrate unrestricted game-production competence.

Use `polyforge capability list --json` and `capability show ID --json` to inspect
the versioned executable contract. Knowledge routing proposes relevant tools
and roles; it does not prove that every requirement in a prompt is supported.

| Area | Current bounded support | Remaining work |
| --- | --- | --- |
| Asset modeling | Static recipes plus [room kits, vehicles, mechanical props, organic practice and typed composition](modeling.md) with editable sources and separate topology checks | Freeform extrusion, decals, sculpt/retopo, broader Geometry Nodes and evaluator-owned transfer |
| Materials | Declared simple material/texture handoffs and native import checks | Broader UV/PBR, baking, channel packing and visual consistency in Phase 13 |
| Animation | Original modular robot rig, Idle/Walk, Unity bindings and six-frame sprite workflow | Character/creature rig families, deformation, motion and retargeting in Phase 14 |
| Gameplay | Original 3D survival arena and approved-sprite 2D checkpoint course, with explicit physical oracles and faults | Broader mechanics, AI, UI, architecture and composition in Phase 15 |
| Worlds | Managed prototype scene construction and native bindings | World/level design, lighting, audio and integrated device profiles in Phase 16 |
| Generalist orchestration | Task-selected role graph, frozen handoffs, ownership, review, resource admission and sequential execution | Broader domain composition, actual host delegation qualification and evaluator-owned transfer in Phase 17 |
| Existing projects | Bounded static inventory, hashes/mtimes, requested/resolved package versions, GUID diagnostics and source syntax analysis | Compilation/runtime compatibility and safe approved changes require separate native evidence |
| Measurement | Declared rendered-loop standalone profile and local-mode measurements | No authenticated model comparison or causal specialization claim without actual comparable trials |

Networking, multiplayer, production save systems, arbitrary mechanics, broad
character rigs, unrestricted sculpt artistry and universal package/API
compatibility are not implemented merely because references discuss them.
GUI-only and visually subjective work needs an explicit assisted/manual path
and appropriate evidence.

The engine does not own a model provider or an external evaluator. Different
local role names are not independent model identities. Missing host delegation,
hidden evaluation, required visual review or hardware measurements remain
visible gaps. A successful operation is separate from an accepted game.

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
