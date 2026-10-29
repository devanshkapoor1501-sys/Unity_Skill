# Review and recovery

Phase 9 adds independent engine checks before promotion, original-brief public
acceptance, forensic routing and verified managed rollback. See the
[Phase 9 evidence](../reports/phase-9.md) for executed qualifications and limits.

## Review before integration

`review board --workspace ROOT --candidate candidate.json --task task.json`
recomputes registered technical checks against sealed files. Technical,
subjective and public gameplay verdicts remain separate. The release supervisor
cannot override a failed required inspector or original gameplay obligation.
Inspector roles have no candidate writes and cannot read evaluator namespaces.
These are engine permissions on one host, not an OS sandbox or protected
evaluator. Performance stays NOT_RUN; game acceptance stays PARTIAL.

An AssetSpec's `visual_approval_required` requires an explicit local decision.
Use `review human --workspace ROOT --candidate candidate.json --verdict
APPROVED --operator NAME --reason TEXT --approved` after inspecting the actual
candidate. Use REJECTED to refuse it. This appends a local attestation bound to
the sealed revision and current amendments. It does not authenticate a person's
identity; producer and inspector role names cannot attest as people. A changed
file, old receipt, missing approval or explicit rejection denies promotion.

For direct sprites, first run `review sprite-source --workspace ROOT --input
sprite-input.json`. Save `data.source_review.candidate` as candidate.json for
human review. The source scope checks license, exact six 128px frames, atlas,
alpha, ordering and pivots before any Unity import. Both capability and workforce
entry points use this gate. Set `visual_approval_required: true` in the sprite
input when artistic approval is required. The first actual admission attempt
persists that requirement for the asset; omitting the flag later cannot bypass
it. A rejection binds the exact source bytes across both entry points. Legacy
technical-only sprite inputs remain supported. Native import/tests have their
own subsequent checks and do not imply artistic approval.

## Approved amendments

Keep the original task brief unchanged. `review amend --workspace ROOT --task
task.json --amendment amendment.json --operator NAME --reason TEXT --approved`
appends a bounded, hash-linked record to its original-brief ledger. For example:

```json
{
  "text": "Keep the painted finish",
  "requirements": [],
  "visual_approval_required": true
}
```

Machine-checkable requirements use `original_phrase`, `feature_id`, `artifact_id`,
`unity_component` and an `oracles` array. The phrase must occur in the amendment.
The supported public arena mappings are in `polyforge/data/arena_acceptance.json`.
Original obligations are never removed. Approved mappings append checks;
unsupported mappings remain REVIEW. Arbitrary prose is not interpreted as a
verified mechanic. The chain digest binds board and human approvals; amendments
invalidate earlier approvals and require renewed review. Stored receipts and
history disclose their same-host local trust boundary.

## Diagnosis and execution

`reconcile --workspace ROOT` observes live native bindings; `diagnose --workspace
ROOT --evidence-dir runs/ID` produces typed issues and forensic capsules.
`repair inspect --workspace ROOT --evidence failure.json` classifies an explicit
versioned cross-tool capsule. `repair propose --workspace ROOT --diagnosis
diagnosis.json` verifies actual referenced hashes and returns `data.proposal`.
Save that exact object and use `repair apply --workspace ROOT --plan plan.json
--approved` to execute it. Existing `repair plan --issue ISSUE-ID` native plans
remain compatible.

The eight playbooks distinguish GUIDs, FBX axes/scale, geometry, Unity API context,
missing components, sprite curves, action slots and worker timeouts. Structured
FAIL evidence takes precedence over log heuristics. BLOCKED/NOT_RUN are never
reclassified as executed failures. Ambiguous null references and novel compiler,
assembly, package, mode or reload errors do not authorize generated patches.

Automatic forensic execution currently admits registered static native binding
rebuilds, including measured importer/prefab scale faults, when the exact original
manifest, source hashes and native symptom can be reconstructed. It reruns
targeted reconciliation and applicable arena, animation and sprite regressions.
Other geometry/export, sprite, motion, timeout and API routes remain BLOCKED when
their original inputs/action cannot be safely reconstructed. The output names
the original specialist and verification route; a suggested action is never an
executed repair. No packages, arbitrary commands or generated patches run.

Forensic attempts are durable across process interruption. Two attempts per
symptom is the maximum; repeating the same proposal escalates immediately.
`resume --workspace ROOT --run-id forensic-ID` closes the durable result or
recovers its recorded transaction. It never silently replays an interrupted
producer. Unsupported run types and stale workforce inputs fail explicitly.

## Verified rollback

Every Unity writer takes the same physical project lock. Recovery snapshots only
managed project state and registered producer sources/sidecars, with provenance,
exact inventory hashes and a complete validated dependency closure. User files
outside that scope and Library caches are excluded. Package/project settings and
applicable game, animation and sprite inputs are retained.

`repair rollback --workspace ROOT --transaction-id ID` restores validated bytes,
forces native reimport, observes GUID/local IDs, references and object counts,
then reruns all applicable original scenario/test profiles. Exact identities and
counts must match; numeric comparison uses 0.1mm absolute / 1ppm relative.
Matching bytes alone is insufficient. Large proof documents use immutable
hash-linked files. Legacy static-only journals cannot claim complete recovery.

A crash after byte restoration leaves ROLLING_BACK. `resume --workspace ROOT
--run-id ID` repeats the native proof. ROLLBACK_FAILED quarantines the project;
ordinary writers are blocked until recovery for the owning transaction succeeds.
Committed side effects are not automatically replayed. A recovered workspace
changed afterward requires explicit reviewed rollback rather than blind resume.
