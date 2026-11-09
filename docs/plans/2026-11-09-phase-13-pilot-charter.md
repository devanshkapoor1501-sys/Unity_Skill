# Phase 13 equal-tool pilot charter — draft for approval

**Status: OWNER TERMS RECORDED / NOT RUN.** The
[machine-readable charter](../../reports/pilot-v7-charter.json) records the
proposal and the approval fields required by v7 §7.5.

## Objective and boundary

Measure whether PolyForge-assisted Codex improves one bounded Blender-to-Unity
asset workflow over Codex with equivalent tools and permissions. The result
applies only to this workflow and tested versions. It cannot establish broad
Blender/Unity expertise or satisfy Phase 11 release gates.

The intended user is a Blender/Unity asset creator who needs an editable model
and a verified Unity import. Freeze the request as a `task_spec`. The workflow
produces editable Blender source, a technical preview, FBX/LOD where applicable,
a managed Unity import, and geometry, axis, socket, reference, and provenance
evidence. Use disposable workspaces. Full games, photorealism, and general
sculpting are outside the trial scope.

## Authority record — must be completed before execution

| Required field | Approval record |
| --- | --- |
| Owner who authorizes this charter | Project owner in this chat |
| Approved start date and expiry/deadline | **PENDING** |
| Total focused-hour budget, including setup, failures, analysis and review | Up to 10 focused hours within seven calendar days |
| Separate reuse-check authorization and time cap, or explicitly declined | **PENDING** |
| Independent evaluator identity and organization | **PENDING** |
| Evaluator confirmation of task custody, rubric control and result signing | **PENDING** |
| Candidate commit and source identity to freeze | **PENDING** |
| Owner approval date and recorded approval reference | 2026-11-09 continuation after presentation of the v7 proposed trial terms |

The owner's go-ahead records the proposed Phase 13 cap and decision rules.
The trial dates are set after evaluator custody and tool parity are established.
The reuse check has a separate approval field and a proposed one-hour cap.

## Prerequisites and custody

Execution is blocked until every authority field is resolved and the evaluator
independently supplies, freezes, and retains the five unseen task briefs and
acceptance rubric. The development team must not author those held-out briefs,
choose the evaluator’s scores, or access task details before each scheduled
attempt. Record hashes and custody attestations without copying protected task
content into this repository.

Before the first attempt, freeze and record:

- Candidate commit, dirty-state check, source package/build identity, and tested
  Blender/Unity versions.
- The same Codex model/version, machine, operating system, Blender/Unity tools,
  MCP access, permissions, network policy, environment, and per-task resource
  limits for both arms. PolyForge availability is the only planned difference.
- Evaluator-selected order/randomization, pair mapping, attempt limits, time and
  token/cost accounting method, intervention definition, and outage handling.
- Rubric, defect severity, acceptance thresholds, coordinate/socket tolerances,
  and evaluator signature before task content is revealed.

Mark materially unequal tool or permission exposure NON_ATTRIBUTABLE. Retain
the affected attempt and mark the comparison INCONCLUSIVE if the evaluator’s
predeclared recovery cannot restore parity. Include failed, blocked, timed-out,
and interrupted attempts in the accounting.

## Trial arms and measurements

For each of five evaluator-selected task pairs, run two separate attempts using
the v7 arm mapping:

- **Arm C — equal-tool baseline:** general Codex with maintained Blender and
  Unity tools, without PolyForge.
- **Arm D — PolyForge-assisted:** the identical Codex setup with the same model,
  effort, hardware, installed tools, permissions, and budgets, with PolyForge
  added as the sole planned difference.

The evaluator supplies one unseen instance for each of these v7 task shapes.

1. Changed room modularity.
2. Noncentered independent sockets.
3. A rotated mechanical assembly.
4. A material/LOD variant.
5. A tricky asymmetric import or repair.

The independent evaluator scores outputs against the frozen rubric. Retain all
ten attempt records and report each pair plus aggregate counts. Record
acceptance, defect severity, elapsed time, setup, human fixes, retries, tokens
and cost when measurable, resource limits, original-project mutation checks,
artifact hashes, Unity import observations, and evaluator signoff. Use UNKNOWN
for unavailable measurements. Check requirements against the frozen brief,
include an injected-reflection negative, and obtain human visual review where
style affects acceptance.

The evaluator controls acceptance and critical-defect classification. The
candidate team may provide evidence but cannot grade its own output or relabel
an evaluator decision.

## Decision rule

The v7 source proposed these provisional management thresholds: accept at least
4/5 Arm D outputs; detect every critical coordinate/socket defect; accept no
fewer Arm D outputs than Arm C; and show either at least 20% lower median
end-to-end time or at least 30% fewer manual corrections, without reducing
quality. The owner accepted the proposed decision rules. The evaluator must
confirm the frozen rubric and measurement method before task reveal.

## Existing tooling readiness and boundary

The local preflight built the wheel and source distribution from a Git archive
of candidate `a77b33b`. Both package hashes match the build receipt. The
machine-readable charter records the package hashes and the observed Blender
5.2.2 and Unity 6000.6.3f1 binaries. The evaluator must still freeze the
candidate and verify the two trial environments.

The current `polyforge.benchmark` runner is not, by itself, a Phase 13 evaluator
or a protected-task harness. Its public suite loader accepts only `DEV_FIXTURE`
tasks, reads briefs from the suite's public `briefs/` directory, and labels
adapter/evaluator identity as declared rather than authenticated. The
`BaselineRunner` / `AcceptanceEvaluator` interfaces can structure development
measurements, but they do not establish task custody or evaluator independence.

Therefore do not put held-out briefs, reference answers, or evaluator secrets in
this repository or treat public-suite results as Phase 13. Before running, the
appointed evaluator and owner must choose a custody-compatible execution path:
the evaluator can operate a separate protected runner and return signed,
per-attempt decisions plus task/rubric hashes; or an explicitly reviewed,
access-controlled evaluator integration can be designed after its trust and
storage boundaries are specified. No code changes to accept protected task data
are justified until that boundary is agreed. Record the selected path and
evaluator signature here before task reveal.

| Evaluator execution/custody path | Approval |
| --- | --- |
| Selected protected execution path and evidence format | **PENDING** |
| Evaluator confirms task/rubric custody and independent scoring | **PENDING** |

| Decision-rule approval | Record |
| --- | --- |
| Accepted thresholds/rubric version | **PENDING** |
| Owner approval | Proposed rules accepted on 2026-11-09 |
| Evaluator approval | **PENDING** |

The terminal decision must be one of **CONTINUE**, **NARROW**, **STOP**, or
**INCONCLUSIVE**, with evaluator-signed rationale and all ten attempt outcomes.
A positive pilot only supports considering one separately scoped workstream; it
does not authorize Phases 14–18 automatically.

## Fresh-workspace reuse check

On calendar days 8–14 of the approved schedule, a different or reset operator
repeats one evaluator-approved task in a clean workspace with separate budget
approval. Record setup, elapsed time, output, manual fixes, reproducibility
costs, and evaluator disposition. Missing reuse evidence makes the pilot result
provisional. A passing reuse check is required for an unconditional CONTINUE.

## Stop rules

Stop the affected trial immediately on expired authority, budget/deadline
overrun, missing evaluator, tool-parity failure, unsafe original-project
mutation, or critical unrecovered regression. Preserve the failure evidence and
record the pilot **STOPPED** or **INCONCLUSIVE** under the predeclared evaluator
protocol. A stop does not permit increasing the cap or replacing a task without
owner and evaluator approval.

## Work sequence and evidence

1. **Approve charter.** Record the owner approval and evaluator confirmation in
   `reports/pilot-v7-charter.json` before any trial starts.
2. **Freeze trial:** record candidate/environment identities and evaluator-held
   task/rubric hashes; verify disposable workspaces and unchanged originals.
3. **Run paired attempts:** evaluator schedules five pairs; operators follow the
   frozen protocol; retain successes and failures without replaying for a better
   score.
4. **Evaluate and decide:** evaluator signs per-attempt results, aggregate
   measurements, exceptions, and CONTINUE/NARROW/STOP/INCONCLUSIVE decision.
5. **Reuse check, if authorized:** run the separately approved fresh-workspace
   check on days 8–14 and record its result independently.
6. **Close Phase 13.** Publish the paired ledger, independent evaluation
   record, exact environments, comparison report, follow-up reuse receipt, and
   `reports/phase-13-decision.md`. Bind public receipts by hash and reconcile
   every authorized attempt.

## Acceptance checklist

- [ ] Owner-approved budget, deadline, charter, and decision thresholds recorded.
- [ ] Independent evaluator appointed and confirms custody before execution.
- [ ] Five unseen paired briefs and rubric frozen under evaluator control.
- [ ] Tool/model/OS/version/permission/resource parity verified before attempts.
- [ ] All ten attempts retained and independently scored, including failures.
- [ ] Resource use, interventions, defects, unknowns, and exceptions reported.
- [ ] Reuse check disposition recorded. A PASS supports unconditional CONTINUE.
- [ ] Signed terminal decision and `reports/phase-13-decision.md` completed.

Trial execution remains **BLOCKED / NOT RUN** pending the evaluator, frozen
tasks and rubric, trial dates, and verified arm parity.
