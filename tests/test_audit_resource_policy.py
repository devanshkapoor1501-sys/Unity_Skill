"""Resource admission, immutable job budgets and cancellation regressions."""

import copy
import threading

import pytest

from polyforge.contracts.results import Result
from polyforge.contracts.validation import InputError, canonical_digest, validate_schema
from polyforge.security.paths import WorkspacePolicy
from polyforge.workforce import discovery, orchestrator
from polyforge.workforce.ledger import JobLedger
from polyforge.workforce.models import resume_plan
from polyforge.workforce.router import plan_task


def request(resources=None):
    return {
        "schema_version": "1.0.0",
        "brief": "Make a crate",
        "task_class": "CREATE_ASSET",
        "domain_tags": ["blender"],
        "feature_ids": ["editable"],
        "capability_id": "mesh.props.crate.v1",
        "input": {
            "schema_version": "1.0.0",
            "asset_id": "crate",
            "parameters": {"size_m": [1, 1, 1]},
        },
        "resources": resources or {},
    }


def snapshot(**changes):
    return {
        "cpu_count": 4,
        "available_ram_bytes": 4_000_000,
        "disk_free_bytes": 4_000_000,
        "gpu_execution": "UNVERIFIED",
        **changes,
    }


def test_request_resource_floors_are_frozen_typed_job_metadata():
    value = request({"min_available_ram_bytes": 2_000_000})
    plan = plan_task(value)
    ticket = plan["jobs"][1]
    assert ticket["context"]["resources"] == {"min_available_ram_bytes": 2_000_000}
    value["resources"]["min_available_ram_bytes"] = 0
    assert ticket["context"]["resources"]["min_available_ram_bytes"] == 2_000_000
    assert canonical_digest(ticket["context"]) == ticket["context_digest"]
    ticket["context"]["resources"]["min_available_ram_bytes"] = "unlimited"
    with pytest.raises(InputError):
        validate_schema(ticket, "job_ticket.schema.json")


def test_old_contexts_and_nine_field_tickets_remain_valid():
    fresh = plan_task(request({"min_available_ram_bytes": 2000}))
    old = copy.deepcopy(fresh)
    for ticket in old["jobs"]:
        ticket["context"].pop("resources", None)
        ticket["context_digest"] = canonical_digest(ticket["context"])
    assert resume_plan(old, fresh) == old
    legacy = copy.deepcopy(fresh)
    for ticket in legacy["jobs"]:
        ticket.pop("context")
        ticket.pop("context_digest")
        assert len(ticket) == 9
    assert resume_plan(legacy, fresh) == legacy


@pytest.mark.parametrize("field", ["available_ram_bytes", "disk_free_bytes"])
@pytest.mark.parametrize("remaining", [None, 1])
@pytest.mark.parametrize("wait_for_monitor", [False, True])
def test_resource_floor_loss_cancels_and_rejects_executor_pass(
    tmp_path, monkeypatch, field, remaining, wait_for_monitor
):
    ticket = plan_task(
        request({"min_available_ram_bytes": 2_000_000, "min_free_disk_bytes": 2_000_000})
    )["jobs"][1]
    ledger = JobLedger(tmp_path, "resources_task")
    lease = ledger.claim("job_1", "crate")
    current = snapshot()
    monkeypatch.setattr(discovery, "resource_snapshot", lambda policy: dict(current))
    monkeypatch.setattr(discovery, "resource_usage", lambda policy: dict(current))
    cancel_events = []

    def execute(identifier, inputs, context):
        cancel_events.append(context.cancel)
        current[field] = remaining
        if wait_for_monitor:
            assert context.cancel.wait(2), "Resource loss did not cancel native work"
        return Result()

    monkeypatch.setattr(orchestrator, "execute", execute)
    result = orchestrator.execute_leased(
        ledger, "job_1", lease, ticket["capability_id"], {}, 42, job_ticket=ticket
    )
    assert result.status != "PASS"
    assert result.error_code == "PF-WORKFORCE-RESOURCE"
    assert cancel_events[0].is_set()
    assert ledger.completed("job_1") is None


def test_preflight_unknown_required_ram_prevents_dispatch(tmp_path, monkeypatch):
    ticket = plan_task(request({"min_available_ram_bytes": 2000}))["jobs"][1]
    ledger = JobLedger(tmp_path, "unknown_ram")
    lease = ledger.claim("job_1", "crate")
    monkeypatch.setattr(
        discovery, "resource_snapshot", lambda policy: snapshot(available_ram_bytes=None)
    )
    monkeypatch.setattr(orchestrator, "execute", lambda *args: Result())
    with pytest.raises(InputError):
        orchestrator.execute_leased(
            ledger, "job_1", lease, ticket["capability_id"], {}, 42, job_ticket=ticket
        )
    assert not ledger.policy.path(".polyforge/operations").exists()


def test_ledger_cancellation_cannot_be_ignored_by_successful_executor(tmp_path, monkeypatch):
    ledger = JobLedger(tmp_path, "cancel_task")
    lease = ledger.claim("produce", "crate")

    def execute(identifier, inputs, context):
        ledger.cancel("produce")
        return Result()

    monkeypatch.setattr(orchestrator, "execute", execute)
    result = orchestrator.execute_leased(ledger, "produce", lease, "mesh.props.crate.v1", {}, 42)
    assert result.status != "PASS" and result.exit_code == 9


def test_live_discovery_failures_cancel_and_reject_pass(tmp_path, monkeypatch):
    ledger = JobLedger(tmp_path, "probe_failure")
    lease = ledger.claim("produce", "crate")
    unavailable = threading.Event()

    def observe(policy):
        if unavailable.is_set():
            raise OSError("volume disappeared")
        return snapshot()

    def execute(identifier, inputs, context):
        unavailable.set()
        assert context.cancel.wait(2)
        return Result()

    monkeypatch.setattr(discovery, "resource_snapshot", observe)
    monkeypatch.setattr(discovery, "resource_usage", observe)
    monkeypatch.setattr(orchestrator, "execute", execute)
    result = orchestrator.execute_leased(ledger, "produce", lease, "mesh.props.crate.v1", {}, 42)
    assert result.status != "PASS" and result.error_code == "PF-WORKFORCE-RESOURCE"


def test_sequential_limits_require_measured_admission_and_never_qualify_gpu(tmp_path, monkeypatch):
    monkeypatch.setattr(discovery, "resource_snapshot", lambda policy: snapshot())
    admitted = discovery.admit_resources(WorkspacePolicy(tmp_path), {})
    assert admitted["mode"] == "LOCAL_SEQUENTIAL"
    assert admitted["worker_limits"] == {
        "blender": 1,
        "unity": 1,
        "model": 0,
        "blender_cpu_threads": 1,
    }
    assert admitted["render_policy"] == "REGISTERED_FIXED_CPU"
    assert admitted["degradation_reason"]
    with pytest.raises(InputError):
        discovery.admit_resources(WorkspacePolicy(tmp_path), {"gpu_required": True})


def test_linux_gpu_metadata_reports_capacity_without_execution_qualification(tmp_path):
    card = tmp_path / "card0" / "device"
    card.mkdir(parents=True)
    (card / "vendor").write_text("0x1002\n")
    (card / "device").write_text("0x73bf\n")
    (card / "mem_info_vram_total").write_text("8589934592\n")
    metadata = discovery.gpu_metadata(platform="linux", drm_root=tmp_path)
    assert metadata["gpu_observation"] == "METADATA_ONLY"
    assert metadata["vram_bytes"] == 8_589_934_592
    assert metadata["gpu_execution"] == "UNVERIFIED"
    assert metadata["adapters"][0]["source"] == "LINUX_DRM_SYSFS"
    (card / "mem_info_vram_total").write_text("not a measurement")
    assert discovery.gpu_metadata(platform="linux", drm_root=tmp_path)["vram_bytes"] is None


def test_unsupported_gpu_observation_is_unknown():
    metadata = discovery.gpu_metadata(platform="unavailable")
    assert metadata["gpu_observation"] == "UNKNOWN"
    assert metadata["vram_bytes"] is None and metadata["adapters"] == []


def test_windows_gpu_registry_metadata_is_read_only_and_bounded(monkeypatch):
    import sys
    from types import SimpleNamespace

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def query(key, name):
        return {"DriverDesc": "Local adapter", "HardwareInformation.qwMemorySize": 2**33}[name], 1

    calls = []

    def open_key(root, name):
        calls.append(name)
        return Key()

    def enum_key(root, index):
        if index == 1:
            raise OSError("end of enumeration")
        return "0000"

    monkeypatch.setitem(
        sys.modules,
        "winreg",
        SimpleNamespace(
            HKEY_LOCAL_MACHINE=1, OpenKey=open_key, EnumKey=enum_key, QueryValueEx=query
        ),
    )
    metadata = discovery.gpu_metadata(platform="win32")
    assert metadata["vram_bytes"] == 2**33
    assert metadata["gpu_execution"] == "UNVERIFIED"
    assert len(calls) == 2


def test_snapshot_exposes_read_only_gpu_metadata(tmp_path, monkeypatch):
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
    result = discovery.resource_snapshot(WorkspacePolicy(tmp_path))
    assert result["gpu_observation"] == "UNKNOWN"
    assert result["adapters"] == []


def test_linux_gpu_absent_or_unreadable_capacity_stays_unknown(tmp_path):
    assert (
        discovery.gpu_metadata(platform="linux", drm_root=tmp_path)["gpu_observation"] == "UNKNOWN"
    )
    card = tmp_path / "card0" / "device"
    card.mkdir(parents=True)
    (card / "vendor").write_text("0x8086")
    (card / "device").write_text("0x1234")
    metadata = discovery.gpu_metadata(platform="linux", drm_root=tmp_path)
    assert metadata["vram_bytes"] is None
    assert metadata["gpu_observation"] == "METADATA_ONLY"


@pytest.mark.parametrize("raw", [(2**33).to_bytes(8, "little"), None, -1, b"bad", 0xFFFFFFFF])
def test_windows_vram_fallback_and_unknown_values_never_enable_gpu(monkeypatch, raw):
    import sys
    from types import SimpleNamespace

    class Key:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    def enum_key(root, index):
        if index == 0:
            return "Configuration"
        if index == 1:
            return "0000"
        raise OSError("end")

    def query(key, name):
        if name == "DriverDesc":
            return "Local adapter", 1
        if name != "HardwareInformation.MemorySize":
            raise OSError("unavailable field")
        return raw, 1

    monkeypatch.setitem(
        sys.modules,
        "winreg",
        SimpleNamespace(
            HKEY_LOCAL_MACHINE=1, OpenKey=lambda *args: Key(), EnumKey=enum_key, QueryValueEx=query
        ),
    )
    metadata = discovery.gpu_metadata(platform="win32")
    assert metadata["vram_bytes"] == (2**33 if isinstance(raw, bytes) and len(raw) == 8 else None)
    assert metadata["gpu_execution"] == "UNVERIFIED"


def test_windows_gpu_access_denied_stays_unknown(monkeypatch):
    import sys
    from types import SimpleNamespace

    def deny(*args):
        raise PermissionError("read denied")

    monkeypatch.setitem(sys.modules, "winreg", SimpleNamespace(HKEY_LOCAL_MACHINE=1, OpenKey=deny))
    metadata = discovery.gpu_metadata(platform="win32")
    assert metadata["gpu_observation"] == "UNKNOWN" and metadata["vram_bytes"] is None


def test_fast_resource_observation_reports_unknown_disk_and_ram_without_gpu_probe(
    tmp_path, monkeypatch
):
    def deny(*args):
        raise OSError("volume unavailable")

    monkeypatch.setattr(discovery.sys, "platform", "unsupported")
    monkeypatch.setattr(discovery.shutil, "disk_usage", deny)
    measured = discovery.resource_usage(WorkspacePolicy(tmp_path))
    assert measured["disk_free_bytes"] is None and measured["available_ram_bytes"] is None


@pytest.mark.parametrize("context_metadata", [False, True])
def test_legacy_jobs_enforce_floors_supplied_by_original_frozen_request(
    tmp_path, monkeypatch, context_metadata
):
    floors = {"min_available_ram_bytes": 2_000_000}
    ticket = plan_task(request(floors))["jobs"][1]
    ticket["context"].pop("resources")
    ticket["context_digest"] = canonical_digest(ticket["context"])
    if not context_metadata:
        ticket.pop("context")
        ticket.pop("context_digest")
    ledger = JobLedger(tmp_path, "legacy_resources")
    lease = ledger.claim("job_1", "crate")
    current = snapshot()
    monkeypatch.setattr(discovery, "resource_snapshot", lambda policy: dict(current))
    monkeypatch.setattr(discovery, "resource_usage", lambda policy: dict(current))

    def execute(identifier, inputs, context):
        current["available_ram_bytes"] = None
        return Result()

    monkeypatch.setattr(orchestrator, "execute", execute)
    result = orchestrator.execute_leased(
        ledger, "job_1", lease, ticket["capability_id"], {}, 42, job_ticket=ticket, resources=floors
    )
    assert result.status != "PASS" and result.error_code == "PF-WORKFORCE-RESOURCE"
