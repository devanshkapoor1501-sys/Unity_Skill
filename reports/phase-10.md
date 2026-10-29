# Phase 10 — portable skill, local knowledge and bounded hosts

**Phase 10 development scope: PASS, with disclosed host-dependent blocks. Game acceptance: PARTIAL.** This phase
implements reference/host affordances around the existing engine. It does not
claim broad game-production expertise or successful authentication on unavailable
hosts. Final quality and publication gates are recorded below after verification.

Authority: v5.1 Section 12 Phase 10, Chapters 16–18 and Appendix G, retaining
original Phase 10 gates. Base: `9f8d97827183502952cda86289fdf19066e02d01`.
[Design](../docs/superpowers/specs/2026-10-29-phase-10-design.md),
[build plan](../docs/superpowers/plans/2026-10-29-phase-10.md) and
[review disposition](phase-10-review.md). Phase 11 has not started.

## Delivered scope

One 656-word portable SKILL.md progressively discloses six domain reference
groups and focused workflow/security/contribution guidance. Eighteen strict
KnowledgeCards carry locally authored summaries, authoritative source links,
applicability, pinned versions, prerequisites, decision alternatives, contrasting
examples, risks, local text digest, API-probe identity, confidence and reviewer.
The data is cached locally; there is no runtime downloader or provider SDK.

`knowledge list`, `knowledge route` and `knowledge probe` use the canonical CLI.
The pure router preserves exact query/output/domain, selects at most three
relevant cards, and returns a minimal proposed role/capability plan plus gaps and
required probes. Supplied sprites, robot bake and unsupported new sprite art have
distinct routes. Unknown mandatory needs remain REVIEW. Keyword selection is
not a natural-language completeness proof; descriptors and every user constraint
still require inspection before executing a typed capability.

Knowledge states are separate from execution support and game acceptance.
Fixed native probes establish VERSION_PROBED only for their exact card/API/version.
All other reference knowledge remains REFERENCE_ONLY. Reading a source, passing
compile or probing an API cannot register/promote a new production capability.
Unsafe novel execution remains BLOCKED behind a declared SAFE_DISCOVERY proposal
and separate owner approval/isolation requirements.

The optional read-only MCP stdio bridge exposes catalog, reference route and
descriptor validation only. It binds one workspace at startup, pins protocol
2025-11-25 and server identity `polyforge-readonly`, validates lifecycle and
typed input, bounds messages/pending requests/IDs, and suppresses cancelled
pending results. Fake client identity or approval fields cannot gain tools.
There is no shell, arbitrary Python, native writer, downloader or human approval
endpoint. Client/server names alone are not authenticated identity.

## Build-plan and blueprint audit

The table maps every Phase 10 task to implementation and evidence. “Implemented”
does not turn explicitly unprobed or blocked external methods into PASS.

| Blueprint item | Implementation and verification |
| --- | --- |
| 10.1 Concise skill/progressive disclosure | Canonical `.agents/skills/polyforge/SKILL.md`; simple-scalar profile, links and body budget validated; official `skills-ref` passes. |
| 10.2 Expertise/support map | 18 cards and six domain overviews cover modeling/topology, UV/PBR, motion, 2D, Editor/C#, mechanics, physics, AI, UI, shaders, worlds, troubleshooting, integration and evaluation; advanced execution gaps remain explicit. |
| 10.3 Authoring decisions | Procedural/manual/Geometry Nodes, rig/baked motion, mesh/sprite, Blender/Unity, tested template/generated code contrasts and version probes. Direct supplied sprites do not require Blender. |
| 10.4 Role playbooks | Six short domain role playbooks plus existing role contracts state inventory, artifacts, scopes, rubric and missing tool/vision/delegation fallback. |
| 10.5 Model-neutral core | Existing JSON CLI and jsonschema dependency retained; fresh offline installed catalog/route/validation/MCP work without a host model. No model SDK or service integration added. |
| 10.6 Two host pathways | Documented Codex and Claude paths actually invoked. Codex app-harness route PASS; standalone Codex CLI BLOCKED by existing model/account mismatch; Claude Code BLOCKED because not logged in. Blueprint permits explicit host-dependent BLOCKED. No account/configuration/permission bypass. |
| 10.7 Canonical grammar/examples | One registry generates CLI docs/fixtures; documented commands execute with typed temporary inputs and zero-write assertions; no unsupported aliases added. |
| 10.8 Skill quality | Fresh baseline/updated reader, relevant-reference router tests, strict unsupported tasks and injection/permission denial. Explicit output/domain and original query preserved; no universal expertise claim. |
| 10.9 New-specialty contribution | Focused contribution reference requires source or typed capability, version applicability, positive/negative fixtures, owner approval, review and public benchmark slot. No automatic promotion API. |
| 10.10 KnowledgeCards | Strict bundled schema and source-host allowlist, local document digest, versions, metadata and capability validation; malformed, substituted, duplicate, nonfinite and unknown-tool inputs denied. |
| 10.11 Version-aware router | Query/domain → selected local cards → current installed probe receipts or UNKNOWN → contrasting examples and operation proposal; no context-wide documentation dump. |
| 10.12 Separate taxonomies | Five knowledge states and five execution-support states in schema/reference guidance. Actual probe does not elevate unrelated topics or execution support. |
| 10.13 SAFE_DISCOVERY | Bounded reviewable proposal and two fixed engine-owned unfamiliar-API scratch probes. Arbitrary generated code execution stays BLOCKED without separately qualified isolation/authorization. |
| 10.14 Retrieval/security | Runtime network DISABLED, curated official HTTPS source allowlist, attribution/date/digest/version metadata, DATA_ONLY reference trust and no inherited permissions. Malicious snippet cannot add tool/network/approval authority. |
| 10.15 Decision reasons/contrasts | Seen examples plus four public transfer prompts held out from card authoring: adjustable pipes, carved idol, physical debris/plate plus cinematic camera, reactive hologram plus standard crate. A fresh reader selected Geometry Nodes/manual, physics/animation, Animator/Timeline and Shader Graph/Lit without erasing unsupported needs. This is reference-decision evidence, not separately controlled hidden evaluation. |
| 10.16 Availability/API probes | Actual Blender context/mesh and Unity headless/Editor type observations; current host paths exposed separately from UNKNOWN skill/delegation/vision/UI/package methods. Headless probe qualifies only its empty-project context, not arbitrary packages or UI actions. |
| 10.17 Forward precedence | Explicit user requirements, current Appendix G and canonical registry govern forward work; historical Appendix A/B cannot override. Skill validator and reference tests enforce the documented rule. |

Plan tasks 1–5 have their code/reference and RED/GREEN evidence. Task 6's local
gates pass: **465 tests**, **94.67% combined / 91.45% branch coverage**, lint,
format (139 Python files), strict Windows/Linux types (99 source files), CLI docs,
dependency consistency, wheel/sdist and **14 fresh offline install/CLI/MCP/resource
checks**. Publication is verified separately below. The machine-checked
`plan-audit.json` maps all 17 blueprint items, hashes implementation files, checks
actual XML/coverage/native/host/install outputs and lists external limits.
Earlier phases' report and artifact trees remain intact.

## Actual native and host evidence

Executed native platform: Windows, Python 3.12.14, Blender 5.2.2 LTS and Unity
6000.6.3f1. Linux type/CI analysis is not native Linux application qualification.

| Check | Observed outcome |
| --- | --- |
| Unchanged offline baseline | **395 passed**, 12 native tests separately deselected; 94.43% combined configured coverage. |
| Unchanged native arena | **PASS**, `game-check-d0f6dbc0853849a4`; exact Editor/PlayMode identities, nominal/input checks and six independent mutants. |
| Blender unfamiliar API | **PASS**, `knowledge-65370d00ada640dc`: actual Mesh.validate positive/degenerate negative and object-context polling false/true. Factory-startup scratch data; no existing .blend input. |
| Unity unfamiliar API | **PASS**, `knowledge-5ee5c80ce6944c0e`: actual TypeCache derived-record inclusion, unrelated Transform exclusion and Editor assembly assertion. Fresh empty scratch project with no package dependencies; no original project opened. |
| Exact receipt scope | Actual binary/source/process/output hashes reread; only matching context/Editor cards become VERSION_PROBED. Source-substitution and stale/forged receipt tests deny reuse. |
| Skill format | Official skills-ref **0.1.0** at source commit `69ef37e9424c0a7ea9dd2293b559e43ec8176379` reports Valid skill. Installed only into an isolated test environment, with no engine dependency change. Local stricter authoring-profile/link validator also passes. |
| Codex app harness | **PASS for narrow EXPLAIN route**, actual exit 0, selected `blender.modeling`, selected executable capability IDs empty, tests NOT_RUN, game PARTIAL. Fresh reader decisions are reference assessments, not native production or protected evaluation. |
| Codex CLI 0.154.0 | **BLOCKED**: its existing configured `gpt-6.1-sol` model is unsupported for its signed-in ChatGPT account. No model substitution/settings change; fixture unchanged. |
| Claude Code 2.1.186 | **BLOCKED**: “Not logged in”; zero model calls. Same canonical skill copied into disposable `.claude/skills`; fixture unchanged; no login/permission bypass. |
| MCP/installed wheel | Real stdio client lifecycle/tools/ping and malformed/oversized/duplicate-JSON tests; pending cancellation and counterfeit authority denial; fresh isolated offline CLI/MCP/resource smoke. See final logs for exact counts. |

The native probes are trusted fixed code under the existing owned runner, not
an OS sandbox for generated code. Native licensing/profile services may write
normal OS state. Probe receipts are same-host evidence, not cryptographic proof
of an external identity. No artistic, performance, new standalone, host-native
delegation or hidden-evaluator PASS follows.

## Sources and limits

Official [Agent Skills specification](https://agentskills.io/specification),
[Codex skill guidance](https://learn.chatgpt.com/docs/build-skills),
[Claude skills](https://code.claude.com/docs/en/skills),
[Claude noninteractive CLI](https://code.claude.com/docs/en/headless) and
[MCP 2025-11-25 lifecycle](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)
were fetched. MCP transport/tools/cancellation references and exact source records
are retained. Blender's web API fetch returned HTTP 402; actual installed native
API behavior and assertions established the probe. Unity's installed
UnityEditor.xml signature was checked before scratch compilation/execution.
Catalog summaries are locally authored, with source attribution rather than
copied vendor articles.

The [evidence index](phase-10-evidence/index.json) hashes raw commands, negative
fixtures, native observations/process logs, tool/probe sources, host blocks,
validation and installed-package checks. Scratch caches, credentials and host
session state are excluded. Source scripts are retained with `.py.txt` suffixes.
The build-plan audit is additionally machine-checked against the executed result
files and committed implementation bytes before publication.

## Publication

Implementation/qualification commit `9dac23dcc45713da93d502f8f24c330420304f1d`
passed all three jobs in [branch run 40921511937](https://github.com/devanshkapoor1501-sys/Unity_Skill/actions/runs/40921511937):
Windows Python 3.11, Windows Python 3.12 and Ubuntu Python 3.12. Raw job logs,
individual step results and exact source revision are retained under
`phase-10-evidence/ci/`. Publication preserves the complete Phase 0–9 history
through a fast-forward of main; no force update or phase artifact replacement.

The final report/evidence commit is checked again on push.
[Main Actions](https://github.com/devanshkapoor1501-sys/Unity_Skill/actions?query=branch%3Amain)
is the authoritative post-publication status. The user-requested plan audit found
no remaining unimplemented Phase 10 code/reference item within this scope;
account-dependent host blocks, unprobed methods and protected evaluation remain
explicitly disclosed. Phase 11 remains unstarted.
