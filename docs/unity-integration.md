# Native Unity static integration

PolyForge's portable skill discovers `unity.scene.static.v1` and invokes the
same engine as `build --through S4`. Python validates contracts before launching
Unity. No model or MCP server is required. Complete host installation validation
remains Phase 10.

## Managed project and authorization

Use Unity 6000.6.3f1 and its installed URP blank 17.2.1 template. The template
declares URP 17.6.0, Input System 1.19.0 and Test Framework 1.8.0. Copy native
Assets/ProjectSettings/Packages bytes, excluding its Library caches. PolyForge
adds the embedded `com.polyforge.engine` package using package JSON. It never
constructs or edits serialized Unity scene/prefab YAML as text.

Initialization refuses an existing unmarked UnityProject. Template/package
manifest identity is checked on reuse. Close the managed Editor before builds
or repairs; hardlinked project files and reparse paths are denied. Original
projects are never opened. `--only` remains available through S3; S4 constructs
complete static scenes.

```powershell
.\.venv\Scripts\polyforge.exe build --workspace workspace/arena_demo --through S4 --dry-run --json
.\.venv\Scripts\polyforge.exe build --workspace workspace/arena_demo --through S4 --allow-package-downloads --json
.\.venv\Scripts\polyforge.exe reconcile --workspace workspace/arena_demo --strict --json
```

The first real S4 launch requires explicit package download authorization. The
workspace retains that authorization for subsequent Unity package resolution;
it does not enable arbitrary downloads/services or change the default TOML
network policy. The user authorized the Phase 5 package downloads in this chat.
Python planning/dry runs remain usable without Unity and write nothing.

Unity is TRUSTED_LOCAL. Its activated OS profile paths must be available to the
native licensing client; no license file or credentials are copied. UPM cache
and requested logs live in the workspace. Native licensing/Editor services may
write OS profile state. This is not OS filesystem or egress containment. The
existing 32-process Windows job ceiling remains enforced; Bee uses two build
threads. Unsupported untrusted profiles remain disabled.

## Native operations and evidence

Separate owned invocations compile/import, execute the builder, and run EditMode
tests. The test invocation omits `-quit`. Parse XML and require all seventeen expected
test identities with Passed results, including fault cases; zero/skipped/wrong
test suites cannot pass. Native failed test exit 2 maps to public exit 7.

ModelImporter uses scale 1, file scale enabled, static animation disabled and
native material import disabled. URP/Lit materials map linear RGBA, metallic and
smoothness = 1 - roughness. Namespaced per-asset materials avoid collisions.
Optional texture interchange remains unsupported and fails preflight.

Unity's FBX conversion reverses X relative to the semantic Blender coordinates.
An explicit X reflection on the nested model corrects this handedness boundary;
the semantic root and collider root stay unit-scaled. Actual asymmetric fixture
and robot left/right socket positions verify the conversion. FBX roundtrip uses
10 micrometres absolute / 1 ppm relative tolerance for float32 coordinates;
semantic identity stays exact. Unity dimensions use 2% / 1mm, sockets 2mm.

PrefabUtility and EditorSceneManager create editable prefabs and Arena/Training
static layouts from shared templates. These are two scene layouts, not accepted
games. PrefabBinding supplies semantic/source references, not future player or
enemy controller behavior. Colliders, camera and directional light are native
components. WASD, enemies, win/restart and PlayMode remain Phase 6.

Binding reports include model/prefab GUIDs, semantic node paths and local file
IDs, dimensions, socket positions, collider intent and scene counts. Python
independently checks report identity and contents rather than trusting PASS.
Each S4 run retains exact input fingerprints, process arguments/versions, logs,
XML, reconciliation, artifact hashes and an immutable native-output.zip.
The live project remains editable; the archive preserves each build's evidence.

Repeated builds retain GUIDs and counts. Registered exports are hash-checked
before reuse. Material-only parameter changes reuse FBX geometry and preserve
runtime C# bytes. Builds report which geometry was reused; no cache-hit claim
substitutes for actual application execution.

## Minimal repair

`diagnose --evidence-dir runs/ID` interprets observed bindings.
`repair plan --issue ISSUE-ID` returns a pure JSON patch preview without writes.
Save its `data.plan` to a workspace-local file, then invoke
`repair apply --plan FILE --approved`. The plan permits only native binding
reconstruction from the same immutable manifest/source identity. Arbitrary
paths, shell commands and different manifests are rejected. Two proposals per
symptom are permitted. Plans must match recorded issue/category/asset evidence;
the retry key is derived internally from input and symptom identity. Only the
affected asset and dependent scenes rebuild. Unchanged unrelated issues remain
visible and do not prevent a scoped repair; new or worsened faults fail it.

Transactions preserve manifest/recipes, native model/material/prefab/scene and
meta bytes, package state and project settings with SHA-256 inventories. Restore
verifies every snapshot byte before replacing anything, removes newly created
managed files, forces Unity reimport, and compares observed bindings to the
actual pre-repair baseline, including pre-existing faults. Numeric restore
equivalence uses 0.1mm absolute / 1ppm relative; identities remain exact. A failed
restore is `PF-ROLLBACK-FAILED` / `ROLLBACK_FAILED`, never repair success.
Phase 9 adds complete cross-application crash/cache/scenario recovery and the
public rollback/resume workflows; this phase proves static managed restoration.

Official references: [ModelImporter](https://docs.unity.com/en-us/engine/6000.3/script-reference/unityeditor/modelimporter),
[Editor command line](https://docs.unity.com/en-us/engine/6000.6/manual/unity-editor/command-line-arguments/editor),
[UPM cache configuration](https://docs.unity.com/en-us/engine/6000.6/manual/packages-list/package-manager-caches/upm-config-cache),
[test command line](https://docs.unity.com/en-us/engine/6000.3/manual/programming-environment/test-framework-introduction/running-tests/run-tests-from-command-line).
