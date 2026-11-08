"""Invoke the actual regression against already generated native assets."""

import json
import runpy
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
tests = runpy.run_path(str(repo / "tests/test_phase12_native.py"))
assets, workspace = (Path(value).resolve() for value in sys.argv[1:])
results = json.loads((assets / "native-results.json").read_text(encoding="utf-8"))
tests["test_unity_imports_modeling_families_and_lods"]((assets, results), workspace)
print("PASS: all 12 main/LOD imports and asymmetric mutation/parent/meta/source checks")
