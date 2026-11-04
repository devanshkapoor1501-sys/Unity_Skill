"""Application-aware managed rollback with resumable proof and quarantine."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.runner.locks import unity_project_lock
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.security.policy import redact
from polyforge.unity.bootstrap import check_project_idle
from polyforge.unity.bridge import configuration, launch, unity_tool
from polyforge.unity.evidence import verify_test_xml
from polyforge.unity.transactions import ManagedTransaction, _registered_dependencies


def source_dependencies(policy: WorkspacePolicy) -> list[str]:
    """Select registered source bundles whose exports actually feed this project."""
    imported = {
        hashlib.sha256(policy.path(p).read_bytes()).hexdigest()
        for p in policy.path("UnityProject/Assets/PolyForgeGenerated").rglob("*")
        if p.is_file() and p.suffix.lower() in {".fbx", ".png"}
    }
    selected: set[str] = set()
    folders = sorted(
        policy.path("runs").glob("*/artifacts.json"),
        key=lambda p: p.stat().st_mtime_ns,
        reverse=True,
    )
    if len(folders) > 4096:
        raise InputError("Source dependency discovery exceeds bounded run inventory")
    owners: set[str] = set()
    for registry in folders:
        records = load_json(policy.path(registry)).get("artifacts", [])
        if not isinstance(records, list):
            raise InputError("Malformed source artifact registry")
        for artifact in records:
            if not isinstance(artifact, dict) or not isinstance(artifact.get("relative_path"), str):
                raise InputError("Malformed source artifact record")
            if artifact.get("sha256") not in imported:
                continue
            relative = policy.path(artifact["relative_path"]).relative_to(policy.root).as_posix()
            parts = relative.split("/")
            if len(parts) < 4 or parts[0] != "runs" or parts[2] != "asset":
                continue
            owner = "/".join(parts[:2])
            if owner in owners:
                continue
            if hashlib.sha256(policy.path(relative).read_bytes()).hexdigest() != artifact["sha256"]:
                raise InputError("Source export differs from the imported artifact identity")
            producer = load_json(policy.path(owner + "/artifacts.json"))["artifacts"]
            for item in producer:
                name = policy.path(item["relative_path"]).relative_to(policy.root).as_posix()
                if name.startswith(owner + "/asset/") and name.endswith(
                    (".blend", ".fbx", ".json", ".png")
                ):
                    selected.add(name)
            owners.add(owner)
    return sorted(selected)


def _profile_inputs(
    policy: WorkspacePolicy, recorded: dict[str, dict[str, str]] | None = None
) -> dict[str, dict[str, str]]:
    result = {}
    present = {
        name
        for name, marker in (
            ("animation", "Animation/AnimationArena.unity"),
            ("sprite", "Sprites/SpriteArena.unity"),
            ("platformer", "Platformer/SpritePlatformer.unity"),
        )
        if policy.path("UnityProject/Assets/PolyForgeGenerated/" + marker).is_file()
    }
    if recorded is not None and (not isinstance(recorded, dict) or set(recorded) != present):
        raise InputError("Native regression profile set changed after snapshot")
    for profile, pattern, marker in (
        ("animation", "animation-*/input.json", "Animation/AnimationArena.unity"),
        ("sprite", "sprite-unity-*/input.json", "Sprites/SpriteArena.unity"),
        ("platformer", "platformer-build-*/game-input.json", "Platformer/SpritePlatformer.unity"),
    ):
        if not policy.path("UnityProject/Assets/PolyForgeGenerated/" + marker).is_file():
            continue
        candidates = sorted(
            policy.path("runs").glob(pattern), key=lambda p: p.stat().st_mtime_ns, reverse=True
        )
        if recorded is not None:
            item = recorded[profile]
            if (
                not isinstance(item, dict)
                or set(item) != {"path", "sha256"}
                or any(not isinstance(item[k], str) for k in ("path", "sha256"))
                or not re.fullmatch(r"[a-f0-9]{64}", item["sha256"])
                or not re.fullmatch(
                    r"(?:\.polyforge/native-inputs/"
                    + profile
                    + r"/[a-f0-9]{64}\.json|runs/"
                    + {
                        "animation": "animation-",
                        "sprite": "sprite-unity-",
                        "platformer": "platformer-build-",
                    }[profile]
                    + r"[A-Za-z0-9_-]{1,80}/"
                    + (r"game-input\.json)" if profile == "platformer" else r"input\.json)"),
                    item["path"],
                )
            ):
                raise InputError("Recorded native input is outside the registered profile")
            candidates = [policy.path(item["path"])]
            if hashlib.sha256(candidates[0].read_bytes()).hexdigest() != item["sha256"]:
                raise InputError("Recorded native regression input changed after snapshot")
        for source in candidates:
            source = policy.path(source)
            job = load_json(source)
            if not isinstance(job, dict) or (
                profile == "animation" and not isinstance(job.get("model_path"), str)
            ):
                raise InputError("Malformed native regression input document")
            if profile == "platformer":
                sources = job.get("source_hashes")
                if (
                    not isinstance(sources, dict)
                    or not sources
                    or canonical_digest(
                        {k: v for k, v in job.items() if k != "game_contract_digest"}
                    )
                    != job.get("game_contract_digest")
                ):
                    raise InputError("Platformer regression contract identity is invalid")
                for name, expected_source in sources.items():
                    source_path = policy.path(name)
                    if (
                        not isinstance(expected_source, str)
                        or not re.fullmatch(r"[a-f0-9]{64}", expected_source)
                        or not source_path.is_file()
                        or hashlib.sha256(source_path.read_bytes()).hexdigest() != expected_source
                    ):
                        raise InputError("Platformer regression source identity changed")
            model = (
                "UnityProject/" + job["model_path"]
                if profile == "animation"
                else "UnityProject/Assets/PolyForgeGenerated/Sprites/atlas.png"
            )
            expected = (
                job.get("expected_fbx_sha256")
                if profile == "animation"
                else job.get("atlas_sha256")
            )
            if (
                policy.path(model).is_file()
                and hashlib.sha256(policy.path(model).read_bytes()).hexdigest() == expected
            ):
                if recorded is not None:
                    result[profile] = recorded[profile]
                else:
                    archived = (
                        ".polyforge/native-inputs/"
                        + profile
                        + "/"
                        + canonical_digest(job)
                        + ".json"
                    )
                    if policy.path(archived).is_file():
                        if load_json(policy.path(archived)) != job:
                            raise InputError("Immutable native input archive was changed")
                    else:
                        atomic_json(policy, archived, job)
                    result[profile] = {
                        "path": archived,
                        "sha256": hashlib.sha256(policy.path(archived).read_bytes()).hexdigest(),
                    }
                break
        if profile not in result:
            raise InputError(
                "Cannot reconstruct current native " + profile + " inputs from registered runs"
            )
    return result


def observe_state(
    policy: WorkspacePolicy,
    relative: str,
    *,
    restore: bool = False,
    profile_inputs: dict[str, dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Called only while the physical project lock is held by this engine flow."""
    from polyforge.unity.game import verify_game
    from polyforge.unity.repairs import current_request

    check_project_idle(policy)
    current_request(policy)
    config = configuration(policy)
    executable = unity_tool(config)
    output = policy.path(relative + "/bindings.json")
    launch(
        policy,
        executable,
        config,
        relative + "/native",
        "restore" if restore else "reconcile",
        request=policy.path(".polyforge/unity-request.json"),
        output=output,
        allow_contract_failure=True,
    )
    identities = policy.path(relative + "/asset-identities.json")
    launch(policy, executable, config, relative + "/identity", "recovery", output=identities)
    native_assets = load_json(identities, max_bytes=33_554_432)
    if (
        native_assets.get("schema_version") != "1.0.0"
        or native_assets.get("unity_version") != "6000.6.3f1"
        or not native_assets.get("assets")
    ):
        raise InputError("Native recovery identity inventory is incomplete")
    regressions: dict[str, Any] = {}
    if policy.path(".polyforge/game-latest.json").is_file():
        checked = verify_game(policy.root, _lock_held=True)
        atomic_json(policy, relative + "/arena-result.json", checked.to_dict())
        oracles = checked.data.get("oracles", checked.data)
        if not isinstance(oracles.get("scenarios"), dict) or not oracles["scenarios"]:
            raise InputError("Native arena regression did not produce scored scenarios")
        regressions["arena"] = {
            "status": oracles["status"],
            "scenarios": {k: v["gate_status"] for k, v in oracles["scenarios"].items()},
        }
    discovered = _profile_inputs(policy, profile_inputs)
    profiles = discovered
    for profile, item in profiles.items():
        request = policy.path(item["path"])
        if hashlib.sha256(request.read_bytes()).hexdigest() != item["sha256"]:
            raise InputError("Native regression input changed after snapshot")
        if profile == "platformer":
            from polyforge.unity.platformer import execute_platformer_checks

            checked = execute_platformer_checks(policy, load_json(request), _lock_held=True)
            atomic_json(policy, relative + "/platformer-result.json", checked.to_dict())
            oracles = checked.data.get("oracles", {})
            if not isinstance(oracles.get("scenarios"), dict) or not oracles["scenarios"]:
                raise InputError("Native platformer regression did not produce scored scenarios")
            regressions[profile] = {
                "status": oracles["status"],
                "scenarios": {k: v["gate_status"] for k, v in oracles["scenarios"].items()},
            }
            continue
        if profile == "animation":
            from polyforge.animation.integration import EDIT_TESTS, PLAY_TESTS

            namespaces = ("PolyForge.Animation.Editor.Tests", "PolyForge.Animation.Tests")
        elif profile == "sprite":
            from polyforge.sprites.integration import EDIT_TESTS, PLAY_TESTS

            namespaces = ("PolyForge.Sprite.Editor.Tests", "PolyForge.Sprite.Tests")
        else:
            raise InputError("Unknown recovery native regression profile")
        results = {}
        for platform, names, namespace in zip(
            ("EditMode", "PlayMode"), (EDIT_TESTS, PLAY_TESTS), namespaces, strict=True
        ):
            xml = policy.path(relative + "/" + profile + "/" + platform + ".xml")
            launch(
                policy,
                executable,
                config,
                relative + "/" + profile + "/" + platform,
                "tests",
                game_input=request,
                output=xml,
                test_platform=platform,
                test_filter=namespace,
            )
            results[platform] = verify_test_xml(xml, names)
        regressions[profile] = results
    return {
        "bindings": load_json(output),
        "native_assets": native_assets,
        "regressions": regressions,
        "profile_inputs": profiles,
        "proof_scope": "NATIVE_REIMPORT_AND_REGRESSION",
    }


def prepare_transaction(
    policy: WorkspacePolicy,
    identifier: str,
    *,
    dependencies: list[str] | None = None,
) -> ManagedTransaction:
    ManagedTransaction(policy, identifier)  # Validate identity before locks/native side effects.
    if policy.path("transactions/" + identifier).exists():
        raise InputError("Transaction already exists")
    if dependencies is not None:
        _registered_dependencies(policy, dependencies)
    with unity_project_lock(policy, policy.path("UnityProject")):
        requested = sorted(set(source_dependencies(policy)) | set(dependencies or []))
        _registered_dependencies(policy, requested)
        prestate = observe_state(policy, "runs/recovery-baseline-" + identifier)
        tx = ManagedTransaction.create(
            policy,
            identifier,
            dependencies=requested,
        )
        tx.record("BASELINE", prestate=prestate, proof_scope="NATIVE_REIMPORT_AND_REGRESSION")
        return tx


def rollback_locked(policy: WorkspacePolicy, tx: ManagedTransaction) -> Result:
    from polyforge.unity.repairs import equivalent_bindings

    journal = tx.read()
    baseline = journal.get("prestate")
    if not isinstance(baseline, dict):
        raise InputError(
            "Legacy transaction lacks application prestate; cannot claim verified rollback"
        )
    attempt = tx.relative + "/recovery/attempt-" + uuid4().hex[:16]
    tx.record(
        "ROLLING_BACK",
        recovery_attempt=attempt,
        recovery_attempts=[*journal.get("recovery_attempts", []), attempt],
    )
    try:
        tx.restore()
        if not tx.verify_restored():
            raise InputError("Restored bytes do not match the source snapshot")
        after = observe_state(
            policy,
            attempt,
            restore=True,
            profile_inputs=baseline["profile_inputs"],
        )
        if not equivalent_bindings(baseline, after) or not tx.verify_restored():
            raise InputError(
                "Native identities/references, scenarios or source hashes differ from prestate"
            )
        tx.record("ROLLED_BACK", recovery=after, bytes_match=True)
        policy.path("UnityProject/.polyforge/repair-quarantine.json").unlink(missing_ok=True)
        return Result(
            rollback_id=tx.identifier,
            evaluated_test_status="PASS",
            data={"repair_status": "ROLLED_BACK", "proof_scope": "NATIVE_REIMPORT_AND_REGRESSION"},
            evidence_paths=[tx.relative + "/journal.json"],
        )
    except (InputError, OSError, KeyboardInterrupt) as exc:
        tx.record("ROLLBACK_FAILED", recovery_failure=redact(str(exc)))
        atomic_json(
            policy,
            "UnityProject/.polyforge/repair-quarantine.json",
            {
                "transaction_id": tx.identifier,
                "status": "ROLLBACK_FAILED",
                "reason": redact(str(exc)),
            },
        )
        from dataclasses import replace

        return replace(
            failure(
                ErrorKind.CONTRACT_FAILURE,
                "PF-ROLLBACK-FAILED",
                "Native recovery could not reproduce prestate; managed project quarantined",
            ),
            rollback_id=tx.identifier,
            evidence_paths=[tx.relative + "/journal.json"],
        )


def repair_rollback(workspace: Path, transaction_id: str) -> Result:
    policy = WorkspacePolicy(workspace)
    tx = ManagedTransaction(policy, transaction_id)
    tx.read()  # Reject unknown/malformed transactions before creating a lock or directory.
    with unity_project_lock(policy, policy.path("UnityProject"), recovery=True):
        marker = policy.path("UnityProject/.polyforge/repair-quarantine.json")
        if marker.is_file():
            quarantine = load_json(marker)
            if (
                not isinstance(quarantine, dict)
                or quarantine.get("transaction_id") != transaction_id
            ):
                raise InputError(
                    "Another transaction owns this recovery quarantine",
                    kind=ErrorKind.POLICY_DENIED,
                )
        return rollback_locked(policy, tx)


def resume_run(workspace: Path, run_id: str) -> Result:
    if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise InputError("Invalid recorded run identity")
    policy = WorkspacePolicy(workspace)
    if run_id.startswith("forensic-") and policy.path("runs/" + run_id + "/intent.json").is_file():
        from polyforge.repairs.execution import resume_forensic

        return resume_forensic(policy, run_id)
    journal = policy.path("transactions/" + run_id + "/journal.json")
    if journal.is_file():
        transaction = ManagedTransaction(policy, run_id)
        status = transaction.read()["status"]
        if status == "COMMITTED":
            raise InputError(
                "Committed repairs are not automatically replayed; explicitly rollback if required"
            )
        if status == "ROLLED_BACK" and not transaction.verify_restored():
            raise InputError(
                "Recovered workspace changed afterward; explicit reviewed rollback is required"
            )
        return repair_rollback(workspace, run_id)
    plan = policy.path("workforce/" + run_id + "/plan.json")
    if plan.is_file():
        from polyforge.workforce.orchestrator import run_task
        from polyforge.workforce.router import plan_task

        saved = load_json(plan)
        if (
            not isinstance(saved, dict)
            or not isinstance(saved.get("task_id"), str)
            or not isinstance(saved.get("original_request"), dict)
        ):
            raise InputError("Malformed workforce resume plan")
        if run_id not in {saved["task_id"], saved["task_id"] + "_single"}:
            raise InputError("Recorded workforce ledger identity differs from the plan")
        if plan_task(saved["original_request"], workspace=workspace) != saved:
            raise InputError("Recorded workforce inputs changed; cannot safely resume")
        return run_task(
            workspace,
            saved["original_request"],
            mode="single" if run_id.endswith("_single") else "sequential",
        )
    raise InputError(
        "No safely reconstructable transaction/workforce run; original stage inputs are required"
    )
