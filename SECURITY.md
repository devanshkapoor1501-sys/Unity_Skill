# Security policy

## Current scope

Phase 0 implements read-only descriptor validation. Its input must resolve inside
the supplied existing workspace. It reads bounded UTF-8 JSON, rejects duplicate
fields and non-finite numbers, uses bundled schemas, and never dynamically
imports or executes a descriptor's runner string. Network operations are absent.

`TRUSTED_LOCAL` is the only available context. It does not contain malicious
Blender scripts, Unity packages, plugins, or arbitrary local code. OS isolation,
worker ACLs, environment filtering, subprocess ownership, and denial probes are
not implemented yet. `SANDBOXED_UNTRUSTED` requests are denied, never downgraded.
Read-only path checks are not a TOCTOU-resistant OS security boundary.

The approved repository root authorizes development of this engine. Executing
future generated or imported code needs a separately recorded trusted project
scope; third-party plugins are not silently enabled.

## Operational defaults

- No runtime network access, package downloads, arbitrary shell, or remote model.
- Invalid input and dry-run validation perform no workspace writes.
- Future generated Unity changes belong only in the managed asset subtree.
- Original projects must never open in Unity during read-only inspection.
- Hidden evaluator material must remain outside development workspaces and logs.
- Missing security evidence remains BLOCKED/NOT_RUN in reports.

## Reporting vulnerabilities

Do not publish credentials or private projects in an issue. A private reporting
contact must be configured by the maintainer before public release. Until then,
share a minimal redacted reproducer directly with the repository owner.
