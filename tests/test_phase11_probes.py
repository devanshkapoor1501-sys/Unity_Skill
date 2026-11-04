"""Unfamiliar API probes remain fixed, version bound and limited in authority."""

from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError
from polyforge.knowledge import probes
from polyforge.security.paths import WorkspacePolicy


@pytest.mark.parametrize(
    "tool,identifier,version",
    [
        ("blender-bvh", "blender.bvh-ray.v1", "5.2.2"),
        ("unity-pool", "unity.object-pool.v1", "6000.6.3f1"),
    ],
)
def test_unfamiliar_probe_is_fixed_and_changed_version_cannot_qualify(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    tool: str,
    identifier: str,
    version: str,
) -> None:
    monkeypatch.setattr(probes, "discover_tool", lambda *a: Path("fixed-tool.exe"))
    dry = probes.probe_tool(tmp_path, tool, dry_run=True)
    assert dry.data["probe_id"] == identifier
    assert dry.data["execution_status"] == "NOT_RUN"
    assert not list(tmp_path.iterdir())
    observation = {
        "schema_version": "1.0.0",
        "probe_id": identifier,
        "tool_version": version,
        "checks": dict(probes.CHECKS[tool]),
        "artifacts": [],
    }
    result = probes.validate_observation(tool, observation)
    assert result["knowledge_state"] == "VERSION_PROBED"
    assert result["execution_support_promoted"] is False
    with pytest.raises(InputError):
        probes.validate_observation(tool, {**observation, "tool_version": "changed-version"})
    for check in observation["checks"]:
        with pytest.raises(InputError):
            probes.validate_observation(
                tool,
                {
                    **observation,
                    "checks": {**observation["checks"], check: not observation["checks"][check]},
                },
            )


@pytest.mark.parametrize("tool", ["blender-bvh", "unity-pool"])
def test_unfamiliar_probe_uses_correct_registered_application(tmp_path: Path, tool: str) -> None:
    from polyforge.cli import build_parser

    arguments = build_parser().parse_args(
        [
            "knowledge",
            "probe",
            "--tool",
            tool,
            "--workspace",
            str(tmp_path),
            "--dry-run",
        ]
    )
    assert arguments.tool == tool
    policy = WorkspacePolicy(tmp_path)
    argv = probes._args(policy, Path("fixed-tool.exe"), tool, "runs/knowledge-test")
    if tool == "blender-bvh":
        assert "--background" in argv and "--python" in argv and "-executeMethod" not in argv
        assert argv[argv.index("--python") + 1].endswith("probe.py")
    else:
        assert "-batchmode" in argv and "-nographics" in argv
        assert argv[argv.index("-executeMethod") + 1] == "PolyForgeKnowledgeProbe.Run"
    assert probes._source(tool)


def test_unknown_api_router_remains_discovery_without_execution_authority(tmp_path: Path) -> None:
    from polyforge.knowledge.router import route_reference

    routed = route_reference(
        WorkspacePolicy(tmp_path),
        {
            "schema_version": "1.0.0",
            "query": "Use an unfamiliar BVHTree ray query to design a new game",
            "output": "GAME",
            "domain": "blender",
        },
    )
    assert routed["status"] == "REVIEW"
    assert routed["capability_ids"] == []
    assert routed["discovery"]["execution_status"] == "BLOCKED"
