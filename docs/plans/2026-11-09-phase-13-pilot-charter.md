# Phase 13 equal-tool pilot charter — draft for approval

**Status: PREPARED / NOT APPROVED / NOT RUN.** This document makes the v7
Phase 13 proposal reviewable. It does not approve its proposed budget or
thresholds, appoint an evaluator, create held-out tasks, or authorize trial
execution. Phase 11 remains at its existing status and is outside this charter.

## Objective and boundary

Measure whether PolyForge-assisted Codex improves one bounded Blender-to-Unity
asset workflow over Codex with equivalent tools and permissions. The result
applies only to this workflow and tested versions. It cannot establish broad
Blender/Unity expertise or satisfy Phase 11 release gates.

The workflow under study is: interpret an evaluator-owned brief; create editable
Blender source; produce a technical preview and FBX/LOD when applicable; import
into a managed Unity project; and provide geometry, axis, socket, reference, and
provenance evidence. Use disposable workspaces. Do not inspect or modify an
original user project.

## Authority record — must be completed before execution

| Required field | Approval record |
| --- | --- |
| Owner who authorizes this charter | **PENDING** |
| Approved start date and expiry/deadline | **PENDING** |
| Total focused-hour budget, including setup, failures, analysis and review | **PENDING** |
| Separate reuse-check authorization and time cap, or explicitly declined | **PENDING** |
| Independent evaluator identity and organization | **PENDING** |
| Evaluator confirmation of task custody, rubric control and result signing | **PENDING** |
| Candidate commit and source identity to freeze | **PENDING** |
| Owner approval date and recorded approval reference | **PENDING** |

The source blueprint proposed 16 focused hours over seven calendar days, with
up to ten hours for Phase 13 after up to six hours for Phase 12, plus a separately
preapproved one-hour reuse check on days 8–14. Those figures are **proposals**;
they are not the budget or deadline until the owner enters and approves concrete
values above. Phase 12 is technically complete, but its historical elapsed time
does not silently authorize any Phase 13 allocation.

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

Any material parity break invalidates the affected pair; retain the attempt and
mark the result INCONCLUSIVE unless the evaluator’s predeclared protocol defines
a valid recovery. Never discard a failed, blocked, timed-out, or interrupted
attempt from the denominator.

## Trial arms and measurements

For each of five evaluator-selected task pairs, run two separate attempts using
the v7 arm mapping:

- **Arm C — equal-tool baseline:** general Codex with maintained Blender and
  Unity tools, without PolyForge.
- **Arm D — PolyForge-assisted:** the identical Codex setup with the same model,
  effort, hardware, installed tools, permissions, and budgets, with PolyForge
  added as the sole planned difference.

The independent evaluator scores outputs against the frozen rubric. Retain all
ten attempt records and report each pair plus aggregate counts. Capture, where
available and allowed: acceptance, defect severity, end-to-end elapsed time,
human interventions/manual corrections, token and monetary cost, native test
results, source/output hashes, versions, logs, and setup overhead. Unknown cost
or resource values stay UNKNOWN; do not infer savings from elapsed time alone.

The evaluator controls acceptance and critical-defect classification. The
candidate team may provide evidence but cannot grade its own output or relabel
an evaluator decision.

## Decision rule

The v7 source proposed these provisional management thresholds: accept at least
4/5 Arm D outputs; detect every critical coordinate/socket defect; accept no
fewer Arm D outputs than Arm C; and show either at least 20% lower median
end-to-end time or at least 30% fewer manual corrections, without reducing
quality. They are not approved statistical claims or permission to execute.
The owner and evaluator must either approve these exact decision rules or enter
replacement rules and rationale here before task reveal.

## Existing tooling readiness and boundary

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
| Owner approval | **PENDING** |
| Evaluator approval | **PENDING** |

The terminal decision must be one of **CONTINUE**, **NARROW**, **STOP**, or
**INCONCLUSIVE**, with evaluator-signed rationale and all ten attempt outcomes.
A positive pilot only supports considering one separately scoped workstream; it
does not authorize Phases 14–18 automatically.

## Optional fresh-workspace reuse check

On calendar days 8–14 after the paired pilot, a fresh/reset operator may repeat
one evaluator-approved task in a clean workspace only if the owner separately
authorizes its budget and date window above. Record install/setup, elapsed time,
output, manual fixes, and evaluator disposition. If not separately approved or
not run, report **NOT AUTHORIZED** or **NOT RUN**, respectively; do not fold a
later unscheduled attempt into the pilot.

## Stop rules

Stop the affected trial immediately on expired authority, budget/deadline
overrun, missing evaluator, tool-parity failure, unsafe original-project
mutation, or critical unrecovered regression. Preserve the failure evidence and
record the pilot **STOPPED** or **INCONCLUSIVE** under the predeclared evaluator
protocol. A stop does not permit increasing the cap or replacing a task without
owner and evaluator approval.

## Work sequence and evidence

1. **Approve charter:** owner fills authority and decision tables; evaluator
   confirms custody, task/rubric control, parity setup, and reporting method.
2. **Freeze trial:** record candidate/environment identities and evaluator-held
   task/rubric hashes; verify disposable workspaces and unchanged originals.
3. **Run paired attempts:** evaluator schedules five pairs; operators follow the
   frozen protocol; retain successes and failures without replaying for a better
   score.
4. **Evaluate and decide:** evaluator signs per-attempt results, aggregate
   measurements, exceptions, and CONTINUE/NARROW/STOP/INCONCLUSIVE decision.
5. **Reuse check, if authorized:** run the separately approved fresh-workspace
   check on days 8–14 and record its result independently.
6. **Close Phase 13:** write `reports/phase-13.md`, bind public receipts by
   hashes, reconcile every authorized attempt, state unknowns, and stop. Any
   next phase requires its own scoped approval.

## Acceptance checklist

- [ ] Owner-approved budget, deadline, charter, and decision thresholds recorded.
- [ ] Independent evaluator appointed and confirms custody before execution.
- [ ] Five unseen paired briefs and rubric frozen under evaluator control.
- [ ] Tool/model/OS/version/permission/resource parity verified before attempts.
- [ ] All ten attempts retained and independently scored, including failures.
- [ ] Resource use, interventions, defects, unknowns, and exceptions reported.
- [ ] Optional reuse check separately authorized or explicitly NOT AUTHORIZED.
- [ ] Signed terminal decision and `reports/phase-13.md` completed.

Until these prerequisites are met, Phase 13 status remains **NOT AUTHORIZED / NOT RUN**.
