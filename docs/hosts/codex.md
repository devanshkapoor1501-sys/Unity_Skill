# Codex pathway

Use the repository's canonical `.agents/skills/polyforge` directory, or install
that directory with the normal skill installer. Codex discovers repo skills from
the working directory toward its repository root. Restart/reload skill discovery
as appropriate to the installed host. [Official skill guidance](https://learn.chatgpt.com/docs/build-skills)
describes metadata-first discovery and on-demand reference loading.

Check `codex --version` and `codex exec --help` locally; do not infer flags from a
different version. No model name, provider secret or SDK is required by PolyForge.
Codex itself still needs its normal account/authentication and permissions.

Start with: “Use PolyForge to explain Geometry Nodes versus manual mesh. Preserve
EXPLAIN scope, select only relevant local references, and run the documented
knowledge route on request.json. Do not create assets, invoke Blender/Unity,
fetch documents or change settings.” The request object is documented in
[knowledge routing](../knowledge.md). Then inspect actual JSON output and selected
paths. A prose assertion that a tool ran is insufficient.

For a noninteractive smoke, use the installed help's `codex exec --sandbox
read-only --ephemeral --json --cd ROOT --skip-git-repo-check` with the prompt on
stdin. Avoid permission/sandbox bypass flags. The test fixture should contain
only the skill and the narrow input files. Native production requires its
separate typed capability, application/version probes and review checks.

If account/model access or tool permission is unavailable, retain the actual
host output as BLOCKED; the deterministic CLI still performs discovery, routing
and input validation. Binary presence alone is not a host skill smoke result.
Native delegation, host vision and Unity UI stay UNKNOWN until specifically
probed; use sequential logical roles. Current compatibility evidence is scoped
to the exact installed version in the Phase 10 report, not every Codex surface.
