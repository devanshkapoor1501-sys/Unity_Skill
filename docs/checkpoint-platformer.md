# Checkpoint platformer capability

`unity.game.platformer.v1` reuses an already approved and natively imported
six-frame sprite prefab, animation controller and shared engine infrastructure.
The current course is a bounded development example: A/D movement, grounded
Space jump, checkpoint respawn, damaging hazards, a goal, failure and R restart.
An unsupported request must retain its missing requirements.

Create a workspace-local JSON request after the sprite import passes:

```json
{
  "schema_version": "1.0.0",
  "scene_id": "checkpoint_course",
  "seed": 42,
  "sprite_receipt": "runs/ACTUAL_SPRITE_RUN/bindings.json",
  "layout": "checkpoint_course_v1"
}
```

Replace the run placeholder with the actual workspace-owned receipt. The
approval, artifact registry, atlas, prefab/clip GUIDs, animation assets and
distinct nonzero signed Unity local identifiers are checked before execution.
Source changes invalidate the frozen worker plan.

```console
polyforge capability show unity.game.platformer.v1 --json
polyforge platformer build --workspace ROOT --input platformer-input.json --dry-run --json
polyforge platformer build --workspace ROOT --input platformer-input.json --standalone --json
```

The capability dispatcher accepts the same typed input. Its optional
`"standalone": true` requests the standalone build and gameplay gates. CLI
`--standalone` also enables those gates. A dry run validates without writes or
native execution.

A BUILD_GAME worker request selects intent analysis, Unity integration and a
gameplay QA inspector. It omits Blender production stages because the approved
sprites already exist. The inspector checks sealed native XML, exact source
identity and observed physical traces. It re-scores behavior rather than
trusting a producer's saved PASS label. Required independent original-brief
acceptance and visual review remain separate promotion gates.

Native checks include two EditMode tests and 24 PlayMode tests, eleven nominal
physical scenarios, three keyboard traces and eight fault mutants. Standalone
gameplay repeats the nominal scenarios. The public oracle applies a fixed
float32 round-trip tolerance to contract coordinates and a hazard contact skin
derived from the pinned Physics2D contact offset. Goal contact and health/reset
requirements remain physical checks. Timing/schedules are version-specific.

Builds preserve generated assets outside the new Platformer subtree. Rollback
discovery includes this style and its immutable input archive; the latest-state
marker belongs to the managed transaction snapshot. No original user project
is opened or changed by static inspection.

Native qualification results are in [Phase 11](../reports/phase-11.md). The
commands above contain workspace/run placeholders and do not constitute a
claim that an arbitrary supplied project or game brief has passed acceptance.
