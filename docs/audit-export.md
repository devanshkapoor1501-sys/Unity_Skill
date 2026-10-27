# Static audit and export

S3 runs the pinned Blender 5.2.2 static pipeline. It produces replayable geometry
and image evidence with source-to-export bindings. Unity import and artistic
acceptance remain separate gates.

```console
polyforge build --workspace workspace/arena_demo --through S3 --dry-run --json
polyforge build --workspace workspace/arena_demo --through S3 --only robot_a --json
polyforge audit --workspace workspace/arena_demo --asset robot_a --dry-run --json
polyforge audit --workspace workspace/arena_demo --asset robot_a --json
polyforge capability run audit.static.multiview.v1 --input examples/static_recipes/audit.json --workspace . --dry-run --json
```

The last example requires an asset named robot_a already registered under that
workspace. Use the initialized managed workspace with a request copied inside
it when invoking the catalog operation there. Build defaults to S2; S3 is explicit.
S4–S5 are still NOT_RUN/5.

## Inputs, preservation and status

Build validates the manifest, all effective recipes, config and S3 preview budget
before publishing files. Dry runs never launch Blender or create locks. Color,
metallic and roughness are supported; S3 texture interchange is explicitly
NOT_RUN/5 before writes. Existing material texture declarations are not silently
exported as working texture support.

Audit finds the latest registered S2 source for a semantic asset ID, verifies its
SHA-256, and copies the original bytes into a new run. An incomplete S3 attempt
without registered artifacts does not hide a prior successful source. Corrupt
metadata and source hashes fail before writes. Audit never saves over the original.
The copy opens with automatic scripts disabled; failures retain their run evidence.
Blender configuration, scripts, data and extension directories point inside the
owned process temporary folder. TRUSTED_LOCAL remains explicit; these settings
do not provide malicious-code containment or network isolation.

Geometry operation PASS, visual_review_status REVIEW and unity_import_status
NOT_RUN are separate facts. Generated report images are available for review;
neither a nonblank image nor an assistant preview establishes human artistic
acceptance. Collider intent is retained in managed build bindings, while actual
collider/physics validation stays NOT_RUN until Unity execution exists.

## Views and diagnostics

The fixed camera names are front, side, top and iso. Source coordinates are Z-up,
front -Y; canonical dimensions use Unity XYZ meters. Each orthographic camera
frames projected bounds with a 20% margin and a deterministic target. CPU Cycles
uses eight samples and seed 42, Standard color view, transparent RGBA8 PNG and
three fixed area lights. Default preview is 512 square pixels; audited previews
are limited to 32–1024. Config values above this limit are rejected before writes.

The host independently decodes PNG chunks, checks CRCs, bounds decompression,
reconstructs all five scanline filters and measures actual alpha/color data.
Required foreground coverage is at least 0.1%, at least two foreground colors,
and no foreground touches an image border. Dimensions must match the requested
preview. These are geometric visibility checks, not artistic-quality scores.

Static preflight identifies inward normals on supported convex primitive modules,
non-unit/nonuniform or reflected transforms, unexpected orientation, missing UVs,
degenerate faces, missing material slots and socket/parent bindings. Issues name
the originating semantic module/socket and recipe/export context. Armatures are
explicitly refused rather than receiving static transform edits. Arbitrary
concave modeling and animation are outside this diagnostic contract.

## Export and sidecars

Only tagged asset roots, mesh modules and socket empties enter the selected FBX
hierarchy. Cameras and lights do not export. Static settings are axis_forward=-Z,
axis_up=Y, global_scale=1, apply_unit_scale=true, FBX_SCALE_UNITS,
bake_space_transform=false, bake_anim=false and custom properties enabled.
No animation actions or leaf bones are requested. Source scales are already
applied; unsupported rig transforms are never baked as a static shortcut.

Output files:

- source.blend, metrics.json and logical-geometry.json preserve editable source
  and checked source identity.
- front.png, side.png, top.png, iso.png and view_checks.json retain actual pixel
  evidence and independent host measurements.
- asset.fbx, material.json, handoff.json and fbx_roundtrip.json retain the selected
  hierarchy, linear base color/metallic/roughness, module material assignments,
  axis/unit metadata, normalized dimensions and semantic sockets.
- audit_metadata.json describes camera/export/renderer configuration and separate
  statuses. review.html is a self-contained local index of the four PNGs.
- artifacts.json and export_binding.json retain SHA-256, sizes, recipe/run identity
  and actual tool fingerprints. The managed build summary binds manifest asset
  IDs, FBX paths, requested materials and collider intent.

The material sidecar preserves the entire editable palette. FBX contains materials
actually used by exported meshes, so unused palette entries are not required in
the Blender import. Host validation checks both scopes independently. Physical
material values use a 1e-6 float tolerance; IDs and bindings must match exactly.

FBX is imported into a fresh Blender scene for a source-side roundtrip. Unequal
dimensions, socket positions, module IDs and used material IDs must agree. This
tests Blender's own exporter/importer, including the asymmetric marker fixture.
It cannot prove Unity import transforms. Intended Unity settings are recorded
for Phase 5: global scale 1, useFileScale true and bakeAxisConversion false; the
native importer must verify or revise them with actual Unity evidence.

Logical source geometry and export metadata repeat on the pinned toolchain.
Binary .blend/FBX files can include producer metadata and are not claimed to have
identical bytes. Each actual file hash is retained. Pure handoff reconciliation
tests exercise axes, scale, socket and material faults; synthetic PASS never
changes application_execution from NOT_RUN.

Official references: [FBX export API](https://docs.blender.org/api/5.0/bpy.ops.export_scene.html)
and [render settings](https://docs.blender.org/UATEST/api/current/bpy.types.RenderSettings.html).
Runtime compatibility is established by actual local 5.2.2 tests, independently
of the documentation version. Actual Unity import is the next acceptance gate.
