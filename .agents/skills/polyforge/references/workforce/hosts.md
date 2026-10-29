# Portable host paths

Codex discovers this canonical skill under .agents/skills/polyforge. For Claude
Code, copy this same directory to .claude/skills/polyforge in the selected project;
do not maintain a second fork of its instructions. Respect host trust/authentication
and permission settings. Restart/reload according to actual installed host help.

Both hosts use the same installed polyforge CLI and typed workspace files. Check
capability discovery and a narrow explanation/validation scenario before native
actions. Installed CLI version is not proof of model execution, tool permission,
vision, delegation or skill triggering. Retain real invocation/output evidence;
missing authentication/permission is host-dependent BLOCKED, not a passed smoke.
Use sequential roles when no qualified delegation is available. Core CLI catalog,
validation and routing remain useful with no host model or provider SDK.

Optional MCP: `polyforge mcp serve --workspace ROOT --transport stdio`. Only catalog,
reference routing and descriptor validation are exposed. Match protocol
2025-11-25 and server name polyforge-readonly; a client/server label alone never
authenticates execution authority. There is no shell/native writer/remote tool.
Cancellation suppresses pending result publication. Network remains disabled.


Explicit availability probes:

```console
polyforge knowledge availability --workspace ROOT --dry-run --json
polyforge knowledge probe --workspace ROOT --tool unity-ui --dry-run --json
```

Run knowledge availability with --host codex or --host claude for a fixed local
feature/help probe with retained output. ENABLED/CLI_DECLARED describes local
configuration, not successful model delegation. Actual roles remain UNKNOWN
until the host smoke completes; account/permission failures are BLOCKED. Neither
host probe calls a model, changes settings nor bypasses authentication.

For Unity UI, remove --dry-run from the unity-ui fixed probe in a disposable
workspace. It opens an empty Editor, paints and closes a temporary window,
and exits. It never opens an original project. This is distinct from the unity
headless fixed probe. Blender's fixed context probe observes operator poll both
with and without an active object. Snapshots revalidate native receipt hashes;
missing observations remain UNKNOWN. Supply --project to inspect package caches
read-only. UI paint proves this window operation only; vision and unrelated UI
methods remain UNKNOWN.
