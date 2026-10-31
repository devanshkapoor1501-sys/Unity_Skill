"""Frozen plan tampering and unavailable OS observations must fail closed."""

import copy
import ctypes
import sys
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace

import pytest

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, canonical_digest
from polyforge.security.paths import WorkspacePolicy
from polyforge.workforce import discovery
from polyforge.workforce.models import resume_plan, validate_review, validate_task
from polyforge.workforce.router import plan_task


@pytest.fixture
def task_request():
    return {
        "schema_version": "1.0.0",
        "brief": "Make an editable crate",
        "task_class": "CREATE_ASSET",
        "domain_tags": ["blender"],
        "feature_ids": ["editable"],
        "capability_id": "mesh.props.crate.v1",
        "input": {
            "schema_version": "1.0.0",
            "asset_id": "crate",
            "parameters": {"size_m": [1, 1, 1]},
        },
        "resources": {"min_available_ram_bytes": 2_000_000},
    }


@pytest.fixture
def plans(task_request):
    fresh = plan_task(task_request)
    return copy.deepcopy(fresh), fresh


@pytest.mark.parametrize("changed", ["request", "job_count"])
def test_resume_rejects_changed_frozen_identity_or_missing_work(plans, changed):
    stored, fresh = plans
    if changed == "request":
        stored["original_request"]["brief"] = "Make a different asset"
    else:
        stored["jobs"].pop()
    with pytest.raises(InputError, match="frozen task identity"):
        resume_plan(stored, fresh)


@pytest.mark.parametrize("legacy", [False, True])
def test_resume_rejects_changed_job_budget_even_without_context(plans, legacy):
    stored, fresh = plans
    job = stored["jobs"][1]
    if legacy:
        job.pop("context")
        job.pop("context_digest")
    job["budget_seconds"] = 1
    with pytest.raises(InputError, match="job contract changed"):
        resume_plan(stored, fresh)


def test_resume_detects_context_tampering_before_allowing_probe_refresh(plans):
    stored, fresh = plans
    stored["jobs"][1]["context"]["seed"] = 123
    with pytest.raises(InputError, match="context digest mismatch"):
        resume_plan(stored, fresh)


@pytest.mark.parametrize("field", ["resources", "tool_allowlist"])
def test_rehashed_context_cannot_relax_budget_or_expand_tools(plans, field):
    stored, fresh = plans
    job = stored["jobs"][1]
    job["context"][field] = (
        {"min_available_ram_bytes": 0} if field == "resources" else ["shell.execute"]
    )
    job["context_digest"] = canonical_digest(job["context"])
    with pytest.raises(InputError, match="beyond a probe refresh"):
        resume_plan(stored, fresh)


def test_legacy_resource_omission_does_not_exempt_other_context_from_integrity(plans):
    stored, fresh = plans
    job = stored["jobs"][1]
    job["context"].pop("resources")
    job["context"]["authorized_write_roots"] = ["outside/"]
    job["context_digest"] = canonical_digest(job["context"])
    with pytest.raises(InputError, match="beyond a probe refresh"):
        resume_plan(stored, fresh)


def test_resume_accepts_probe_refresh_without_relabeling_historical_evidence(plans):
    stored, fresh = plans
    before = copy.deepcopy(stored)
    for job in fresh["jobs"]:
        job["context"]["toolchain_probes"] = [
            {"tool": "blender", "status": "VERSION_PROBED", "evidence_digest": "b" * 64}
        ]
        job["context_digest"] = canonical_digest(job["context"])
    resumed = resume_plan(stored, fresh)
    assert resumed is stored
    assert resumed == before
    assert resumed["jobs"][1]["context"]["resources"] == {"min_available_ram_bytes": 2_000_000}
    assert (
        resumed["jobs"][1]["context"]["toolchain_probes"]
        != fresh["jobs"][1]["context"]["toolchain_probes"]
    )


def test_resume_rejects_incomplete_context_digest_pair(plans):
    stored, fresh = plans
    stored["jobs"][1].pop("context_digest")
    with pytest.raises(InputError):
        resume_plan(stored, fresh)


def test_non_ascii_whitespace_is_not_a_task_brief(task_request):
    task_request["brief"] = "\t\r\n\u00a0"
    with pytest.raises(InputError, match="brief cannot be blank"):
        validate_task(task_request)


@pytest.mark.parametrize("evidence", [r"runs\..\outside.json", r"runs/review\..\outside.json"])
def test_mixed_separator_traversal_in_later_review_evidence_is_rejected(evidence):
    review = {
        "schema_version": "1.0.0",
        "artifact_id": "crate",
        "candidate_digest": "a" * 64,
        "producer_id": "producer",
        "reviewer_id": "inspector",
        "verdict": "APPROVED",
        "independence": "DIFFERENT_ROLE_SAME_HOST",
        "evidence": ["runs/review.json", evidence],
    }
    with pytest.raises(InputError, match="escape its workspace"):
        validate_review(review)
    review["evidence"] = [r"runs\crate..draft\review.json"]
    assert validate_review(review) is None


@pytest.mark.parametrize(
    "meminfo,expected_ram",
    [
        ("MemTotal: 9999 kB\nMemAvailable: 2048 kB\nCached: 512 kB\n", 2_097_152),
        ("MemTotal: 9999 kB\nCached: 512 kB\n", None),
        ("MemAvailable: unavailable kB\n", None),
        (None, None),
    ],
)
def test_linux_ram_observation_uses_available_memory_and_keeps_failures_unknown(
    tmp_path, monkeypatch, meminfo, expected_ram
):
    read_text = Path.read_text

    def read_os_metadata(path, *args, **kwargs):
        if path == Path("/proc/meminfo"):
            if meminfo is None:
                raise PermissionError("procfs denied")
            return meminfo
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(discovery, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setattr(Path, "read_text", read_os_metadata)
    observed = discovery.resource_usage(WorkspacePolicy(tmp_path))
    assert observed["available_ram_bytes"] == expected_ram
    if expected_ram is None:
        with pytest.raises(InputError) as error:
            discovery.check_resource_floors(observed, {"min_available_ram_bytes": 1})
        assert error.value.kind == ErrorKind.POLICY_DENIED
    else:
        discovery.check_resource_floors(observed, {"min_available_ram_bytes": 2_097_152})


@pytest.mark.parametrize("success", [False, True])
def test_windows_memory_api_failure_does_not_trust_populated_buffer(tmp_path, monkeypatch, success):
    def memory_status(pointer):
        pointer._obj.available = 2_097_152
        return int(success)

    monkeypatch.setattr(discovery, "sys", SimpleNamespace(platform="win32"))
    monkeypatch.setattr(
        ctypes,
        "windll",
        SimpleNamespace(kernel32=SimpleNamespace(GlobalMemoryStatusEx=memory_status)),
        raising=False,
    )
    observed = discovery.resource_usage(WorkspacePolicy(tmp_path))
    assert observed["available_ram_bytes"] == (2_097_152 if success else None)


@pytest.mark.parametrize("capacity", ["0", str(2**63)])
def test_linux_adapter_with_invalid_capacity_remains_metadata_only(tmp_path, capacity):
    device = tmp_path / "card0" / "device"
    device.mkdir(parents=True)
    (device / "vendor").write_text("0x1002", encoding="utf-8")
    (device / "device").write_text("0x73bf", encoding="utf-8")
    (device / "mem_info_vram_total").write_text(capacity, encoding="utf-8")
    observed = discovery.gpu_metadata(platform="linux", drm_root=tmp_path)
    assert observed["gpu_observation"] == "METADATA_ONLY"
    assert observed["gpu_execution"] == "UNVERIFIED"
    assert observed["vram_bytes"] is None
    assert observed["adapters"][0]["vram_bytes"] is None


def test_windows_unreadable_adapter_does_not_hide_readable_sibling(monkeypatch):
    def open_key(root, name):
        if name == "0000":
            raise PermissionError("adapter metadata denied")
        return nullcontext(name)

    def enum_key(root, index):
        if index < 2:
            return ("0000", "0001")[index]
        raise OSError("end of adapters")

    def query_value(key, field):
        if field == "DriverDesc":
            return "Readable adapter", 1
        return (2**30).to_bytes(4, "little"), 3

    monkeypatch.setitem(
        sys.modules,
        "winreg",
        SimpleNamespace(
            HKEY_LOCAL_MACHINE=1,
            OpenKey=open_key,
            EnumKey=enum_key,
            QueryValueEx=query_value,
        ),
    )
    observed = discovery.gpu_metadata(platform="win32")
    assert observed["adapters"] == [
        {
            "name": "Readable adapter",
            "vram_bytes": 1_073_741_824,
            "source": "WINDOWS_DISPLAY_CLASS_REGISTRY",
        }
    ]
    assert observed["gpu_execution"] == "UNVERIFIED"


@pytest.mark.parametrize("unknown", ["cpu_count", "disk_free_bytes"])
def test_discovery_blocks_all_native_workers_when_default_floor_is_unknown(
    tmp_path, monkeypatch, unknown
):
    measured = {"cpu_count": 4, "disk_free_bytes": 2_000_000, "available_ram_bytes": None}
    measured[unknown] = None
    monkeypatch.setattr(discovery, "resource_usage", lambda policy: dict(measured))
    monkeypatch.setattr(discovery, "hardware_fingerprint", lambda: {})
    monkeypatch.setattr(discovery, "discover_tool", lambda *args: None)
    monkeypatch.setattr(
        discovery,
        "gpu_metadata",
        lambda: {
            "gpu_observation": "UNKNOWN",
            "gpu_execution": "UNVERIFIED",
            "vram_bytes": None,
            "adapters": [],
        },
    )
    observed = discovery.discover(WorkspacePolicy(tmp_path))
    assert observed["resource_mode"] == "BLOCKED"
    assert observed["max_parallel_blender"] == observed["max_parallel_unity"] == 0
    assert observed["max_parallel_model"] == 0
    assert not list(tmp_path.iterdir())
