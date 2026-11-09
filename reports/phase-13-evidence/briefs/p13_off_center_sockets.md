# p13_off_center_sockets

Create an editable Blender model and Unity FBX handoff for the off center sockets case.
Use Unity world XYZ in meters, with Y up and the floor at Y=0. Sizes are full dimensions.
Each listed module is a distinct editable closed mesh with UV0 and its exact named material.
Positive yaw is about Unity Y. Keep names exactly as listed for the receiving pipeline.

| Object name | Shape | Full XYZ size | World XYZ center | Yaw degrees | Material |
| --- | --- | --- | --- | --- | --- |
| p13_off_center_sockets:module:offset_block | box | [1.3, 1.1, 0.85] | [-1.65, 0.55, 0.75] | 0 | base |
| p13_off_center_sockets:module:offset_column | cylinder | [0.7, 1.8, 0.7] | [0.85, 0.9, -1.25] | 0 | trim |
| p13_off_center_sockets:module:offset_foot | box | [0.65, 0.4, 1.15] | [2.1, 0.2, 1.55] | 0 | accent |

Include these named empty sockets in the editable source and in both exports.

- `p13_off_center_sockets:socket:offset_socket_left` at [-2.15, 0.85, 0.4] m.
- `p13_off_center_sockets:socket:offset_socket_right` at [1.05, 1.45, -1.35] m.

Deliver four files in this scratch workspace.

- `source.blend` with editable modules, named empties, and an editable LOD1 mesh.
- `asset.fbx` with the main meshes and sockets.
- `lod.fbx` with matching bounds, material inventory, and sockets.
- `preview.png` with a visible technical preview.

Socket position tolerance is 0.005 m. Bounds tolerance is 0.015 m per axis.
The LOD must use no more triangles than the main mesh.
