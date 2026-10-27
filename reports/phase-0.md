# Phase 0 — repository foundation

**Phase status: PASS. Game status: PARTIAL. Phases 1–11: NOT_RUN.**

The installable foundation and its acceptance checks are implemented. No game,
Blender asset, Unity scene, worker sandbox, or benchmark result is claimed.
Execution stops here at the approved phase boundary.

## Actual changes

- Python package/console command, version 0.0.1; Apache-2.0 license and notices.
- One command registry defines all 25 leaf command syntaxes and availability.
  Help, CLI documentation, and invocation fixtures derive from it.
- Implemented capability list/show/run and one read-only descriptor validator.
  Future commands report NOT_RUN/5 without side effects.
- Versioned capability, result, and benchmark-task schemas; strict bounded JSON;
  canonical SHA-256; separate operation/test/game statuses; typed error exits.
- Capability Protocol/RunContext, default-denied network/isolation claims, and
  benchmark runner/evaluator interfaces. Absent evaluator returns BLOCKED/3.
- Public arena brief/manifest, frozen development brief hash, good/bad capability
  fixtures, tests, locked development dependencies, generated docs, and skill stub.
- Windows/Linux Python CI definition, source/wheel packaging, architecture,
  security/contribution notes, and full remaining implementation sequence.

Created source groups: `polyforge/`, `tests/`, `tools/`, `examples/`,
`benchmarks/`, `capabilities/`, `unity_package/`, `docs/`, `reports/`,
`.agents/skills/polyforge/`, `.github/workflows/`, and root packaging/license files.
The exact staged source inventory is recorded in `evidence/created-files.txt`.

## Commands and evidence

All commands used the workspace-local `.venv/Scripts/python.exe` unless otherwise
noted. `TEMP` and `TMP` were set to this repository's `.tmp` directory because
the execution sandbox's default temporary directory denied writes.

| Check | Actual outcome | Evidence |
| --- | --- | --- |
| pytest --cov --cov-report=term-missing | PASS: 33 tests; 100% security/contracts statement and branch coverage | evidence/pytest.txt, python-tests.xml, coverage.json |
| python -m ruff check . | PASS, exit 0 | evidence/ruff.txt |
| python -m ruff format --check . | PASS, exit 0 | evidence/format.txt |
| python -m mypy | PASS: 16 source files, strict mode | evidence/mypy.txt |
| python -m tools.generate_cli_docs --check | PASS | evidence/cli-docs.txt |
| python -m build --no-isolation | PASS: wheel and source archive | evidence/build.txt |
| python -m pip check | PASS: no broken requirements | evidence/pip-check.txt |
| python -m polyforge --help | PASS | evidence/help.txt |
| capability list and positive descriptor validation | PASS/0, game PARTIAL | evidence/catalog.txt, descriptor.txt |
| invalid descriptor | Expected FAIL/2 | evidence/negative-descriptor.txt |
| unimplemented build --through S3 | Expected NOT_RUN/5 | evidence/future-build.txt |
| Fresh editable installation | PASS, with isolated dependencies and no index access | evidence/fresh-editable-*.txt |
| Fresh wheel installation | PASS, console commands run outside checkout | evidence/fresh-wheel-*.txt |
| Wheel resource/source archive inspection | PASS, schemas/catalog/type marker and skill included | evidence/distribution.json |

`evidence/verification.json` contains exact argument arrays, expected/actual exits,
timestamps, durations, and individual logs. `evidence/fresh-installs.json` records
offline installation commands and console tests. Wheel-location evidence proves
the non-editable check imported the installed wheel rather than source files.

Tests cover Windows spaces/Unicode, invalid/schema-unknown fields, duplicate IDs
and JSON keys, non-finite and oversized/deep input, input path confinement,
zero workspace writes for invalid/dry-run operations, exact status/exit semantics,
unavailable evaluation, command examples, and truthful capability availability.

The skill stub has required name/description and matching folder name, with
single-hop references. Its documented CLI commands execute in acceptance tests.
Official skills-ref and actual two-host integration remain Phase 10 checks.

## Environment and tool versions

- Executed: Windows, Python 3.12.14; pytest 8.4.2; pytest-cov 6.3.0;
  Ruff 0.13.3; mypy 1.18.2; jsonschema 4.25.1; build 1.3.0;
  setuptools 80.9.0; wheel 0.45.1. Full resolved pins: requirements-dev.lock.
- Planned application targets: locally discovered Blender 5.2.2 LTS and Unity
  6000.6.3f1. No Blender/Unity execution was required or attempted in Phase 0.
- Unity template metadata declares URP 17.6.0, Input System 1.19.0 and Test
  Framework 1.8.0. License/package readiness remains unverified for later gates.
- Python 3.11/Linux matrix is configured but was NOT_RUN on this Windows host.
  The GitHub Actions workflow has not been executed remotely.
- No AI credentials are required by any implemented operation.

## Review, recovery, and limitations

Independent read-only review found three correctness issues. Each was reproduced
by failing tests, fixed, and included in the passing full suite. Details are in
review-phase-0.md. No actionable findings were deferred.

Dependency provisioning initially failed on sandbox temp access, DNS, read
timeouts, and metadata resolution. A local temp root and known stable package
versions with the legacy resolver succeeded; pip check subsequently passed.
Resolved runtime/build wheels were downloaded for truly offline clean-install
checks. No insecure transport, missing-test waiver, or fake sandbox was used.

The initial catalog intentionally contains no Blender/game capabilities. The
robot descriptor is metadata used to validate schema behavior. The arena
manifest references recipes to be supplied in Phase 3; it is requested design,
not a validated/generated game. Context worker logging and process enforcement
belong to Phase 1; OS-enforced untrusted execution remains unavailable.

Hidden rubric storage, evaluator-controlled task freezing, manual artistic/game
review, application integrations, target-device measurements, and comparative
benchmarks remain NOT_RUN/BLOCKED at their later designated gates. Original
research was absent; the supplied v4 blueprint is authoritative.

## Source preservation and next action

Original blueprint SHA-256 before and after implementation:
`9d92fea8880b03b6d00e0bbe69b6fb8c1bf3f22f4c1ff16c1de7ae1f42970505`.
The source file was never edited and is excluded from distributable archives.

Repository initialized on `codex/polyforge-phase-0`; no remote publishing or
tagging performed. Phase 1 is next: doctor/config, worker ownership, locks,
atomic state/journals, redaction, and expanded Windows workspace policy.
