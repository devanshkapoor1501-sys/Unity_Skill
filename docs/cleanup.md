# Bounded workspace cleanup

`polyforge clean --workspace ROOT --dry-run --json` lists eligible temporary
files without changing the workspace. Omitting both flags also previews. Add
`--confirm` to remove eligible files; `--dry-run` always takes precedence.

The scope is deliberately narrow: `.tmp`, `.temp` and `.cache` files inside
completed native processes' private `runs/<run-id>/.../tmp/` directories. The
workspace must be initialized, the durable run must be completed, and the
process must be verifiably dead. Referenced artifacts, sources, ordinary run
outputs, XML/log evidence, transactions and Unity projects are preserved.
Live or uncertain processes are skipped with a reason.

The command rejects unsafe links and bounded-inventory failures. Confirmed
cleanup rechecks ownership, state and file identity before unlinking each file.
It does not recursively remove directories. Any partial failure reports files
already removed; cleanup is not a transactional source-repair operation.

These checks apply to trusted local maintenance. They do not establish an OS
sandbox or protection against a hostile concurrent filesystem writer. Review the
candidate list before confirming. Never use cleanup as a substitute for keeping
editable source, native evidence or recovery snapshots.
