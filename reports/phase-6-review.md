# Phase 6 fresh review resolution

One fresh read-only whole-phase reviewer examined the uncommitted change against
base 6366ac2, the approved plan, source blueprint, ledger and real native evidence.
It reported no Critical or Minor issues and four Important findings.

1. Stale scenes could stamp current-request identity into telemetry. Fixed by
   emitting loaded session identity, asserting loaded scene/seed/actor/spawn
   identity in native EditMode, and comparing saved jobs with freshly compiled
   contracts. The actual wrong-digest/seed request passed before the fix and
   fails after it with native test exit 2, mapped to engine test failure 7.
2. Malformed telemetry could count as a detected mutant. Added scenario-specific
   structural validation for bounds, collision dimensions, baseline positions,
   events and unique entity identities. Four missing-field tests failed before
   the fix and pass now; valid native mutants still count as detected.
3. One moving enemy could mask frozen enemies. Match observations by semantic
   ID and require every declared enemy to move. The two-enemy negative/order
   test failed before the fix and passes now.
4. Optional unsupported features could be marked implemented. Derive status per
   feature and applicable evidence; unsupported options retain NOT_RUN. The
   optional-feature negative test passes, with mandatory gaps still preflight
   failures.

See [RED output](phase-6-evidence/review-red.txt),
[focused GREEN output](phase-6-evidence/review-green.txt),
[native RED](phase-6-evidence/identity-red.txt),
[native GREEN](phase-6-evidence/identity-green.txt), and the final full/native runs
in [the acceptance report](phase-6.md). No redundant second review was dispatched.

The reviewer declined aesthetic/manual, full profiling, hidden evaluation,
second-genre and future crash-recovery judgments. These remain separate gates;
the user subsequently completed the manual play review. No deferred minors.
