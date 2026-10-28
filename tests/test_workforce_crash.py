"""An actual dead worker's expired lease can be reclaimed and committed once."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError
from polyforge.workforce.ledger import JobLedger


def test_real_worker_death_and_expired_lease_recovery(tmp_path, monkeypatch):
    import polyforge.workforce.ledger as module

    script = """import os,sys
from pathlib import Path
from polyforge.workforce.ledger import JobLedger
from polyforge.runner.state import atomic_json
j=JobLedger(Path(sys.argv[1]),'crash_task')
lease=j.claim('produce','crate',ttl=1)
atomic_json(j.policy,'candidate.json',{'revision':1,'lease':lease})
os._exit(9)
"""
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    child = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)], env=env, capture_output=True, timeout=20
    )
    assert child.returncode == 9, child.stderr
    original = json.loads((tmp_path / "candidate.json").read_text())
    ledger = JobLedger(tmp_path, "crash_task")
    monkeypatch.setattr(module.time, "time", lambda: original["lease"]["until"] + 1)
    lease = ledger.claim("produce", "crate", ttl=60)
    assert lease["token"] != original["lease"]["token"]
    ledger.commit("produce", lease, {"status": "PASS", "revision": 1})
    assert ledger.claim("produce", "crate") is None
    with pytest.raises(InputError):
        ledger.commit("produce", original["lease"], {"revision": 2})
