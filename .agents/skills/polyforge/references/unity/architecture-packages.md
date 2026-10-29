# Unity architecture and package decisions

Revision 1.0.1; applicability Unity 6000.6.3f1. REFERENCE_ONLY knowledge;
no generated code or package installation is an executable capability.

Use ScriptableObject assets for shared authored configuration, MonoBehaviour for
per-instance scene lifecycle, and plain C# for pure logic. Enemy tuning shared
by prefabs belongs in an asset; each enemy's current health stays instance state.
Do not mutate shared asset defaults to store runtime state. For a small prototype,
default assemblies may suffice. Introduce assembly definitions for real module
boundaries: Editor tooling depends on runtime code; runtime never depends on
UnityEditor. Check compilation and reject dependency cycles in a scratch copy.

Package applicability pins: com.unity.render-pipelines.universal 17.6.0 and
com.unity.test-framework 1.8.0 on Unity 6000.6.3f1. Other versions are UNKNOWN
until inspected and tested. The manifest requests dependencies; packages-lock
records resolution; local PackageCache/package.json observes cached installation.
Compare each separately. A requested package or documentation link never proves
an installed API. A cache version mismatch requires review. No automatic
download, registry lookup, package resolution, Editor change or project mutation.

```console
polyforge knowledge availability --workspace ROOT --project . --json
```

The result distinguishes requested/resolved/cached versions and leaves API
compatibility UNKNOWN. Read the matching package manual and run a reviewed
fixed smoke before claiming a version-sensitive method. A new architecture or
package operation needs SAFE_DISCOVERY and independent negative fixtures.

Sources (local authored summary, vendor articles not copied):
[ScriptableObject](https://docs.unity3d.com/6000.6/Documentation/Manual/class-ScriptableObject.html),
[assemblies](https://docs.unity3d.com/6000.6/Documentation/Manual/assembly-definition-files.html),
[URP 17.6](https://docs.unity3d.com/Packages/com.unity.render-pipelines.universal@17.6/manual/index.html).

Role playbook: Unity integrator inventories CLI descriptors, exact Editor/package
versions and assemblies; emits a typed plan and compile/behavior evidence.
Reviewer checks shared-state lifetime, runtime/Editor boundary and version match.
If Unity or package probes are unavailable, explain the design and report BLOCKED
for execution. A reference route does not authorize code execution or acceptance.
