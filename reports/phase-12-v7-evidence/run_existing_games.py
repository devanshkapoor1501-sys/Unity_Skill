"""Recheck frozen public fixtures in a disposable independent workspace copy."""

import hashlib
import json
import shutil
from pathlib import Path

from polyforge.contracts.validation import load_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bootstrap import check_project_idle
from polyforge.unity.game import execute_game_checks
from polyforge.unity.platformer import execute_platformer_checks

repo = Path(__file__).resolve().parents[2]
source = (repo / ".tmp/phase12/v1-arena").resolve()
clone = (repo / ".tmp/v7games").resolve()
assert clone.is_relative_to(repo / ".tmp") and not clone.exists()
assert (source / "UnityProject/.polyforge-project.json").is_file()
assert not (source / "UnityProject/Temp/UnityLockfile").exists()
assert not any(path.is_symlink() or path.is_junction() for path in source.rglob("*"))


def inventory(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for scope in ("Assets", "Packages", "ProjectSettings")
        for path in (root / "UnityProject" / scope).rglob("*")
        if path.is_file()
    }


before = inventory(source)
receipt = {"scope": "PUBLIC_DEVELOPMENT", "standalone": "NOT_RUN", "games": {}}
try:
    shutil.copytree(
        source,
        clone,
        ignore=shutil.ignore_patterns("Temp", "Logs", "obj", ".UnityProject.polyforge.lock"),
    )
    assert inventory(clone) == before
    policy = WorkspacePolicy(clone)
    check_project_idle(policy)
    for name, pointer, check in (
        ("arena", "game-latest.json", execute_game_checks),
        ("platformer", "platformer-latest.json", execute_platformer_checks),
    ):
        latest = load_json(policy.path(".polyforge/" + pointer))
        # Pointers retain the public fixture's original build request.
        game = load_json(policy.path(latest["request"]))
        result = check(policy, game, standalone=False)
        receipt["games"][name] = result.to_dict()
        assert result.status == "PASS", result.to_dict()
finally:
    receipt["original_unchanged"] = inventory(source) == before
    receipt["source_inventory"] = before
    (Path(__file__).parent / "game-regressions.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    assert receipt["original_unchanged"]
print("PASS: arena and platformer EditMode/PlayMode/oracles; original project unchanged")
