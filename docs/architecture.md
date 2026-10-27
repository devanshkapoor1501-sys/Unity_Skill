# Architecture and capability-first decision

PolyForge provides executable reusable infrastructure, not a claim that prompts
or existing Blender/Unity MCP tools cannot construct the same software.

## ADR-001: local capability engine

Use a deterministic Python kernel with versioned JSON contracts, subprocess
adapters, and a separate native Unity Editor/runtime package. A portable Agent
Skill and optional stdio MCP bridge call the same kernel. No core operation
requires model credentials, a central server, or arbitrary model-generated code.
Generic editor control is existing prior art; reusable contracts, invariants,
independent behavioral verification, and recoverable repairs are release-critical.

## Data and ownership

Frozen brief -> feature contracts -> validated manifest -> scene contract ->
dependency plan -> Blender outputs -> Unity native import -> actual behavior
evidence -> independently owned acceptance -> human/machine report.

The manifest is user-owned design. Scene contracts, run state, and artifact
registries are derived. Repairs cannot silently weaken original requirements.
Stages S0-S5 mean precheck, plan, model, audit/export, Unity build, verify.
Semantic IDs, hashes, seeds, tool versions, and explicit tolerances connect stages.

## Phase 0 interfaces

`Capability.execute(inputs, RunContext) -> Result` is implemented by a read-only
capability-descriptor validator. Context includes workspace, seed, time/output
budgets, retry limit, transaction ID, artifact registry, and lock path. Worker
locking, structured event logging, cancellation, and OS isolation arrive in Phase 1.
Network permission and claims of isolation are denied in this initial context.

`BaselineRunner.run(task, arm, seed)` and `AcceptanceEvaluator.grade(request)`
define independent interfaces. The unavailable evaluator returns BLOCKED/3;
it never assigns a passing grade. No benchmark execution is implemented yet.

## Versions and compatibility

Engine package: 0.0.1. Public contract/schema major: 1. Capability IDs end in a
versioned namespace such as `.v1`; descriptor versions use MAJOR.MINOR.PATCH.
Breaking changes require a new contract major and explicit reversible migration;
there are no previous persisted contracts to migrate in Phase 0.

Local application targets established during planning: Blender 5.2.2 LTS and
Unity 6000.6.3f1. Installed template metadata declares URP 17.6.0, Input System
1.19.0, and Test Framework 1.8.0. Installation presence is not integration proof.
Original blueprint baseline versions are not silently advertised as tested.

## Deferred capability claims

No asset-generation worker, Unity importer, gameplay, animation, sprite baker,
repair executor, sandbox, profiler, MCP server, or benchmark runner is implemented.
Registered future CLI commands fail explicitly with NOT_RUN/5.

## Phase 1 runtime

Config is bounded TOML with explicit executable overrides and default-denied
network/outside-root/untrusted settings. Doctor prefers installed application
roots over PATH (the generic Unity CLI can be unrelated to the Editor), probes
versions without opening projects, records limits/hardware/provenance, and writes
a structured report even when tools are missing. License and rendering readiness
remain independently NOT_RUN. Optional project checks are static known-file reads.

Each run has a durable append-only sequence of complete state snapshots plus an
atomic state.json cache. A killed cache write is recovered from events; incomplete
final event bytes are ignored until explicit recovery. Stage success requires
real nonempty evidence. Attempts, ownership locks and crash recovery are bounded.
State recovery is a library operation; CLI producer retry scheduling remains
unavailable until actual build stages exist. Manifest validation is Phase 2.

Trusted workers use allowlisted binaries and owned process trees. Windows launches
suspend before job assignment and resume only after limits are set. Project locks
live at one physical project path so nested workspace roots cannot admit two Unity
workers. These resource/cleanup controls do not claim filesystem/network isolation.

API references: [Python subprocess](https://docs.python.org/3.11/library/subprocess.html),
[Windows Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects),
[Unity Editor arguments](https://docs.unity3d.com/6000.6/Documentation/Manual/EditorCommandLineArguments.html).
