# Unity reference decisions

Versioned curated summaries; DATA_ONLY. Installed APIs need fixed probes.

## unity.sprites

Supplied six-frame 128px strips go directly to Unity after license/pixel/source approval. Do not discover Blender for an existing-sprite task. Bake through Blender only when an approved editable source needs a sprite sequence. Native PPtr curve and physics tests remain separate from appearance approval.

Support: VERIFIED_EXECUTABLE; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: Existing sprites: native Unity route; approved 3D source: Blender bake then native import.

Contrasts: Six supplied transparent walk frames use DIRECT_SPRITES. A rendered turntable from a model needs a camera/bake workflow first.

[Authoritative source](https://docs.unity3d.com/Packages/com.unity.2d.sprite@1.0/manual/index.html). Locally authored summary, not copied vendor text.

## unity.animation

Animator suits stateful interactive character motion; Timeline suits authored cinematic sequencing. Current native robot integration tests Idle/Walk transitions and actual skin movement. Timeline authoring is reference-only and must not be substituted for requested gameplay control.

Support: VERIFIED_EXECUTABLE; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: Animator for responsive locomotion; Timeline for fixed directed scenes.

Contrasts: A controllable patrolling robot uses Animator. A fixed cutscene uses Timeline conceptually, not an implemented engine capability.

[Authoritative source](https://docs.unity3d.com/6000.0/Documentation/Manual/AnimationSection.html). Locally authored summary, not copied vendor text.

## unity.editor

Keep UnityEditor APIs in Editor assemblies and use native prefab/asset APIs. TypeCache.GetTypesDerivedFrom returns discovered derived types in the loaded Editor domain. A local documentation signature is VERSION_PROBED only; isolated execution and positive/negative assertions are required for a workflow claim.

Support: VERIFIED_EXECUTABLE; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: Headless registered build for repeatable imports; GUI only when its actual UI affordance is probed.

Contrasts: Discover a known ScriptableObject subtype in a scratch project. A runtime assembly cannot import UnityEditor.

[Authoritative source](https://docs.unity3d.com/6000.0/Documentation/ScriptReference/TypeCache.GetTypesDerivedFrom.html). Locally authored summary, not copied vendor text.

## unity.csharp

Use reviewed tested templates for supported mechanics. Novel generated C# requires a typed proposal, separate scratch project, compilation and independent behavior tests. Documentation and compiler success alone cannot establish gameplay or authorize arbitrary source execution.

Support: REFERENCE_ONLY; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: Tested template for known mechanics; reviewed isolated experiment for unfamiliar code.

Contrasts: Use existing Health for the arena. A novel networking component stays unsupported until independently tested.

[Authoritative source](https://docs.unity3d.com/6000.0/Documentation/Manual/creating-scripts.html). Locally authored summary, not copied vendor text.

## unity.physics

Use physics for interactions and contacts that must react to the environment; animation alone describes motion and cannot prove collision. The arena and 2D fixture have measured collision oracles. Arbitrary physics behaviors need explicit tolerances and independent tests.

Support: REFERENCE_ONLY; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: Physics for responsive contacts; animation for authored motion without collision claims.

Contrasts: A moving sprite stopped by a wall needs Rigidbody2D checks. A decorative waving prop may use animation without a contact mechanic.

[Authoritative source](https://docs.unity3d.com/6000.0/Documentation/Manual/PhysicsSection.html). Locally authored summary, not copied vendor text.

## unity.ai

Current enemy patrol is a bounded fixture. NavMesh planning, behavior trees and general NPC reasoning are reference-only. Choose a simple deterministic patrol for its known requirement; use pathfinding only when navigability is actually modeled and tested.

Support: REFERENCE_ONLY; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: Waypoint patrol for bounded paths; NavMesh for obstacle-aware routing after qualification.

Contrasts: Known arena patrol is tested. A maze-solving creature needs new navigation and stuck-agent negative tests.

[Authoritative source](https://docs.unity3d.com/6000.0/Documentation/Manual/nav-NavigationSystem.html). Locally authored summary, not copied vendor text.

## unity.ui

The arena HUD displays measured state. General UI Toolkit or uGUI authoring remains reference-only. Choose the UI system for target/runtime needs, verify bindings and accessibility, and test state changes rather than accepting a screenshot.

Support: REFERENCE_ONLY; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: Existing HUD for the fixture; qualified UI Toolkit/uGUI workflow for a new interface.

Contrasts: Health text reflects real health. A responsive inventory menu needs separate inputs and UI tests.

[Authoritative source](https://docs.unity3d.com/6000.0/Documentation/Manual/UIElements.html). Locally authored summary, not copied vendor text.

## unity.shaders

Basic URP Lit color, metallic and roughness mapping is implemented. Shader Graph enables custom visual logic but needs its own version/package, render and material-transfer proof. Complex procedural graphs do not round-trip through FBX by implication.

Support: REFERENCE_ONLY; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"unity": ["6000.6.3f1"]}.

Decision: URP Lit for bounded standard materials; Shader Graph for custom effects after explicit qualification.

Contrasts: Use Lit for a colored crate. A dissolving hologram requires unsupported shader authoring and actual render tests.

[Authoritative source](https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@17.0/manual/lit-shader.html). Locally authored summary, not copied vendor text.

## Role playbook

Unity integration: inventory unity.scene.static.v1, animation.robot.unity.v1, sprite.unity.strip.v1 and unity.game.arena.v1. Consume approved sealed source; produce native GUID/local-ID bindings, source hashes, exact XML/telemetry and editable scenes. Serialize project writes; keep Editor APIs out of runtime. Missing license/tool/package or headless API support stays BLOCKED; unprobed GUI stays UNKNOWN.

[Architecture and package applicability](architecture-packages.md).
