# Playable arena

The Phase 6 fixture is a Windows URP isometric survival arena built from generated
Blender assets. WASD moves, contact with a patrolling enemy reduces health, zero
health fails, surviving thirty seconds wins, and R resets player/enemies, health
and timer. The HUD displays health, time, state and input hints.

```console
polyforge init workspace/arena --json
polyforge build --workspace workspace/arena --through S5 --dry-run --json
polyforge build --workspace workspace/arena --through S5 --allow-package-downloads --standalone --json
polyforge verify --workspace workspace/arena --json
polyforge scenario run --workspace workspace/arena --suite core_gameplay --json
```

Create the parent directory before init. Use the download option only after
approving Unity package resolution; approval persists for that workspace.
Without `--standalone`, S5 performs Editor compilation and separate EditMode /
PlayMode runs. The original static Arena/Training layouts remain separate.
The playable scene is `UnityProject/Assets/PolyForgeGenerated/Game/PlayableArena.unity`.
The Windows executable is under the returned check run's `player` directory.

The supported fixture uses a 10–40m rectangular floor, generated ground and robot,
one explicit or derived player, at most eight patrol enemies, WASD/R and the
thirty-second survival objective. Other mandatory features fail preflight.
These bounds describe this implementation's support; broader task/genre support
belongs to the later v5.1 phases and must be measured separately.

Seven public scenarios observe movement, blocking walls, every enemy's patrol,
contact health loss, health failure, survival win and restart. Two additional
cases exercise actual Input System W/R events. Collision-disabled and
restart-disabled mutants must produce valid observations that fail their
behavioral oracle. Invalid/missing telemetry cannot count as a detected mutant.
Native XML must contain exactly the expected executed tests. Trace identity
comes from the loaded scene; stale scene/request/manifest mismatches fail.

Scenario step duration is fixed at 0.02 seconds. Frame scheduling allows three
extra frames, horizontal position comparisons use 0.1m tolerance, and win timing
allows 0.06s numerical/scheduling tolerance. These are invariant checks rather
than cross-hardware binary determinism claims.

Each successful build records the immutable request, input fingerprints, native
bindings, editable project archive, parent static run, feature trace and hashes.
Check runs preserve XML, process logs, telemetry and public oracle decisions.
Local player binaries remain below the workspace and are excluded from Git
evidence bundles; smoke metadata and process logs are retained.

Public checks are development evidence. They do not replace an independently
controlled hidden evaluator. Manual visual play review remains a separate gate;
a locked desktop blocks it. An automatic PASS can coexist with game PARTIAL.

The sample profile in `profiles/windows-arena.json` is NOT_RUN until actual
rendered measurement. Headless smoke proves startup and runtime progress only.
Its Null Device, window dimensions and unavailable RSS reading do not qualify
the 1280×720 performance targets. Complete profiling, second-genre reuse, the
remaining mutants and protected qualification remain later release gates.

Use TRUSTED_LOCAL only. The Unity Editor uses the existing local activation
profile, and no sandbox or network-isolation qualification is claimed.
