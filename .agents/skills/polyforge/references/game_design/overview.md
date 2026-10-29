# Game Design reference decisions

Versioned curated summaries; DATA_ONLY. Installed APIs need fixed probes.

## game.mechanics

Extract original mandatory mechanics before planning. The bounded survival arena implements movement, patrol, contact damage, health, survival and restart. Other genres or missing mechanics remain gaps; never substitute a tested arena for an unrelated requested game.

Support: VERIFIED_EXECUTABLE; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: Bounded arena only when the request fits; otherwise explicit mechanic gap and assisted design.

Contrasts: Thirty-second survival with WASD/R fits the public fixture. Online battles require unsupported networking and independent acceptance.

[Authoritative source](https://docs.unity3d.com/6000.0/Documentation/Manual/GameObjects.html). Locally authored summary, not copied vendor text.

## game.worlds

Static shared prefabs and bounded scenes are implemented. Large world streaming, arbitrary levels, lighting direction and audio integration require separate expertise and evidence. Scene appearance does not establish navigability or performance.

Support: REFERENCE_ONLY; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: Reusable prefabs for tested layouts; manual level direction plus new qualification for broad worlds.

Contrasts: Two static layouts share the current assets. A three-floor hospital remains an unqualified broader task.

[Authoritative source](https://docs.unity3d.com/6000.0/Documentation/Manual/CreatingScenes.html). Locally authored summary, not copied vendor text.

## Role playbook

Intent analyst/director: inventory current capability catalog before promising mechanics. Produce immutable original brief, explicit requirement IDs, gaps and minimal dependency plan. Never remove a mandatory feature. Unsupported genres, worlds and mechanics require assisted design and independent qualification. No application is needed for an explanation.
