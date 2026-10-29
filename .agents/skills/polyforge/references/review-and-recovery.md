# Review and recovery commands

Keep technical, artistic and gameplay approvals separate. Independent registered
checks bind sealed file hashes, revision, original brief and amendment digest.
Same-host role separation is not a protected evaluator or an OS sandbox.

For six-frame direct sprites, use `review sprite-source --workspace ROOT --input
FILE --json`. Save `data.source_review.candidate` to a workspace candidate file.
Set `visual_approval_required: true` when artistic approval is required. Pending
review or rejection blocks both capability and workforce imports before Unity
writes. The first actual admission persists the requirement for the asset.
Use `review human --workspace ROOT --candidate candidate.json --verdict APPROVED
--operator NAME --reason TEXT --approved --json` only after an explicit actual
operator decision. REJECTED refuses that source. This is a local attestation,
not identity authentication. Never let an assistant role attest as a person.
Changed source bytes require new inspection/approval. Optional dry runs write
nothing; technical-only legacy strips remain supported.

Use `review board --workspace ROOT --candidate FILE --task FILE --json` for
produced candidate promotion. It recomputes technical checks, required subjective
approval and independent public gameplay obligations. No supervisor can override
a gameplay veto. Performance is NOT_RUN; external evaluation is NOT_SUPPLIED;
game acceptance remains PARTIAL.

Preserve the exact original task brief. To append an explicitly approved new
requirement, use `review amend --workspace ROOT --task task.json --amendment
amendment.json --operator NAME --reason TEXT --approved --json`. Amendment JSON
contains `text`, `requirements` and boolean `visual_approval_required`.
Requirements are typed rows: `original_phrase`, `feature_id`, `artifact_id`,
`unity_component`, `oracles`. Phrases must occur in the amendment text. The
append-only hash chain retains all original obligations and invalidates earlier
approvals. Unsupported mappings remain REVIEW; never invent prose verification.
For visual-only clarification use an empty requirements array.

Use `reconcile --workspace ROOT --json`, then `diagnose --workspace ROOT
--evidence-dir runs/ID --json` for observed native issues. `repair inspect
--workspace ROOT --evidence failure.json --json` classifies a forensic capsule;
`repair propose --workspace ROOT --diagnosis diagnosis.json --json` previews an
evidence-bound action. Save data.proposal and use `repair apply --workspace ROOT
--plan FILE --approved --json` only within the authorized repair scope. Only
registered static native binding actions with reconstructable frozen inputs are
automatically executable. Other source/export, sprite, motion, timeout or API
routes remain BLOCKED when no safe original action is reconstructable. Return
them to the named original specialist. Two attempts maximum; repeating the same
proposal escalates. No arbitrary commands, source patches or implicit downloads.

After a crash between restored bytes and native reimport, use `resume --workspace
ROOT --run-id TRANSACTION_ID --json`. ROLLING_BACK resumes native reimport and
GUID/local-ID/reference/count plus applicable arena/animation/sprite checks.
Matching bytes alone cannot establish success. ROLLBACK_FAILED quarantines the
project. Use `repair rollback --workspace ROOT --transaction-id ID --json` for
explicit recovery of the owning transaction; only successful native proof clears
quarantine. Committed side effects are never automatically replayed. Forensic
run IDs resume their existing result/transaction rather than rerunning a worker.
Unknown run types and changed workforce inputs fail explicitly. Do not silently
remove Unity locks; establish that the owned Editor process has exited first.
