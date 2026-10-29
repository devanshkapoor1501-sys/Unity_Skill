# Phase 10 review and verification

A fresh read-only whole-phase reviewer examined the diff from Phase 9. Initial
verdict: request changes for one Important evidence-contract issue; no other
Critical/Important finding. The reviewer ran 67 focused offline tests and did
not claim native application or final package qualification.

**Finding:** a matching installed-tool version receipt could mark unrelated
KnowledgeCards VERSION_PROBED. The router ignored each card's `api_probe_id`.
For example, a Unity TypeCache observation could elevate a generic repair card.

**Fix:** require the exact registered probe identity as well as matching version.
Only `blender.context` and `unity.editor` name the two fixed native probes;
unrelated modeling, materials, gameplay and repair cards retain REFERENCE_ONLY.
No capability support is promoted by a probe. The reproduced three RED cases
became GREEN, including a positive matching Editor card and negative unrelated
cards. Actual native receipt hashes were reread and the exact scoped state
verified after the fix (`native-receipts-verified.json`).

The implementer's additional build-plan checks found and corrected two details:
the route now distinguishes supplied-sprite import, approved robot bake and
unsupported new sprite artwork; strict version-map keys deny unknown tool names.
Both started with failing contrasts. Dry-run probe planning now succeeds without
an installed native tool while explicitly reporting UNAVAILABLE/NOT_RUN; actual
execution still blocks on a missing dependency. Documented runnable commands are
executed against a temporary typed fixture and checked for zero writes.

The official Agent Skills reference validator passes. A separate fresh reader
tested the skill before/after references were added. The available Codex app
harness executed the narrow explanation route; standalone Codex CLI and Claude
Code produced explicitly retained account/configuration BLOCKED outcomes.
Authentication, model settings, permissions and assertions were not bypassed.

This is the implementer's verified fix disposition, not a second independent
review or a claim that the reviewer approved the final package. Full results,
remaining host limits and the requirement-by-requirement plan audit are in the
[Phase 10 report](phase-10.md).
