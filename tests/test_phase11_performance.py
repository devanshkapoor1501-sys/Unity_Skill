"""Rendered qualification must not accept smoke, missing data or selected samples."""

import json

import pytest


def performance():
    # A useful assertion failure during the first red run, rather than collection failure.
    import importlib.util

    assert importlib.util.find_spec("polyforge.unity.performance"), "performance slice missing"
    return importlib.import_module("polyforge.unity.performance")


def sample(index=0):
    return {
        "schema_version": "1.0.0",
        "scope": "WINDOWS_STANDALONE_RENDERED",
        "sample_index": index,
        "input_digest": "a" * 64,
        "profile_digest": "b" * 64,
        "executable_sha256": "d" * 64,
        "scene_id": "main",
        "scene": "PlayableArena",
        "game_kind": "arena",
        "unity_version": "6000.6.3f1",
        "build_type": "Development",
        "is_editor": False,
        "batchmode": False,
        "graphics_type": "Direct3D11",
        "hardware": {
            "cpu": "fixture CPU",
            "logical_cpus": 8,
            "ram_bytes": 16 * 1024**3,
            "gpu": "fixture GPU",
            "gpu_driver": "fixture driver",
            "gpu_memory_mb": 4096,
        },
        "width": 1280,
        "height": 720,
        "quality": "PC",
        "v_sync": 0,
        "target_frame_rate": -1,
        "warmup_seconds": 10.0,
        "measurement_seconds": 60.0,
        "frame_times_ms": [20.0] * 3000,
        "frames_recorded": 3000,
        "complete": True,
        "focused": True,
        "focus_policy": "OBSERVE_CONTINUOUS_BACKGROUND_ENABLED",
        "renderer_observation": "UNITY_END_OF_FRAME",
        "run_in_background": True,
        "gpu_presentation": "NOT_MEASURED",
        "focused_frames": 3000,
        "unfocused_frames": 0,
        "focus_changes": 0,
        "sample_overflow": False,
        "activity": {
            "ticks": 3500,
            "restarts": 3,
            "player_distance": 10.0,
            "enemy_distance": 12.0,
        },
        "process": {
            "pid": 123,
            "birth": "42",
            "identity_status": "BOUND",
            "fatal": False,
            "errors": [],
            "rss_source": "WINDOWS_PEAK_WORKING_SET",
            "reason": "exit",
            "returncode": 0,
            "ready_seconds": 2.0,
            "peak_rss_bytes": 512 * 1024**2,
            "cpu_seconds": 12.0,
            "ready_observed": True,
        },
    }


def group():
    return [sample(i) for i in range(3)]


def registered_player(tmp_path):
    """Fixture the persisted output of an owned native build, without running Unity."""
    from polyforge.runner.state import atomic_json
    from polyforge.security.paths import WorkspacePolicy
    from polyforge.unity.game import register_game_artifacts

    module = performance()
    policy = WorkspacePolicy(tmp_path)
    relative = "runs/game-check-fixture"
    player = policy.mkdir(relative + "/player") / "PolyForgeArena.exe"
    player.write_bytes(b"fixture executable")
    (player.parent / "UnityPlayer.dll").write_bytes(b"fixture player dependency")
    job = {"input_digest": "a" * 64, "scene_id": "main"}
    atomic_json(policy, relative + "/game-input.json", job)
    player_input = atomic_json(
        policy, relative + "/player-input.json", {**job, "player_output": str(player)}
    )
    atomic_json(
        policy,
        relative + "/player-build/process.json",
        {
            "reason": "exit",
            "returncode": 0,
            "argv": [
                str(tmp_path / "Unity.exe"),
                "-executeMethod",
                "PolyForge.Game.Editor.GameBuilder.BuildPlayerBatch",
                "-polyforgeGameInput",
                str(player_input),
            ],
        },
    )
    module.seal_player_build(policy, player)
    register_game_artifacts(policy, relative, job["input_digest"])
    return player


def test_three_complete_rendered_samples_pass_without_claiming_game_acceptance():
    verdict = performance().score_profile(group())
    assert verdict["status"] == "PASS"
    assert verdict["scope"] == "PUBLIC_DEVELOPMENT"
    assert verdict["qualification"] is False
    assert verdict["samples"][0]["median_fps"] == 50.0
    assert verdict["samples"][0]["p95_frame_ms"] == 20.0


@pytest.mark.parametrize("count", [0, 1, 2, 4])
def test_exact_three_samples_required(count):
    samples = [sample(i) for i in range(count)]
    assert performance().score_profile(samples)["status"] == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("graphics_type", "Null"),
        ("graphics_type", ""),
        ("graphics_type", []),
        ("is_editor", True),
        ("batchmode", True),
        ("width", 640),
        ("height", 480),
        ("complete", False),
        ("sample_overflow", True),
        ("focused", False),
        ("warmup_seconds", 9.0),
        ("measurement_seconds", 59.0),
        ("frames_recorded", 100),
        ("frame_times_ms", [float("nan")]),
        ("frame_times_ms", [0.0] * 3000),
        ("frame_times_ms", [5e-324]),
    ],
)
def test_unrendered_incomplete_or_invalid_sample_cannot_qualify(field, value):
    samples = group()
    samples[1][field] = value
    assert performance().score_profile(samples)["status"] == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("reason", "timeout"),
        ("returncode", 7),
        ("ready_observed", False),
        ("peak_rss_bytes", None),
        ("peak_rss_bytes", 0),
        ("ready_seconds", None),
        ("ready_seconds", 30.01),
        ("peak_rss_bytes", 2 * 1024**3 + 1),
    ],
)
def test_external_process_observations_must_be_complete_and_within_budget(field, value):
    samples = group()
    samples[2]["process"][field] = value
    assert performance().score_profile(samples)["status"] == "FAIL"


def test_a_slow_sample_cannot_be_hidden_by_two_fast_samples():
    samples = group()
    samples[1]["frame_times_ms"] = [40.0] * 1500
    samples[1]["frames_recorded"] = 1500
    verdict = performance().score_profile(samples)
    assert verdict["status"] == "FAIL"
    assert verdict["samples"][1]["median_fps"] == 25.0


def test_p95_uses_all_frames_and_can_fail_despite_good_median():
    samples = group()
    samples[0]["frame_times_ms"] = [18.0] * 2700 + [60.0] * 300
    samples[0]["measurement_seconds"] = 66.6
    verdict = performance().score_profile(samples)
    assert verdict["status"] == "FAIL"
    assert verdict["samples"][0]["median_fps"] > 30
    assert verdict["samples"][0]["p95_frame_ms"] == 60


@pytest.mark.parametrize("field", ["hardware", "quality", "input_digest", "profile_digest"])
def test_changed_hardware_quality_or_identity_invalidates_group(field):
    samples = group()
    samples[1][field] = {**samples[1][field], "gpu": "other"} if field == "hardware" else "changed"
    assert performance().score_profile(samples)["status"] == "FAIL"


def test_missing_profile_data_has_explicit_failures():
    verdict = performance().score_profile([{}, {}, {}])
    assert verdict["status"] == "FAIL"
    assert verdict["issues"]


def test_frozen_scene_without_activity_does_not_count_as_rendered_game_workload():
    samples = group()
    samples[0]["activity"]["restarts"] = 0
    samples[0]["activity"]["enemy_distance"] = 0
    assert performance().score_profile(samples)["status"] == "FAIL"


def test_cpu_counter_unavailable_does_not_fabricate_a_value():
    samples = group()
    for item in samples:
        item["process"]["cpu_seconds"] = None
    verdict = performance().score_profile(samples)
    assert verdict["status"] == "PASS"
    assert verdict["samples"][0]["cpu_seconds"] is None


def test_duplicate_sample_identity_is_not_three_measurements():
    samples = group()
    samples[1]["sample_index"] = 0
    assert performance().score_profile(samples)["status"] == "FAIL"


def test_dry_run_validates_owned_player_without_creating_run_directories(tmp_path):
    player = registered_player(tmp_path)
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    result = performance().profile_player(tmp_path, player, dry_run=True)
    assert result.status == "PASS"
    assert result.data["execution_status"] == "NOT_RUN"
    assert result.data["launches"] == 3
    assert result.data["warmup_seconds"] == 10
    assert result.data["sample_seconds"] == 60
    after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    assert after == before


def test_profile_rejects_outside_player_before_writes(tmp_path):
    from polyforge.contracts.validation import InputError

    outside = tmp_path.parent / "outside-profile-fixture.exe"
    with pytest.raises(InputError):
        performance().profile_player(tmp_path, outside, dry_run=True)
    assert list(tmp_path.iterdir()) == []


def observation_module():
    import importlib.util

    assert importlib.util.find_spec("polyforge.runner.metrics"), "owned metrics slice missing"
    return importlib.import_module("polyforge.runner.metrics")


@pytest.fixture
def snapshot_counters(monkeypatch):
    """The observer policy tests replace the native handle reader, not observation logic."""
    metrics = observation_module()

    class Counters:
        def __init__(self, pid, birth):
            self.pid, self.birth = pid, birth

        def read(self):
            return metrics.process_counters(self.pid, self.birth)

        def close(self):
            pass

    monkeypatch.setattr(metrics, "ProcessCounters", Counters)


def test_owned_observer_retains_real_peak_and_reports_ready_after_fast_exit(
    tmp_path, monkeypatch, snapshot_counters
):
    from polyforge.security.paths import WorkspacePolicy

    metrics = observation_module()
    clock = [100.0]
    alive = [True]
    monkeypatch.setattr(metrics.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(metrics, "process_identity", lambda pid: "birth" if alive[0] else None)
    monkeypatch.setattr(
        metrics,
        "process_counters",
        lambda pid, birth=None: {"peak_rss_bytes": 123456, "cpu_seconds": 0.25},
    )
    observer = metrics.ProcessObservation(WorkspacePolicy(tmp_path), "run", "run/ready.json")
    observer.start(123, 100.0)
    observer.poll()
    clock[0] = 102.0
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "ready.json").write_text(json.dumps({"ready": True}))
    alive[0] = False
    observer.finish()
    assert observer.data["ready_seconds"] == 2.0
    assert observer.data["peak_rss_bytes"] == 123456
    assert observer.data["cpu_seconds"] == 0.25
    assert json.loads((tmp_path / "run" / "observations.json").read_text())["pid"] == 123


def test_observer_missing_counter_is_unknown_and_pid_reuse_not_observed(
    tmp_path, monkeypatch, snapshot_counters
):
    from polyforge.security.paths import WorkspacePolicy

    metrics = observation_module()
    identity = ["birth"]
    monkeypatch.setattr(metrics, "process_identity", lambda pid: identity[0])

    def unavailable(pid, birth=None):
        raise OSError("query denied")

    monkeypatch.setattr(metrics, "process_counters", unavailable)
    observer = metrics.ProcessObservation(WorkspacePolicy(tmp_path), "run", "run/ready.json")
    observer.start(123, 1.0)
    observer.poll()
    assert observer.data["peak_rss_bytes"] is None
    assert observer.data["cpu_seconds"] is None
    identity[0] = "different birth"
    observer.poll()
    assert observer.data["identity_status"] == "CHANGED"
    assert observer.data["errors"]


def test_observer_rejects_paths_outside_workspace_without_writes(tmp_path):
    from polyforge.contracts.validation import InputError
    from polyforge.security.paths import WorkspacePolicy

    metrics = observation_module()
    with pytest.raises(InputError):
        metrics.ProcessObservation(WorkspacePolicy(tmp_path), "run", "../outside.json")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("elapsed,rss", [(31, 10), (1, 2 * 1024**3 + 1)])
def test_observer_stops_missing_readiness_or_excess_rss(
    tmp_path, monkeypatch, elapsed, rss, snapshot_counters
):
    from polyforge.security.paths import WorkspacePolicy

    metrics = observation_module()
    monkeypatch.setattr(metrics, "process_identity", lambda pid: "birth")
    monkeypatch.setattr(metrics.time, "monotonic", lambda: 100.0 + elapsed)
    monkeypatch.setattr(
        metrics, "process_counters", lambda pid, birth: {"peak_rss_bytes": rss, "cpu_seconds": None}
    )
    observer = metrics.ProcessObservation(WorkspacePolicy(tmp_path), "run", "run/ready.json")
    observer.start(123, 100.0)
    observer.poll()
    assert observer.fatal


def test_runner_rejects_arbitrary_observation_callbacks_before_writes(tmp_path):
    import sys
    from pathlib import Path

    from polyforge.contracts.validation import InputError
    from polyforge.runner.processes import ProcessPolicy, run_process
    from polyforge.security.paths import WorkspacePolicy

    with pytest.raises(InputError):
        run_process(
            [sys.executable, "-c", "print('unreachable')"],
            WorkspacePolicy(tmp_path),
            "run",
            ProcessPolicy((Path(sys.executable),)),
            observation=object(),
        )
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "case",
    ["pass", "timeout", "missing", "stale", "malformed", "raises", "interrupt", "package_changed"],
)
def test_profile_orchestration_preserves_each_observation_and_stops_bad_group(
    tmp_path, monkeypatch, case
):
    from pathlib import Path

    from polyforge.contracts.validation import InputError
    from polyforge.runner.processes import ProcessOutcome

    module = performance()
    player = registered_player(tmp_path)
    launches = []

    def run(argv, policy, relative, limits, *, observation):
        launches.append(argv)
        assert "-batchmode" not in argv and "-nographics" not in argv
        assert limits.timeout_seconds == 120
        job = json.loads(Path(argv[-1]).read_text())
        assert job["focus_policy"] == "OBSERVE_CONTINUOUS_BACKGROUND_ENABLED"
        assert job["renderer_observation"] == "UNITY_END_OF_FRAME"
        assert job["run_in_background"] is True
        record = sample(job["sample_index"])
        record["profile_digest"] = job["profile_digest"]
        record["executable_sha256"] = job["executable_sha256"]
        observation.data.update(record["process"])
        if case == "raises":
            raise InputError("injected launch failure")
        if case == "interrupt":
            raise KeyboardInterrupt
        if case == "package_changed":
            (player.parent / "UnityPlayer.dll").write_bytes(b"changed player dependency")
        if case == "stale":
            record["input_digest"] = "c" * 64
        if case == "malformed":
            Path(job["evidence_path"]).write_text("not json")
        elif case != "missing":
            Path(job["evidence_path"]).write_text(json.dumps(record))
        return ProcessOutcome(
            0 if case != "timeout" else None,
            "exit" if case != "timeout" else "timeout",
            123,
            "WINDOWS_JOB",
            72,
            "",
            "",
            True,
        )

    monkeypatch.setattr(module, "run_process", run)
    result = module.profile_player(tmp_path, player)
    assert result.status == ("PASS" if case == "pass" else "FAIL")
    assert len(launches) == (3 if case == "pass" else 1)
    assert result.game_status == "PARTIAL"
    assert result.artifact_ids
    assert all((tmp_path / path).is_file() for path in result.evidence_paths)
    assert result.data["samples"][0]["cpu_seconds"] == 12


@pytest.mark.parametrize("field", ["warmup_seconds", "frame_times_ms"])
def test_oversized_integer_telemetry_fails_without_crashing_scorer(field):
    samples = group()
    samples[0][field] = [10**1000] if field == "frame_times_ms" else 10**1000
    assert performance().score_profile(samples)["status"] == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [("unity_version", "6000.0.1"), ("build_type", "invented"), ("sample_index", False)],
)
def test_profile_rejects_unsupported_runtime_or_illtyped_identity(field, value):
    samples = group()
    for item in samples if field != "sample_index" else samples[:1]:
        item[field] = value
    assert performance().score_profile(samples)["status"] == "FAIL"


def test_arbitrary_workspace_executable_with_forged_game_input_cannot_launch(tmp_path):
    from polyforge.contracts.validation import InputError

    player = tmp_path / "unrelated.exe"
    player.write_bytes(b"unrelated executable")
    (tmp_path / "game-input.json").write_text(
        json.dumps({"input_digest": "a" * 64, "scene_id": "main"})
    )
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    with pytest.raises(InputError):
        performance().profile_player(tmp_path, player, dry_run=True)
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before


@pytest.mark.parametrize("tamper", ["exe", "dll", "input", "receipt", "registry", "native"])
def test_stale_or_unregistered_player_payload_refused_before_any_launch(tmp_path, tamper):
    from polyforge.contracts.validation import InputError

    player = registered_player(tmp_path)
    targets = {
        "exe": player,
        "dll": player.parent / "UnityPlayer.dll",
        "input": player.parent.parent / "game-input.json",
        "receipt": player.parent.parent / "player-build-artifacts.json",
        "registry": player.parent.parent / "artifacts.json",
        "native": player.parent.parent / "player-build/process.json",
    }
    targets[tamper].write_bytes(b"tampered")
    before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
    with pytest.raises(InputError):
        performance().profile_player(tmp_path, player, dry_run=True)
    assert sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*")) == before


@pytest.mark.parametrize("failure", [None, "open", "times", "memory", "birth"])
def test_windows_counter_handle_identity_errors_and_close_are_explicit(monkeypatch, failure):
    metrics = observation_module()
    closed = []

    class Call:
        def __init__(self, fn):
            self.fn = fn

        def __call__(self, *args):
            return self.fn(*args)

    class API:
        pass

    api = API()
    api.OpenProcess = Call(lambda *args: 0 if failure == "open" else 123)
    api.CloseHandle = Call(lambda handle: closed.append(handle))

    def times(handle, creation, exit_time, kernel, user):
        creation._obj.dwLowDateTime = 42
        kernel._obj.dwLowDateTime = 10_000_000
        user._obj.dwLowDateTime = 20_000_000
        return failure != "times"

    def memory(handle, pointer, size):
        pointer._obj.peak_rss = 1048576
        return failure != "memory"

    api.GetProcessTimes = Call(times)
    api.GetProcessMemoryInfo = Call(memory)
    monkeypatch.setattr(metrics.sys, "platform", "win32")
    monkeypatch.setattr(metrics.ct, "WinDLL", lambda *args, **kwargs: api, raising=False)
    monkeypatch.setattr(metrics.ct, "get_last_error", lambda: 5, raising=False)
    if failure:
        with pytest.raises(OSError):
            metrics.process_counters(123, "43" if failure == "birth" else "42")
    else:
        assert metrics.process_counters(123, "42") == {
            "peak_rss_bytes": 1048576,
            "cpu_seconds": 3.0,
        }
    assert closed == ([] if failure == "open" else [123])


def test_process_counters_unsupported_os_is_unknown(monkeypatch):
    metrics = observation_module()
    monkeypatch.setattr(metrics.sys, "platform", "unsupported")
    with pytest.raises(OSError):
        metrics.process_counters(123)


def test_observer_rejects_unrelated_run_and_missing_birth(tmp_path, monkeypatch):
    from polyforge.contracts.validation import InputError
    from polyforge.security.paths import WorkspacePolicy

    metrics = observation_module()
    policy = WorkspacePolicy(tmp_path)
    with pytest.raises(InputError):
        metrics.ProcessObservation(policy, "run", "other/ready.json")
    observer = metrics.ProcessObservation(policy, "run", "run/ready.json")
    monkeypatch.setattr(metrics, "process_identity", lambda pid: None)
    with pytest.raises(OSError):
        observer.start(123, 100)
    observer.finish()
    assert observer.data["peak_rss_bytes"] is None


def test_observer_malformed_ready_does_not_discard_birth_bound_counters(
    tmp_path, monkeypatch, snapshot_counters
):
    from polyforge.security.paths import WorkspacePolicy

    metrics = observation_module()
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "ready.json").write_text("[]")
    identities = iter(["birth", "birth"])
    monkeypatch.setattr(metrics, "process_identity", lambda pid: next(identities))
    monkeypatch.setattr(
        metrics, "process_counters", lambda pid, birth: {"peak_rss_bytes": 123, "cpu_seconds": 0.25}
    )
    observer = metrics.ProcessObservation(WorkspacePolicy(tmp_path), "run", "run/ready.json")
    observer.start(123, 1e100)
    observer.poll()
    assert not observer.data["ready_observed"]
    assert observer.data["peak_rss_bytes"] == 123
    assert observer.data["errors"]


@pytest.fixture
def native_counter_api(monkeypatch):
    """Exercise handle ownership while replacing only Windows API calls."""
    from types import SimpleNamespace

    metrics = observation_module()
    state = SimpleNamespace(
        peak=536870912, cpu_ticks=30000000, birth=42, failure=None, opened=[], closed=[]
    )

    class Call:
        def __init__(self, fn):
            self.fn = fn

        def __call__(self, *args):
            return self.fn(*args)

    def open_process(*args):
        state.opened.append(args[-1])
        return 123

    def times(handle, creation, exit_time, kernel, user):
        creation._obj.dwLowDateTime = state.birth
        kernel._obj.dwLowDateTime = state.cpu_ticks
        user._obj.dwLowDateTime = 0
        return state.failure != "times"

    def memory(handle, pointer, size):
        pointer._obj.peak_rss = state.peak
        return state.failure != "memory"

    api = SimpleNamespace(
        OpenProcess=Call(open_process),
        CloseHandle=Call(lambda handle: state.closed.append(handle)),
        GetProcessTimes=Call(times),
        GetProcessMemoryInfo=Call(memory),
    )
    monkeypatch.setattr(metrics.sys, "platform", "win32")
    monkeypatch.setattr(metrics.ct, "WinDLL", lambda *args, **kwargs: api, raising=False)
    monkeypatch.setattr(metrics.ct, "get_last_error", lambda: 5, raising=False)
    return state


def test_terminal_peak_is_read_from_retained_handle_after_exit(
    tmp_path, monkeypatch, native_counter_api
):
    from polyforge.security.paths import WorkspacePolicy

    metrics = observation_module()
    alive = [True]
    monkeypatch.setattr(metrics, "process_identity", lambda pid: "42" if alive[0] else None)
    observer = metrics.ProcessObservation(WorkspacePolicy(tmp_path), "run", "run/ready.json")
    observer.start(123, 1e100)
    observer.poll()
    native_counter_api.peak = 3221225472
    native_counter_api.cpu_ticks = 45000000
    alive[0] = False
    observer.finish()
    assert observer.data["peak_rss_bytes"] == 3221225472
    assert observer.data["cpu_seconds"] == 4.5
    assert observer.fatal
    assert native_counter_api.opened == [123]
    assert native_counter_api.closed == [123]


@pytest.mark.parametrize(
    "field,value",
    [
        ("identity_status", "CHANGED"),
        ("identity_status", None),
        ("pid", None),
        ("pid", True),
        ("birth", None),
        ("birth", "not-a-birth-token"),
        ("birth", "0"),
        ("fatal", True),
        ("fatal", None),
        ("errors", ["counter query failed"]),
        ("errors", None),
        ("returncode", False),
        ("rss_source", None),
    ],
)
def test_invalid_process_identity_or_final_observation_cannot_pass(field, value):
    samples = group()
    samples[0]["process"][field] = value
    assert performance().score_profile(samples)["status"] == "FAIL"


@pytest.mark.parametrize(
    "field,value",
    [
        ("cpu", ["CPU"]),
        ("gpu", {"name": "GPU"}),
        ("gpu_driver", True),
        ("logical_cpus", True),
        ("logical_cpus", -1),
        ("ram_bytes", -1),
    ],
)
def test_malformed_hardware_identity_cannot_pass(field, value):
    samples = group()
    for item in samples:
        item["hardware"][field] = value
    assert performance().score_profile(samples)["status"] == "FAIL"


@pytest.mark.parametrize(
    "failure", ["memory", "birth", "cancel", "interrupt", "start", "write", "launch"]
)
def test_runner_propagates_final_failure_and_closes_handles_on_all_exit_paths(
    tmp_path, monkeypatch, native_counter_api, failure
):
    import io
    import sys
    import threading
    from contextlib import nullcontext
    from pathlib import Path
    from types import SimpleNamespace

    import polyforge.runner.processes as processes
    from polyforge.contracts.validation import InputError
    from polyforge.security.paths import WorkspacePolicy

    job_closed = []
    cancel = threading.Event()

    class Job:
        def __init__(self, *args):
            pass

        def assign_and_resume(self, pid):
            pass

        def terminate(self):
            pass

        def close(self):
            job_closed.append(True)

    class Process:
        pid, returncode = 123, 0

        def __init__(self, *args, **kwargs):
            if failure == "launch":
                raise OSError("injected launch failure")
            self.stdout, self.stderr = io.BytesIO(), io.BytesIO()
            self.polls = 0

        def poll(self):
            self.polls += 1
            if self.polls == 1:
                if failure == "cancel":
                    cancel.set()
                if failure == "interrupt":
                    raise KeyboardInterrupt
                return None
            if failure == "birth":
                native_counter_api.birth = 43
            elif failure == "memory":
                native_counter_api.failure = "memory"
            return 0

        def wait(self, **kwargs):
            return 0

    monkeypatch.setattr(processes, "WindowsJob", Job)
    monkeypatch.setattr(processes, "os", SimpleNamespace(name="nt"))
    monkeypatch.setattr(processes.subprocess, "Popen", Process)
    monkeypatch.setattr(observation_module(), "process_identity", lambda pid: "42")
    policy = WorkspacePolicy(tmp_path)
    observer = observation_module().ProcessObservation(policy, "run", "run/ready.json")
    if failure == "start":
        native_counter_api.birth = 43
    if failure == "write":

        def fail_write(*args):
            raise OSError("injected observation write failure")

        monkeypatch.setattr(observation_module(), "atomic_json", fail_write)
    expected_error = {
        "interrupt": KeyboardInterrupt,
        "start": InputError,
        "write": OSError,
        "launch": InputError,
    }.get(failure)
    with pytest.raises(expected_error) if expected_error else nullcontext():
        outcome = processes.run_process(
            [sys.executable],
            policy,
            "run",
            processes.ProcessPolicy((Path(sys.executable),)),
            observation=observer,
            cancel=cancel,
        )
        assert outcome.reason == ("cancelled" if failure == "cancel" else "observation_failure")
        if failure != "cancel":
            assert observer.fatal
            assert observer.data["errors"]
    expected_handles = [] if failure == "launch" else [123]
    assert native_counter_api.opened == expected_handles
    assert native_counter_api.closed == expected_handles
    assert job_closed == [True]


@pytest.mark.parametrize(
    "field,value",
    [
        ("width", 1280.0),
        ("height", 720.0),
        ("v_sync", False),
        ("target_frame_rate", -1.0),
        ("frames_recorded", 3000.0),
    ],
)
def test_integer_profile_fields_do_not_accept_float_or_bool_aliases(field, value):
    samples = group()
    for item in samples:
        item[field] = value
    assert performance().score_profile(samples)["status"] == "FAIL"


@pytest.mark.parametrize("boundary", ["registration_return", "lock_entry"])
@pytest.mark.parametrize("payload", ["dll", "exe"])
def test_registered_payload_cannot_be_replaced_before_profile_freeze(
    tmp_path, monkeypatch, boundary, payload
):
    from contextlib import contextmanager
    from pathlib import Path

    from polyforge.contracts.validation import InputError
    from polyforge.runner.processes import ProcessOutcome

    module = performance()
    player = registered_player(tmp_path)
    target = player.parent / "UnityPlayer.dll" if payload == "dll" else player
    original_register = module._registered_player
    original_lock = module.unity_project_lock
    launches = []

    def validate_then_change(policy, path):
        registered = original_register(policy, path)
        if boundary == "registration_return":
            target.write_bytes(b"unregistered replacement payload")
        return registered

    @contextmanager
    def lock_then_change(*args, **kwargs):
        with original_lock(*args, **kwargs) as lock:
            if boundary == "lock_entry":
                target.write_bytes(b"unregistered replacement payload")
            yield lock

    def run(argv, policy, relative, limits, *, observation):
        launches.append(argv)
        request = json.loads(Path(argv[-1]).read_text())
        record = sample(request["sample_index"])
        record["profile_digest"] = request["profile_digest"]
        record["executable_sha256"] = request["executable_sha256"]
        observation.data.update(record["process"])
        Path(request["evidence_path"]).write_text(json.dumps(record))
        return ProcessOutcome(0, "exit", 123, "WINDOWS_JOB", 72, "", "", True)

    monkeypatch.setattr(module, "_registered_player", validate_then_change)
    monkeypatch.setattr(module, "unity_project_lock", lock_then_change)
    monkeypatch.setattr(module, "run_process", run)
    with pytest.raises(InputError):
        module.profile_player(tmp_path, player)
    assert launches == []
    assert not (player.parent / "profiles").exists()


@pytest.mark.parametrize(
    "focused_frames,unfocused_frames,changes", [(3000, 0, 0), (1500, 1500, 20), (0, 3000, 0)]
)
def test_continuous_focus_policy_preserves_focused_mixed_and_unfocused_samples(
    focused_frames, unfocused_frames, changes
):
    samples = group()
    for record in samples:
        record.update(
            focused=unfocused_frames == 0,
            focused_frames=focused_frames,
            unfocused_frames=unfocused_frames,
            focus_changes=changes,
        )
    verdict = performance().score_profile(samples)
    assert verdict["status"] == "PASS"
    assert verdict.get("gpu_presentation") == "NOT_MEASURED"
    assert verdict.get("renderer_observation") == "UNITY_END_OF_FRAME"
    assert verdict.get("focus_policy") == "OBSERVE_CONTINUOUS_BACKGROUND_ENABLED"
    for measured in verdict["samples"]:
        assert measured.get("focused_frames") == focused_frames
        assert measured.get("unfocused_frames") == unfocused_frames
        assert measured.get("focus_changes") == changes
        assert measured.get("focused") is (unfocused_frames == 0)
        assert measured.get("run_in_background") is True


@pytest.mark.parametrize(
    "field,value",
    [
        ("focus_policy", None),
        ("focus_policy", "FOREGROUND_ONLY"),
        ("renderer_observation", None),
        ("renderer_observation", "UNMEASURED"),
        ("run_in_background", False),
        ("run_in_background", 1),
        ("gpu_presentation", "MEASURED"),
        ("focused_frames", -1),
        ("focused_frames", True),
        ("focused_frames", 3000.0),
        ("focused_frames", 1000001),
        ("unfocused_frames", -1),
        ("unfocused_frames", 1),
        ("unfocused_frames", None),
        ("focus_changes", -1),
        ("focus_changes", True),
        ("focus_changes", 0.5),
        ("focus_changes", 3001),
        ("focused", None),
    ],
)
def test_focus_policy_and_counts_must_be_complete_typed_and_consistent(field, value):
    samples = group()
    for record in samples:
        record[field] = value
    assert performance().score_profile(samples)["status"] == "FAIL"


def test_legacy_foreground_evidence_cannot_be_rescored_under_new_policy():
    samples = group()
    for record in samples:
        for key in (
            "focus_policy",
            "renderer_observation",
            "run_in_background",
            "gpu_presentation",
            "focused_frames",
            "unfocused_frames",
            "focus_changes",
        ):
            del record[key]
    assert performance().score_profile(samples)["status"] == "FAIL"


def test_unfocused_slow_intervals_are_scored_without_omission():
    samples = group()
    samples[1].update(
        focused=False,
        focused_frames=0,
        unfocused_frames=1500,
        focus_changes=0,
        frame_times_ms=[40.0] * 1500,
        frames_recorded=1500,
    )
    verdict = performance().score_profile(samples)
    assert verdict["status"] == "FAIL"
    assert verdict["samples"][1]["median_fps"] == 25.0
    assert "Median FPS below 30" in verdict["samples"][1]["issues"]


@pytest.mark.parametrize(
    "focused_frames,unfocused_frames,changes,expected",
    [
        (3000, 0, 3000, "FAIL"),
        (0, 3000, 2, "FAIL"),
        (1500, 1500, 0, "FAIL"),
        (2999, 1, 4, "FAIL"),
        (3000, 0, 1, "PASS"),
        (0, 3000, 1, "PASS"),
        (1500, 1500, 1, "PASS"),
        (2999, 1, 3, "PASS"),
    ],
)
def test_focus_transition_counts_are_feasible(focused_frames, unfocused_frames, changes, expected):
    records = group()
    for record in records:
        record.update(
            focused_frames=focused_frames,
            unfocused_frames=unfocused_frames,
            focused=unfocused_frames == 0,
            focus_changes=changes,
        )
    assert performance().score_profile(records)["status"] == expected
