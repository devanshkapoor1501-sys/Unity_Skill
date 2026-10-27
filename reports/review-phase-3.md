# Phase 3 independent review

A fresh-context read-only reviewer inspected the working tree against Phase 2
commit 026a268. Scope was static recipe contracts, Blender worker/adapter,
managed S0–S2 builds, actual source/geometry evidence and phase tests. Unity,
rendering/export and hidden game acceptance were outside this phase.

Required findings and fixes:

1. Effective overrides were validated after publication. A manifest assigning
   17 materials fits the manifest schema but exceeds a recipe's 16-material
   bound; dry run falsely passed and normal execution could write before exit 2.
   Every effective recipe is now prepared/validated before writes. The regression
   checks both normal and dry execution, including complete source hashes.
   Configuration is likewise validated before publication.
2. Pivot evidence was constant. A generated root shifted 10 m retained correct
   dimensions and falsely reported zero pivot. Metrics now read the actual saved
   root transform and scene unit scale. Validation enforces both measured pivot
   and centered X/Y/base-Z bounds. Real probes corrupt root position, mesh offset
   and unit scale independently and must fail.
3. Logical output used the user-input 1 MiB reader. A valid 128-sphere recipe
   produces 16,384 polygons and over 3 MiB of logical data inside the declared
   module/polygon budgets. Output reads now use an explicit bounded 32 MiB limit;
   input reads retain their 1 MiB default. A real 128-sphere regression failed
   before the fix and passed afterward.

All findings were reproduced before fixes. Focused regressions passed afterward;
the full offline and application gates are recorded in phase-3.md. No required
finding is deferred. The reviewer did not edit files or rerun the full suite.

Additional observed integration failures were corrected without lowering gates:
Blender's LTS suffix is retained as a label while numeric version is checked;
unused editable palette resources survive reload; sphere face order is normalized
by oriented coordinates/UVs; missing UV data produces a diagnostic instead of a
hashing crash. Nonfinite/malformed producer output maps to contract failure 6.
