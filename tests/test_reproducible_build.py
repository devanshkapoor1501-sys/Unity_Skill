"""Contract tests for the reproducible release build wrapper."""

from __future__ import annotations

import gzip
import hashlib
import importlib
import importlib.util
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

EPOCH = 1793318400


def packaging_tool():
    assert importlib.util.find_spec("tools.reproducible_build") is not None, (
        "the reproducible build helper is not implemented"
    )
    return importlib.import_module("tools.reproducible_build")


def write_sdist(path: Path, timestamp: int, *, unsafe: str | None = None) -> None:
    with path.open("wb") as raw:
        with gzip.GzipFile(
            filename=f"source-{timestamp}.tar", mode="wb", fileobj=raw, mtime=timestamp
        ) as compressed:
            with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for name, content in reversed(
                    [
                        ("demo-1.0/README.md", b"hello\n"),
                        ("demo-1.0/src/demo.py", b"print('demo')\n"),
                    ]
                ):
                    member = tarfile.TarInfo(unsafe or name)
                    member.size = len(content)
                    member.mtime = timestamp + 0.5
                    member.uid, member.gid = timestamp, timestamp
                    member.uname, member.gname = "builder", "machine"
                    member.mode = 0o664
                    archive.addfile(member, io.BytesIO(content))


def test_timestamp_divergent_sdists_become_identical_without_changing_contents(tmp_path):
    tool = packaging_tool()
    first, second = tmp_path / "a.tar.gz", tmp_path / "b.tar.gz"
    write_sdist(first, 100)
    write_sdist(second, 200)
    assert first.read_bytes() != second.read_bytes()
    tool.normalize_sdist(first, EPOCH)
    tool.normalize_sdist(second, EPOCH)
    assert first.read_bytes() == second.read_bytes()
    assert int.from_bytes(first.read_bytes()[4:8], "little") == EPOCH
    assert first.read_bytes()[3] & 8 == 0  # No host-dependent gzip filename.
    with tarfile.open(first, "r:gz") as archive:
        assert archive.getnames() == ["demo-1.0/README.md", "demo-1.0/src/demo.py"]
        assert [archive.extractfile(m).read() for m in archive] == [
            b"hello\n",
            b"print('demo')\n",
        ]
        for member in archive:
            assert (member.mtime, member.uid, member.gid, member.uname, member.gname) == (
                EPOCH,
                0,
                0,
                "",
                "",
            )
            assert member.mode == 0o644


@pytest.mark.parametrize("name", ["../escape", "/absolute", "demo/../escape", "demo\\escape"])
def test_unsafe_archive_names_are_rejected_without_replacing_input(tmp_path, name):
    tool = packaging_tool()
    archive = tmp_path / "unsafe.tar.gz"
    write_sdist(archive, 100, unsafe=name)
    original = archive.read_bytes()
    with pytest.raises(ValueError):
        tool.normalize_sdist(archive, EPOCH)
    assert archive.read_bytes() == original


@pytest.mark.parametrize("kind", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE])
def test_archive_links_and_special_files_are_rejected(tmp_path, kind):
    tool = packaging_tool()
    archive = tmp_path / "link.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        member = tarfile.TarInfo("demo-1.0/link")
        member.type, member.linkname = kind, "../../outside"
        output.addfile(member)
    original = archive.read_bytes()
    with pytest.raises(ValueError):
        tool.normalize_sdist(archive, EPOCH)
    assert archive.read_bytes() == original


def test_invalid_compressed_input_is_rejected_without_replacing_input(tmp_path):
    tool = packaging_tool()
    archive = tmp_path / "broken.tar.gz"
    archive.write_bytes(b"not a gzip archive")
    with pytest.raises(ValueError):
        tool.normalize_sdist(archive, EPOCH)
    assert archive.read_bytes() == b"not a gzip archive"


@pytest.mark.parametrize("epoch", [-1, 4294967296, True, "bad"])
def test_invalid_epoch_is_rejected_before_output_creation(tmp_path, epoch):
    tool = packaging_tool()
    output = tmp_path / "missing" / "release"
    with pytest.raises(ValueError):
        tool.build_release(output, epoch)
    assert not output.parent.exists()


def test_existing_output_is_never_overwritten(tmp_path):
    tool = packaging_tool()
    output = tmp_path / "release"
    output.mkdir()
    marker = output / "keep"
    marker.write_bytes(b"existing")
    with pytest.raises(FileExistsError):
        tool.build_release(output, EPOCH)
    assert marker.read_bytes() == b"existing"


def test_build_preserves_wheel_and_emits_verifiable_receipt(tmp_path, monkeypatch):
    tool = packaging_tool()
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "release"

    def backend(command, *, cwd, env, check):
        assert command[1:4] == ["-m", "build", "--no-isolation"]
        assert Path(cwd) == source
        assert env["SOURCE_DATE_EPOCH"] == str(EPOCH)
        assert check is True
        staging = Path(command[command.index("--outdir") + 1])
        (staging / "demo-1.0-py3-none-any.whl").write_bytes(b"backend wheel bytes")
        write_sdist(staging / "demo-1.0.tar.gz", 123)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(tool.subprocess, "run", backend)
    tool.build_release(output, EPOCH, source=source)
    wheel = output / "demo-1.0-py3-none-any.whl"
    assert wheel.read_bytes() == b"backend wheel bytes"
    receipt = json.loads((output / "build-receipt.json").read_text())
    assert receipt["source_date_epoch"] == EPOCH
    assert set(receipt["sha256"]) == {wheel.name, "demo-1.0.tar.gz"}
    for name, digest in receipt["sha256"].items():
        assert digest == hashlib.sha256((output / name).read_bytes()).hexdigest()


def test_failed_backend_preserves_exit_code_and_does_not_publish(tmp_path, monkeypatch):
    tool = packaging_tool()
    output = tmp_path / "release"

    def backend(command, **kwargs):
        raise subprocess.CalledProcessError(7, command)

    monkeypatch.setattr(tool.subprocess, "run", backend)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", str(EPOCH))
    assert tool.main(["--outdir", str(output)]) == 7
    assert not output.exists()


def test_corrupt_deflate_stream_is_reported_as_invalid_without_replacing_input(tmp_path):
    tool = packaging_tool()
    archive = tmp_path / "corrupt.tar.gz"
    # Valid gzip header followed by a reserved deflate block type.
    original = bytes.fromhex("1f8b08000000000002ff07")
    archive.write_bytes(original)
    with pytest.raises(ValueError):
        tool.normalize_sdist(archive, EPOCH)
    assert archive.read_bytes() == original


def test_hardlinked_archive_is_rejected_without_touching_either_name(tmp_path):
    tool = packaging_tool()
    archive = tmp_path / "source.tar.gz"
    write_sdist(archive, 100)
    linked = tmp_path / "linked.tar.gz"
    linked.hardlink_to(archive)
    original = archive.read_bytes()
    with pytest.raises(ValueError):
        tool.normalize_sdist(linked, EPOCH)
    assert linked.read_bytes() == original == archive.read_bytes()


def test_duplicate_members_are_rejected_without_replacing_archive(tmp_path):
    tool = packaging_tool()
    archive = tmp_path / "duplicate.tar.gz"
    with tarfile.open(archive, "w:gz") as output:
        for _ in range(2):
            member = tarfile.TarInfo("demo-1.0/same")
            output.addfile(member)
    original = archive.read_bytes()
    with pytest.raises(ValueError):
        tool.normalize_sdist(archive, EPOCH)
    assert archive.read_bytes() == original


@pytest.mark.parametrize("limit", ["MAX_ARCHIVE_BYTES", "MAX_TAR_BYTES", "MAX_MEMBERS"])
def test_archive_resource_limits_are_enforced_before_replacement(tmp_path, monkeypatch, limit):
    tool = packaging_tool()
    archive = tmp_path / "large.tar.gz"
    write_sdist(archive, 100)
    original = archive.read_bytes()
    monkeypatch.setattr(tool, limit, 1)
    with pytest.raises(ValueError):
        tool.normalize_sdist(archive, EPOCH)
    assert archive.read_bytes() == original


def test_missing_epoch_does_not_create_output(tmp_path, monkeypatch):
    tool = packaging_tool()
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    output = tmp_path / "release"
    assert tool.main(["--outdir", str(output)]) == 1
    assert not output.exists()


def test_unexpected_backend_output_is_rejected_without_publication(tmp_path, monkeypatch):
    tool = packaging_tool()
    output = tmp_path / "release"

    def backend(command, **kwargs):
        staging = Path(command[command.index("--outdir") + 1])
        (staging / "demo.whl").mkdir()
        write_sdist(staging / "demo.tar.gz", 123)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(tool.subprocess, "run", backend)
    assert tool.main(["--outdir", str(output), "--epoch", str(EPOCH)]) == 1
    assert not output.exists()


def test_non_regular_archive_is_rejected_before_open(tmp_path):
    tool = packaging_tool()
    directory = tmp_path / "directory.tar.gz"
    directory.mkdir()
    with pytest.raises(ValueError):
        tool.normalize_sdist(directory, EPOCH)
    assert directory.is_dir()
