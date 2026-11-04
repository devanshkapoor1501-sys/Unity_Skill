# Phase 11: core release qualification

Authority: the original v5.1 blueprint, Section 12 Phase 11, inherited
Sections 13.3–13.6, Chapters 16–18 and Appendix G; approved
`docs/implementation-plan.md`. Starting revision: `31827d1`.

The user authorized implementing all remaining phases in order, thorough
verification and fixes, then commit/push after each phase. This document makes
the already approved Phase 11 requirements concrete. It does not replace any
requirement or authorize broader security claims. Existing requested checkout
is retained; work is on `codex/polyforge-phase-11`.

## Intent and success criteria

User clarification (2026-11-01): the final deliverable is a portable skill that
teaches Codex, Claude and compatible hosts to select Blender/Unity tools, compose
specialized workers and produce different kinds of games from simple prompts.
Examples are learning and verification fixtures. They must not become the only
supported requests or replace an unfamiliar request with a familiar template.
Remaining phases must grow reusable tool knowledge, workflow composition,
transfer tests and honest discovery paths alongside executable capabilities.
No finite example set proves unrestricted support for every possible game.

Deliver the reproducible core release, measured public development results,
worker/evaluator interfaces, non-mutating existing-project inspection, declared
standalone performance, two distinct game styles from shared capabilities and
an immutable regression baseline. Preserve every required gate and every failed
attempt. Phase 12 starts only after Phase 11's actual gate disposition is known;
unmet mandatory release requirements cannot become PASS through documentation.

## Approach

Extend the existing native Python engine and UPM package in verifiable slices.
Reuse typed results, capability registry, physical path policy, owned process
runner, job ledger, Unity project locks, native APIs and independent telemetry
oracles. No second engine, arbitrary shell runner, model-provider dependency or
copied MCP tool catalog is introduced. Runtime network remains off.

1. Static inspection hashes a complete bounded inventory before and after
   analysis, rejects links/ambiguous or unstable paths, and never starts Unity.
   It reports requested/resolved versions, GUID/meta/reference diagnostics and
   unmanaged source risk as observations, never execution compatibility.
2. Benchmark contracts freeze public task identity, arm/tool/model/hardware/
   budgets, seed and original brief. Existing `BaselineRunner` and
   `AcceptanceEvaluator` interfaces remain compatible. The harness retains
   failed, blocked and unrun attempts, stratifies all six task classes, checks
   C/D generic-tool parity and keeps complete-game denominators separate.
   Report generation is offline and escapes all untrusted text.
3. Native qualification adds measured rendered standalone profiling and a
   genuinely distinct second game style built from shared assets/infrastructure.
   Required behavior has independent positive/negative evidence; compile,
   EditMode, PlayMode, player build, smoke, visual/manual and performance verdicts
   remain separate.
4. Release validation checks all command help/examples/contracts, unfamiliar
   Blender/Unity API fallback and changed-version rejection, coverage,
   reproducible package bytes, clean installation and a frozen fixture baseline.
   Worker architecture, support map, unsupported areas and exact limits ship
   with the report.

## Independent evaluation boundary

The user has no independent evaluator/service. Implement its public interface
and honest missing-evidence handling; do not invent protected briefs, rubrics,
external ownership, authenticated model trials or host delegation. Public
development comparisons and reviewers cannot satisfy separately controlled
hidden evaluation. Such requirements remain BLOCKED/NOT_RUN until actual
independent evidence exists. §13.5 permits an experimental toolkit without a
superiority claim; that allowance does not establish the mandatory stable release
or held-out generalization gate. Tag/release labels must reflect actual evidence.

## Verification and execution

Run the full unchanged baseline before modifying runtime/native sources.
For each slice: failing semantic tests, implementation, passing focused checks,
fresh review, meaningful fault cases. Serialize native Unity writes. Freeze
runtime/native bytes during complete suites and native qualification; compare
engine identities before and after. Include new security/contract logic in the
unchanged >=90% combined and branch coverage bars. Preserve Phase 0–10 evidence.

Final qualification includes all relevant unit/integration/security/race/crash,
Blender/native Unity, standalone, package/install, lint/types, docs and CI checks.
Keep external or unavailable gates visible. Commit and push the phase with its
precise report; never claim all tests pass when a required gate was not run.
