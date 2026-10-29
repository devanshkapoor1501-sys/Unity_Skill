# Local knowledge and host routing

Availability uses explicit probes. `knowledge availability --workspace ROOT --host codex`
runs the fixed local `features list` query; Claude uses its local help. Feature
ENABLED/CLI_DECLARED is configuration evidence; actual delegation remains UNKNOWN
until a successful host smoke. No model call or settings change is made.
`--project PROJECT` statically compares requested manifest versions, resolved
lock versions and installed cache/embedded package metadata, with bounded reads.
A mismatch is reported even without a lock file. Cache presence never establishes
API compatibility. Project sources are never opened in Unity by this command.

The separate `knowledge probe --workspace ROOT --tool unity-ui` opens an empty
scratch Editor and checks a temporary window actually paints before closing it.
This fixed UI observation is separate from the existing headless TypeCache
probe and Blender context polling. Only exact native receipts populate observed
availability; vision and other methods remain UNKNOWN. Use `--dry-run` to inspect
the plan without launching native tools.

`knowledge list --json` reads 20 source-attributed KnowledgeCards. Their curated
summaries cover modeling/topology, UV/PBR, rigs/motion, Blender operator context,
sprites, Unity Editor/runtime/C#, animation, mechanics, physics, AI, UI, shaders,
world design, integration, recovery, evaluation, architecture, packages and reference security.
Each card names applicability, prerequisites, alternatives, contrasting examples,
risks, versions, source, local text digest, fixed probe, confidence and reviewer.
Sources are linked, not copied vendor articles. Curated summaries are cached
locally; there is no runtime downloader or network retrieval API.

Save this to a workspace-local request.json:

```json
{"schema_version":"1.0.0","query":"Explain Geometry Nodes versus manual mesh","output":"EXPLAIN","domain":"blender"}
```

```console
polyforge knowledge route --workspace ROOT --request request.json --json
polyforge knowledge probe --workspace ROOT --tool blender --dry-run --json
polyforge knowledge probe --workspace ROOT --tool unity --dry-run --json
polyforge knowledge probe --workspace ROOT --tool unity-ui --dry-run --json
polyforge knowledge availability --workspace ROOT --dry-run --json
```

Routing reads at most three matching cards, preserves the original query and
returns relevant reference paths, missing/probe requirements and a proposed
operation/role plan. It does not run a capability or interpret every requirement
in arbitrary prose. Check the descriptor and each user constraint before acting.
Unknown required features remain REVIEW. Explicit output/domain take precedence
over lexical hints. Existing sprites omit Blender; explanation omits native
tools; unfamiliar authoring gets a SAFE_DISCOVERY proposal, never silent fallback.

Knowledge state is separate from execution support and game acceptance. Fresh
cards start REFERENCE_ONLY. Successful fixed probes establish VERSION_PROBED for
their exact APIs/tool versions, without promoting an executable action. Broader
workflow knowledge needs its own independent measured evidence. Missing or stale
evidence never grants universal expertise. Host delegation, vision and Unity UI
remain UNKNOWN until actually tested.

Run `knowledge probe --workspace ROOT --tool blender|unity --json` to execute a
fixed engine-owned probe in a new empty scratch location. Blender checks valid
versus degenerate mesh validation and context polling. Unity checks TypeCache's
known subtype, unrelated-type exclusion and Editor assembly. No arbitrary source
or existing project is accepted. The Unity scratch project has no package
dependencies. Receipts bind tool binary, registered source, actual output and
process invocation hashes; changed evidence denies reuse. The trusted-local
probe is explicitly not an OS sandbox or authorization for generated code.

References cannot change network/tool/role/acceptance authority. Current explicit
user requirements, normative Appendix G and canonical CLI govern forward work;
historical Appendix A/B examples remain provenance. An unfamiliar action requires
a reviewable scratch proposal, declared API/packages/writes/budget/risk, owner
approval, positive/negative tests and actual outputs. Promotion additionally
requires a typed registered capability and benchmark slot. See the portable
skill's security and contribution references.

The optional `mcp serve --workspace ROOT --transport stdio` exposes only
`polyforge_catalog`, `polyforge_reference_route` and
`polyforge_validate_descriptor`. It binds one workspace at startup and supports
MCP 2025-11-25 initialization, tool listing/calls, ping and cancellation. Messages
are newline-delimited JSON-RPC, at most 64 KiB; pending calls are bounded to eight.
No shell/Python/native writer, download or operator-approval action is exposed.
Names and annotations do not authenticate a peer. A cancelled pending call does
not publish a result. After 4096 request identities, restart the connection.

[Codex guide](hosts/codex.md), [Claude guide](hosts/claude.md) and the Phase 10
report distinguish actual host execution from installed executables and blocked
accounts. Core discovery/routing/validation remains model-neutral and offline.
