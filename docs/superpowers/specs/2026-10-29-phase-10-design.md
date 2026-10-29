# Phase 10: portable skill and version-aware reference routing

Status: implemented and locally verified; see reports/phase-10.md for exact
qualification, explicit host-dependent blocks and publication results.

Authority: v5.1 Section 12 Phase 10, Chapters 16–18 and Appendix G; preserve
Phases 0–9 and stop before Phase 11. User requested continuation and previously
authorized routine implementation decisions without repeated confirmation.

## Outcome and approach

Keep one concise portable skill, add a locally packaged knowledge catalog and
reference router, explicit availability/probe records and two actual host paths.
Reuse the canonical CLI, schema loader, workspace policy, runner and workforce
discovery. No provider SDK, secret or remote service is required by the engine.

Chosen approach: static versioned cards plus deterministic bounded routing and
fixed registered probes. A vector database/network crawler would add dependencies
and retrieval authority unnecessarily. A documentation-only update would omit
the required operational routing, version and injection gates.

## Knowledge and routing

KnowledgeCards cover modeling/topology, UV/PBR, rigging/motion, sprites, Unity
Editor/runtime/C#, mechanics, physics, AI, UI, shaders, world design, repair,
integration and evaluation. Every card binds authoritative sources, curated
locally cached reference digest, applicability/versions, prerequisites, risks,
examples/contrasts, probe identity, confidence and attribution. Knowledge states
and executable support states are distinct. Documentation never promotes an
operation. Explicit capability IDs resolve through the existing catalog.

`knowledge list`, `knowledge route --request FILE` and `knowledge probe --tool
blender|unity` use the canonical command registry. Route inputs preserve the exact
query and requested output; selection returns at most three relevant cards and
reference paths, required version probes, supported capability IDs or an explicit
gap, minimal role plan and no implicit execution. Unknown/unsupported needs are
REVIEW; missing tools BLOCKED. Explanation needs no application tool. Explicit
domains/constraints outrank lexical hints; no natural-language completeness claim.

Fixed probes produce actual tool/version/API evidence without arbitrary code or
commands from cards. Pure routing never launches an application or writes files.
Unprobed UI, delegation, package and operator context methods remain UNKNOWN.
Probe receipts bind tool binary and source/output hashes; malformed/stale receipts
cannot elevate knowledge. Engine code owns permissions outside retrieved text.

## Safety and discovery

References are DATA_ONLY with no inherited filesystem, network, role or approval
authority. Retrieval is offline by default. Only curated official-domain links
are supported; adding downloaded text requires explicit approval, provenance,
license, version, digest and review. No runtime downloader is added. Malicious
snippets cannot change routing, capability allowlists, permissions or acceptance.

SAFE_DISCOVERY produces a reviewable bounded proposal containing requirement,
API/tool, scratch-copy scope, budget, expected writes and checks. Arbitrary
generated code execution remains BLOCKED without verified isolation and separate
approval. Phase 10 executes two engine-owned unfamiliar API qualification probes
in disposable locations; this does not authorize a generic code executor or
promote experimental actions to the production catalog.

## Portable hosts and optional MCP

Codex uses the standard `.agents/skills/polyforge` path; Claude uses an explicit
copy into a disposable `.claude/skills/polyforge` directory. Host-specific guides
reference the same skill and CLI. Probe actual installed host versions and use
their normal authentication/permission settings. Never bypass permissions or
claim a model ran merely because its executable exists. A narrow host scenario
must actually complete, or report host-dependent BLOCKED with retained evidence.
Host delegation remains UNKNOWN unless actually tested; serial roles stay valid.

The optional MCP server is limited to read-only catalog/reference/validation tools
on a startup-bound workspace. It has no shell, arbitrary Python, network or native
writer. Stdio JSON-RPC lifecycle, bounded messages, exact server/protocol identity,
request IDs and cancellation are tested. Client names do not grant authority.
Unsupported methods and fake identity/approval claims fail explicitly.

## Skill and extension guidance

Progressive disclosure loads only relevant references. Decision trees cover
Blender/Unity, procedural/manual, rig/baked, mesh/sprite, tested template/generated
code and version probes. Role playbooks state tool inventory, artifacts, rubric,
scope and unavailable-tool fallback. Contrasting seen and new public tasks test
decisions; these are development tests, never separately controlled holdouts.
Historical prompts cannot override Appendix G, explicit user constraints or the
current command registry. Contributor guidance requires a typed capability or
reference-only card, version probe, positive/negative fixtures, owner review and
benchmark slot before executable promotion.

## Qualification

Run old offline and Phase 6 native baselines before product changes. TDD covers
strict cards, routing, byte/context limits, version mismatch, absent tools,
malicious references, receipts, fake MCP identity and cancellation. Maintain
>=90% combined AND branch coverage, including new trust contracts. Validate skill
format/links and real commands; run fresh reference-only trigger/routing readers,
actual Codex/Claude scenarios or precise blocks, Blender/Unity unknown API probes,
lint/format/types/docs/build/fresh offline installs. One fresh whole-phase review,
fix required findings, retain hash-indexed evidence and exact Phase 10 report,
then commit/push and check branch/main CI under existing publication authority.
No universal expertise, host delegation, protected evaluation, aesthetic,
standalone, performance or OS isolation PASS is inferred.
