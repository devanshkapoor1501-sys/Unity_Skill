# Unity package ownership

Phase 5 introduces the UPM-compatible Editor package, followed by runtime and
test assemblies. Editor-only APIs must stay outside runtime code. Managed output
belongs under Assets/PolyForgeGenerated in a newly initialized project.

This scaffold contains no executable Unity package yet. There is no Unity build,
scene, PlayMode evidence, animation, or serialization generated in Phase 0.
