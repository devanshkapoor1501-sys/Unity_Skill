"""Scratch API probe evidence must survive verification and replay."""

import hashlib
import sys
from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError
from polyforge.knowledge import probes
from polyforge.runner.processes import ProcessOutcome
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy

TOOL = "blender-modeling"


def observation():
    return {
        "schema_version": "1.0.0",
        "probe_id": "blender.modeling-scratch.v1",
        "tool_version": "5.2.2",
        "checks": dict(probes.CHECKS[TOOL]),
        "artifacts": [{"path": "scratch/baseline.blend", "sha256": "a" * 64}],
    }


@pytest.mark.parametrize("artifact", [[], None, [None], [{"path": "../baseline.blend"}]])
def test_modeling_probe_requires_the_fixed_owned_artifact(artifact):
    with pytest.raises(InputError, match="scratch"):
        probes.validate_observation(TOOL, {**observation(), "artifacts": artifact})


@pytest.mark.parametrize("case", ["valid", "missing", "changed", "oversized"])
def test_probe_verifies_checkpoint_bytes_before_publication_and_on_replay(
    tmp_path, monkeypatch, case
):
    monkeypatch.setattr(probes, "discover_tool", lambda *_: Path(sys.executable))
    payload = b"scratch test fixture bytes"

    def native(argv, policy, relative, limits):
        assert "--disable-autoexec" in argv and "--python-exit-code" in argv
        output = Path(argv[-1])
        checkpoint = policy.path(output.parent / "scratch/baseline.blend")
        data = observation()
        data["artifacts"][0]["sha256"] = hashlib.sha256(payload).hexdigest()
        if case != "missing":
            checkpoint.write_bytes(payload if case != "changed" else b"changed")
        if case == "oversized":
            with checkpoint.open("r+b") as stream:
                stream.truncate(16_777_217)
        atomic_json(policy, output, data)
        return ProcessOutcome(0, "exit", 123, "UNIT_FIXTURE", 0, "", "", False)

    monkeypatch.setattr(probes, "run_process", native)
    policy = WorkspacePolicy(tmp_path)
    if case != "valid":
        with pytest.raises(InputError, match="scratch checkpoint"):
            probes.probe_tool(tmp_path, TOOL)
        assert not policy.path(".polyforge/knowledge-blender-modeling.json").exists()
        return
    result = probes.probe_tool(tmp_path, TOOL)
    assert result.data["knowledge_state"] == "VERSION_PROBED"
    assert result.data["execution_support_promoted"] is False
    evidence = probes.read_probe(policy, TOOL)
    assert evidence is not None and evidence["checks"]["checkpoint_restored"]
    policy.path(result.evidence_paths[-1]).write_bytes(b"changed after publication")
    with pytest.raises(InputError, match="checkpoint bytes changed"):
        probes.read_probe(policy, TOOL)


@pytest.mark.blender
def test_real_modeling_probe_recovers_saved_baseline(tmp_path):
    result = probes.probe_tool(tmp_path, TOOL)
    assert result.status == "PASS", result.to_dict()
    observed = probes.read_probe(WorkspacePolicy(tmp_path), TOOL)
    assert observed is not None and observed["checks"] == probes.CHECKS[TOOL]
    assert (tmp_path / result.evidence_paths[-1]).is_file()
