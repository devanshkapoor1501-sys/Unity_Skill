"""Bounded cleanup previews and mutations use only disposable owned fixtures."""

import hashlib
import json
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError
from polyforge.runner.state import RunJournal
from polyforge.security.paths import WorkspacePolicy


def workspace(root: Path) -> tuple[Path, Path]:
    root.mkdir()
    marker = root / ".polyforge/workspace.json"
    marker.parent.mkdir()
    marker.write_text(
        json.dumps(
            {
                "schema_version": "1.0.0",
                "workspace_id": "a" * 32,
                "security_scope": "TRUSTED_LOCAL",
                "trusted_local_approved": True,
            }
        )
    )
    journal = RunJournal.create(WorkspacePolicy(root), "native-1")
    journal.transition("S0", "running")
    (root / "proof.txt").write_text("actual fixture evidence")
    journal.transition("S0", "passed", evidence=["proof.txt"])
    process = root / "runs/native-1/compile"
    temporary = process / "tmp"
    temporary.mkdir(parents=True)
    (process / "process.json").write_text(
        json.dumps(
            {
                "pid": 2147483646,
                "returncode": 0,
                "reason": "exit",
                "ownership": "WINDOWS_JOB",
                "duration_seconds": 1,
            }
        )
    )
    candidate = temporary / "discard.tmp"
    candidate.write_bytes(b"temporary bytes")
    return root, candidate


def snapshot(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_preview_lists_only_private_terminal_temporary_candidates_without_writes(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    (candidate.parent / "editable.blend").write_bytes(b"source")
    (candidate.parent.parent / "stdout.txt").write_text("evidence")
    before = snapshot(root)
    result = clean_workspace(root)
    assert result.status == "PASS"
    assert result.game_status == "PARTIAL"
    assert result.data["dry_run"] is True
    assert result.data["candidates"] == [
        {
            "relative_path": "runs/native-1/compile/tmp/discard.tmp",
            "bytes": len(b"temporary bytes"),
            "sha256": hashlib.sha256(b"temporary bytes").hexdigest(),
        }
    ]
    assert result.data["deleted"] == []
    assert result.data["total_candidate_bytes"] == len(b"temporary bytes")
    assert snapshot(root) == before


def test_confirm_deletes_only_candidates_and_keeps_sources_evidence_and_directories(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    source = candidate.parent / "source.blend"
    source.write_bytes(b"editable source")
    result = clean_workspace(root, confirm=True)
    assert result.status == "PASS"
    assert result.data["dry_run"] is False
    assert result.data["deleted"] == ["runs/native-1/compile/tmp/discard.tmp"]
    assert not candidate.exists()
    assert source.read_bytes() == b"editable source"
    assert candidate.parent.is_dir()
    assert (root / "proof.txt").read_text() == "actual fixture evidence"


def test_explicit_dry_run_overrides_confirmation_without_any_writes(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, _ = workspace(tmp_path / "owned")
    before = snapshot(root)
    result = clean_workspace(root, dry_run=True, confirm=True)
    assert result.data["dry_run"] is True and result.data["deleted"] == []
    assert snapshot(root) == before


def test_registered_temporary_shaped_artifacts_and_directory_evidence_are_preserved(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    registry = candidate.parent.parent / "registry.json"
    registry.write_text(
        json.dumps({"artifacts": [{"relative_path": candidate.relative_to(root).as_posix()}]})
    )
    before = snapshot(root)
    assert clean_workspace(root, confirm=True).data["candidates"] == []
    assert snapshot(root) == before


@pytest.mark.parametrize("kind", ["missing", "empty", "running", "live", "uncertain"])
def test_unproven_or_active_runs_and_processes_are_preserved(tmp_path, monkeypatch, kind):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    if kind == "missing":
        (root / "runs/native-1/events.jsonl").unlink()
    elif kind == "empty":
        journal = RunJournal(WorkspacePolicy(root), "native-1")
        state = journal.read()
        for stage in state["stages"].values():
            stage["status"] = "pending"
        journal._save(state, "fixture")
    elif kind == "running":
        RunJournal(WorkspacePolicy(root), "native-1").transition("S1", "running")
    else:

        def identity(pid):
            if kind == "uncertain":
                raise OSError("cannot establish process liveness")
            return "live-birth-token"

        monkeypatch.setattr(cleanup, "process_identity", identity)
    before = snapshot(root)
    result = cleanup.clean_workspace(root)
    assert result.data["candidates"] == []
    assert result.data["skipped"]
    assert candidate.exists() and snapshot(root) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("workspace_id", None),
        ("trusted_local_approved", False),
        ("security_scope", "SANDBOXED_UNTRUSTED"),
        ("schema_version", "2"),
    ],
)
def test_invalid_workspace_metadata_rejects_without_mutation(tmp_path, field, value):
    from polyforge.cleanup import clean_workspace

    root, _ = workspace(tmp_path / "owned")
    marker = root / ".polyforge/workspace.json"
    data = json.loads(marker.read_text())
    data[field] = value
    marker.write_text(json.dumps(data))
    before = snapshot(root)
    with pytest.raises(InputError):
        clean_workspace(root, confirm=True)
    assert snapshot(root) == before


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        {"pid": True, "returncode": 0, "reason": "exit"},
        {"pid": 2147483646, "returncode": True, "reason": "exit"},
        {"pid": 2147483646, "returncode": 0, "reason": "running"},
    ],
)
def test_malformed_process_records_fail_closed_before_deletion(tmp_path, value):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    (candidate.parent.parent / "process.json").write_text(json.dumps(value))
    before = snapshot(root)
    with pytest.raises(InputError):
        clean_workspace(root, confirm=True)
    assert snapshot(root) == before


def test_hardlinked_candidate_is_rejected_and_both_names_survive(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    outside = tmp_path / "outside.tmp"
    os.link(candidate, outside)
    with pytest.raises(InputError):
        clean_workspace(root, confirm=True)
    assert candidate.read_bytes() == outside.read_bytes() == b"temporary bytes"


@pytest.mark.parametrize("limit", ["MAX_ENTRIES", "MAX_FILE_BYTES", "MAX_TOTAL_BYTES"])
def test_inventory_limits_fail_before_any_deletion(tmp_path, monkeypatch, limit):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    monkeypatch.setattr(cleanup, limit, 1)
    before = snapshot(root)
    with pytest.raises(InputError):
        cleanup.clean_workspace(root, confirm=True)
    assert candidate.exists() and snapshot(root) == before


@pytest.mark.parametrize("field", ["reason", "ownership"])
def test_nonstring_process_enums_are_invalid_input_not_uncaught_type_errors(tmp_path, field):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    process = candidate.parent.parent / "process.json"
    value = json.loads(process.read_text())
    value[field] = []
    process.write_text(json.dumps(value))
    with pytest.raises(InputError):
        clean_workspace(root, confirm=True)
    assert candidate.exists()


def test_incomplete_journal_tail_does_not_establish_cleanup_readiness(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    with (root / "runs/native-1/events.jsonl").open("ab") as stream:
        stream.write(b'{"incomplete":')
    before = snapshot(root)
    result = clean_workspace(root, confirm=True)
    assert result.data["candidates"] == [] and result.data["skipped"]
    assert snapshot(root) == before and candidate.exists()


def test_nested_process_temp_scopes_cannot_duplicate_deletion_targets(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    nested = candidate.parent / "nested"
    (nested / "tmp").mkdir(parents=True)
    (nested / "process.json").write_bytes((candidate.parent.parent / "process.json").read_bytes())
    (nested / "tmp/discard.tmp").write_bytes(b"nested")
    before = snapshot(root)
    with pytest.raises(InputError):
        clean_workspace(root, confirm=True)
    assert snapshot(root) == before


def test_candidate_change_during_lock_acquisition_fails_before_any_deletion(tmp_path, monkeypatch):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    lock = cleanup.FileLock

    class ConcurrentWriter(lock):
        def __enter__(self):
            result = super().__enter__()
            if self.relative == ".polyforge/locks/cleanup.lock":
                candidate.write_bytes(b"changed")
            return result

    monkeypatch.setattr(cleanup, "FileLock", ConcurrentWriter)
    with pytest.raises(InputError, match="changed"):
        cleanup.clean_workspace(root, confirm=True)
    assert candidate.read_bytes() == b"changed"


@pytest.mark.parametrize("failure", ["io", "file_changed", "process_live"])
def test_partial_deletion_reports_exact_paths_and_preserves_remaining_candidate(
    tmp_path, monkeypatch, failure
):
    import polyforge.cleanup as cleanup

    root, first = workspace(tmp_path / "owned")
    second = first.parent / "zzz.tmp"
    second.write_bytes(b"second")
    unlink = Path.unlink

    def competing_unlink(path, *args, **kwargs):
        if path == second and failure == "io":
            raise PermissionError("fixture denied second unlink")
        result = unlink(path, *args, **kwargs)
        if path == first:
            if failure == "file_changed":
                second.write_bytes(b"changed second")
            elif failure == "process_live":
                process = first.parent.parent / "process.json"
                value = json.loads(process.read_text())
                value["pid"] = os.getpid()
                process.write_text(json.dumps(value))
        return result

    monkeypatch.setattr(Path, "unlink", competing_unlink)
    result = cleanup.clean_workspace(root, confirm=True)
    assert result.status == "FAIL" and result.error_code == "PF-CLEAN-PARTIAL"
    assert result.data["deleted"] == ["runs/native-1/compile/tmp/discard.tmp"]
    assert second.exists() and not first.exists()


def test_real_directory_link_rejection_preserves_outside_tree(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.tmp"
    secret.write_bytes(b"preserve outside")
    link = candidate.parent / "linked"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True
        )
    else:
        link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(InputError):
        clean_workspace(root, confirm=True)
    assert secret.read_bytes() == b"preserve outside" and candidate.exists()


@pytest.mark.parametrize("field", ["dry_run", "confirm"])
def test_nonboolean_flags_reject_before_reading_workspace(tmp_path, field):
    from polyforge.cleanup import clean_workspace

    with pytest.raises(InputError, match="boolean"):
        clean_workspace(tmp_path / "absent", **{field: 1})


def test_empty_owned_workspace_cleanup_leaves_no_lock_files(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, _ = workspace(tmp_path / "owned")
    empty = tmp_path / "empty"
    (empty / ".polyforge").mkdir(parents=True)
    (empty / ".polyforge/workspace.json").write_bytes(
        (root / ".polyforge/workspace.json").read_bytes()
    )
    before = snapshot(empty)
    result = clean_workspace(empty, confirm=True)
    assert result.status == "PASS" and result.data["candidates"] == []
    assert snapshot(empty) == before


@pytest.mark.parametrize("reference", ["directory", "absolute", "artifact_id", "basename"])
def test_registered_reference_spellings_protect_temporary_candidates(tmp_path, reference):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    value = {
        "directory": candidate.parent.relative_to(root).as_posix(),
        "absolute": str(candidate),
        "artifact_id": "native-1:" + candidate.relative_to(root).as_posix(),
        "basename": candidate.name,
    }[reference]
    (candidate.parent.parent / "artifacts.json").write_text(json.dumps({"artifact": value}))
    assert clean_workspace(root, confirm=True).data["candidates"] == []
    assert candidate.exists()


def test_unjournaled_process_and_files_outside_private_temp_are_preserved(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    (candidate.parent.parent / "process.json").unlink()
    (root / "user.tmp").write_bytes(b"user source")
    before = snapshot(root)
    assert clean_workspace(root, confirm=True).data["candidates"] == []
    assert snapshot(root) == before


def test_failed_terminal_run_cleanup_and_cli_preview_work(tmp_path, capsys):
    from polyforge.cleanup import clean_workspace
    from polyforge.cli import main

    root, candidate = workspace(tmp_path / "owned")
    journal = RunJournal(WorkspacePolicy(root), "native-1")
    journal.transition("S1", "running")
    journal.transition("S1", "failed", note="expected fixture")
    before = snapshot(root)
    assert main(["clean", "--workspace", str(root), "--dry-run", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["data"]["candidates"]
    assert snapshot(root) == before
    assert clean_workspace(root, confirm=True).status == "PASS"
    assert not candidate.exists()


@pytest.mark.parametrize("owner", ["run", "active_run", "workforce", "transactions", ".polyforge"])
def test_references_across_engine_metadata_roots_protect_temporary_files(tmp_path, owner):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    relative = candidate.relative_to(root).as_posix()
    if owner in {"run", "active_run"}:
        journal = RunJournal.create(WorkspacePolicy(root), "dependent-2")
        journal.transition("S0", "running")
        if owner == "run":
            journal.transition("S0", "passed", evidence=[relative])
        folder = root / "runs/dependent-2"
    else:
        folder = root / owner / "task-2"
        folder.mkdir(parents=True)
    (folder / "handoff.json").write_text(json.dumps({"artifacts": [{"relative_path": relative}]}))
    before = snapshot(root)
    assert clean_workspace(root, confirm=True).data["candidates"] == []
    assert snapshot(root) == before and candidate.exists()


@pytest.mark.parametrize("folder", ["UnityProject/Library", "Library", "Assets", "transactions"])
def test_native_project_source_cache_and_recovery_subtrees_are_never_candidates(tmp_path, folder):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    candidate.unlink()
    protected = candidate.parent / folder / "keep.cache"
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b"native source or cache")
    before = snapshot(root)
    result = clean_workspace(root, confirm=True)
    assert result.data["candidates"] == [] and snapshot(root) == before


def test_reference_registration_after_first_unlink_stops_before_next_file(tmp_path, monkeypatch):
    import polyforge.cleanup as cleanup

    root, first = workspace(tmp_path / "owned")
    second = first.parent / "zzz.tmp"
    second.write_bytes(b"second")
    unlink = Path.unlink

    def register_after_unlink(path, *args, **kwargs):
        result = unlink(path, *args, **kwargs)
        if path == first:
            (root / ".polyforge/new-artifact.json").write_text(
                json.dumps({"relative_path": second.relative_to(root).as_posix()})
            )
        return result

    monkeypatch.setattr(Path, "unlink", register_after_unlink)
    result = cleanup.clean_workspace(root, confirm=True)
    assert result.status == "FAIL" and result.error_code == "PF-CLEAN-PARTIAL"
    assert result.data["deleted"] == [first.relative_to(root).as_posix()]
    assert second.exists()


def test_lock_release_failure_keeps_exact_deletion_receipt(tmp_path, monkeypatch):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    exit_lock = cleanup.FileLock.__exit__

    def failing_exit(lock, *args):
        exit_lock(lock, *args)
        if lock.relative.endswith("run-native-1.lock"):
            raise OSError("fixture lock release failure")

    monkeypatch.setattr(cleanup.FileLock, "__exit__", failing_exit)
    result = cleanup.clean_workspace(root, confirm=True)
    assert result.status == "FAIL" and result.error_code == "PF-CLEAN-PARTIAL"
    assert result.data["deleted"] == [candidate.relative_to(root).as_posix()]
    assert not candidate.exists()


@pytest.mark.parametrize("lock_name", ["cleanup.lock", "run-native-1.lock"])
def test_hardlinked_lock_is_rejected_before_its_outside_inode_is_written(tmp_path, lock_name):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    lock = root / ".polyforge/locks" / lock_name
    if lock.exists():
        lock.unlink()
    outside = tmp_path / "outside.lock"
    outside.write_text('{"released": true}')
    before = outside.read_bytes()
    os.link(outside, lock)
    with pytest.raises(InputError):
        clean_workspace(root, confirm=True)
    assert outside.read_bytes() == before and candidate.exists()


@pytest.mark.parametrize("liveness", ["live", "uncertain"])
def test_live_or_uncertain_nested_process_temp_cannot_inherit_dead_parent_eligibility(
    tmp_path, monkeypatch, liveness
):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    candidate.unlink()
    nested = candidate.parent / "nested"
    (nested / "tmp").mkdir(parents=True)
    record = json.loads((candidate.parent.parent / "process.json").read_text())
    record["pid"] = os.getpid()
    (nested / "process.json").write_text(json.dumps(record))
    child = nested / "tmp/active.tmp"
    child.write_bytes(b"live child bytes")
    if liveness == "uncertain":
        identity = cleanup.process_identity

        def uncertain(pid):
            if pid == os.getpid():
                raise OSError("unknown nested owner")
            return identity(pid)

        monkeypatch.setattr(cleanup, "process_identity", uncertain)
    before = snapshot(root)
    with pytest.raises(InputError):
        cleanup.clean_workspace(root, confirm=True)
    assert child.read_bytes() == b"live child bytes" and snapshot(root) == before


@pytest.mark.parametrize("raw", [b'{"a":1,"a":2}\n', b'{"a":NaN}\n', b'{"bad":}\n', b"\xff\n"])
def test_invalid_complete_jsonl_metadata_blocks_cleanup_without_deletion(tmp_path, raw):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    record = root / "workforce/records.jsonl"
    record.parent.mkdir()
    record.write_bytes(raw)
    before = snapshot(root)
    with pytest.raises(InputError):
        clean_workspace(root, confirm=True)
    assert snapshot(root) == before and candidate.exists()


def test_explicit_dot_relative_artifact_reference_remains_protected(tmp_path):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    (candidate.parent.parent / "registry.json").write_text(
        json.dumps({"relative_path": "./" + candidate.relative_to(root).as_posix()})
    )
    assert clean_workspace(root).data["candidates"] == []


@pytest.mark.parametrize("kind", ["candidate", "jsonl"])
def test_oversized_temporary_or_jsonl_metadata_fails_before_reading_payload(tmp_path, kind):
    from polyforge.cleanup import MAX_FILE_BYTES, clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    target = candidate if kind == "candidate" else candidate.parent.parent / "metadata.jsonl"
    with target.open("wb") as stream:
        stream.truncate(MAX_FILE_BYTES + 1)
    with pytest.raises(InputError, match="bound"):
        clean_workspace(root, confirm=True)
    assert candidate.exists()


def test_aggregate_temporary_byte_budget_is_independent_of_metadata_budget(tmp_path, monkeypatch):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    candidate.write_bytes(b"a" * 6000)
    (candidate.parent / "second.tmp").write_bytes(b"b" * 6000)
    monkeypatch.setattr(cleanup, "MAX_TOTAL_BYTES", 10000)
    with pytest.raises(InputError, match="candidates exceed"):
        cleanup.clean_workspace(root, confirm=True)
    assert candidate.exists()


def test_metadata_root_must_be_a_directory_and_nesting_is_bounded(tmp_path, monkeypatch):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    (root / "workforce").write_text("not a directory")
    with pytest.raises(InputError, match="roots must be directories"):
        cleanup.clean_workspace(root, confirm=True)
    (root / "workforce").unlink()
    monkeypatch.setattr(cleanup, "MAX_DEPTH", 1)
    with pytest.raises(InputError, match="nesting"):
        cleanup.clean_workspace(root, confirm=True)
    assert candidate.exists()


@pytest.mark.parametrize("budget", ["pending_values", "distinct_references"])
def test_reference_processing_has_bounded_memory_even_with_few_files(tmp_path, monkeypatch, budget):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    workforce = root / "workforce"
    workforce.mkdir()
    if budget == "pending_values":
        (workforce / "one.json").write_text(json.dumps(["same"] * 300))
    else:
        for index in range(2):
            (workforce / f"{index}.json").write_text(
                json.dumps([f"unique-{index}-{i}" for i in range(150)])
            )
    monkeypatch.setattr(cleanup, "MAX_ENTRIES", 20)
    with pytest.raises(InputError, match="reference"):
        cleanup.clean_workspace(root, confirm=True)
    assert candidate.exists()


@pytest.mark.parametrize(
    "kind", ["metadata", "candidate_open", "candidate_close", "journal", "jsonl"]
)
def test_read_time_changes_fail_closed_without_deleting_candidate(tmp_path, monkeypatch, kind):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    target = root / ".polyforge/workspace.json" if kind == "metadata" else candidate
    if kind in {"journal", "jsonl"}:
        target = root / "runs/native-1/events.jsonl"
    original_open = Path.open
    reads = 0

    @contextmanager
    def racing_open(path, mode="r", *args, **kwargs):
        nonlocal reads
        stream = original_open(path, mode, *args, **kwargs)
        matching = path == target and mode == "rb"
        if matching:
            reads += 1
        trigger = matching and reads == (3 if kind == "journal" else 1)
        try:
            if trigger and kind == "candidate_open":
                with original_open(target, "ab") as writer:
                    writer.write(b"changed")
            yield stream
        finally:
            stream.close()
            if trigger and kind != "candidate_open":
                with original_open(target, "ab") as writer:
                    writer.write(b" ")

    monkeypatch.setattr(Path, "open", racing_open)
    with pytest.raises(InputError, match="changed"):
        cleanup.clean_workspace(root, confirm=True)
    assert candidate.exists()


def test_directory_change_during_inventory_is_detected(tmp_path, monkeypatch):
    import polyforge.cleanup as cleanup

    root, candidate = workspace(tmp_path / "owned")
    scandir = os.scandir

    @contextmanager
    def racing_scandir(path):
        with scandir(path) as iterator:
            yield iterator
        if Path(path) == candidate.parent:
            (candidate.parent / "new.tmp").write_bytes(b"new")

    monkeypatch.setattr(cleanup.os, "scandir", racing_scandir)
    with pytest.raises(InputError, match="directory changed"):
        cleanup.clean_workspace(root, confirm=True)
    assert candidate.exists()


def test_first_unlink_os_error_is_structured_without_claiming_deletion(tmp_path, monkeypatch):
    from polyforge.cleanup import clean_workspace

    root, candidate = workspace(tmp_path / "owned")
    unlink = Path.unlink

    def denied(path, *args, **kwargs):
        if path == candidate:
            raise PermissionError("fixture first unlink denied")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", denied)
    with pytest.raises(InputError, match="mutation failed"):
        clean_workspace(root, confirm=True)
    assert candidate.exists()
