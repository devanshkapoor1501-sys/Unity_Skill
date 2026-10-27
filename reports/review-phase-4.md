# Phase 4 independent review

A fresh-context read-only reviewer inspected the working tree against 71b25a0,
covering the S3 worker, managed source lookup, PNG decoding, export evidence,
CLI preflight and tests. Actual Unity import and artistic acceptance were explicitly
outside the phase. The reviewer made no edits or full-suite execution.

Three Important findings were reproduced and fixed:

1. A failed S3 run could have S2 passed but no artifacts.json; lookup selected it
   and hid the preceding usable source. Candidates now require a registered
   artifact inventory. The regression retains an older hashed source and a newer
   failed/unregistered attempt, and proves the registered source is selected.
2. S3 preview resolution above 1024 was rejected only after planning writes.
   Build now validates the S3-specific budget before both dry run and publication.
   The regression checks exit 2 and complete unchanged file hashes for both modes.
3. Roundtrip material checks required every declared palette material, including
   unused editable entries. Actual crate evidence proved FBX contains only used
   materials. The sidecar validates the whole palette; roundtrip validation checks
   the used set. An explicit unused-palette regression and real crate export pass.

The reviewer also confirmed the previously known malformed-metadata path. Added
tests reject invalid/null timestamps and artifact lists as typed InputError;
nested state and recipe shapes are checked before access. No required finding
remains deferred.

Other implementation tests independently validate PNG content/CRCs/decompression,
sidecar values and bindings, source hash preservation, synthetic asymmetric
handoffs and six real source-corruption categories. Initial logs showed Blender
attempting a user-profile extension cache write; environment overrides now place
Blender resources under the owned temporary directory. No OS containment claim
is inferred from that redirection.
