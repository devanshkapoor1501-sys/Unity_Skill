# Unity package ownership

Embedded UPM package `com.polyforge.engine`, pinned to Unity 6000.6.3f1/URP 17.6.0.
Editor code imports static FBX, creates URP materials/prefabs/scenes and writes
observed binding reports through native APIs. Runtime contains semantic bindings;
gameplay controllers are a later phase. Seventeen independent EditMode tests cover
import, material parameters, repeat stability and known defects.

The Python engine owns request validation, project authorization, subprocess
limits, provenance and repair snapshots. Invoke it through the CLI/portable skill;
do not hand-author Unity YAML. Generated assets live under
Assets/PolyForgeGenerated in a new managed project. No PlayMode or standalone
playability is claimed. See docs/unity-integration.md in the PolyForge repository.
