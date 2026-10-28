# Asset and sprite workflows

PolyForge's Phase 8 capabilities remain bounded registered operations. AssetSpec
is an explicit specification supplied by the user or host; the engine preserves
the original brief instead of claiming unrestricted natural-language design.

## Asset package

`asset.package.build.v1` accepts `schema_version` and `spec`. Examples under
`examples/phase8/` declare the brief, silhouette, primitive family, dimensions,
triangle budget, single LOD, generated UV0, base color/metallic/roughness, pivot,
collider, license, coordinate basis and technical rubric.

The Asset Architect freezes that input. The Modeler produces a separate source
revision while the UV/Material Artist prepares a data-only palette plan. A
read-only inspector compares the measured geometry and material values against
the specification. A material rejection permits one scoped rebuild by the
Refiner. Each revision retains its source and digest. Other failures stop rather
than triggering an arbitrary patch. The second attempt is the last attempt.

Bundles require editable geometry, UV source, material source, FBX and geometry
metrics. Units are meters, native up Z/forward -Y, scale one and base-center pivot.
Reference files need workspace-safe paths, hashes, source licenses and DATA_ONLY
authority. An image caption, filename or source comment cannot grant execution,
network or filesystem permissions. No reference is required; image interpretation
and subjective resemblance remain assisted review.

Technical APPROVED and visual REVIEW are distinct. `import_ready` is false when
required visual approval is absent. A fabricated approval or another revision's
receipt cannot promote a package. Phase 8 supports basic URP Lit values, with
smoothness derived as one minus roughness. It does not implement advanced image
textures, UV painting, procedural PBR, arbitrary topology or multiple LODs.

Unrelated asset workflows can overlap, including material planning, while the
owned Blender process is queued conservatively one at a time. Canonical asset
leases reject a second writer to the same asset. Lock waits are bounded and
cancellable; malformed or unverifiable ownership does not become permission.

## Six-frame sprite fixture

`sprite.robot.bake.v1` accepts a registered Phase 7 robot source path and its hash.
It opens that source with auto-execution disabled, samples Walk at frames
1/5/9/13/17/21 and renders six 128×128 transparent images with one fixed camera.
The root projects to pivot (0.5, 0.1). A 768×128 horizontal atlas uses no trimming,
64 pixels per unit and six frames per second, for a one-second loop. Editable
source, camera/sample provenance, individual PNGs and metadata are retained.

Pixel audits decode the PNG data independently, check framing and transparency,
compare frame hashes/order/pivots, and compare atlas pixels with the ordered
frames. Cropping, substituted frames, reordered pixels and pivot drift fail.
Rendered pose appearance/confidence stays separate from these deterministic tests.

## Direct 2D

`sprite.unity.strip.v1` also accepts six existing sprites via `DIRECT_SPRITES`.
That route requires Unity and omits Blender discovery/generation. The current
version supports the same six-frame 128px strip format; it is not a universal
sprite importer. Requests outside that format remain unsupported rather than
being silently converted into a robot or 3D project.

The input names `asset_id`, `source_kind`, `metadata_file`, `atlas_file` and six
unique `frame_files` under the workspace. Metadata includes frame size/count,
order, FPS, pivot, PPU, trim/framing policy, frame hashes and source license.
A new managed URP project requires explicit `allow_package_downloads: true`
authorization for the pinned template packages. Existing workspace approval is
retained. The 2D Sprite 1.0.0 package is installed with the pinned Editor; no
third-party sprite tool is required. Original unmanaged projects are refused.

Native Sprite Data Provider APIs create six rectangles and stable sprite IDs.
The clip animates `SpriteRenderer.m_Sprite` with actual imported references.
Unity holds the final object-reference key for one frame, so six keys at
0 through 5/6 seconds produce the measured one-second clip. A separate
SpriteArena scene contains a top-down WASD controller, Rigidbody2D and wall
collider. It preserves preexisting 3D scene bytes. Editor and PlayMode gates check
references, duration, loop playback, actual keyboard input and collision.

Use `workforce plan/run` with `task_class: CREATE_ASSET` and domain tags
`["unity", "2d"]` for this direct route. It plans S0/S1/S4/S5, without the Blender
stages. Use the engine's returned run/artifact IDs for status and inspection.
Capabilities also run through the standard `capability run` command and accept
`--dry-run`; invalid inputs and dry runs do not create files.

These are public development checks in TRUSTED_LOCAL, not protected evaluation
or OS isolation. Host-subagent qualification remains Phase 10; full rollback
remains Phase 9. No Phase 8 standalone player or performance result is implied.
