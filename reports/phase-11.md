# Phase 11 evidence reconciliation and release checkpoint

**Disposition: BLOCKED for stable CORE v1.0 release. Phase 12 entry is BLOCKED.**

The original entry rule below records the Phase 11 qualification decision. The
user later authorized Phase 12 development while stable qualification remains
blocked. Main commit `941717b` passed [workflow 41877839001](https://github.com/devanshkapoor1501-sys/Unity_Skill/actions/runs/41877839001).
See the [Phase 12 checkpoint](phase-12.md) for the separate development status.
This checkpoint preserves the implemented Phase 11 work and reconciles actual
results. It does not declare Phase 11 closed, create a release tag, or implement
Phases 12–17. Reconciled on 2026-11-04, branch `codex/polyforge-phase-11`, base
`31827d134102650604aaa0998c0d06d6f4a579c3`.

Authority: the complete v5.1 blueprint, SHA-256
`8f186fa13ce3fc085cab96ee5991dce2e85dde36277f2c6c631f7e8d5a9331d6`,
Section 12, Chapters 16–18 and Appendix G. The three review lanes read the
complete document before reconciliation edits. The user's current instruction
requires every mandatory Phase 11 gate, remote checkpoint and CI before Phase 12.
Historical permission to continue does not waive those gates.

## Source identity and tools

Checkpoint runtime engine identity is
`4711a8c26098c4c19b0a0bbdbecaaa8399610286ce76d32e45f90cb598a9ca4b`.
Earlier native and offline runs used `a7b4b8e…`. The focused cleanup review used
`b9f91bd…` before the working tree was normalized to Git’s LF line endings.
Python 3.12.14; Blender 5.2.2; Unity 6000.6.3f1; URP 17.6.0;
Input System 1.19.0; Unity Test Framework 1.8.0. Python qualification uses pytest
8.4.2, pytest-cov 6.3.0, coverage 7.17.0, ruff 0.13.3, mypy 1.18.2,
setuptools 80.9.0 and wheel 0.45.1. Package version remains `0.0.1` while stable
release requirements are unmet. No v1.0 or v2.0 tag is claimed.

Native tool versions come from the recorded probes. Offline, installed package
and native checks each have separate receipts.
Linux-target mypy is static checking on Windows, not Linux native verification.
The configured CI matrix covers Windows Python 3.11/3.12 and Ubuntu Python 3.12;
Blender/Unity Linux/macOS operation remains NOT_RUN.

## Skills and worker selection

The repository-local PolyForge skill was selected for capability contracts,
review/promotion boundaries and recovery semantics. The codebase-memory skill
was selected for structure lookup; its project list was empty and coverage check
reported an unindexed project, so this audit used direct source/evidence reads.
Verification-before-completion governs observed test claims. The document skill
was inspected for the supplied DOCX; no DOCX authoring was required. Broad build,
brainstorming, website and unrelated media skills add no value to this closure.

Registry discovery returned 19 bounded capabilities and 17 workforce roles.
A quality INSPECT knowledge route selected evaluation/recovery references,
returned REVIEW with unverified requirement coverage, and proposed no writes.
Its route is not execution or release acceptance. Native tools were discovered
at their installed paths. The wheel installed from the existing offline
wheelhouse. The native demo uses the pinned Unity template and its approved
package resolution scope.

Two Codex native reviewers audited the inherited gates and evidence. A native
executor implemented cleanup with test driven development. A separate reviewer
verified the safety repairs. Agent Team and parallel dispatch were used for
package qualification, evidence review, and Git and CI preflight while the
coordinator ran the full suite and native demo. The desktop session runs
outside tmux and the Phase 11 branch already held implementation work, so the
team used the existing native agents and bounded file ownership.

These engineering assignments are separate from PolyForge runtime worker
measurements and protected gameplay evaluation. Runtime evidence remains
LOCAL_SINGLE_ROLE and LOCAL_MULTIROLE_SEQUENTIAL.

## Reconciled observed evidence

Paths below are relative to [the retained evidence directory](phase-11-evidence/).
[index.json](phase-11-evidence/index.json) records exported size/SHA-256, original
source size/hash lineage and transformations. Native caches, authentication
profiles and player binaries are excluded; editable sources, run inputs,
XML/telemetry, rollback journals and provenance are retained. Scripts and C#
diagnostics are stored as `.txt` so evidence cannot enter test discovery.

| Check | Observed result | Evidence |
| --- | --- | --- |
| Original starting baseline | 660 passed, 12 deselected; 94.87% combined / 91.68% branch | `baseline.txt`, `baseline-coverage.json` |
| Earlier expanded regression | 989 passed, 12 deselected; 95.10% combined; historical scope | `final-unit.xml`, `final-coverage.json` |
| Later complete frozen regression | 1,145 passed, 12 deselected; 93.4667% combined / 90.1119% branch; lint, both type targets and CLI docs PASS; unchanged runtime identity | `release-complete-summary.json`, `release-complete-unit.xml` |
| Pre-cleanup local rerun | 1,145 passed / 12 deselected with 93.4667% combined and 90.1119% branch coverage. Lint, format, both type targets and CLI docs PASS on `a7b4b8e…` | `closure/release-qualified-summary.json`, `closure/release-qualified-unit.xml` |
| Final offline regression | 1,218 passed and 12 deselected. Combined coverage 93.8104% and branch coverage 90.6332%. Lint, format, Windows/Linux-target typing and CLI docs PASS. Engine digest matched before and after | `closure/release-final-summary.json`, `closure/release-final-unit.xml` |
| Bounded cleanup | 73 focused tests PASS, 100% statement and 99.23% branch coverage. Separate safety review and unrestricted rerun PASS | `closure/cleanup-summary.json`, `closure/cleanup-coverage.json` |
| Final arena native integration | 1 EditMode + 18 PlayMode PASS; 10 nominal public scenarios + seven killed mutants, including M1–M6; standalone build/smoke PASS | `arena-final-result.json`, `native/arena-final/runs/` |
| Arena original-brief public traceability | Public checks PASS; external evaluator EXTERNAL_NOT_SUPPLIED; manual review REVIEW; game PARTIAL | `arena-final-public-acceptance.json` |
| Checkpoint platformer attempt 3 | 2 EditMode + 24 PlayMode PASS; 14 nominal physical scenarios + eight killed mutants; standalone build/smoke/gameplay PASS; game PARTIAL | `platformer-attempt-3.json`, `native/platformer-demo/runs/` |
| Later shared-project platformer rerun | Separate 2+24 test / 22-scenario PASS; standalone NOT_RUN for this run | `shared-retry-platformer-result.json` |
| Shared-project native rollback | PASS, ROLLED_BACK; native reimport and regression proof, restored source bytes | `shared-retry-native-rollback-result.json`, `native/demo/transactions/phase11_shared_cross_tool_retry/journal.json` |
| Original-project static scan | Non-mutation PASS: 30,632 files / 1,337,954,940 bytes, equal original inventories; no Unity execution; overall REVIEW, API compatibility UNKNOWN | `static-project-reviewed.json` |
| Installed CLI/resource/parser smoke | PASS; 24 schemas, 43 command help paths, 100 parser iterations, unchanged static fixture | `clean-installed-final-summary.json`, `clean-install-final.txt` |
| Earlier clean-installed native arena | S5, standalone build, smoke and public behavior PASS. 1 EditMode and 18 PlayMode tests. Manual review REVIEW and game PARTIAL on `a7b4b8e…` | `closure/clean-installed-native-summary.json`, `closure/native/clean-native-demo/runs/game-check-a135ce2bfc8b4df5/` |
| Final reproducible package build | Wheel, source archive and receipt match byte for byte between two builds. Wheel SHA-256 `a5219b88d704418abbc9b58b14767da1c9b78bd453b05c2bc7c7f16b2d69d8e1` | `closure/final-reproducibility.json` |
| Final offline wheel install | PASS. 24 schemas, 43 command help paths, parser and read-only inspection smoke, clean preview lists the expected candidate with byte preservation | `closure/final-installed-summary.json`, `closure/final-clean-preview.json` |
| Final installed native demo | PASS through S5 in a new disposable Blender and Unity project. 1 EditMode and 18 PlayMode tests passed, along with standalone build and smoke. Current manual review REVIEW and game PARTIAL | `closure/final-installed-native-summary.json`, `closure/native/final-native-demo/runs/game-check-4f95281f9e214a8e/` |
| Portable skill format | PASS for format/reference integrity; nine listed runnable commands remain distinct from invocation evidence | `skill-validation-final.txt` |
| Early unfamiliar Blender API | BVH hit/miss/distance checks PASS on 5.2.2 | `blender-bvh-result.json` |
| Early unfamiliar Unity API | Pool reuse, duplicate-release rejection and cleanup PASS after license refresh | `unity-pool-retry-1.json` |
| Worker race/crash, permissions, rollback failures, version fallback and negative contracts | Covered by full Python regressions and native rollback; original assertion strength retained | `release-complete-unit.xml`, scoped test logs and retained negative attempts |
| Platformer workforce promotion | BLOCKED because every required approval for the revision is not present | `platformer-workforce-final-result.json` |

The final static scan's non-mutation result does not resolve its 269 GUID
observations, 33 namespace candidates or 213 incomplete source analyses. Its
REVIEW result is retained. A static scan never proves native package/runtime
compatibility and never authorizes modifying an original project.

The earlier implementation fixed a parser access violation, signed sprite
local IDs, float32 round trips, physics oracle schedules, benchmark repetitions,
package resolution reporting and rollback comparison. Their prior reviews and
failed attempts are retained.

This reconciliation implemented the inherited `clean` command. Preview is the
default. Confirmation checks the managed workspace, completed run, process
liveness, links, referenced artifacts and file identity before each deletion.
Independent review found and retested cross-run references, embedded Unity
caches, malformed process metadata, lock link safety, nested live scopes and
partial deletion receipts. These checks ran on disposable fixtures. The command
has a trusted local scope. See [cleanup usage](../docs/cleanup.md) and
[the repair contract](phase-11-cleanup-contract.md).

The native source comparison found 140 identical packaged files and two files
with line ending changes alone. The prior native receipts retain their engine
identities. The final arena demo and final offline suite have separate receipts.

## Rendered profile and resource limitations

`arena-final-profile.json` records three complete 60-second windows after a
10-second warmup at 1280×720, PC quality. All declared numerical checks PASS.
Sample median FPS: 582.309 / 619.233 / 657.203. P95 end-of-frame interval:
2.802 / 2.607 / 2.353 ms. Peak RSS is at most 410,411,008 bytes; load at most
5.297 seconds. Median across samples is 619.233 FPS; spread is 12.0946%.
The profile retains PUBLIC_DEVELOPMENT and `qualification=false`.

The machine inventory records 16 logical CPUs, 24,841,998,336 bytes physical RAM,
AMD Radeon 780M and NVIDIA GeForce RTX 5050 Laptop GPU. Device inventory does
not establish which GPU performed work. GPU utilization is UNKNOWN and physical
presentation/GPU execution time is NOT_MEASURED. Focus state is observed while
continuous background-enabled intervals are kept. Earlier failed focused-readiness
samples remain FAIL; they are not combined with these three passing samples.

## Benchmarks and ablations

The original 12 public tasks and briefs are preserved. At five repetitions,
the bundled suite plans 60 cases per arm. The additive public release suite
has 14 DEV_FIXTURE tasks, including two 3D games and one 2D game, planning
70 cases per arm. The earlier 12-case availability artifact is historical.
**Each A–D arm has zero executed trials.** `release-suite-availability.json`
reports external withheld variant NOT_PROVIDED and independent scoring NOT_RUN.
The availability check's PASS means honest definitions/blocked records, not
benchmark success. Accepted-game rate is NOT_MEASURABLE; tokens/costs are unknown.
No comparison, parity-qualified causal advantage or superiority result is claimed.

Five single and five sequential local asset runs PASS, medians 8.110 and 8.031
seconds (variances 10.39497 and 0.12427 seconds squared). Both run the same
three-role graph. `local-mode-measurements/summary.json` binds these historical
measurements to engine `4998fcac…`, not the final engine. They do not measure
specialization gains. Concurrent roles, inspector-off evaluation, and
specialist-versus-general model trials remain NOT_RUN because corresponding
qualified adapters/evaluation paths are absent. Native code-review subagents
in this chat do not retroactively execute those benchmark arms.

## Gate reconciliation

[phase-11-gates.json](phase-11-gates.json) is the machine-readable requirement
matrix. Combined requirements retain the least satisfied mandatory component.

| Section 12 requirement | Current disposition |
| --- | --- |
| 11.1 security, licensing, portability and non-mutation | Bounded Windows/trusted checks PASS; native other OS and untrusted isolation NOT_RUN/BLOCKED |
| 11.2 four-arm comparison | Harness/negative tests PASS; actual trials and independent scoring BLOCKED |
| 11.3 worker ablations | Local mode measurements PASS at historical identity; required further ablations NOT_RUN |
| 11.4 two styles plus hidden combination | Public arena/platformer technical checks PASS; protected holdout BLOCKED |
| 11.5 mutants, rollback, races/crashes, performance | Public M1–M6/native rollback/profile and offline safety PASS; separately controlled acceptance remains BLOCKED |
| 11.6 docs and support/coverage maps | Present and reconciled; advanced phases explicitly unsupported; preserved denominator |
| 11.7 reproducible release, clean installation and demo | Final packages, offline installation and native technical demo PASS. Stable release remains BLOCKED |
| 11.8 Phase 0–11 fixture digest | Frozen inventory in `phase-11-baseline.json`; bytes do not imply acceptance |
| 11.9 Publish verified CORE v1 | BLOCKED. Current labeling reflects the experimental checkpoint |
| 11.10 actual delegation/resource measurements | Local role observations retained; model concurrency/ablation/GPU evidence NOT_RUN |
| 11.11 unfamiliar probes and changed-version rejection | Fixed native probes and negative/version regression evidence retained |
| 11.12 CLI consistency | Registry, help, docs and fixtures agree. Inherited cleanup now executes and the final installed preview passes |

| Inherited gate | Disposition and scope |
| --- | --- |
| G1 installation/schema/skill | PASS in bounded Windows install and offline checks |
| G2 geometry/export/four views | PASS for supported retained fixtures and fresh arena asset generation |
| G3 Unity import/scene/build | PASS on the final installed wheel with pinned Windows tooling |
| G4 playable loop + manual review | Public technical checks PASS; historical Phase 6 user review PASS; current build review REVIEW |
| G5 fault safety | PASS for covered negative/race/crash cases; retained failures surfaced |
| G6 docs/licensing/reproducibility | PASS for bounded experimental package; stable release remains blocked |
| G7 executable differentiated core | Public bounded capability evidence retained; no broad superiority claim; missing trials explicit |
| G8 independent required-feature acceptance | BLOCKED; game remains PARTIAL |
| G9 independent six-mutant oracle | Public M1–M6 detected; evaluator-owned qualification BLOCKED |
| G10 security | TRUSTED_LOCAL only; SANDBOXED_UNTRUSTED BLOCKED without real OS denial probes |
| G11 performance | Declared public Windows numerical profile PASS; GPU presentation NOT_MEASURED |
| G12 existing-project safety | Original non-mutation PASS; scan semantics REVIEW |
| G13 true holdout/generalization | BLOCKED; three evaluator-controlled unseen combinations not supplied/executed |
| G14 interface consistency | Generated CLI/docs and regression checks; no accepted contradictory syntax |
| G15 cross-application transaction | Native reimport/regression rollback PASS; earlier failed attempt retained |
| G16 physics tolerances | Public pinned Windows event-level checks PASS; no bitwise cross-platform claim |
| G17 parity and task eligibility | Public validators PASS; actual comparable C/D trials BLOCKED |

## Earlier chats and ownership

At the user's request, relevant earlier chats were searched: “Continue current
work” and “Inspect and implement build plan.” The latter contains the genuine
user response “All listed play checks passed,” preserved in
[the Phase 6 manual receipt](phase-6-evidence/manual-review.json), for player
`game-check-d9ccc8eca7304c16`. It supports that historical arena's seven play
checks. Its hidden-evaluator qualification is explicitly NOT_RUN. It does not
approve the rebuilt Phase 11 executable, platformer or visual style.

The Phase 11 kickoff in the earlier chat explicitly retained the separately
controlled evaluator gap. No protected evaluator results were found in the
searched turns. User trust/design approval is authorization to engineer, not a
recorded gameplay, aesthetic or hidden evaluation result. The user reports no
additional evaluator receipts are available. Development agents cannot create
newly hidden tasks in their own workspace and relabel them evaluator-owned.

`acceptance_oracle.json` preserves the historical Phase 8 receipt as a nested
record and points to the Phase 11 scoped evidence. Workforce history is appended,
not rewritten. Fixed registered native probes are distinguished from newly
generated experimental actions. The frozen competency denominator remains
20 subfeatures / weight 51; independent whole-row qualification remains absent.

## Exact verification commands

Run in the repository with its existing `.venv`; no dependency download required.
The retained receipt includes exact arguments, start/end times and exit codes.

```powershell
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m ruff format --check polyforge tools tests
.venv/Scripts/python.exe -m mypy
.venv/Scripts/python.exe -m mypy --platform linux
.venv/Scripts/python.exe -m tools.generate_cli_docs --check
.venv/Scripts/python.exe -m pytest --cov --cov-report=term-missing --cov-report=json:.tmp/phase11-closure/release-final-coverage.json --junitxml=.tmp/phase11-closure/release-final-unit.xml --basetemp=.tmp/phase11-closure/release-final-unit-temp
.venv/Scripts/python.exe -m tools.reproducible_build --outdir .tmp/phase11-closure/final-build-a --epoch 1793318400
.venv/Scripts/python.exe -m tools.reproducible_build --outdir .tmp/phase11-closure/final-build-b --epoch 1793318400
```

The restricted first rerun had 1,141 passes and four failures while creating
Windows junction/hardlink fixtures (Access is denied); its branch bar was 89.8787%.
That failed attempt is retained in `closure/release-complete-*`. The unrestricted
rerun passed all 1,145 tests in 430.82 seconds, including the real link fixtures,
and restored the unchanged branch bar to 90.1119%. No assertions were removed or
skipped. An additional inspection-only rerun passed 54 tests after formatting.

## Git, CI and continuation

This document is written before its checkpoint commit. The containing commit's
Git SHA is the authoritative content identity; later checkpoint/CI receipts may
refer to an earlier commit without claiming that later HEAD passed its checks.
Remote push and CI on the final pushed HEAD must be observed before any claim.
Local qualification passed. The publication receipt records the checkpoint SHA, remote branch verification and Actions result after push.
No force push, history rewrite, existing-tag replacement or unrelated video-skill
files are included. Those unrelated untracked files remain in the workspace.

Final release eligibility: **BLOCKED**, regardless of local or CI success.
To close Phase 11, supply independently controlled evaluation results for the
three unseen combinations and required acceptance, qualify missing benchmark
and ablation paths, complete required current gameplay/artistic approvals,
and satisfy every remaining stable-core gate. Verify final remote HEAD and CI,
then create/verify v1.0 only when justified. Until then, Phase 12 must not start.
Phases 12–17 remain requested and pending; no v2 qualification is claimed.

## CI correction after the first push

Checkpoint `2218efd` reached the authorized remote. Push workflow
`41872517019` passed both Windows jobs and failed the Ubuntu Python 3.12
job in 14 cleanup cases. Blank journal notes matched the synthetic empty
prefix of an absolute POSIX path, causing all temporary candidates to be
protected. The correction skips that empty prefix and retains explicit
file and directory reference checks.

The correction passed 76 cleanup tests locally, including the three new
POSIX spelling cases and real Windows link fixtures, with 100% statement
and 99.24% branch coverage. An independent review accepted the change and
ran 13 relevant cases. Two fresh package builds matched byte for byte.
Corrected engine identity is
`a1355a7f8698d1e19619f534cab600ff8c1a4edbdf3f6682169c6e6b8624bb31`.
The prior native receipts retain their recorded engine identity. The corrected
commit requires fresh CI confirmation. The publication receipt records that
result after the push.
