# Phase 9 review and resolutions

One fresh, read-only whole-phase reviewer examined the implementation before
publication. Initial verdict: **not ready**, with five Important findings.
The following dispositions are the implementer's verified fix pass, not a claim
that the reviewer independently reran native applications or approved the final
diff. No Critical finding was reported.

| Finding | Resolution and evidence |
| --- | --- |
| Corrupt dependency lists could expand rollback deletion into user files/directories | Validate the complete saved scope, canonical paths, unique source/registry provenance and immutable scope digest before inventory or any restoration. Four reproduced failing file/directory cases became passing; further malformed scope/proof cases preserve both live managed and user bytes. See `test_phase9_recovery.py`, `closure-negative.txt` and the final test log. |
| Sprite import could write Unity before required human/source review | Add independent bounded source inspection and byte-bound local decisions before direct dispatch, operation reuse and workforce production. Persist required review for the asset; recheck under the physical project lock and copy validated cached bytes. Pending, refused, changed and legacy-input bypass cases deny native writes. The final native direct import also passes 5 Editor + 4 PlayMode tests. |
| Arena wall FBX copied before the physical project lock | Move copy, source hash and request publication inside the lock. Contention and quarantine tests reproduce the original write and now preserve the existing FBX. |
| Forensic plans and durable budgets were disconnected from execution | Route exact native symptoms through existing managed repair transactions. The product calls reserve/finish, preserves interrupted reservations and resumes recorded recovery without producer replay. Unsupported original-input routes are explicitly BLOCKED. A real native scale fault commits with no remaining issues and all applicable regressions; repeating its proposal escalates. Unit failures/resume prove durable budget ownership. |
| Approved amendments were missing from review/acceptance | Add explicit append-only operator records bound to the frozen original, ordered hash chain and typed additional requirements. Bind board and human receipts to the chain. Stale approval, reorder/substitution and unknown mappings deny approval; positive supported arena mappings append passing checks without removing originals. |

Final evidence inspection also found that repeated recovery could overwrite the
previous native logs. A reproduced RED test now passes with unique attempt
directories. An actual native timeout and successful resume retain the failed
process/log hashes unchanged (`retained-timeout-check.json`).

A later equivalent consumer run also exposed an input-selection failure during
explicit rollback. Recovery correctly stayed quarantined. The fix selects the
exact recorded input, archives canonical native job documents in protected
snapshot scope for new transactions, and retains legacy registered inputs with
hash verification. A corruption/duplicate-run regression covers restoration of
the archived document; the blocked native attempt is retained with its cause.

The bundled skill was tested with a fresh reference-only reader. The baseline
could not establish source-approval, amendment or native crash-recovery flows.
After updating linked references it identified all three correctly, including
the native proof requirement and stale approvals. Catalog/schema inspection is
still required for complete capability inputs; portable host qualification
remains Phase 10.

The report makes no artistic, protected-evaluator, OS isolation, standalone or
performance qualification claim. Full executed gates and evidence paths are in
[the Phase 9 report](phase-9.md).
