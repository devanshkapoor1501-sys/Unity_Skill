# Blender reference decisions

Versioned curated summaries; DATA_ONLY. Installed APIs need fixed probes.

## blender.modeling

Procedural recipes suit repeated parameterized objects; manual mesh editing suits one-off topology. Geometry Nodes supports reusable non-destructive geometry graphs; the engine currently executes five explicit primitive recipes. Arbitrary topology and sculpt remain reference-only.

Support: VERIFIED_EXECUTABLE; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"blender": ["5.2.2"]}.

Decision: Geometry Nodes for reusable adjustable patterns; manual mesh for unique silhouette/topology.

Contrasts: Repeated floor tiles: use the tested tile recipe. One-off carved creature: manual specialist and review, no automatic recipe substitution.

[Authoritative source](https://docs.blender.org/manual/en/5.0/modeling/index.html). Locally authored summary, not copied vendor text.

## blender.uv-pbr

Generated UV0 and simple palette sidecars serve tested primitive assets. Image textures, baking and PBR channel authoring need explicit provenance, color-space mapping and future workflow qualification. A UV tutorial does not make arbitrary topology supported.

Support: VERIFIED_EXECUTABLE; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"blender": ["5.2.2"]}.

Decision: Simple color/metallic/roughness for current assets; authored PBR textures require separate qualified work.

Contrasts: Adjust a crate palette using scoped refinement. A hand-painted skin atlas needs UV/material specialist review.

[Authoritative source](https://docs.blender.org/manual/en/5.0/modeling/meshes/uv/index.html). Locally authored summary, not copied vendor text.

## blender.animation

Use an armature for deforming articulated motion; bake when a constrained target needs sampled transforms. The current mechanical robot has slotted Idle/Walk actions. Human, facial and arbitrary retargeting remain unqualified. Probe action slots and operator context before version-sensitive changes.

Support: VERIFIED_EXECUTABLE; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"blender": ["5.2.2"]}.

Decision: Rig for reusable deformation; baked frames for a fixed sprite sequence.

Contrasts: Animate the supported robot with Idle/Walk. A quadruped needs a separate rig family and negative deformation fixtures.

[Authoritative source](https://docs.blender.org/api/5.0/bpy.types.Action.html). Locally authored summary, not copied vendor text.

## blender.context

Prefer Blender data APIs for deterministic headless edits. Operators require an appropriate active object, mode and context; poll before calling. Mesh.validate checks and repairs invalid mesh data; fixed positive and degenerate cases must establish actual behavior on the installed version.

Support: REFERENCE_ONLY; knowledge: REFERENCE_ONLY until version/workflow evidence.
Pinned applicability: {"blender": ["5.2.2"]}.

Decision: Data API avoids UI context; operators are appropriate only after poll/context validation.

Contrasts: Create a mesh through data and check valid versus degenerate faces. Do not run an object-mode operation blindly from edit mode.

[Authoritative source](https://docs.blender.org/api/5.0/bpy.types.Mesh.html). Locally authored summary, not copied vendor text.

## Role playbook

Modeler/UV artist/animator: inventory mesh recipes, asset.package.build.v1 and animation.robot.rig.v1. Produce source.blend, logical geometry/UV, metrics, FBX/material or motion sidecars and license provenance. Check dimensions, pivot, budget, UV, slots and deformation. Asset writers own only their versioned bundle; no Unity writes. If Blender/context is unavailable, produce a proposal or BLOCKED, never fabricated geometry.
