# p13_material_lod

Create an editable Blender model and Unity FBX handoff for the material lod case.
Use Unity world XYZ in meters, with Y up and the floor at Y=0. Sizes are full dimensions.
Each listed module is a distinct editable closed mesh with UV0 and its exact named material.
Positive yaw is about Unity Y. Keep names exactly as listed for the receiving pipeline.

| Object name | Shape | Full XYZ size | World XYZ center | Yaw degrees | Material |
| --- | --- | --- | --- | --- | --- |
| p13_material_lod:module:lod_pedestal | box | [2.8, 0.35, 2.2] | [0, 0.175, 0] | 0 | base |
| p13_material_lod:module:lod_drum | cylinder | [1.15, 1.65, 1.15] | [-0.55, 1.175, 0.15] | 0 | trim |
| p13_material_lod:module:lod_indicator | box | [0.45, 0.75, 0.65] | [0.85, 0.725, -0.35] | 0 | accent |

Include these named empty sockets in the editable source and in both exports.

- `p13_material_lod:socket:lod_socket_left` at [-0.55, 2, 0.15] m.
- `p13_material_lod:socket:lod_socket_right` at [0.85, 1.1, -0.35] m.

Deliver four files in this scratch workspace.

- `source.blend` with editable modules, named empties, and an editable LOD1 mesh.
- `asset.fbx` with the main meshes and sockets.
- `lod.fbx` with matching bounds, material inventory, and sockets.
- `preview.png` with a visible technical preview.

Socket position tolerance is 0.005 m. Bounds tolerance is 0.015 m per axis.
The LOD must use no more triangles than the main mesh.
The LOD must use strictly fewer triangles than the main mesh.
