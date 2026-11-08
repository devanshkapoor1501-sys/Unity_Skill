# Phase 12 v7 asymmetric handoff repair

The user requested assessment and continuation against the updated plan on
2026-11-08. The local v7 blueprint supersedes future work in the older roadmap.
This work item is limited to its first concrete work order: reproduce and repair
the coolant-valve socket reflection and verify the existing modeling handoff.
Preserve all existing uncommitted work, earlier fixtures and historical evidence.

## Acceptance and boundary

- Preserve the intended outlet `(0.90, 0.77, 0.35)` and reproduce the incorrect
  Unity observation `(-0.90, 0.77, 0.35)` before changing production code.
- Trace source, export and imported parent/local/world transforms. Fix the
  faulty conversion in the existing implementation; retain the 5 mm tolerance.
- Import both composition cases as well as all four families, main and LOD.
  Check asymmetric geometry/sockets, UVs, materials, stable GUIDs and source hashes.
- Exercise positive/negative coordinates, transformed/nested parents and a
  deliberate reflection mutant in a disposable managed native project.
- Run relevant offline and native regressions, lint, typing and documentation
  checks. Record unavailable checks separately from passing results.
- Write `reports/phase-12-v7.md` with current evidence and reconcile Phase 11.
  Independent transfer and artistic acceptance remain separate outstanding gates.
- Stop at the repair boundary. Phase 13 needs its charter/evaluator decision;
  the proposed multi-day trial and its budget are not activated by this work.

## Implementation sequence

1. Audit reports, dirty state and v7 work order; probe installed binaries.
2. Run the existing expanded native import test as the red reproduction.
3. Compare the established static-asset export convention with modeling export,
   using official API documentation and observed transforms.
4. Strengthen the existing native import fixture and add only regression checks
   needed for the defect; patch the confirmed cause in the modeling exporter.
5. Run green native and offline checks, collect exact logs and inspect the diff.

Likely files: `polyforge/blender/modeling_worker.py`,
`tests/test_phase12_native.py`, `tests/fixtures/modeling/ModelingImportProbe.cs`,
focused modeling tests, modeling/skill references and the evidence reports.
The coordinator owns integration and native processes. Read-only native agents
audit baseline evidence, trace code and verify official documentation in parallel.
Their review is same-host development review, not external evaluator acceptance.

## Resource and authority record

Use the existing installed tools and dependencies. The first unrestricted Unity
startup resolved the installed template's pinned packages through UPM; later
runs reuse copied caches. No new project dependencies are adopted. Original Unity
project launches, publication, commits or remote changes are outside this item.
The request authorizes bounded local continuation; it does not supply an external
evaluator or approve v7's proposed 16-hour pilot. Track actual elapsed execution
and stop if the repair requires a broader investment decision. Unknown model
costs and OS resource measurements remain UNKNOWN.
