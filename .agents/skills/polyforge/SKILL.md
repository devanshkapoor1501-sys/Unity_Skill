---
name: polyforge
description: Discover and invoke the local PolyForge Blender-to-Unity capability engine, validate capability descriptors, and inspect structured results. Use for PolyForge workflows; check the catalog before attempting asset or game generation.
license: Apache-2.0
compatibility: Python 3.11+ and an installed polyforge CLI. Blender and Unity capabilities depend on their implementation phase and local toolchain.
---

# PolyForge

Discover available capabilities first. The Phase 0 catalog contains only the
read-only capability-descriptor validator. Game-generation commands are future
interfaces and return NOT_RUN with a nonzero exit; do not substitute invented
tool output or claim a game exists.

Phase 1 also provides init, doctor, status and report. Doctor's --dry-run writes
nothing. An actual doctor run writes version-probe logs and state, including
blocked dependencies. It never proves Unity activation, rendering or gameplay.

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
