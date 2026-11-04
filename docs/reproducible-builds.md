# Reproducible release artifacts

Use the existing environment with `build`, `setuptools`, and `wheel` installed:

```powershell
.venv/Scripts/python.exe -m tools.reproducible_build --outdir .tmp/release-a --epoch 1793318400
.venv/Scripts/python.exe -m tools.reproducible_build --outdir .tmp/release-b --epoch 1793318400
```

Each destination must not exist. `--source PATH` selects a source directory;
the default is the current directory. Alternatively, declare `SOURCE_DATE_EPOCH`
and omit `--epoch`. An explicit epoch takes precedence. Epochs must be integers
between 0 and 4294967295, matching the gzip timestamp field.

The wrapper invokes the current Python interpreter's standard
`-m build --no-isolation` frontend in a temporary output directory. It keeps
backend wheel bytes unchanged and rewrites only the sdist's tar/gzip container:
entries sorted by name, fixed timestamps, zero uid/gid, empty owner names, no
gzip filename, and modes 0644 for regular files or 0755 for directories and
executable files. File names and file contents are preserved. The wrapper does
not extract archives or change the source tree; the backend can still produce
its usual source-side build metadata.

`build-receipt.json` records the epoch and SHA-256 of both distribution files.
With identical source contents, file executable bits, build dependencies,
Python and compression implementation, the two receipts and distribution
files should match byte for byte. Compare all three files across independent
builds; a receipt by itself is not proof of reproducibility. The wrapper does
not normalize wheel payloads or promise identical output across different
build toolchains.

Artifacts must be regular files with a single hardlink. Linked paths, Windows
reparse points, archive links and special files, duplicate member names, and
unsafe member paths are rejected. Each compressed artifact is limited to
256 MiB; an sdist may expand to at most 512 MiB and contain at most 100,000
members. Normalization is bounded and occurs in memory, so large accepted
archives require additional memory for compressed and uncompressed copies.

Validation errors and backend failures do not publish the destination. Backend
exit codes are preserved. Once publication starts, an I/O failure can leave a
partial destination; inspect it and choose a new destination for the next run.
Existing destinations are never overwritten. Treat source directories and the
local filesystem as trusted: path checks are conservative, but are not a
sandbox against concurrent filesystem mutation by another process.
