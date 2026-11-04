"""Build with the standard frontend and canonicalize only sdist container metadata.

Run ``python -m tools.reproducible_build --outdir dist/release --epoch 1793318400``.
The destination must not exist. The environment variable SOURCE_DATE_EPOCH may
supply the epoch instead. Use identical sources and build dependencies for
reproducible results; this wrapper does not rewrite wheel or source contents.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import stat
import subprocess
import sys
import tarfile
import tempfile
import zlib
from pathlib import Path, PurePosixPath

MAX_ARCHIVE_BYTES = 256 * 1024 * 1024
MAX_TAR_BYTES = 512 * 1024 * 1024
MAX_MEMBERS = 100_000


def _validate_epoch(epoch: int) -> None:
    if type(epoch) is not int or not 0 <= epoch <= 0xFFFFFFFF:
        raise ValueError("epoch must be an integer from 0 through 4294967295")


def _reject_links(path: Path) -> None:
    for component in (path, *path.parents):
        try:
            info = component.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError(f"linked or reparse paths are not supported: {component}")


def _read_regular(path: Path) -> bytes:
    _reject_links(path)
    initial = path.lstat()
    if not stat.S_ISREG(initial.st_mode) or initial.st_nlink != 1:
        raise ValueError(f"artifact must be a regular file with one link: {path}")
    descriptor = os.open(
        path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    )
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(f"artifact must be a regular file with one link: {path}")
        if info.st_size > MAX_ARCHIVE_BYTES:
            raise ValueError("artifact exceeds the compressed size limit")
        result = source.read(MAX_ARCHIVE_BYTES + 1)
    if len(result) > MAX_ARCHIVE_BYTES:
        raise ValueError("artifact exceeds the compressed size limit")
    return result


def _canonical_sdist(data: bytes, epoch: int) -> bytes:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data), mode="rb") as compressed:
            raw = compressed.read(MAX_TAR_BYTES + 1)
        if len(raw) > MAX_TAR_BYTES:
            raise ValueError("sdist exceeds the uncompressed size limit")
        with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as archive:
            members: list[tarfile.TarInfo] = []
            names: set[str] = set()
            for member in archive:
                name = member.name.rstrip("/")
                if (
                    not name
                    or len(name) > 4096
                    or "\\" in name
                    or ":" in name
                    or PurePosixPath(name).is_absolute()
                    or any(part in {"", ".", ".."} for part in name.split("/"))
                ):
                    raise ValueError(f"unsafe archive member: {member.name!r}")
                if name in names:
                    raise ValueError(f"duplicate archive member: {name}")
                if not (member.isfile() or member.isdir()) or member.sparse is not None:
                    raise ValueError(f"unsupported archive member: {name}")
                if member.size < 0 or (member.isdir() and member.size):
                    raise ValueError(f"invalid archive member size: {name}")
                names.add(name)
                members.append(member)
                if len(members) > MAX_MEMBERS:
                    raise ValueError("sdist exceeds the member count limit")
            if not members:
                raise ValueError("sdist is empty")
            output = io.BytesIO()
            with gzip.GzipFile(filename="", fileobj=output, mode="wb", mtime=epoch) as zipped:
                with tarfile.open(fileobj=zipped, mode="w", format=tarfile.PAX_FORMAT) as target:
                    for member in sorted(members, key=lambda item: item.name.rstrip("/")):
                        canonical = tarfile.TarInfo(member.name.rstrip("/"))
                        canonical.type = tarfile.DIRTYPE if member.isdir() else tarfile.REGTYPE
                        canonical.size = member.size
                        canonical.mtime = epoch
                        canonical.mode = 0o755 if member.isdir() or member.mode & 0o111 else 0o644
                        target.addfile(
                            canonical, archive.extractfile(member) if member.isfile() else None
                        )
            return output.getvalue()
    except (OSError, EOFError, tarfile.TarError, zlib.error) as error:
        raise ValueError(f"invalid sdist: {error}") from error


def normalize_sdist(path: Path, epoch: int) -> None:
    """Replace a regular sdist with canonical bytes, without extracting files."""
    _validate_epoch(epoch)
    path = Path(path).absolute()
    canonical = _canonical_sdist(_read_regular(path), epoch)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            output.write(canonical)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def build_release(outdir: Path, epoch: int, *, source: Path | None = None) -> Path:
    """Build wheel and sdist, then publish artifacts and a SHA-256 receipt."""
    _validate_epoch(epoch)
    outdir = Path(outdir).absolute()
    source = Path.cwd() if source is None else Path(source).absolute()
    _reject_links(outdir)
    if outdir.exists():
        raise FileExistsError(f"output directory already exists: {outdir}")
    environment = dict(os.environ, SOURCE_DATE_EPOCH=str(epoch))
    # Build away from the source tree so intermediate artifacts cannot enter the sdist.
    with tempfile.TemporaryDirectory(prefix="polyforge-repro-") as temporary:
        staging = Path(temporary)
        subprocess.run(
            [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(staging)],
            cwd=source,
            env=environment,
            check=True,
        )
        artifacts = sorted(staging.iterdir())
        if (
            len(artifacts) != 2
            or sum(p.name.endswith(".whl") for p in artifacts) != 1
            or sum(p.name.endswith(".tar.gz") for p in artifacts) != 1
        ):
            raise ValueError("build must produce exactly one wheel and one .tar.gz sdist")
        # Validate every output before modifying or publishing any artifact.
        contents = {artifact.name: _read_regular(artifact) for artifact in artifacts}
        for name, content in contents.items():
            if name.endswith(".tar.gz"):
                contents[name] = _canonical_sdist(content, epoch)
        receipt = {
            "source_date_epoch": epoch,
            "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in contents.items()},
        }
        _reject_links(outdir)
        outdir.parent.mkdir(parents=True, exist_ok=True)
        outdir.mkdir()  # Exclusive creation refuses an existing output, even an empty directory.
        for name, content in contents.items():
            with (outdir / name).open("xb") as output:
                output.write(content)
        with (outdir / "build-receipt.json").open("x", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(receipt, sort_keys=True, indent=2) + "\n")
    return outdir


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--epoch", type=int, default=os.environ.get("SOURCE_DATE_EPOCH"))
    args = parser.parse_args(argv)
    try:
        build_release(args.outdir, args.epoch, source=args.source)
    except subprocess.CalledProcessError as error:
        return error.returncode
    except (OSError, ValueError) as error:
        print(f"reproducible build: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
