# Advanced modeling with PolyForge

The modeling capabilities produce editable Blender files, main and lower detail
FBX exports, four inspection views and a separate geometry report. See the skill
reference for workflow selection, supported operations and assisted alternatives.
[Advanced modeling reference](../.agents/skills/polyforge/references/blender/modeling.md)

Save the following as `room.json` inside a managed workspace.

```json
{
  "schema_version": "1.0.0",
  "asset_id": "workshop_room",
  "parameters": {
    "size_m": [6, 3, 5],
    "wall_thickness_m": 0.18,
    "detail": 2,
    "max_polygons": 5000,
    "lod_ratio": 0.5
  }
}
```

```console
polyforge capability show mesh.modeling.room_kit.v1 --json
polyforge capability run mesh.modeling.room_kit.v1 --workspace ROOT --input room.json --dry-run --json
polyforge capability run mesh.modeling.room_kit.v1 --workspace ROOT --input room.json --json
```

Start with preview to check the compiled plan without writes. Production uses
Blender 5.2.2 and a fresh run directory. Its successful result lists the artifact
paths and reports technical checks separately from artistic review. The same
typed input can enter workforce planning as `CREATE_ASSET` in the `blender`
domain. Workforce assigns a modeling specialist and independent inspection.
Promotion requires a separate artistic approval for the exact sealed revision.

For a custom asset, use `mesh.modeling.compose.v1` and supply typed `objects`
and optional `sockets`. Use the registered [request schema](../polyforge/contracts/modeling_request.schema.json)
for field names, ranges, and modifier parameters. IDs are stable within the
asset. Position and rotation are in Unity axes. Declare `DISALLOW` for
compositions that must have disjoint object bounds. Use `ASSEMBLY_CONTACTS` for
designed contacts such as walls on a floor or a shaft inside its housing.

Modeling FBXs compensate for Unity's X handedness conversion at the export
hierarchy, consistently for evaluated meshes, sockets and the LOD. The editable
Blender source retains its original transforms. Import these modeling exports
directly; applying the legacy static-recipe prefab's additional X reflection
would compensate twice. That older importer remains for its existing recipe
pipeline. Use asymmetric sockets and individual module bounds when checking an
import: symmetric overall dimensions alone cannot detect a reflection.
The [v7 repair report](../reports/phase-12-v7.md) records executed checks and
separates technical results from independent transfer and artistic approval.

For API exploration, run the fixed scratch probe before trying a context-sensitive
mesh operation. Preview it with `--dry-run`. The probe records the expected
Object Mode rejection, a successful Edit Mode selection and edit, and recovery
from the same saved baseline. It opens only its own scratch file.

```console
polyforge knowledge probe --workspace ROOT --tool blender-modeling --json
```

An explicit capped or beveled polyline can route to the typed composition
candidate. Requests for particles, simulation, text, Grease Pencil, sculpting,
retopology, decals, or freeform extrusion enter assisted review, including
requests that also mention a supported mesh. Preserve the complete request and
review the identified assisted needs before planning production.

The vehicle preview seats its cabin on the chassis while retaining the full
requested height. Organic practice exposes its crown and editable ridge paths.
The ridge layout follows an ideal ellipsoid; the actual main/LOD meshes are
faceted. Continuous ridge contact on extreme anisotropic shapes is unqualified.
Inspect native views and geometry when exact surface attachment is required;
analytic placement tests alone do not establish that result. Current visual
evidence covers the dimensions recorded in the [owner review](../reports/phase-12-v7-review.md).
