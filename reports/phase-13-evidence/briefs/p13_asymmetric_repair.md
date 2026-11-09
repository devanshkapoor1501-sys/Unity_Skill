# p13_asymmetric_repair

Create an editable Blender model and Unity FBX handoff for the asymmetric repair case.
Use Unity world XYZ in meters, with Y up and the floor at Y=0. Sizes are full dimensions.
Each listed module is a distinct editable closed mesh with UV0 and its exact named material.
Positive yaw is about Unity Y. Keep names exactly as listed for the receiving pipeline.

| Object name | Shape | Full XYZ size | World XYZ center | Yaw degrees | Material |
| --- | --- | --- | --- | --- | --- |
| p13_asymmetric_repair:module:repair_main_block | box | [1.55, 1.35, 1.05] | [-1.25, 0.675, -0.65] | 0 | base |
| p13_asymmetric_repair:module:repair_displaced_piece | box | [0.55, 0.9, 0.75] | [1.65, 0.45, 1.2] | 0 | accent |
| p13_asymmetric_repair:module:repair_short_post | cylinder | [0.8, 0.55, 0.8] | [-0.35, 0.275, 1.65] | 0 | trim |

Include these named empty sockets in the editable source and in both exports.

- `p13_asymmetric_repair:socket:repair_socket_left` at [-1.85, 1.2, -0.95] m.
- `p13_asymmetric_repair:socket:repair_socket_right` at [1.9, 0.3, 1.45] m.

Deliver four files in this scratch workspace.

- `source.blend` with editable modules, named empties, and an editable LOD1 mesh.
- `asset.fbx` with the main meshes and sockets.
- `lod.fbx` with matching bounds, material inventory, and sockets.
- `preview.png` with a visible technical preview.

Socket position tolerance is 0.005 m. Bounds tolerance is 0.015 m per axis.
The LOD must use no more triangles than the main mesh.
A previously observed X reflection is the defect to prevent. Match the stated signed coordinates.
