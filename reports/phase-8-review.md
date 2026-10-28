# Phase 8 review resolution

One fresh whole-phase review by `phase8_review` found four Important and two
Minor issues. One tested correction pass followed; no second review was used.

| Finding | Resolution |
| --- | --- |
| Direct-sprite inputs at the workspace root or a nested input directory were mistaken for the production run | Handoffs now carry the producer run identity. Inspection validates that run against registered artifacts instead of inferring it from the first sorted path. Root and nested path fixtures pass. Legacy handoffs require a unique matching run. |
| An existing managed project could resolve packages without recorded download approval | Both fresh and existing projects require explicit approval or the existing workspace approval record before native synchronization. The denial test forbids synchronization and launch. |
| An asset bundle could omit or replace its reference/license dependencies | Dependencies must match the frozen AssetSpec, including source hash, license and DATA_ONLY authority. Omission, substitution and authority changes fail. |
| Partial, duplicate or unknown material identities could pass inspection | Inspection requires the complete unique material set and exact semantic module assignments. Missing, duplicate, unknown and swapped bindings fail. |
| The declared dimension tolerance was ignored | Asset inspection now applies the declared absolute tolerance. Strict and relaxed rubric fixtures both failed before the fix and pass afterward. Existing geometry validation keeps its original default tolerance. |
| Replacing a sprite input handler leaked its subscription | The controller disposes the previous handler once, retains identical assignments, and releases its handler on destruction. The native Editor test demonstrated the original leak; Editor replacement and actual PlayMode destruction are checked separately. |

Dimension tolerance was treated as a mandatory quality boundary, not deferred as
a cosmetic issue. Follow-up provenance fixtures also reject a changed sprite
input on resume and bind the operation digest to actual frame, atlas and metadata
bytes. Asset source inspection verifies the measured geometry digest.

Final verification exposed a separate fresh-project upgrade case: an unchanged
new package returned without recording its trusted source baseline. A failing
test demonstrated that its next legitimate upgrade was denied. Initial exact
matches now retain the same immutable source provenance used by later upgrades.
An older project without a verifiable source baseline remains denied; local edits
are never adopted as trusted source. The final fresh project exercises this path.

The initial failing fixtures, native failure XML, passing correction tests and
final native results are retained in the [evidence inventory](phase-8-evidence/index.json).
No test assertion, coverage threshold or native test inventory was removed to
obtain a passing result. Artistic approval remains REVIEW, role separation is
DIFFERENT_ROLE_SAME_HOST, and protected evaluation remains external.
