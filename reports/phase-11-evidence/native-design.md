# Phase 11 native gates — read-only implementation design

Inspected 2026-10-31 at `31827d1`, branch `codex/polyforge-phase-11`.
This document is a proposal, not native execution evidence. No implementation,
native run, test run, or commit was performed for this task.

## Findings grounded in current source

* `polyforge/unity/game.py:81` supports only the bounded 3D survival arena;
  `execute_game_checks` runs separate native EditMode and PlayMode suites and
  scores their traces with Python. Its player launch at lines 426–427 passes
  `-batchmode -nographics`, and line 475 explicitly returns profiling NOT_RUN.
* `unity_package/Editor/GameBuilder.cs:109` builds only PlayableArena, as a
  Windows64 Development player. It sets window defaults to 1280×720, which is
  not evidence of the actual rendered size. `Build` replaces the global build
  scene list with the arena at line 106.
* `unity_package/Runtime/ArenaPerformance.cs` currently collects Update delta
  times from startup, limits the list to 18,000 frames, quits smoke at fixed
  frame 150, reports engine-start-relative load, and leaves qualification false.
  Failed RSS reads become zero. None of these values qualify rendered performance.
* `SpriteBuilder.cs:28,59–64` creates SpriteArena: a zero-gravity six-frame
  animated sprite, WASD movement, one wall, and a camera. SpritePlayer overwrites
  both velocity axes every physics tick. There is no objective, hazard, health,
  session, win/failure, or restart. It is a useful 2D import/control fixture, not
  a second complete game. The benchmark brief `sprite_survival_game.md` requests
  more than the existing fixture implements; it must keep that original brief.
* `polyforge/sprites/integration.py:102,208` already hashes preexisting non-Sprites
  scenes before/after import. This does not yet cover preserving the original
  SpriteArena assets when another 2D game is built.
* `polyforge/unity/bridge.py:68,131` has fixed test-filter/mode allowlists;
  `polyforge/unity/recovery.py:68,159` discovers only arena/animation/sprite
  regression profiles. A new gameplay scene must join those protections.
* `profiles/windows-arena.json` already declares the exact required numerical
  budget, including 2,147,483,648 bytes (2 GiB). Preserve these thresholds.

## Minimal second game: bounded 2D checkpoint platformer

Keep PlayableArena and SpriteArena byte-for-byte. Add
`Assets/PolyForgeGenerated/Platformer/SpritePlatformer.unity` with a derived
player prefab, a small side-view level of static platforms, a checkpoint,
one visible hazard, a death plane, a finish trigger, and a HUD. Horizontal
movement + Space jump, R restart; gravity and grounded-only jump make this
meaningfully different from the arena's top-down survival loop. A checkpoint
changes respawn position; a hazard costs one life and respawns; exhausting
three lives enters FAILED; entering the goal enters WON; R resets position,
velocity, health/lives, checkpoint, timer, and state. Terminal states freeze
the motor until restart. Do not silently reclassify a survival benchmark as this.

Bound the first contract to a single scene, one actor, 3–8 static platforms,
one checkpoint, one hazard/death plane, and one goal, fixed 0.02 s steps, Windows
URP, and fixed jump/movement parameters. Reject nonfinite data, duplicate IDs,
out-of-bounds geometry, unsupported mandatory features, unreachable default
layout parameters, missing approved sprite bindings, and stale atlas/metadata
identities before native writes. The fixture's declared brief and layout remain
the acceptance source; no broad platformer/world support claim follows.

Reuse:

| Existing capability or contract | Actual reuse |
| --- | --- |
| `sprite.unity.strip.v1` | Approved atlas, SpriteRenderer references, six stable sprite IDs, Walk clip, Animator, source provenance; instantiate the existing Robot2D prefab without modifying it |
| `IPlayerInput`, `KeyboardPlayerInput` | Existing Movement.x and queued R semantics; subscription replacement/disposal pattern |
| `Health` | Configure three lives, Damage(1), ResetHealth; do not couple platformer to ArenaSession/ContactDamage |
| Scene/prefab APIs, `launch`, exact XML validation | Native creation, version binding, expected test inventories, owned processes |
| Arena scenario architecture | Frozen input schedules, observed physical traces, Python behavioral scoring, in-memory mutant fixtures |
| WorkspacePolicy, atomic_json, artifact registry, Unity lock | All paths, evidence seals, dry-run/invalid no-write behavior, single physical writer |

Add `IPlatformerInput : IPlayerInput` with `ConsumeJump()` and a small
`KeyboardPlatformerInput` which composes the existing keyboard adapter and queues
Space once. Do not add required members to IPlayerInput and break old adapters.
`PlatformerPlayer` replaces SpritePlayer only on the new prefab instance; preserve
vertical Rigidbody2D velocity during horizontal movement, apply a queued jump only
when grounded, and dispose inputs when replaced/destroyed. Grounding must observe
collider contact with the declared ground layer rather than velocity==0.

`PlatformerSession` owns state, checkpoint, lives, timer, round, reset behavior,
and bounded event records. Use a single small typed trigger component with
checkpoint/hazard/goal kinds and explicit actor/session binding; no generic
mechanic engine. `PlatformerHud` renders goal, lives, state, and controls.

## Concrete files and interfaces

Proposed additions are deliberately separate from old game contracts:

* `polyforge/contracts/platformer_build.schema.json`: strict schema for source
  sprite receipt identity, declared level/layout, seed, optional standalone.
* `polyforge/unity/platformer.py`: `compile_platformer_request(inputs, policy)`,
  `build_platformer(inputs, RunContext)`, `verify_platformer(policy, request,
  standalone=False)`. Persist immutable input and `.polyforge/platformer-latest.json`.
  Resolve approved existing sprite artifacts and hashes; do not rerun/rewrite
  SpriteBuilder just to construct the platformer.
* `polyforge/scenarios/platformer_oracle.py` and
  `polyforge/data/platformer_scenarios.json`: validate trace identity and schedule,
  then score physical/health/checkpoint/state invariants independently of events.
* `unity_package/Editor/PlatformerBuilder.cs`: native scene construction,
  explicit bindings report, derived prefab, and fixed `BuildPlayerBatch` selecting
  only SpritePlatformer for that player. Reuse the few common Windows build
  settings via a small static helper if necessary; no dynamic arbitrary scene path.
* `unity_package/Runtime/PlatformerInput.cs`, `PlatformerPlayer.cs`,
  `PlatformerSession.cs`, `PlatformerTrigger.cs`, `PlatformerHud.cs`.
* Separate `Tests/PlatformerEditor` and `Tests/PlatformerPlayMode` assemblies and
  their .meta files. Add exact expected test names in Python.
* Register `unity.game.platformer.v1` in catalog, safe dispatch, support/feature
  map, and CLI discoverability. Prefer the existing capability run interface over
  inventing a second command family. Keep arena/sprite IDs and their meaning.
* Extend bridge's fixed mode/filter allowlists for platformer build/player/tests.
  Extend recovery profile discovery with immutable request/archive hash and scene
  marker; `observe_state` must rerun the platformer tests and Python oracle.
* `polyforge/unity/performance.py`, `polyforge/contracts/player_profile.schema.json`,
  and `unity_package/Runtime/StandaloneProfile.cs` implement the shared profile
  described below. ArenaPerformance remains the old headless smoke adapter or
  delegates its existing behavior; old smoke behavior need not change.
* Add platformer profile plus a real declared-quality value to the current arena
  profile; update arena/docs/support claims only after actual evidence exists.

Preservation inventory includes all preexisting generated scenes, prefabs, clips,
controllers, atlas files and .meta GUIDs. Hash them before/after platformer creation
and repeat build; compare object counts/bindings. Append the new scene to build
settings; either preserve all existing entries in GameBuilder.Build too or restore
the settings from a saved inventory. BuildPlayer itself passes an explicit owned
scene list and need not mutate scene assets. Archive editable package/project
sources and reports alongside both final builds.

## Shared rendered performance protocol

Use three fresh launches per game, each with 10 seconds of warmup followed by
60 seconds of measured rendered frames. This gives three independent load/RSS
observations and is a conservative, explicit interpretation of the existing
10-second warmup / three 60-second measurements. Record this choice in the profile
instead of ambiguously mixing a single warmup with restarts.

1. Build one identified Windows64 player per game with identical declared build
   type, quality name, pipeline/configuration and fixed sources. Freeze/hash that
   output and contract before all three launches. Existing Development builds
   can be measured if the report clearly identifies Development; do not call them
   release-build evidence. Build time is separate from load time.
2. Launch with `-screen-width 1280 -screen-height 720 -screen-fullscreen 0` and
   fixed profile/request/evidence arguments. Do not use `-nographics` or
   `-batchmode` for this measurement. Fixed profile mode cannot also enable smoke.
   Set and report vSyncCount=0 and targetFrameRate=-1; use a declared quality name
   which exists on this actual build. Require actual Screen dimensions to match.
3. A shared StandaloneProfile component records double-precision monotonic
   end-of-render-frame intervals with a bounded, explicit phase machine:
   READY -> WARMUP -> MEASURE -> COMPLETE. Emit READY only once the active
   scene, camera, runtime bindings and real graphics API are valid and a frame
   has rendered. Reject Null/unknown graphics, zero/invalid timing and missing
   render progress. These are CPU-observed rendered frame intervals; do not
   claim GPU execution duration or display scanout timing.
4. Record every interval in the 60-second window (including slow frames), with
   phase boundaries, sample index and monotonic times. Warmup intervals stay
   separate and cannot improve results. Replace the current 18,000-frame silent
   truncation with a documented high bound; reaching a bound is incomplete/FAIL,
   never a successful shortened sample. Freeze the exact endpoint convention.
5. Keep a deterministic, documented activity schedule running throughout the
   profile. The arena normally stops at 30 seconds; a passive measurement would
   spend most of its time profiling a terminal scene. A profile-only adapter
   drives real input and restarts rounds at declared fixed ticks. The platformer
   uses its own input/jump/restart schedule. Neither adapter changes physics,
   damage, survival duration or rendering settings outside the declared profile.
   Trace active rounds, moving enemies/actor, input schedule hash and restart
   counts. Report profile automation as separate from keyboard/manual acceptance.
6. Use runner-owned Windows process observations for load and RSS. Minimal seam:
   add an optional internal `ProcessObservation` to `run_process`, implemented in
   `polyforge/runner/metrics.py`; the default remains unchanged. It receives the
   owned PID, measures monotonic launch-to-READY sidecar observation, and polls
   GetProcessMemoryInfo PeakWorkingSetSize while alive (plus final available
   read). Include poll cadence/ready polling uncertainty. Retain the PID birth
   token. Do not substitute job committed-memory limits for RSS. A failed memory
   query is null with its error, never zero. This seam has no arbitrary callbacks,
   subprocesses, shell or unowned-PID authority. Save observations alongside the
   existing process outcome even on timeout/cancellation.
7. Pure Python `validate_profile_evidence` and `score_profile` validate identity,
   completeness, resolution, graphics device, quality, build and source hashes,
   exact three samples, durations and numeric finiteness before computing gates.
   Use median instantaneous FPS = median(1000/frame_ms) and nearest-rank P95 of
   frame_ms (sorted index ceil(.95*n)-1). Also report elapsed frames/time FPS to
   expose differences. Require every sample's median >=30 and P95 <=50ms, and
   every launch's peak RSS <=2147483648 bytes and load <=30s; report cross-sample
   median as descriptive only. A bad sample cannot be averaged away.

The shared record contains scope PUBLIC_DEVELOPMENT, profile version/hash,
game/scene/contract identity, run and sample IDs, executable/package/source hashes,
Unity/OS/build type, quality name/index, pipeline settings, actual resolution,
fullscreen/focus/vSync/targetFrameRate, CPU model/logical count, physical RAM,
graphics API/name/vendor/device/driver/VRAM, timestamps, all raw intervals,
runner process observations and individual gate reasons. Seal raw and scored
evidence including player-side reports; `register_game_artifacts` currently skips
the player subtree, so copy/seal the reports outside that subtree or extend the
registry specifically for reports without including executable payloads.

Capture host `hardware_fingerprint`/`gpu_metadata` before and after; active device
comes from runtime SystemInfo, because registry adapters are metadata only.
Record min/max/median across the three runs and percentage spread. A hardware or
quality change invalidates aggregation. Unchanged hardware does not establish
cross-hardware performance; high run variance stays visible. Do not drop a slow
run or auto-rerun until green. A documented external interruption may invalidate
one run; preserve it and explicitly label the replacement/new run group.

Stop conditions: cancellation, ownership/Unity-lock conflict, missing binary or
bindings, stale identities, no real renderer, resolution/quality mismatch,
scene/input runtime failure, focus loss/minimization if declared disallowed,
30-second readiness deadline, frame-sample overflow, missing telemetry, process
exit/crash, resource/log cap, or overall per-launch 120-second timeout. A launch
that is merely slow is FAIL; environmental inability to render is BLOCKED/NOT_RUN.
Retain partial evidence and stop this profile group rather than retrying silently.
The configured process memory cap remains a safety cap (normally 8 GiB), separate
from the measured 2 GiB performance threshold; crossing 2 GiB can be recorded and
the owned process stopped with a FAIL observation. Existing 60-second smoke
timeout must not accidentally apply to 70-second profile launches.

## Native positive, negative, standalone and gameplay gates

Score these dimensions separately for each game:

| Gate | Evidence / required result |
| --- | --- |
| Native compile/EditMode | Exact executed test inventory, actual component/native asset bindings, scene identity, no missing scripts, stable GUID/count preservation on repeat build |
| Nominal PlayMode | Fresh scene per case, real physics/input, fixed frozen steps, valid traces, independent Python oracle PASS |
| Mutation sensitivity | Valid observed trace for each intentionally broken behavior; corresponding behavioral oracle FAIL; native test records the executed mutant, not expected generator events |
| Standalone build | BuildPipeline report success plus actual hashed exe/dependencies; scene-specific Windows player |
| Standalone smoke | Owned process success, scene/digest binding and observed runtime progress; preserve current arena smoke, add analogous platformer smoke which exercises move/jump/goal/restart with traces |
| Standalone gameplay | Player itself executes fixed real-input schedules and emits traces scored by the same independent Python oracle; Editor-only PASS is insufficient |
| Rendered profile | Complete three rendered samples and external process measurements satisfying every fixed threshold |
| Human visual/play | Actual review tied to original brief/build; stays REVIEW without evidence |
| Protected acceptance | Separately controlled evaluator only; same-host development checks do not qualify independence |

Platformer nominal cases: horizontal move; ground/fall collision; grounded jump
then land; airborne jump rejected; real Input System A/D/Space/R; checkpoint
activation; hazard damage and checkpoint respawn; life exhaustion FAILED; goal
WON only on contact; explicit R restores complete initial state after both terminal
states; input subscription replacement/destruction; physics stays in the 2D plane.
Test checkpoint/goal triggering through actual collision movement, not direct
session method calls. A default-layout reachability journey crosses the checkpoint
and reaches the goal, so disconnected isolated behaviors cannot masquerade as a
complete game. Individual setup cases may reposition only via declared test setup.

Platformer mutants: disconnected input, zero jump impulse, disabled platform
collider, disabled checkpoint update, hazard that does not reduce Health, disabled
goal, reversed/premature win, and no-op restart. Reload scene after every mutant.
For collision mutants use geometric samples demonstrating crossing/falling;
for checkpoint use subsequent actual hazard/respawn; for health compare values;
for goal assert spatial contact and state; for restart compare position, velocity,
lives/checkpoint/timer/round. Missing/malformed traces never count as detected.

Keep existing arena seven mutation cases and exact nominal/input suites intact.
Run both old games' preservation/regression profiles after the platformer build,
including recovery/rollback coverage. Separate native execution errors from valid
behavior FAIL and from mutation-detection gate PASS in the final report.

## Critical unknowns and bounded implementation order

* This task did not launch Unity, query live hardware, or measure rendering. Native
  API/Windows RSS access and desktop availability remain unverified. Probe Unity
  before version-sensitive implementation; validate the installed Input System,
  Physics2D API and rendered coroutine behavior on 6000.6.3f1.
* Verify the approved source document's precise second-genre/native release wording
  and required evaluator ownership before saying Phase 11 complete. The source
  currently provides no protected external evaluator (`UnavailableEvaluator`).
* A new platformer does not fulfill the existing sprite-survival benchmark brief.
  Keep that task/outcome truthful; add a distinct platformer reuse brief/task rather
  than rewriting historical requests. If release rules mandate completion of the
  survival brief too, that remains a separately declared game task.
* Runtime quality name and GPU/driver availability must be measured on this host.
  No source-only design can select a proven actual hardware preset.
* Native frame-timing endpoint, fixed-input schedule and platform layout must be
  frozen before collection, with documented physical tolerances. Do not adjust
  quality, duration, acceptance thresholds or tolerances after seeing results.

Implement in thin slices: (1) strict platformer contract + pure oracle and malformed
trace negatives; (2) native builder/motor/session and nominal/mutant XML traces;
(3) preservation + recovery integration; (4) scene-specific standalone smoke and
gameplay traces; (5) shared rendered recorder, owned process RSS/load and pure
profile scorer with null/stale/incomplete/threshold negatives; (6) one declared
hardware run group for each game, preserved raw evidence and honest gate report.
Run native tools sequentially under the physical Unity lock. No full baseline
restart is part of this design task.

## Suggested parallel ownership and exact integration seams

The root agent requested these ownership boundaries after the initial design:

| Owner | Files |
| --- | --- |
| Performance implementation | New `polyforge/unity/performance.py`, strict profile schema, `StandaloneProfile.cs`, profile-only workload adapters, scorer/recorder tests; coordinate before editing the existing runner |
| Platformer implementation | New platformer contract/module/oracle/scenarios, PlatformerBuilder, Platformer runtime files, platformer test assemblies and .meta files |
| Root integration | Existing `bridge.py`, `commands.py`/CLI handler, dispatch/catalog/support feature maps, `GameBuilder.cs`, recovery/repair profile registration, docs/release result integration |

Use these Python entry points to make the parent hooks small:

```python
def profile_player(
    policy: WorkspacePolicy,
    *,
    player_path: Path,
    game_kind: str,       # fixed enum: arena | platformer
    scene_id: str,
    input_digest: str,
    profile: dict[str, Any],
    cancel: threading.Event | None = None,
) -> Result: ...

def validate_profile_evidence(
    evidence: dict[str, Any], expected: dict[str, Any]
) -> None: ...

def score_profile(samples: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]: ...
```

`profile_player` receives an already built player; it does not rebuild the scene,
call EditMode/PlayMode, or claim those gates. It seals a new run group, validates
the exe is workspace-owned, launches exactly three times using the shared owned
process runner, and returns explicit per-launch/per-threshold outcomes plus raw
and scored evidence paths. A root entry point selects a fixed builder for the
game kind first, and invokes this function afterward. Dry-run validates and
describes all planned launches without mkdir/native calls. Public result keeps
`operation_status`, `evaluated_test_status`, `game_status`, standalone and rendered
performance fields independent; external acceptance remains PARTIAL/NOT_RUN.

Parent GameBuilder hook: add `StandaloneProfile` alongside the existing
`ArenaPerformance`; assign immutable `gameKind="arena"`, `inputDigest`, and
`sceneId` from GameInput. The new component is inert unless the explicit profile
flag is present. PlatformerBuilder does the same with gameKind="platformer".
Profile args reference only validated request/evidence files under the owned
player output. The request records the exact actual scene name in addition to
semantic scene_id; arena semantic scene_id is not necessarily "PlayableArena".

The workload seam should be a small profile-only adapter on each scene, not a
change to ArenaSession or the production motor. Keep activity input and recorder
separate. Agree on its tiny native contract before two agents edit it: e.g.
`Begin()`, `FixedStep(int tick)`, and `CaptureProgress()` returning a shared DTO of
round/restart count, observed position changes and validity. Existing profile
injection remains explicitly documented and cannot substitute for real keyboard
or manual acceptance. The platformer must not make StandaloneProfile reference
an uncommitted class name; shared interfaces/DTO belong in StandaloneProfile.cs.

Recovery hook: add `platformer` scene marker and immutable request/archive path
to `_profile_inputs`; map its exact Editor/PlayMode namespaces and expected
inventories in `observe_state`; score the resulting behavior traces, not merely
the XML. Preserve the entire before/after profile-key set through rollback.

Parent should commit or synchronize the small shared native contract before the
two native implementations compile. All current baseline work stays untouched
until the root authorizes the next implementation slice.
