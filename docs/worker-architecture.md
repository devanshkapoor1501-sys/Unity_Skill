# Worker architecture and execution evidence

The original v5.1 blueprint Chapters 16–18 define a task-selected workforce over
one capability engine. The coordinator freezes the original brief and acceptance
requirements, checks installed versions and supported capabilities, then builds
a dependency graph containing only the roles required for that request.

## Ownership and handoffs

Planning roles produce intent, asset/mechanic specifications and dependency
decisions. Producers receive isolated artifact ownership and a permitted subset
of registered capabilities. Each candidate binds exact source/export bytes,
semantic identities, license/provenance and its original task. Inspectors read
those bytes and write review evidence; they cannot silently edit the candidate
or approve their own production. Refinement creates a new version with scoped
requested changes. A supervisor consolidates promotion decisions without
overriding independent test failures.

Unity integration is serialized under the physical project lock. Separate assets
or read-only snapshot inspections may be parallel-safe, but shared source and
project writes require exclusive ownership. The native process runner owns its
descendant processes, enforces configured time/output/memory limits, and accepts
cancellation. Durable job leases, intents and completion receipts permit bounded
resume without duplicating scene objects or relabeling old provenance.

Jobs use versioned JSON records. Their identity includes original request,
implementation/tool/input digests, role/capability, dependencies, authorized
paths, selected knowledge and probe context, budgets, required resources and
expected evidence. Probe refresh does not rewrite a stored plan's history.
Operation intents separately bind the actual dispatched inputs. Unknown resource
requirements fail admission; live RAM/disk floors and deadlines can cancel an
operation and prevent a passing result even if an executor ignores cancellation.

## Modes and present boundary

The current registered engine supports `LOCAL_SINGLE_ROLE` and
`LOCAL_MULTIROLE_SEQUENTIAL`. These use the same technical validation and return
explicit role lineage. They do not establish separate model identities, genuine
parallel host agents or an independently controlled evaluator. Host-native
delegation requires a tested adapter, observed host capability and actual
execution evidence. Missing delegation is an availability result, never a reason
to invent parallel timings.

Measured admission currently chooses one sequential CPU worker, one Unity writer
and no engine-owned model workers. GPU/VRAM device capacity is read-only metadata;
it does not qualify GPU execution or adaptive render quality. Unknown or
unsupported execution modes remain denied. No role, document, reference or model
output may grant shell/network permissions or broaden an authorized path.

## Quality authorities

L1 technical checks cover finite geometry, bindings, import, compile, behavior,
mutations, resources and artifact integrity. L2 visual/motion inspection uses
actual images or animations against the declared style/quality brief; absent
required visual evidence stays REVIEW. L3 independent acceptance derives from
the original brief under a separately controlled evaluator and can veto any
candidate or supervisor decision. Same-host reviewers and public development
oracles do not satisfy hidden-evaluator ownership.

Worker PASS means the bounded operation completed. Candidate APPROVED means the
applicable review gate passed. GAME ACCEPTED additionally requires independent
executed PASS for every mandatory original-brief requirement. FAIL, BLOCKED,
NOT_RUN or required REVIEW remains a visible unmet requirement.

## Recovery and comparison

Failures retain diagnostics and actual output before a bounded repair is
proposed. Re-run the affected dependency subtree and required regressions; when
repair cannot commit safely, restore the transaction and verify native semantics.
Rollback failure is explicit and blocks reuse. Preserve original user projects:
static inspection never launches Unity, and experimental execution requires an
approved disposable workspace with truthful isolation classification.

Benchmark single/sequential/concurrent execution only when each mode actually
runs. Report model/tool/hardware/budget parity, installation versus warm costs,
time, tokens/cost where measured, failures and interventions. Inspector-off runs
are evaluation ablations; they never bypass production acceptance requirements.
No unavailable host/evaluator or unmeasured cost may be filled with an assumed
zero, successful run or claimed efficiency gain.

See [worker workflow](workforce.md), [approved sequence](implementation-plan.md)
and [Phase 0–10 audit](../reports/phases-0-10-audit.md). Phase 11 qualification
and later expertise retain their own evidence and release gates.
