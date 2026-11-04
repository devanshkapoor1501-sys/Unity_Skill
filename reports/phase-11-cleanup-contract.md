# Phase 11 bounded cleanup contract and repair plan

Authority: blueprint 7.1 clean preview (lines575–577), existing CLI flags and
Result status/exit schema. No REST/event/inter-service interface is introduced;
API-contract-first was inspected and does not require OpenAPI for this CLI.
Use the existing contract, with these explicit safety restrictions.

Public interface: clean_workspace(root: Path, *, dry_run: bool=False, confirm: bool=False) -> Result.
Default and --dry-run preview only; --dry-run plus --confirm still preview only.
No new flags/dependencies. Confirm deletes only the same eligible temporary files,
never directories. Return candidates [{relative_path, bytes, sha256}], deleted
paths, dry_run, scope, skipped process observations and total candidate bytes.
No accepted-game claim. Invalid roots/metadata and unsafe inventory fail closed
using InputError/Result conventions; bounded output max10000 entries, file bound
16MiB, aggregate256MiB, bounded directory traversal.

Only files with .tmp/.temp/.cache suffix inside native process-private
runs/<run-id>/.../tmp/ directories qualify. Require a matching sibling completed
process.json with integer exit code and supported terminal reason, and a PID
proven dead by existing process_identity; uncertainty/live PID skips that
process. Require initialized PolyForge workspace ownership metadata, valid run
identity and completed durable RunJournal with no running stage; a failed run
with terminal process is allowed. A run without provable completed journal is
skipped. Preserve source files, logs/XML, process metadata, all ordinary run
outputs/registries and transactions; never remove Unity caches or Unity files.
Registered artifacts referenced by run evidence/registry must remain preserved
even if their path looks temporary.

Preview creates no files, locks, directories or journal changes. For confirm,
serialize cleaners with an existing FileLock in the owned workspace; re-read
run/process state/liveness and revalidate file lstat/hash/link count immediately
before unlink. Complete inventory/preflight before first deletion, with per-file
recheck and truthful partial-deletion diagnostics on later I/O failure. Reject
symlinks/junctions/reparse points/hardlinks/special files and out-of-root paths.
This is TRUSTED_LOCAL maintenance, not an OS sandbox or hostile-filesystem race
guarantee. No recursive deletion or unconstrained file-target argument.

Plan: (1) executor writes a behavior-level failing preview test and observes RED;
(2) minimal implementation then expand meaningful confirm/safety/active-run/
metadata/bounds/changed-file failure tests using RED/GREEN; (3) parent integrates
existing CLI registry/dispatch and regenerates help fixtures/docs, adds module
to configured coverage; (4) independent review plus targeted tests, full final
regression, lint/types/format/docs/build/install; (5) re-freeze baseline, reconcile
evidence, checkpoint push and exact-HEAD CI. External evaluator gates remain
blocked. Do not run cleaner against retained qualification evidence.
