"""Preflight and copy a pinned, installed template without editing Unity YAML."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
from importlib.resources import files
from pathlib import Path, PurePosixPath

from polyforge.contracts.results import ErrorKind
from polyforge.contracts.validation import InputError, load_json
from polyforge.runner.state import atomic_json
from polyforge.security.paths import WorkspacePolicy

UNITY_VERSION = "6000.6.3f1"


def check_project_idle(policy: WorkspacePolicy) -> None:
    if policy.path("UnityProject/Temp/UnityLockfile").exists():
        raise InputError(
            "Close the managed Unity Editor before building or repairing",
            kind=ErrorKind.POLICY_DENIED,
        )
    for scope in ("Assets", "Packages", "ProjectSettings"):
        path = policy.path("UnityProject/" + scope)
        for child in path.rglob("*"):
            child = policy.path(child)
            if child.is_file() and child.stat().st_nlink > 1:
                raise InputError(
                    "Hardlinked Unity project files are not writable managed outputs",
                    kind=ErrorKind.POLICY_DENIED,
                )


def installed_template(executable: Path) -> Path:
    path = executable.parent / (
        "Data/Resources/PackageManager/ProjectTemplates/com.unity.template.urp-blank-17.2.1.tgz"
    )
    if not path.is_file():
        raise InputError("Install the pinned Unity URP template", kind=ErrorKind.MISSING_DEPENDENCY)
    return path


def template_files(template: Path) -> dict[str, bytes]:
    """Validate the entire archive before any output; never extract links/caches."""
    result: dict[str, bytes] = {}
    total = 0
    try:
        with tarfile.open(template) as archive:
            for member in archive:
                name = member.name
                path = PurePosixPath(name)
                if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
                    raise InputError("Unsafe template member path")
                if not member.isdir() and not member.isfile():
                    raise InputError("Template links and special files are forbidden")
                prefix = "package/ProjectData~/"
                if not member.isfile() or not name.startswith(prefix):
                    continue
                relative = name[len(prefix) :]
                if relative.split("/")[0] not in {"Assets", "ProjectSettings", "Packages"}:
                    continue
                total += member.size
                if total > 134_217_728 or len(result) >= 5000 or relative in result:
                    raise InputError("Template expansion/duplicate member limit")
                stream = archive.extractfile(member)
                assert stream is not None
                result[relative] = stream.read()
        manifest = json.loads(result["Packages/manifest.json"])
        if not isinstance(manifest.get("dependencies"), dict):
            raise ValueError("Missing dependencies")
    except (tarfile.TarError, OSError, KeyError, ValueError) as exc:
        raise InputError(f"Invalid Unity template: {exc}") from exc
    return result


def prepare_project(policy: WorkspacePolicy, template: Path, *, dry_run: bool = False) -> Path:
    """Only initialize a fresh managed project, or reuse its verified package lock."""
    content = template_files(template)
    project = policy.path("UnityProject")
    marker = project / ".polyforge-project.json"
    template_hash = hashlib.sha256(template.read_bytes()).hexdigest()
    if project.exists():
        if not marker.is_file():
            raise InputError("Refusing to open or overwrite an unmanaged UnityProject")
        state = load_json(policy.path(marker))
        manifest = policy.path(project / "Packages/manifest.json")
        if (
            state.get("template_sha256") != template_hash
            or state.get("unity_version") != UNITY_VERSION
            or hashlib.sha256(manifest.read_bytes()).hexdigest() != state.get("manifest_sha256")
        ):
            raise InputError("Managed project template/package identity changed")
        return project
    for relative in content:
        policy.path(project / relative)
    if dry_run:
        return project
    for relative, payload in content.items():
        path = policy.path(project / relative)
        policy.mkdir(path.parent)
        path.write_bytes(payload)
    package = files("unity_package")
    package_path = policy.mkdir(project / "Packages/com.polyforge.engine")
    # The UPM source is an installed Python resource as well as a separate package.
    shutil.copytree(
        str(package),
        package_path,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("__pycache__", "*.py", "*.pyc"),
    )
    manifest = json.loads(content["Packages/manifest.json"])
    manifest["dependencies"]["com.polyforge.engine"] = "file:com.polyforge.engine"
    manifest["testables"] = ["com.polyforge.engine"]
    manifest_path = atomic_json(policy, project / "Packages/manifest.json", manifest)
    version = policy.path(project / "ProjectSettings/ProjectVersion.txt")
    policy.mkdir(version.parent)
    version.write_text(f"m_EditorVersion: {UNITY_VERSION}\n", encoding="utf-8")
    atomic_json(
        policy,
        marker,
        {
            "schema_version": "1.0.0",
            "unity_version": UNITY_VERSION,
            "template_sha256": template_hash,
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "scope": "TRUSTED_LOCAL",
            "game_status": "PARTIAL",
        },
    )
    return project
