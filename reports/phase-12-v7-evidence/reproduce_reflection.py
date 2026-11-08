"""Preserve the original failure with full native Unity transform diagnostics."""

import json
import shutil
from pathlib import Path

from polyforge.runner.locks import unity_project_lock
from polyforge.runner.processes import ProcessPolicy, run_process
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bridge import configuration, unity_tool

repo = Path(__file__).resolve().parents[2]
evidence = Path(__file__).parent
original = repo / ".tmp/phase12-v7-red-unrestricted"
policy = WorkspacePolicy(repo / ".tmp/v7u")
editor = unity_tool(configuration(policy))
models = json.loads(
    (original / "test_unity_imports_modeling_fa0/unity-input.json").read_text(encoding="utf-8")
)["models"]
model = next(row for row in models if row["path"].endswith("/compose_asset.fbx"))
model["path"] = "Assets/Phase12Models/coolant_regression.fbx"
request = policy.path("reflection-input.json")
request.write_text(json.dumps({"models": [model]}), encoding="utf-8")
receipt = policy.path("reflection-result.json")
project = policy.path("UnityProject")
with unity_project_lock(policy, project):
    shutil.copyfile(
        original / "phase12-blender0/runs/model-compose/asset/asset.fbx",
        project / model["path"],
    )
    shutil.copyfile(
        repo / "tests/fixtures/modeling/ModelingImportProbe.cs",
        project / "Assets/Editor/ModelingImportProbe.cs",
    )
    process = run_process(
        [
            str(editor),
            "-batchmode",
            "-nographics",
            "-quit",
            "-job-worker-count",
            "2",
            "-projectPath",
            str(project),
            "-logFile",
            "-",
            "-executeMethod",
            "ModelingImportProbe.Run",
            "-modelingInput",
            str(request),
            "-modelingResult",
            str(receipt),
        ],
        policy,
        "red-coordinate-process",
        ProcessPolicy((editor,), 300),
    )
observed = json.loads(receipt.read_text(encoding="utf-8"))
assert process.returncode != 0 and process.reason == "exit"
assert not observed["passed"] and "Socket outlet moved" in observed["error"]
(outlet,) = observed["observations"][0]["sockets"]
assert all(
    abs(a - b) < 0.000001 for a, b in zip(outlet["expected"], [0.9, 0.77, 0.35], strict=True)
)
assert all(abs(a - b) < 0.005 for a, b in zip(outlet["observed"], [-0.9, 0.77, 0.35], strict=True))
(evidence / "red-unity-frames.json").write_text(json.dumps(observed, indent=2), encoding="utf-8")
print("PASS: original FBX independently rejected at the exact reflected outlet; matrices retained")
