"""Bounded model/material/refine/inspect workflow using registered primitive workers."""

import copy
import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import uuid4

from polyforge.assets.contracts import inspect_bundle, seal_bundle, validate_spec
from polyforge.blender.adapter import execute_recipe
from polyforge.blender.recipes import expand_recipe
from polyforge.capabilities.protocol import RunContext
from polyforge.contracts.results import ErrorKind, Result, failure
from polyforge.contracts.validation import canonical_digest, validate_schema
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.unity.bridge import configuration
from polyforge.workforce.ledger import JobLedger


def material_plan(spec: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": spec["asset_id"],
        "spec_digest": canonical_digest(spec),
        "material": copy.deepcopy(spec["material"]),
        "shader": "Universal Render Pipeline/Lit",
        "roughness_mapping": "smoothness=1-roughness",
        "textures": [],
        "provenance": "ORIGINAL_REGISTERED_PALETTE",
        "source_license": spec["source_license"],
    }


def build_asset(inputs: dict[str, Any], context: RunContext) -> Result:
    validate_schema(inputs, "asset_build.schema.json")
    spec = validate_spec(inputs["spec"], context.workspace)
    configuration(WorkspacePolicy(context.workspace))
    if context.dry_run:
        return Result(
            data={"execution_status": "NOT_RUN", "dry_run": True, "asset_id": spec["asset_id"]}
        )
    identity = "asset_" + (context.operation_id or uuid4().hex)
    ledger = JobLedger(context.workspace, identity)
    prior = ledger.completed("asset")
    if prior is not None:
        inspect_bundle(context.workspace, prior["bundle"], spec)
        return Result(**{k: v for k, v in prior["result"].items() if k != "operation_status"})
    lease = ledger.claim("asset", spec["asset_id"])
    policy = ledger.policy
    relative = "runs/" + identity
    start = time.monotonic()
    recipe = expand_recipe(
        spec["kind"],
        {
            "schema_version": "1.0.0",
            "asset_id": spec["asset_id"],
            "parameters": {"size_m": spec["dimensions_m"]},
        },
        seed=context.seed,
    )
    history = []
    trace = [{"role": "asset_architect", "state": "PLANNED", "spec_digest": canonical_digest(spec)}]
    try:
        atomic_json(policy, relative + "/spec.json", spec)
        with ThreadPoolExecutor(max_workers=1) as pool:
            material_future = pool.submit(material_plan, spec)
            for revision in (1, 2):
                if context.cancel is not None and context.cancel.is_set():
                    ledger.cancel("asset")
                    return failure(ErrorKind.INTERRUPTED, "PF-ASSET-CANCELLED", "Asset cancelled")
                result = execute_recipe(
                    recipe,
                    replace(context, run_id=identity + "_r" + str(revision)),
                    audit_export=True,
                )
                if result.status != "PASS":
                    ledger.cancel("asset")
                    return result
                folder = Path(result.data["source_blend"]).parent
                slots = {
                    name: (folder / file).as_posix()
                    for name, file in {
                        "geometry_source": "source.blend",
                        "uv_source": "logical-geometry.json",
                        "material_source": "material.json",
                        "export": "asset.fbx",
                        "geometry_metrics": "metrics.json",
                    }.items()
                }
                bundle = seal_bundle(
                    context.workspace,
                    spec,
                    slots,
                    revision=revision,
                    producer="modeler" if revision == 1 else "asset_refiner",
                )
                review = inspect_bundle(context.workspace, bundle, spec)
                history.append(review)
                atomic_json(
                    policy,
                    relative + f"/revision-{revision}.json",
                    {"bundle": bundle, "inspection": review},
                )
                trace.extend(
                    [
                        {
                            "role": bundle["producer_id"],
                            "state": "PRODUCED",
                            "revision_digest": bundle["revision_digest"],
                        },
                        {
                            "role": "asset_quality_inspector",
                            "state": review["technical_verdict"],
                            "revision_digest": bundle["revision_digest"],
                        },
                    ]
                )
                if review["technical_verdict"] == "APPROVED":
                    break
                plan = material_future.result()
                atomic_json(policy, relative + "/material-plan.json", plan)
                trace.append(
                    {"role": "uv_material_artist", "state": "PROPOSED", "scope": review["issues"]}
                )
                if revision == 2 or any(
                    not issue.startswith("material.") for issue in review["issues"]
                ):
                    ledger.cancel("asset")
                    atomic_json(policy, relative + "/trace.json", trace)
                    return failure(
                        ErrorKind.CONTRACT_FAILURE,
                        "PF-ASSET-REJECTED",
                        "Scoped refinement cannot satisfy: " + str(review["issues"]),
                    )
                recipe = copy.deepcopy(recipe)
                for material in recipe["materials"]:
                    material.update(
                        color_rgba=plan["material"]["base_color_rgba"],
                        metallic=plan["material"]["metallic"],
                        roughness=plan["material"]["roughness"],
                    )
        ready = not spec["visual_approval_required"]
        atomic_json(policy, relative + "/trace.json", trace)
        atomic_json(policy, relative + "/bundle.json", bundle)
        atomic_json(policy, relative + "/review.json", review)
        registered = [
            policy.path(relative + "/" + name)
            for name in ("spec.json", "bundle.json", "review.json", "trace.json")
        ] + [policy.path(item["path"]) for item in bundle["slots"].values()]
        atomic_json(
            policy,
            relative + "/artifacts.json",
            {
                "artifacts": [
                    {
                        "relative_path": p.relative_to(policy.root).as_posix(),
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "bytes": p.stat().st_size,
                    }
                    for p in registered
                ]
            },
        )
        result = Result(
            run_id=identity,
            input_digest=canonical_digest(inputs),
            evaluated_test_status="PASS",
            data={
                "bundle": bundle,
                "review": review,
                "history": history,
                "trace": trace,
                "import_ready": ready,
                "visual_review": "REVIEW",
                "visual_confidence": None,
                "execution_mode": "LOCAL_MULTIROLE_SEQUENTIAL_WITH_MATERIAL_PLANNING",
                "evaluator_owner": "PUBLIC_DEVELOPMENT",
            },
            metrics={
                "workflow_seconds": round(time.monotonic() - start, 3),
                "production_attempts": len(history),
            },
            evidence_paths=[
                relative + "/bundle.json",
                relative + "/review.json",
                relative + "/trace.json",
                *[item["path"] for item in bundle["slots"].values()],
            ],
        )
        ledger.commit("asset", lease, {"bundle": bundle, "result": result.to_dict()})
        return result
    except Exception:
        ledger.cancel("asset")
        raise
