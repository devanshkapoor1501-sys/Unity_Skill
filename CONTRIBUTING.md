# Contributing

Install the development extra in an isolated Python 3.11+ environment and run
the checks in the [development guide](docs/development-guide.md). Write a meaningful failing test before behavior changes.
Keep security/contracts coverage at least 90%; do not suppress failures to pass.

Capability contributions need a versioned schema, positive/negative fixtures,
model-free invocation, provenance, artifact constraints, and actual integration
evidence before catalog inclusion. Examples and registered future commands are
not executable capability claims. Add source/license notices for external data.

Keep Unity Editor code separate from runtime assemblies. Author scenes/prefabs
through Unity APIs, never raw serialized YAML. Every phase ends with an evidence
report and stops at the documented acceptance boundary.

Apache-2.0 applies to original contributions. The maintainer must establish
private vulnerability reporting and release ownership before publication.
