# Editable Blender modeling

Choose the geometry representation and check the asset brief before selecting an
operator. Use the room kit for modular walls and openings, vehicle for wheeled
hard surface forms, mechanical prop for bored housings, and organic practice for
primitive forms and editable ridges. Use composition to combine operations across
these families. Inspect the requested footprint, attachment points, material
slots, target polygon budget and silhouette before committing to a plan.

| Workflow | Capability |
| --- | --- |
| Modular room kit | `mesh.modeling.room_kit.v1` |
| Stylized vehicle | `mesh.modeling.vehicle.v1` |
| Mechanical prop | `mesh.modeling.mechanical_prop.v1` |
| Organic practice | `mesh.modeling.organic.v1` |
| Typed composition | `mesh.modeling.compose.v1` |

| Concept | Use when | Check before handoff |
| --- | --- | --- |
| Primitive topology | The shape can start from predictable solids with bounded edges | Closed, outward winding and sufficient edges for the silhouette |
| Extrusion and Boolean | A profile needs depth, or intersecting solids define a cut | Extrusion is assisted. Typed Boolean inputs require mesh operands and an acyclic dependency graph. Inspect coplanar cuts and thin walls. |
| Bevel, subdivision, symmetry | Edge treatment, rounded forms, or symmetric detail should stay editable | Keep modifiers in deliberate order. Check the evaluated bounds, minimum features and budget. |
| Curves | An editable path needs a bounded round profile | Inspect caps, collapsed segments, bend clearance and the mesh result after evaluation. |
| Geometry Nodes | A reusable procedural box needs predictable dimensions or density | The supported graph is fixed. Inspect size, UVs and the evaluated polygon count. |
| UVs, decals and material slots | A surface needs repeatable texture or material placement | The engine checks slot and UV validity. Layout quality and decals require manual review. |
| Sculpt and retopology | The reference depends on freeform volumes or deformation loops | Build a separate topology target and inspect edge flow manually. |
| Armature hooks | The mesh has named future attachment sites | Preserve socket transforms. Use the separate animation workflow for supported rigs and bind weights in the appropriate workflow. |
| Camera and export | The same asset needs views for audit and an editable interchange handoff | Frame from several axes, compare silhouettes, check the FBX in the target app and keep the original modifier stack. |

Use `capability show` and `capability run --dry-run` to inspect the contract and
plan. Use Blender 5.2.2 for production. Input dimensions use Unity meters in
width, height, depth order. The asset root is at the base center. The engine
converts positions and local rotations to Blender Z up. Set the base dimensions
before evaluating modifiers and review modifier order, particularly where a
Boolean depends on another object's evaluated geometry.

Composition accepts boxes, cylinders, spheres, a procedural box with an editable
Geometry Nodes graph, and capped polyline curves. The bounded modifier vocabulary
includes bevel, subdivision, mirror, solidify and Boolean union or difference.
Curves accept mirror as their user modifier. The compiler checks declared local
and world bounds, cutter dependencies, resource estimates and socket positions
before Blender runs. Dimensions, control points and material bindings are then
checked against the saved source by a separate Blender process.

Keep the source and use evaluated copies for export. Review `source.blend`,
`asset.fbx`, `lod.fbx`, the independent `inspection.json` and the four audit
views. The LOD reconstructs lower detail primitives and may fail if the shape
cannot meet the requested ratio. Inspect the silhouette and UV layout in Blender
and check the model in the target Unity scene. Finite UVs do not establish island
packing. Closed, outward winding does not detect arbitrary self intersections.
Conservative bounds overlap checks can reject separated shapes with overlapping
boxes. Use assembly contacts only for intended contacts. Artistic approval is a
separate decision about the sealed revision.

For unknown Blender APIs, start with an owned scratch file and a fixed versioned
probe. Check the active object, selection, mode and operator `poll()` before
running an operator. Prefer the data API where practical. Evaluate modifiers
through the dependency graph and release temporary evaluated meshes after use.
Record the probe's expected edits and inspect actual side effects, file hashes
and output limits. Discard scratch outputs on failure. For interactive edits,
save an owned copy before context changes and use Blender's undo history within
that copy. Headless recovery uses owned artifacts and receipts.

Manual sculpt, retopology, freeform extrusion, decals, text, Grease Pencil and
simulation require assisted work. Preserve the brief, identify the missing
operation and open an authorized scratch copy only when requested. Choose the
manual tool and review criteria based on the requested result. A polyline bevel
does not qualify all curve techniques, and organic practice does not qualify
sculpt or deformation topology.
