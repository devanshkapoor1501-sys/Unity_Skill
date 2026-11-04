"""New game styles must join immutable native rollback regression profiles."""

import hashlib

import pytest

from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy


def fixture(tmp_path):
    policy = WorkspacePolicy(tmp_path)
    policy.mkdir("UnityProject/Assets/PolyForgeGenerated/Platformer")
    policy.path(
        "UnityProject/Assets/PolyForgeGenerated/Platformer/SpritePlatformer.unity"
    ).write_bytes(b"native scene")
    atlas = policy.path("UnityProject/Assets/PolyForgeGenerated/Sprites/atlas.png")
    policy.mkdir(atlas.parent)
    atlas.write_bytes(b"approved sprite atlas")
    job = {
        "schema_version": "1.0.0",
        "input_digest": "a" * 64,
        "atlas_sha256": hashlib.sha256(atlas.read_bytes()).hexdigest(),
        "source_hashes": {
            atlas.relative_to(policy.root).as_posix(): hashlib.sha256(
                atlas.read_bytes()
            ).hexdigest()
        },
    }
    job["game_contract_digest"] = canonical_digest(job)
    atomic_json(policy, "runs/platformer-build-first/game-input.json", job)
    return policy, job


def test_platformer_native_input_is_archived_and_reused_immutably(tmp_path):
    from polyforge.unity.recovery import _profile_inputs

    policy, job = fixture(tmp_path)
    profiles = _profile_inputs(policy)
    assert set(profiles) == {"platformer"}
    path = profiles["platformer"]["path"]
    assert path.startswith(".polyforge/native-inputs/platformer/")
    assert load_json(policy.path(path)) == job
    atomic_json(policy, "runs/platformer-build-first/game-input.json", {"tampered": True})
    assert _profile_inputs(policy, profiles) == profiles


def test_new_platformer_scene_cannot_be_omitted_from_recorded_regressions(tmp_path):
    from polyforge.unity.recovery import _profile_inputs

    policy, _ = fixture(tmp_path)
    with pytest.raises(InputError, match="profile set changed"):
        _profile_inputs(policy, {})


def test_changed_platformer_source_and_archived_input_fail_closed(tmp_path):
    from polyforge.unity.recovery import _profile_inputs

    policy, _ = fixture(tmp_path)
    profiles = _profile_inputs(policy)
    policy.path("UnityProject/Assets/PolyForgeGenerated/Sprites/atlas.png").write_bytes(b"changed")
    with pytest.raises(InputError):
        _profile_inputs(policy, profiles)
    policy.path(profiles["platformer"]["path"]).write_bytes(b"changed")
    with pytest.raises(InputError, match="input changed"):
        _profile_inputs(policy, profiles)
