"""Independent motion requirements; source producers cannot decide their own verdict."""

import copy

import pytest

from polyforge.contracts.validation import InputError


def fixture():
    bones = ["root", "body", "head", "upper_arm_l", "upper_arm_r", "thigh_l", "thigh_r"]
    rest = {
        b: {
            "head": [-1 if b.endswith("_l") else 1 if b.endswith("_r") else 0, 0, 1],
            "parent": "" if b == "root" else "root" if b == "body" else "body",
        }
        for b in bones
    }
    clips = {}
    for name in ["Idle", "Walk"]:
        frames = []
        for f in [1, 7, 13, 19, 25]:
            phase = {1: 0, 7: 1, 13: 0, 19: -1, 25: 0}[f]
            angles = {
                b: phase * (0.4 if name == "Walk" else 0.02) * (-1 if b.endswith("_r") else 1)
                for b in bones
            }
            angles["root"] = 0
            frames.append(
                {
                    "frame": f,
                    "angles": angles,
                    "root_position": [0, 0, 0],
                    "skin_error_m": 0,
                    "socket_error_m": 0,
                }
            )
        clips[name] = {
            "slot_count": 1,
            "channelbag_count": 1,
            "duration_seconds": 1,
            "samples": frames,
        }
    return {
        "schema_version": "1.0.0",
        "asset_id": "robot_a",
        "family": "robot.modular.rigid.v1",
        "blender_version": "5.2.2",
        "root_motion": "IN_PLACE",
        "bones": rest,
        "bindings": {b: b for b in bones if b != "root"},
        "clips": clips,
        "source_reopened": True,
        "weights_complete": True,
        "sockets_preserved": True,
    }


def test_motion_contract_rejects_wrong_mapping_detachment_and_root_motion():
    from polyforge.animation.contract import inspect_motion

    assert inspect_motion(fixture())["status"] == "PASS"
    for mutate in [
        lambda r: r["bindings"].update(thigh_l="thigh_r"),
        lambda r: r["clips"]["Walk"]["samples"][1].update(skin_error_m=0.5),
        lambda r: r["clips"]["Walk"]["samples"][1].update(root_position=[1, 0, 0]),
        lambda r: r["clips"].pop("Idle"),
        lambda r: r.update(weights_complete=False),
        lambda r: r["clips"]["Walk"]["samples"][1]["angles"].update(thigh_l=0, thigh_r=0),
        lambda r: r["bones"]["thigh_l"].update(head=[1, 0, 1]),
    ]:
        report = copy.deepcopy(fixture())
        mutate(report)
        with pytest.raises(InputError):
            inspect_motion(report)


def test_animation_invalid_and_dry_run_write_nothing(tmp_path):
    from polyforge.animation.adapter import animate_robot
    from polyforge.capabilities.protocol import RunContext

    request = {
        "schema_version": "1.0.0",
        "asset_id": "robot_a",
        "parameters": {"size_m": [1, 2, 1]},
    }
    assert animate_robot(request, RunContext(tmp_path, dry_run=True)).status == "PASS"
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(InputError):
        animate_robot({**request, "asset_id": "../bad"}, RunContext(tmp_path))
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "fault", ["family", "bones", "slot", "frames", "angles", "idle", "opposed"]
)
def test_missing_or_incompatible_motion_evidence_fails(fault):
    from polyforge.animation.contract import inspect_motion

    report = fixture()
    if fault == "family":
        report["family"] = "humanoid.untested"
    elif fault == "bones":
        report["bones"].pop("head")
    elif fault == "slot":
        report["clips"]["Walk"]["slot_count"] = 0
    elif fault == "frames":
        report["clips"]["Walk"]["samples"].pop()
    elif fault == "angles":
        report["clips"]["Walk"]["samples"][1]["angles"].pop("head")
    elif fault == "idle":
        for frame in report["clips"]["Idle"]["samples"]:
            frame["angles"]["body"] = 0
    else:
        for frame in report["clips"]["Walk"]["samples"]:
            frame["angles"]["thigh_r"] = frame["angles"]["thigh_l"]
    with pytest.raises(InputError):
        inspect_motion(report)
