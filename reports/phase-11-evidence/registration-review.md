# Phase 11 platformer registration review

Read-only review of registration, CLI, workforce roles/routing, candidate inspection, transaction scopes, operation receipts, and knowledge metadata. No source files or native workspaces were edited; no native process or full suite was run.

## Confirmed findings

1. **P1 — Platformer worker handoff does not seal its editable deliverable.** `polyforge/workforce/workers.py:14` reads only the registry for `result.run_id`, which is the platformer **check** run. `build_platformer` returns the build-run archive via `artifact_ids`/`data.build_run_id`; those files never enter that candidate. The new platformer branch (`workers.py:164`) requires only check contract/XML/traces and approves evidence with zero scene, bindings, or native archive. Using the real attempt-3 native contract, both XML files and all 22 traces, a valid 25-file candidate returned technical `APPROVED` with no archive, scene, build bindings, or standalone files. The technical approval therefore does not bind the editable project to the checked game. Require a sealed exact build-run identity, its typed inputs/bindings/archive, and a check-to-build relationship; verify the archive contains the expected scene/source identity.

2. **P2 — Durable recovery omits the platformer build archive.** `polyforge/workforce/operations.py:61` collects the result check-run directory, evidence paths and current managed project, but ignores the separate build run and artifact IDs. Bounded reproduction under `registration-review/recovery`: complete a passing platformer operation with a separate `runs/build/native-output.zip`, change that archive, recover the operation: result remains `PASS`. Include the explicitly linked build-run deliverables in the durable fingerprint inventory.

3. **P2 — Capability nonobject inputs escape structured validation.** `polyforge/capabilities/dispatch.py:38` calls `inputs.get` before `compile_platformer_request` validates the schema. Direct capability calls with `[]`, `None`, `True`, `42`, or a string raise `AttributeError` instead of `InputError`. All five cases produced zero writes. CLI already guards object shape; the reusable capability boundary also needs schema validation before reading `standalone`.

4. **P2 — Requested standalone proof is not independently inspected.** `polyforge/workforce/workers.py:164-185` checks only the main editor traces regardless of `request.input.standalone`. It neither requires standalone smoke/process/build evidence nor re-scores `standalone/telemetry`. A producer PASS or sealed saved standalone PASS is insufficient as independent proof for a standalone request. Require matching standalone smoke identity and independently score every nominal standalone trace when requested; seal the actual distributable or its bound archive. This omission is confirmed by control-flow inspection; no new standalone native execution was performed.

## Evidence and limits

- `registration-review/observations.json`: five wrong-type exceptions (zero writes) and real-evidence minimal-candidate approval.
- Focused `tests/test_phase11_registration.py --no-cov --basetemp=.tmp/phase11/registration-review/pytest -q`: 7 passed; 5 newly added nonobject contract cases failed with the confirmed AttributeError. Shared source/tests changed during the review only through the parent agent; this reviewer changed none.
- Reviewed role separation: only Unity integration has platformer production tool authority; gameplay QA can inspect and cannot produce. Platformer planning preserves source hashes and omits arena fixtures; imported-source changes affect task identity.
- Existing L3 acceptance remains REVIEW for the platformer brief; these findings concern technical evidence and durable handoff, not a demonstrated broad final-promotion bypass.
- Knowledge metadata does not claim new unconstrained creative expertise. No new high-severity finding in typed standalone schema, latest-marker transaction scope, or 2D route was confirmed.

## Scoped re-review after registration fixes

The four original defects are addressed in the revised control flow: capability schema validation precedes reading `standalone`; passing production merges both run registries and seals `delivery.json`; inspection requires the linked build request, bindings, preservation receipt and archive; operation receipts fingerprint the build run; standalone delivery requires sealed process/smoke identities and every nominal trace is independently rescored. Registration-only verification: **23 passed in 25.04s** with `--no-cov`, own `recheck-pytest` base temp. New native qualification was deliberately not run by this reviewer.

One related **P2 remains** in `verify_platformer_archive` (`polyforge/workforce/workers.py:16`): archive imported source payloads are not compared with the frozen `game.source_hashes`. The verifier checks scene/prefab GUID metadata and atlas digest, but accepts an empty `Robot2D.prefab` payload despite an explicit frozen SHA256 for a different nonempty approved prefab. Bounded reproduction artifact: `registration-review/recheck/empty-prefab.zip`; the direct verifier returned successfully. This permits a stale or corrupted editable source payload to pass while its GUID remains intact. Compare archive members corresponding to `UnityProject/` source hashes (prefab, animation, controller, atlas and metadata) against those hashes. This requests consistency with already frozen local source identities, not authentication against a malicious local owner.

## Final scoped verification

The residual archive fingerprint finding is **resolved**: `verify_platformer_archive` now reads every frozen `UnityProject/` source member through its bounded ZIP reader, requires the member to exist, and compares its SHA256 with the compiled source fingerprint. The previous empty-prefab counterexample now raises `InputError` for a differing frozen fingerprint.

The platformer board now explicitly reports absent independent original-brief acceptance as `REVIEW` before attempting arena-specific acceptance loading. This preserves the L3 gate for a platformer-only workspace and avoids both missing-brief exceptions and arena substitution. The existing promotion requirement continues to deny promotion when the recomputed board is REVIEW.

Targeted fresh verification: **13 passed, 13 deselected in 20.74s** (`test_phase11_registration.py -k 'editable_archive or inspector_requires' --no-cov`, own final-recheck temporary directory). Tests cover missing delivery/bindings/archive/standalone evidence, mismatched prefab/controller/clip payloads, and successful technical inspection with REVIEW at the board. No unresolved confirmed finding remains in this requested review scope. This is an integrity/development-evidence review; no independent identity authentication claim is made. No new native run, full suite, or shared source edit was performed by this reviewer.
