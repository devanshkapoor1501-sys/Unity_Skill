"""Independent sampled-motion inspector; clip names alone are never evidence."""

import math
from typing import Any

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest


def inspect_motion(report: dict[str, Any]) -> dict[str, Any]:
    canonical_digest(report)
    try:
        if (
            report["family"] != "robot.modular.rigid.v1"
            or report["blender_version"] != "5.2.2"
            or report["root_motion"] != "IN_PLACE"
            or not all(
                report[k] is True
                for k in ("weights_complete", "sockets_preserved", "source_reopened")
            )
        ):
            raise ValueError(
                "Unsupported rig/version/root policy or incomplete source/skin/socket evidence"
            )
        bones = report["bones"]
        required = {"root", "body", "head", "upper_arm_l", "upper_arm_r", "thigh_l", "thigh_r"}
        if not required <= bones.keys():
            raise ValueError("Missing named joints")
        if any(module != bone or bone not in bones for module, bone in report["bindings"].items()):
            raise ValueError("Wrong semantic bone mapping")
        for bone in required - {"root", "body", "head"}:
            x = bones[bone]["head"][0]
            if (bone.endswith("_l") and x >= 0) or (bone.endswith("_r") and x <= 0):
                raise ValueError("Left/right bone orientation swapped")
        for name in ("Idle", "Walk"):
            clip = report["clips"][name]
            frames = clip["samples"]
            if (
                clip["slot_count"] != 1
                or clip["channelbag_count"] != 1
                or abs(clip["duration_seconds"] - 1) > 0.001
                or [f["frame"] for f in frames] != [1, 7, 13, 19, 25]
            ):
                raise ValueError("Missing action slot/channelbag/frame sample")
            for frame in frames:
                if (
                    frame["skin_error_m"] > 0.0001
                    or frame["socket_error_m"] > 0.0001
                    or math.dist(frame["root_position"], frames[0]["root_position"]) > 0.0001
                ):
                    raise ValueError("Detached skin/socket or moving root")
                if set(frame["angles"]) != set(bones):
                    raise ValueError("Missing sampled bones")
            if name == "Walk":
                for bone in ("thigh_l", "thigh_r", "upper_arm_l", "upper_arm_r"):
                    values = [f["angles"][bone] for f in frames]
                    if max(values) - min(values) < 0.5 or abs(values[0] - values[-1]) > 0.001:
                        raise ValueError("Walk limb is static or does not loop")
                if frames[1]["angles"]["thigh_l"] * frames[1]["angles"]["thigh_r"] >= 0:
                    raise ValueError("Walk does not alternate legs")
            elif not 0.001 < max(abs(f["angles"]["body"]) for f in frames) < 0.1:
                raise ValueError("Idle body motion absent or excessive")
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        raise InputError(
            "Motion inspection failed: " + str(exc), kind=ErrorKind.CONTRACT_FAILURE
        ) from exc
    return {
        "status": "PASS",
        "family": report["family"],
        "root_motion": "IN_PLACE",
        "inspector": "PUBLIC_TECHNICAL_SAMPLES",
        "visual_review": "REVIEW",
        "hidden_evaluation": "NOT_RUN",
    }
