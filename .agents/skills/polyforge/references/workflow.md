# Working with PolyForge results

Current catalog capabilities: contract.capability.validate.v1,
contract.manifest.validate.v1, contract.scene.compile.v1 and plan.scene.v1.
They validate bounded JSON under the workspace and emit results on stdout,
without creating files or executing Blender/Unity.

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
