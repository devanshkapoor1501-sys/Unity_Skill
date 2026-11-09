# p13_rotated_mechanical

Create an editable Blender model and Unity FBX handoff for the rotated mechanical case.
Use Unity world XYZ in meters, with Y up and the floor at Y=0. Sizes are full dimensions.
Each listed module is a distinct editable closed mesh with UV0 and its exact named material.
Positive yaw is about Unity Y. Keep names exactly as listed for the receiving pipeline.

| Object name | Shape | Full XYZ size | World XYZ center | Yaw degrees | Material |
| --- | --- | --- | --- | --- | --- |
| p13_rotated_mechanical:module:mechanical_plinth | box | [3.6, 0.4, 3.2] | [0, 0.2, 0] | 0 | base |
| p13_rotated_mechanical:module:mechanical_angled_housing | box | [1.4, 0.8, 0.6] | [-0.7, 0.8, 0] | 27 | trim |
| p13_rotated_mechanical:module:mechanical_spindle | cylinder | [0.6, 0.9, 0.6] | [0.9, 0.85, 0.5] | 0 | accent |

Include these named empty sockets in the editable source and in both exports.

- `p13_rotated_mechanical:socket:mechanical_socket_left` at [-1.15, 0.95, -0.15] m.
- `p13_rotated_mechanical:socket:mechanical_socket_right` at [0.9, 1.3, 0.5] m.

Deliver four files in this scratch workspace.

- `source.blend` with editable modules, named empties, and an editable LOD1 mesh.
- `asset.fbx` with the main meshes and sockets.
- `lod.fbx` with matching bounds, material inventory, and sockets.
- `preview.png` with a visible technical preview.

Socket position tolerance is 0.005 m. Bounds tolerance is 0.015 m per axis.
The LOD must use no more triangles than the main mesh.
