# Windows CI short-path correction

Original failed run: [40540296484](https://github.com/devanshkapoor1501-sys/Unity_Skill/actions/runs/40540296484),
commit 71b25a0. Windows Python 3.12 failed 27 tests; Python 3.11 was cancelled by
the fail-fast matrix. Ubuntu Python 3.12 passed. Raw failing logs are retained in
ci-windows-evidence/original-failure.txt.

## Cause and correction

GitHub's Windows TEMP uses an NTFS short name such as C:/Users/RUNNER~1, while
Path.resolve expands it to C:/Users/runneradmin. WorkspacePolicy canonicalized
the root but compared input paths lexically before expanding their aliases.
Legitimate files inside the authorized workspace were incorrectly denied.
Coverage fell because these tests could not reach contract validation.

The policy now checks every original absolute component for ambiguous Windows
names, symlinks, junctions and reparse points before resolving aliases. Canonical
containment is then enforced against the canonical workspace root. Parent
traversal and outside paths remain denied. This also refuses a junction outside
the workspace that points back inside. No isolation or path requirement is relaxed.

Two new tests use actual GetShortPathNameW spellings to reproduce the original
failure, including CLI initialization and manifest validation. Both were observed
failing before the correction and passing afterward. On other platforms they
exercise ordinary canonical paths. Existing path assertions now compare canonical
physical paths, including one Phase 4 saved-source assertion reproduced with a
short TEMP directory. Junction tests still create and reject actual links.

The workflow sets fail-fast=false, preserving results from all three matrix jobs
instead of cancelling another platform after a failure. No job, test, platform
or coverage threshold is removed. The separate Blender gates and Phase 4 evidence
remain unchanged.

## Verification and publication

Local verification records exact argv, exit codes, logs, XML and coverage in
ci-windows-evidence/verification.json and ci-windows-short-temp-final-evidence/verification.json.
The latter full run uses a real short TEMP path to reproduce hosted Windows
behavior. Independent read-only review found no actionable security regression.
Both complete local suites passed: 120 tests, no skips, with the nine separate
Blender integration tests deliberately deselected as in hosted offline CI.
Security/contracts/recipe coverage is 95.96%, above the unchanged 90% gate.
Ruff, formatting, strict Windows/Linux-target typing, command documentation,
dependency checks and package builds also pass.
The initial short-TEMP run is also retained in ci-windows-short-temp-evidence/;
it exposed the saved-source test's unnormalized path assertion, which was then
reproduced and corrected. Coverage requirements remain unchanged.

Phase 4 is preserved as commit e35da8a. The correction is committed separately,
then both are pushed without rewriting existing history. Final remote commit IDs
and actual GitHub Actions outcomes are verified after the push; local passing
tests alone do not establish a successful hosted check.
