# Phase 13 equal-tool pilot

**Decision — NARROW.** The required paired run and clean-workspace repeat
are complete. Phase 14 remains gated.
[Machine-readable decision](phase-13-evidence/decision.json)

The v7.1 pilot compared general Codex (C) with Codex plus PolyForge (D) on
five frozen Blender-to-Unity cases. The baseline passed **5/5** and the
assisted arm passed **1/5**, below the required 4/5 and baseline parity.
The assisted median was 12.32% slower, missing the 20% improvement gate.

## Evidence and scope

- Candidate `a77b33b6b8459028197ec8e14b3d0acddb6ef96d`, with the pinned
  wheel and skill identities recorded in the freeze. Both arms used Codex
  CLI 0.154.0, `gpt-6-astra` at low reasoning effort, Blender 5.2.2 LTS and
  Unity 6000.6.3f1 on the same Windows host. They used fresh, read-only
  producer sessions, a common data-only Blender/Unity broker, and a
  240-second attempt cap, 8 GiB memory cap and zero retries. Arm D also had
  the pinned PolyForge compose backend. [Freeze and environment comparison](phase-13-evidence/freeze-r2.json)
- The verifier froze the case order and rubric before the producer turns.
  The initial setup failed before model launch because the output schema
  path was relative. The repaired runner kept the original cases and
  rubric. The earlier direct producer-shell preflight was blocked for both
  arms. The successful parity comparison covers the fixed broker.
  [Preregistration](phase-13-evidence/evaluator-preregistration.json) ·
  [Invalid setup receipts](phase-13-evidence/invalid-setup) ·
  [Parity preflight](phase-13-evidence/preflight)
- A separate Codex verifier reconciled the frozen files, ten producer
  receipts, 40 artifact hashes, the Unity observations and the aggregate
  score. Assurance is `SAME_HOST_NONBLIND` because access separation was
  not enforced by the OS. External acceptance is `UNVERIFIED`. The five
  pairs are exploratory evidence for this workflow and these versions.
  [Frozen rubric](phase-13-evidence/verified-rubric.json) ·
  [Evidence index](phase-13-evidence/index.json)

## Paired outcomes

| Case | C verdict | C seconds | D backend | D verdict | D seconds |
| --- | --- | ---: | --- | --- | ---: |
| Modular room alcove | ACCEPTED | 32.846 | Blender | ACCEPTED | 37.268 |
| Off-center sockets | ACCEPTED | 36.202 | PolyForge | REJECTED | 41.482 |
| Material and LOD | ACCEPTED | 36.933 | PolyForge | REJECTED | 43.403 |
| Rotated mechanical assembly | ACCEPTED | 39.039 | PolyForge | REJECTED | 40.736 |
| Asymmetric import/repair | ACCEPTED | 39.201 | PolyForge | REJECTED | 45.673 |

The medians were **36.933 s** for C and **41.482 s** for D. The timing
includes production and per-attempt native checks. The shared Unity batch
took 261.046 s and was reported separately. Both arms recorded zero manual
corrections, making that comparison `NOT_APPLICABLE`. Producer token counts
are in the receipts. Monetary costs were unavailable.
[Per-attempt score and receipts](phase-13-evidence/trial/score.json)

Blender reopened all ten editable sources successfully. Unity inspected
20 main and LOD FBXs. Reimport preserved GUIDs and metadata hashes, and
the verifier confirmed the producer artifacts were unchanged. All 40
applicable missing-socket and X-reflection mutants were detected and
cleaned up. The only accepted D output used the common Blender backend.
[Unity receipt](phase-13-evidence/trial/unity.json)

Unity found zero exact matches for the twelve named module meshes across
the four PolyForge main exports. The Blender sources held the expected
names, but the exported objects carried an `_evaluated` suffix. Because
the importer could not identify the modules by name, the verifier had no
per-module bounds or material measurements for them. The socket checks
passed. [Export code](../polyforge/blender/modeling_worker.py#L123) ·
[Unity name check](../tests/fixtures/modeling/Phase13ImportProbe.cs#L194)

## Immediate clean reuse

The off-center socket case was chosen after the paired run to check the
observed module-name failure alongside asymmetric socket coordinates. The
repeat used a fresh detached checkout, a reset producer session and an
offline install from the pinned wheel. Setup recovered from Git's default
Windows path-length limit with command-scoped long-path support. The
dependency check passed and the broker rejected an invalid request.
[Clean setup receipt](phase-13-evidence/immediate-reuse/setup.json)

The reset session used PolyForge and produced the editable source, preview,
main FBX and LOD. Blender reopened the source. Unity imported both FBXs and
rejected the output because none of the three named modules matched. All four
applicable socket faults were detected and cleaned up. Socket positions,
artifact hashes and reimport identities remained valid. The repeat took
73.655 s using the paired timing method, plus 38.828 s for setup and a
377.609 s shared Unity batch. The optional day-8–14 retention check is
`NOT_RUN`. [Reuse score](phase-13-evidence/immediate-reuse/score.json) ·
[Reuse Unity receipt](phase-13-evidence/immediate-reuse/unity.json)

Any subsequent work under this result is limited to the exact exported module
identity issue in the tested handoff. A qualifying paired result and accepted
clean reuse are required before opening Phase 14.

## CI context

The closeout ran 238 offline modeling tests successfully. One native test was
deselected by the offline marker. The pilot scripts passed lint and format
checks, and mypy passed across 123 source files.

All three foundation jobs passed on the historical `0c22b18` checkpoint
cited in the roadmap. [GitHub Actions run 42584209969](https://github.com/devanshkapoor1501-sys/Unity_Skill/actions/runs/42584209969)

The evidence closeout commit `b1173871000134fe566ba1161b2f30baee9d67ce`
contains the exact frozen verifier source. A later compatibility fix made the
same Windows reparse-point check type-check on Linux. The frozen trial and
its verdict remain tied to the closeout commit.
[Closeout commit](https://github.com/devanshkapoor1501-sys/Unity_Skill/commit/b1173871000134fe566ba1161b2f30baee9d67ce)
