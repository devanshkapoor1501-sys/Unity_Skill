---
name: polyforge
description: Discover and invoke the local PolyForge Blender-to-Unity capability engine, validate capability descriptors, and inspect structured results. Use for PolyForge workflows; check the catalog before attempting asset or game generation.
license: Apache-2.0
compatibility: Python 3.11+ and an installed polyforge CLI. Blender and Unity capabilities depend on their implementation phase and local toolchain.
---

# PolyForge

Discover available capabilities first. The Phase 7 catalog contains read-only
descriptor/manifest validation, scene-contract compilation/planning and five
Blender mesh recipes, managed static audit/export and native Unity static scenes.
S5 builds the bounded playable survival arena and runs independent public checks.
Claim playable output only after actual native build/tests and manual evidence.

Phase 1 also provides init, doctor, status and report. Doctor's --dry-run writes
nothing. An actual doctor run writes version-probe logs and state, including
blocked dependencies. It never proves Unity activation, rendering or gameplay.

Validate a managed manifest before planning. CLI compile-contract and plan publish
derived JSON and freeze the original brief unless --dry-run is supplied. Validation/planning catalog
capability execution is pure. Treat generator annotations as development intent;
BLOCKED/UNSUPPORTED features and missing evaluator evidence keep games PARTIAL.

Static mesh capabilities write editable .blend and checked geometry evidence.
Use build --workspace ROOT --through S3 for source, four-view audit and FBX;
audit --workspace ROOT --asset ID audits a registered saved source. Both accept
--dry-run with zero writes. S4 builds a managed URP project and executes native EditMode tests. The first
real S4 build requires --allow-package-downloads after user authorization; that
authorization persists for this workspace's Unity package resolution. Use
reconcile for observed bindings, diagnose for evidence-based issues, and repair
plan for a no-write native-binding patch preview. S5 runs seven behavioral scenarios, real keyboard input cases and two mutants.
Use --standalone on build for a Windows player build and smoke run.
verify and scenario run --suite core_gameplay rerun native checks.
Visual quality stays REVIEW
until separately reviewed; Blender FBX roundtrip is not Unity import evidence.
Never call source generation game acceptance.

```console
polyforge capability list --json
polyforge capability show contract.capability.validate.v1 --json
```

Invoke a catalog capability with a JSON input under its authorized workspace.
Use --dry-run to validate and describe planned writes without changing files.
Read [the result and trust rules](references/workflow.md) when interpreting
statuses, planning later stages, or handling a blocked operation.

Report operation_status, evaluated_test_status, and game_status separately.
A successful descriptor check is not gameplay evidence. Preserve failed and
unexecuted checks. Hidden evaluator fixtures stay outside the agent workspace.

Phase 7 adds one mechanical robot rig with slotted Idle/Walk actions, sampled
skin/socket checks, FBX clips and native Unity Animator playback. Use
animation.robot.rig.v1 for Blender-only animation; Unity integration requires an
existing managed arena and an approved candidate. Do not force a robot or Unity
project for a mesh-only or explanation request.

Workforce plan/run accepts explicit task_class, domain_tags and the exact original
brief. Inspect workforce roles first; use returned task/artifact IDs. Sequential
roles are the supported fallback. No verified native host delegation adapter is
available; different role IDs do not establish an independently controlled
evaluator. Resume verifies completion receipts and file hashes; stale outputs
invalidate success. See [workforce and animation rules](references/workflow.md)
for supported capabilities and authority boundaries.

Phase 7 integration does not qualify portable installation in multiple hosts.
Final Codex/Claude guides, host smoke tests and optional MCP remain Phase 10.
