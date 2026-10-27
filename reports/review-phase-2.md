# Phase 2 independent review

Reviewed the Phase 2 working tree against Phase 1 commit 36b77c0. A fresh-context
read-only reviewer inspected the compiler, input policies, semantic contracts,
planner/cache and phase tests. Application workers, external holdouts and runtime
acceptance were explicitly outside this phase. No reviewer edited files.

Two required findings were returned:

1. P1: compile publication could replace an input named scene_contract.json, or
   a recipe/brief/texture occupying a generated or metadata destination. Preflight
   now checks source/output overlap, including case-insensitive spellings and
   existing same-file aliases, before creating the planning lock. The regression
   covers manifest, recipe, texture, brief and lock collisions, normal and dry
   execution, checking exit 2 and complete byte inventory preservation.
2. P2: material edits did not invalidate sprite bakes. Bake task dependencies now
   include the owning asset's appearance tasks. A regression changes roughness,
   verifies the bake digest changes, and verifies mesh hashes remain unchanged.

Both regressions were observed failing before their fixes and passing afterward.
Other boundary checks added during implementation reject malformed/vacuous handoff
contracts, propagate rig edits to baked sprites, and bind operation input identity
to recipes, referenced files and the original brief as well as the manifest.
An actual Windows source-range regression also demonstrated that default newline
conversion shifted initialized annotation offsets. Init now writes LF explicitly;
every compiled source excerpt matches the bundled original brief.

No required review finding is deferred. Full post-fix acceptance results and
exact command records are in phase-2.md and phase-2-evidence/.
