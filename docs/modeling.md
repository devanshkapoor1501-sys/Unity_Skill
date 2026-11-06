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
