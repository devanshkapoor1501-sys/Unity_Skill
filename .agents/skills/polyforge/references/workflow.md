# Working with PolyForge results

Current catalog capabilities: contract.capability.validate.v1,
contract.manifest.validate.v1, contract.scene.compile.v1 and plan.scene.v1.
They validate bounded JSON under the workspace and emit results on stdout,
without creating files or executing Blender/Unity.

The catalog also exposes mesh.robot.modular.v1, mesh.props.crate.v1,
mesh.architecture.wall.v1, mesh.architecture.doorway.v1 and mesh.environment.tile.v1.
These accept recipe requests with schema_version, asset_id and parameters.size_m
in Unity XYZ meters. They require Blender 5.2.2 and write isolated run evidence;
--dry-run validates without launching or writing. Source .blend, logical geometry
and metrics must all validate before PASS. These operations are TRUSTED_LOCAL.
Managed build supports S0 precheck, S1 contracts, S2 generation and S3 audit/export.
S4 performs native static Unity integration. S5 builds the bounded playable arena
and verifies seven behavior scenarios, actual W/R input and two smoke mutants. Resume scheduling remains unavailable pending managed retry work.

audit.static.multiview.v1 accepts schema_version and asset_id, locating the latest
registered successful source and checking its hash before writes. audit CLI exposes
the same operation. Missing/changed source fails; an incomplete export does not
hide earlier registered sources. Four PNGs, FBX, material/handoff/roundtrip reports,
artifact hashes and review.html are written in a fresh run. Original source bytes
are preserved. Visual artistic quality is REVIEW and actual Unity import NOT_RUN.

CLI validate is read-only. CLI compile-contract --manifest FILE and plan
--workspace ROOT normally publish scene_contract.json, feature_contract.json,
requirement_coverage.json and (for plan) plan.json. Both accept --dry-run with
zero writes. Publication freezes the exact original brief bytes and records an
artifact inventory and PREPARING/COMMITTED marker. A changed frozen brief is
invalid input; use a new workspace. No amendment workflow is implemented yet.
Generated scenarios and feature intent never substitute for evaluator acceptance.

Phase 1 CLI init creates a new managed workspace and refuses overwrites. Doctor
writes a precheck report and run journal with version-probe logs. Status/report
read durable run facts, separating their own PASS from failed/not-run stages.
The generic process runner is not an arbitrary-code CLI capability.

PASS/0 means an operation ran successfully. FAIL, BLOCKED, NOT_RUN, and REVIEW
never mean a game was accepted. Game status remains PARTIAL until every mandatory
feature has independently executed passing evidence. Missing dependencies return
BLOCKED/3, policy denial BLOCKED/4, unimplemented commands NOT_RUN/5.

The context defaults to no network and TRUSTED_LOCAL with isolation_verified=false.
It cannot contain malicious plugins or source. Untrusted execution requests are
denied until OS-enforced isolation is implemented and independently tested.

For later phases: inspect available tools, validate the manifest, review the plan,
run eligible stages, examine artifacts/tests, and propose only bounded managed
repairs. Original projects must not open in Unity during read-only inspection.
Do not enable downloads, third-party plugins, or external services implicitly.

S4 is now implemented for new managed URP projects. It compiles, builds native
static prefabs/scenes and executes seventeen required EditMode cases. Public test
status remains separate from gameplay. S5 executes separate native PlayMode
and independent public telemetry oracles; game acceptance still stays PARTIAL. Native missing-reference
and scale repairs are bounded to frozen source identity and managed outputs.
Full cross-application rollback/resume remains Phase 9. Explicit Unity package
download approval is retained per workspace; OS activation profile access is
required, and trusted Unity licensing services may write profile state. No
sandbox or egress-containment claim follows from this development profile.

S5 optional --standalone produces a local Windows executable and owned smoke run.
Manual play review, full rendered performance qualification and external hidden
evaluation are distinct gates. Invalid/malformed mutant evidence never counts
as a detected regression. Reject stale loaded scene identities and saved jobs.

Phase 7 adds animation.robot.rig.v1, artifact.candidate.inspect.v1 and
animation.robot.unity.v1. Rig input is a robot recipe request; inspection uses
candidate_file/task_file, and import uses candidate_file/review_file/production_file
within the authorized workspace. Import requires approval derived from inspection
of the exact sealed candidate and original request. A caller-supplied label alone
cannot grant approval. The approved FBX hash must match the source imported.

Workforce task.json carries explicit task_class, domain_tags, feature_ids, brief
and supported capability/input. Save exact brief text in a workspace file for
workforce plan --brief FILE. Use --dry-run to validate without writes, then the
returned plan path for workforce run. Blender-only ANIMATE omits Unity; supported
BUILD_GAME keeps S0–S5. Ambiguous intent requires host/user interpretation;
unsupported inspection/repair/mechanic execution remains REVIEW/NOT_RUN.

Workforce execution is LOCAL_MULTIROLE_SEQUENTIAL or the comparison
LOCAL_SINGLE_ROLE. Native subagent delegation is UNAVAILABLE. The same-host
technical inspector checks actual samples and imported skin/transition behavior;
it has no protected evaluator authority. Hidden evaluation stays NOT_RUN.
Leases, cancellation and completion receipts guard native operations; resume
rejects changed code/inputs/output hashes. These guards do not imply full Phase 9
rollback or operating-system isolation. Use workforce status/review for evidence
and workforce cancel for an active job; cancelled work cannot publish a result.
