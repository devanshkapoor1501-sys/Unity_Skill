# p13_modular_room_alcove

Create an editable Blender model and Unity FBX handoff for the modular room case.
Use Unity world XYZ in meters, with Y up and the floor at Y=0. Sizes are full dimensions.
Each listed module is a distinct editable closed mesh with UV0 and its exact named material.
Positive yaw is about Unity Y. Keep names exactly as listed for the receiving pipeline.

| Object name | Shape | Full XYZ size | World XYZ center | Yaw degrees | Material |
| --- | --- | --- | --- | --- | --- |
| p13_modular_room_alcove:module:room_floor | box | [3.8, 0.3, 3.4] | [0, 0.15, 0] | 0 | base |
| p13_modular_room_alcove:module:room_rear_panel | box | [3.4, 2.6, 0.25] | [0, 1.6, 1.475] | 0 | trim |
| p13_modular_room_alcove:module:room_side_pier | box | [0.45, 1.9, 0.7] | [-1.575, 1.25, -0.85] | 0 | accent |

Include these named empty sockets in the editable source and in both exports.

- `p13_modular_room_alcove:socket:room_socket_left` at [-1.35, 1.15, -1.2] m.
- `p13_modular_room_alcove:socket:room_socket_right` at [1.15, 1.85, 1.35] m.

Deliver four files in this scratch workspace.

- `source.blend` with editable modules, named empties, and an editable LOD1 mesh.
- `asset.fbx` with the main meshes and sockets.
- `lod.fbx` with matching bounds, material inventory, and sockets.
- `preview.png` with a visible technical preview.

Socket position tolerance is 0.005 m. Bounds tolerance is 0.015 m per axis.
The LOD must use no more triangles than the main mesh.
