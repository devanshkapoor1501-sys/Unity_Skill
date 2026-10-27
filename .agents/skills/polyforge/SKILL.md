---
name: polyforge
description: Discover and invoke the local PolyForge Blender-to-Unity capability engine, validate capability descriptors, and inspect structured results. Use for PolyForge workflows; check the catalog before attempting asset or game generation.
license: Apache-2.0
compatibility: Python 3.11+ and an installed polyforge CLI. Blender and Unity capabilities depend on their implementation phase and local toolchain.
---

# PolyForge

Discover available capabilities first. The Phase 3 catalog contains read-only
descriptor/manifest validation, scene-contract compilation/planning and five
Blender mesh recipes. Unity/game-generation commands are future
interfaces and return NOT_RUN with a nonzero exit; do not substitute invented
tool output or claim a game exists.

Phase 1 also provides init, doctor, status and report. Doctor's --dry-run writes
nothing. An actual doctor run writes version-probe logs and state, including
blocked dependencies. It never proves Unity activation, rendering or gameplay.

Validate a managed manifest before planning. CLI compile-contract and plan publish
derived JSON and freeze the original brief unless --dry-run is supplied. Catalog
capability execution is pure. Treat generator annotations as development intent;
BLOCKED/UNSUPPORTED features and missing evaluator evidence keep games PARTIAL.

Static mesh capabilities write editable .blend and checked geometry evidence.
Use build --workspace ROOT --through S2 for managed assets, with --dry-run first
when previewing. S3–S5 are unavailable. Never call source generation game acceptance.

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
