"""Enforce the branch-only bar as well as coverage.py's combined bar."""

import json
from pathlib import Path


def main() -> int:
    totals = json.loads(Path("coverage.json").read_text(encoding="utf-8"))["totals"]
    total = totals["num_branches"]
    branches = 100 * totals["covered_branches"] / total if total else 0
    print(f"Combined coverage: {totals['percent_covered']:.2f}%; branches: {branches:.2f}%")
    return 0 if totals["percent_covered"] >= 90 and branches >= 90 else 1


if __name__ == "__main__":
    raise SystemExit(main())
