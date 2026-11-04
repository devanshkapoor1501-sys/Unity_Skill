# Public benchmark execution and limits

The frozen public suite contains twelve development tasks across assets,
animation/import, mechanics, repair and complete 2D game work. The schema also
supports complete 3D games. This suite does not contain evaluator-owned hidden
tasks or satisfy the required expanded release game sample by itself.

```console
polyforge benchmark run --suite benchmark_core --arm A --output results/A --dry-run --json
polyforge benchmark run --suite benchmark_core --arm A --output results/A --json
polyforge benchmark report --run results/A --format human
polyforge benchmark report --run results/A --format json
polyforge benchmark report --run results/A --format html
```

Choose a fresh output path; existing evidence is never overwritten. Repeat for
arms B, C and D. The declared five repetitions produce sixty planned cases per
arm, using default seeds 42–46. The trusted Python interface accepts an explicit
unique seed tuple of exactly the declared length. A differently sized schedule
is rejected before writes; exploratory suites must declare their actual size.

These commands currently record BLOCKED availability rows because no model/host
runner or independently controlled evaluator is configured. They do not execute
the same engine under four invented model labels. A dry run writes nothing.
Reporting returns escaped offline HTML or JSON as stdout and preserves measured,
failed, censored and unexecuted observations separately. Unknown cost, tokens,
GPU usage and process metrics remain unknown.

Adapters are trusted injected Python implementations of `BaselineRunner` and
`AcceptanceEvaluator`; arbitrary plugin source cannot be loaded through a suite.
Each adapter must enforce its process deadlines. The harness additionally checks
observed usage and end-to-end wall time, including grading. Metadata and evaluator
identities are declarations, without provider or external-ownership authentication.

The ledger checkpoints started/finished attempts and immutable identities.
Committed-prefix tampering fails validation. An otherwise complete uncommitted
suffix forces REVIEW and retains the prior censored attempt; it earns no success.
Complete-game acceptance rates use only executed eligible complete-game attempts,
including failures and timeouts. Other task categories have separate denominators.

C and D require identical generic tool inventories, versions and permissions.
Parity mismatches are NON_ATTRIBUTABLE. Neither missing trials nor a passing
development scorer establishes superiority, stable release qualification or
unseen transfer. Actual host concurrency, inspector ablations and independently
controlled holdouts need their own executed evidence.
