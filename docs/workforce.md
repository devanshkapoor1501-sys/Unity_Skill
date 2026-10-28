# Phase 7 task and worker workflow

The engine accepts an explicit task classification supplied by the user or host:
EXPLAIN, INSPECT, CREATE_ASSET, ANIMATE, FIX_PROJECT, ADD_MECHANIC or BUILD_GAME.
It preserves the exact original brief and feature IDs. This classifier is not a
natural-language model: unsupported interpretation needs host/user clarification.
EXPLAIN does not require an asset recipe or launch Unity. A single mesh task uses
only Blender; supported complete-game tasks retain S0–S5. Inspection/repair tasks
without a supported executor remain REVIEW/NOT_RUN rather than producing a game.

## Task input

Create task.json in the authorized workspace and save its exact `brief` text
as task-brief.md. Paths are resolved under that workspace; inputs are strict JSON.

```json
{
  "schema_version": "1.0.0",
  "brief": "Create an industrial crate with editable source.",
  "task_class": "CREATE_ASSET",
  "domain_tags": ["blender"],
  "feature_ids": ["editable_source"],
  "capability_id": "mesh.props.crate.v1",
  "input": {
    "schema_version": "1.0.0",
    "asset_id": "industrial_box",
    "parameters": {"size_m": [1.1, 0.8, 1.3]}
  }
}
```

```console
polyforge workforce roles --workspace . --json
polyforge workforce plan --workspace WORKSPACE --brief task-brief.md --dry-run --json
polyforge workforce plan --workspace WORKSPACE --brief task-brief.md --json
polyforge workforce run --workspace WORKSPACE --plan workforce/TASK_ID/plan.json --mode sequential --json
polyforge workforce status --workspace WORKSPACE --run-id TASK_ID --json
polyforge workforce review --workspace WORKSPACE --artifact-id ARTIFACT_ID --json
polyforge workforce cancel --workspace WORKSPACE --run-id TASK_ID --job-id job_1 --json
```

Use IDs and plan paths returned by the engine. `run --dry-run` is also pure.
Plan identity includes request and implementation fingerprints, preventing a
changed engine code, schema or Unity package from silently reusing an older job's success.

## Roles, ownership and evidence

Animation uses Intent Analyst → Rig/Animation Artist → Animation Inspector →
Unity Integration. Mesh creation uses the same coordinator with a mesh producer
and geometry inspector, without a robot or game manifest. Role descriptions live
in roles/; enforced capability subsets live in workforce/permissions.py.

Production and inspection dispatch through the shared versioned capability
registry. The coordinator leases asset ownership with a process birth identity,
token and expiry; live owners cannot be displaced by expired time alone. It
heartbeats active execution and propagates cancellation to the owned process
runner. Cancellation fences publication; expired dead jobs can be reclaimed.
Committed results are reused, while changed candidate bytes are rejected.
Durable operation and native completion receipts bridge a crash before the
coordinator commits. Resume verifies file hashes, skips completed generation or
asset import, and repeats outstanding checks. This does not establish the full
cross-application rollback guarantees reserved for Phase 9.

Candidates contain hashed source files, brief identity and a revision. Reviews
bind to that exact digest and cannot self-approve. Inspectors read candidate
files; only the coordinator publishes the receipt. Approved candidates enter
native Unity under one project writer lock. The original playable arena is
preserved, and a separate AnimationArena demonstrates imported motion.

The current engine executes registered operations sequentially. `--mode single`
provides the single-worker comparison path with the same technical checks.
Neither mode claims parallel AI agents or an independently controlled evaluator.
Native host delegation has no verified adapter and is reported UNAVAILABLE.
Different role identities on the same host are DIFFERENT_ROLE_SAME_HOST; protected
hidden evaluator storage and authority remain separate release requirements.

Local discovery records installed binary paths and resource availability without
launching applications. Presence is UNPROBED until actual version execution.
Unfamiliar Python/C#/bpy code and remote retrieval remain blocked; no reference
or role prompt can grant shell, network, installation or file access.

## Supported animation

animation.robot.rig.v1 creates one rigid mechanical robot family from the existing
parameterized mesh. Every module has a named bone and full rigid weights; sockets
retain their parent bindings. Idle and Walk are one-second slotted Blender
actions with explicit channelbags, five measured frames and an in-place root.
Editable source, FBX, motion samples and four pose previews are preserved.

The technical inspector checks actual evaluated skin/socket attachments, bone
mapping, alternating limb motion and loop closure. Native Unity tests check the
imported clips, skin weights, Animator transitions and real PlayMode skin motion.
Wrong bone mapping, disconnected weights and a missing transition are deliberate
negative fixtures. This family does not establish humanoid, facial or arbitrary
retargeting support. Visual appearance and protected acceptance remain distinct.

The local build tools and pinned Blender/Unity versions described in the
[development guide](development-guide.md) are still required. Portable host/plugin
qualification remains Phase 10; this phase supplies the coordination foundation.

## Reproduce the animation handoff

Start with a managed workspace whose S5 arena passed its native checks. For a
new workspace, run `polyforge init WORKSPACE`, then `polyforge build --workspace
WORKSPACE --through S5`; first-time Unity package resolution needs the existing
explicit download approval. Copy `examples/phase7/animation-task.json` to
`WORKSPACE/task.json` and its matching `animation-brief.md` to
`WORKSPACE/task-brief.md`. Run the plan/run commands above using returned IDs.
Use `--mode single` for the comparison path. These modes run the same registered
operations; they do not benchmark real model workers or parallel host agents.

For a crate-only handoff, create an empty authorized workspace and copy the
matching crate example files instead. No game manifest or Unity project is
required. This exact route is exercised from the isolated installed wheel.
