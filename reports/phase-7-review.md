# Phase 7 review resolution

One fresh whole-phase review was performed by `phase7_review` against the
implementation and v5.1 requirements. It found six Important issues and no
Critical issues. One RED→GREEN correction pass followed; no second review was
requested.

| Finding | Resolution and evidence |
| --- | --- |
| An approved candidate could be paired with a different FBX path | Import requires membership in the sealed candidate, matching production identity and the expected source hash; native Editor verifies the copied FBX hash. Substitution fails before native writes. |
| Distinct reviewer labels could pass without inspection of the exact request | Review binds the original brief, supported task, complete artifact inventory and candidate digest. Approval reruns the deterministic inspector and compares the receipt. Wrong briefs, unsealed motion and forged authority fail. |
| A committed result could survive changed project inputs or native outputs | Plans fingerprint code, schemas, package resources and workspace inputs. Durable receipts hash generated outputs; every resumed producer/import job validates its receipt. Missing-controller and changed-manifest probes fail closed. |
| BUILD_GAME dropped cancellation before reaching native work | Cancellation passes through generation, game/static integration, application checks and the player runner. An actual owned child is cancelled; publication remains fenced. |
| A crash after native completion could repeat mutation before ledger publication | Stable operation IDs and intents precede launch. Atomic native completion inventories and operation receipts permit recovery before the coordinator commits. Real process-death tests cover production/integration receipt boundaries with a deterministic backend. Actual Blender recovery skips launch; actual Unity recovery skips the asset build and reruns checks. |
| Blender-only animation forced Unity integration | Explicit domain routing uses three jobs for Blender-only animation and four when Unity is requested. Complete-game requests retain S0–S5. |

Two initially Minor findings were treated as Important because they affect the
mandatory acceptance fixtures: canonical asset IDs must reach Unity, and the
missing-transition mutation must have valid clips so that it isolates the
transition defect. Both were corrected; no minor deferrals remain.

`tests/test_phase7_review.py` records the boundary regressions, including actual
owned-process cancellation and two actual coordinator process deaths. The
initial failing fixtures and the 84-test correction suite are retained in
[review evidence](phase-7-evidence/review-red.txt) and
[passing correction tests](phase-7-evidence/review-green.txt). Two additional
RED→GREEN tests demonstrated that adapter/schema changes also need to invalidate
the engine identity; the final inventory covers all executable engine/package
resources rather than a selected source-file list.

The final suite, native completion proof, native negative fixtures, installed
wheel commands and regression XML are indexed in
[the Phase 7 evidence inventory](phase-7-evidence/index.json). Same-host role
separation is disclosed. Protected evaluator authority, OS isolation and full
cross-application rollback are separate later gates.
