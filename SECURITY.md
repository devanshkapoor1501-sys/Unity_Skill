# Security policy

## Current scope

Descriptor validation is read-only. Its input must resolve inside
the supplied existing workspace. It reads bounded UTF-8 JSON, rejects duplicate
fields and non-finite numbers, uses bundled schemas, and never dynamically
imports or executes a descriptor's runner string. Network operations are absent.

`TRUSTED_LOCAL` is the only available context. It does not contain malicious
Blender scripts, Unity packages, plugins, or arbitrary local code. OS isolation,
worker filesystem ACLs and denial probes are not implemented yet.
`SANDBOXED_UNTRUSTED` requests are denied, never downgraded.
Read-only path checks are not a TOCTOU-resistant OS security boundary.

The approved repository root authorizes development of this engine. Executing
future generated or imported code needs a separately recorded trusted project
scope; third-party plugins are not silently enabled.

## Operational defaults

Phase 1 adds strict trusted-local write paths (including junction/reparse denial),
OS-exclusive PID/host/birth locks, durable event replay, atomic state replacement,
and explicit binary allowlists. Workers receive a minimal environment. Bounded
logs redact credentials, including quoted assignments and truncated known values.
Windows Job Objects own suspended-then-resumed process trees with kill-on-close,
memory and process-count limits. POSIX process groups provide cleanup; POSIX
memory-limit enforcement remains unverified. These controls do not restrict a
trusted worker's ambient filesystem or network privileges.

- No runtime network access, package downloads, arbitrary shell, or remote model.
- Invalid input and dry-run validation perform no workspace writes.
- Future generated Unity changes belong only in the managed asset subtree.
- Original projects must never open in Unity during read-only inspection.
- Hidden evaluator material must remain outside development workspaces and logs.
- Missing security evidence remains BLOCKED/NOT_RUN in reports.

## Static inspection and evaluation evidence

`inspect-project --read-only` inventories every regular original file, including
caches and `.meta` files, before and after analysis. It compares bytes, SHA-256
and available mtimes, rejects links and changes, and applies file, directory,
byte and source-node limits. C# syntax uses the pinned Tree-sitter grammar;
Python syntax uses `ast`. Neither source is executed and Unity never opens the
original project. Syntax observations do not establish compilation, assembly
binding, package safety or runtime compatibility.

Benchmark adapters are trusted injected Python interfaces, not a sandbox or an
authenticated provider connection. They own process deadlines; the harness also
checks observed end-to-end elapsed time and usage. Digests protect against
accidental evidence changes but do not authenticate a malicious local owner.
Imported grades remain declared observations. Missing independent ownership,
hidden tests or model execution never becomes verified acceptance.

Rendered profiling accepts registered owned player payloads, verifies executable
and data hashes, and records bounded native process observations. A development
performance result does not grant game acceptance or untrusted-code isolation.

## Reporting vulnerabilities

Do not publish credentials or private projects in an issue. A private reporting
contact must be configured by the maintainer before public release. Until then,
share a minimal redacted reproducer directly with the repository owner.
