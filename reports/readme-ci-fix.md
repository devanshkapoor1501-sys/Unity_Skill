# README documentation CI repair

Date: 2026-10-28. Original failing commit: df26844.
[Original main run](https://github.com/devanshkapoor1501-sys/Unity_Skill/actions/runs/40669067064).
All three jobs failed the same documentation test; each otherwise passed 198 tests.

The old test required executable `polyforge` commands in README.md. The requested
user-facing README replaced those with a Codex skill-install prompt and moved
developer commands to docs/development-guide.md. The test still read the old path.

Changed the documentation check to execute the preserved examples from the
developer guide and portable skill. Added a separate README check for the installer
syntax, repository URL, skill path, existing SKILL.md and matching skill name.
No test was skipped and no coverage threshold was reduced. Phase 7 was not started.

| Executed command | Exit | Result |
| --- | --- | --- |
| `python -m pytest tests/test_contract_boundaries.py -k readme_and_skill -q` before fix | 1 | Reproduced the CI assertion locally |
| `python -m pytest tests/test_contract_boundaries.py -k 'readme or development_guide' -q` after fix | 0 | 2 passed |
| `python -m pytest --cov --cov-report=term-missing --junitxml=.tmp/readme-ci/tests.xml` | 0 | 200 passed, 12 application cases deselected; 94.99% coverage |
| `python -m ruff check .` | 0 | PASS |
| `python -m mypy` | 0 | PASS; 57 source files |
| `python -m tools.generate_cli_docs --check` | 0 | PASS |
| `python -m build --no-isolation` | 0 | wheel/source archive built |
| `git diff --check` | 0 | PASS |

Local commands used `.venv/Scripts/python.exe` (Python 3.12.14), workspace-local
TEMP/TMP, and actual Windows junction/hardlink permissions for the full suite.
See [failure](readme-ci-evidence/red.txt), [focused checks](readme-ci-evidence/green.txt),
[full output](readme-ci-evidence/tests.txt) and [XML](readme-ci-evidence/tests.xml).
This validates the README install target; actual cross-host installation remains
a separate qualification gate.
