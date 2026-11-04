"""Bounded static inspection with complete original-file hash comparison."""

from __future__ import annotations

import ast
import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any

import tree_sitter_c_sharp
from tree_sitter import Language, Node, Parser

from polyforge.contracts.results import ErrorKind, Result
from polyforge.contracts.validation import InputError, canonical_digest, load_json
from polyforge.security.paths import WorkspacePolicy
from polyforge.security.policy import redact


def inventory_project(
    policy: WorkspacePolicy, *, max_files: int, max_total_bytes: int, max_file_bytes: int
) -> list[dict[str, Any]]:
    """Hash every regular file, including Library/cache and GUID-bearing metadata."""
    rows: list[dict[str, Any]] = []
    pending = [policy.root]
    total = 0
    directories = 1
    while pending:
        directory = policy.path(pending.pop())
        with os.scandir(directory) as stream:
            for entry in stream:
                path = policy.path(entry.path)
                before = path.lstat()
                if stat.S_ISDIR(before.st_mode):
                    directories += 1
                    if directories > max_files:
                        raise InputError("Project directory inventory exceeds its read budget")
                    pending.append(path)
                    continue
                if not stat.S_ISREG(before.st_mode):
                    raise InputError("Only regular files/directories may enter static inspection")
                if len(rows) >= max_files or before.st_size > max_file_bytes:
                    raise InputError("Project file inventory exceeds its read budget")
                digest = hashlib.sha256()
                consumed = 0
                with path.open("rb") as source:
                    opened = os.fstat(source.fileno())
                    if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                        raise InputError("Project file identity changed before hashing")
                    while chunk := source.read(1_048_576):
                        consumed += len(chunk)
                        total += len(chunk)
                        if consumed > max_file_bytes or total > max_total_bytes:
                            raise InputError("Project content exceeds its bounded hash budget")
                        digest.update(chunk)
                after = policy.path(path).stat()
                if consumed != before.st_size or (
                    before.st_size,
                    before.st_mtime_ns,
                    before.st_ino,
                    before.st_dev,
                ) != (after.st_size, after.st_mtime_ns, after.st_ino, after.st_dev):
                    raise InputError("Project file changed during hashing")
                rows.append(
                    {
                        "path": path.relative_to(policy.root).as_posix(),
                        "bytes": consumed,
                        "sha256": digest.hexdigest(),
                        "mtime_ns": before.st_mtime_ns,
                    }
                )
    return sorted(rows, key=lambda row: row["path"])


def _path_diffs(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> list[dict[str, Any]]:
    old = {row["path"]: row for row in before}
    new = {row["path"]: row for row in after}
    diffs = []
    for path in sorted(old.keys() | new.keys()):
        if path not in old:
            diffs.append({"kind": "added", "path": path})
        elif path not in new:
            diffs.append({"kind": "deleted", "path": path})
        elif old[path] != new[path]:
            diffs.append(
                {
                    "kind": "modified",
                    "path": path,
                    "fields": [
                        key
                        for key in ("bytes", "sha256", "mtime_ns")
                        if old[path][key] != new[path][key]
                    ],
                }
            )
    return diffs


def _guid_observations(
    policy: WorkspacePolicy, inventory: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    definitions: dict[str, list[str]] = {}
    references: list[tuple[str, str]] = []
    issues: list[dict[str, Any]] = []
    incomplete: list[str] = []
    serialized = {".meta", ".unity", ".prefab", ".asset", ".mat", ".controller", ".anim"}
    for row in inventory:
        path = Path(row["path"])
        if path.parts[0] not in {"Assets", "Packages"} or path.suffix not in serialized:
            continue
        if row["bytes"] > 1_048_576:
            incomplete.append(row["path"])
            continue
        with policy.path(path).open("rb") as source:
            raw = source.read(1_048_577)
        if len(raw) != row["bytes"] or hashlib.sha256(raw).hexdigest() != row["sha256"]:
            raise InputError("Project changed before static metadata analysis")
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            incomplete.append(row["path"])
            continue
        if path.suffix == ".meta":
            matches = re.findall(r"^guid:\s*([a-fA-F0-9]{32})\s*$", text, re.MULTILINE)
            if len(matches) != 1:
                issues.append({"kind": "missing_guid", "path": row["path"]})
            else:
                definitions.setdefault(matches[0].lower(), []).append(row["path"])
        else:
            references.extend(
                (row["path"], value.lower())
                for value in re.findall(r"\bguid:\s*([a-fA-F0-9]{32})\b", text)
            )
    for guid, paths in definitions.items():
        if len(paths) > 1:
            issues.append({"kind": "duplicate_guid", "guid": guid, "paths": sorted(paths)})
    for source_path, guid in references:
        # Unity built-in references are not user-owned project GUID definitions.
        if guid not in definitions and not guid.startswith("0000000000000000"):
            issues.append(
                {
                    "kind": "dangling_guid",
                    "path": source_path,
                    "guid": guid,
                    "resolution": "NOT_FOUND_IN_PROJECT; package/binary lookup NOT_RUN",
                }
            )
    return issues, incomplete


def _csharp_source(raw: bytes) -> tuple[list[str], list[dict[str, Any]], str]:
    """Parse concrete syntax only; assembly and preprocessor semantics are unknown."""
    tree = Parser(Language(tree_sitter_c_sharp.language())).parse(raw)
    if tree.root_node.has_error:
        return [], [], "SYNTAX_ERROR"
    if tree.root_node.named_child_count > 100_000:
        return [], [], "NODE_LIMIT"

    def name(node: Node | None) -> str:
        if node is None:
            return ""
        # Qualified names may contain comments/trivia: read identifier nodes only.
        pending = [node]
        identifiers = []
        while pending:
            current = pending.pop()
            if current.type == "identifier":
                identifiers.append(raw[current.start_byte : current.end_byte].decode().lstrip("@"))
            else:
                pending.extend(reversed(current.named_children))
        return ".".join(identifiers)

    file_namespace = ""
    for child in tree.root_node.named_children:
        if child.type == "file_scoped_namespace_declaration":
            file_namespace = name(child.child_by_field_name("name"))
    namespaces = {file_namespace} if file_namespace else set()
    types: list[dict[str, Any]] = []
    pending = [(tree.root_node, file_namespace, "")]
    visited = 0
    kinds = {
        "class_declaration",
        "struct_declaration",
        "interface_declaration",
        "enum_declaration",
        "record_declaration",
        "delegate_declaration",
    }
    while pending:
        node, namespace, container = pending.pop()
        visited += 1
        if visited + len(pending) + node.named_child_count > 100_000:
            return [], [], "NODE_LIMIT"
        if node.type == "namespace_declaration":
            namespace = ".".join(filter(None, (namespace, name(node.child_by_field_name("name")))))
            namespaces.add(namespace)
        elif node.type in kinds:
            local = name(node.child_by_field_name("name"))
            parameters = next(
                (c for c in node.named_children if c.type == "type_parameter_list"), None
            )
            if parameters is not None:
                local += "`" + str(parameters.named_child_count)
            container = ".".join(filter(None, (container, local)))
            types.append(
                {
                    "qualified_name": ".".join(filter(None, (namespace, container))),
                    "kind": node.type.removesuffix("_declaration"),
                    "partial": any(
                        c.type == "modifier" and raw[c.start_byte : c.end_byte] == b"partial"
                        for c in node.named_children
                    ),
                    # tree-sitter 0.26.0's Point.row accessor corrupts native
                    # ownership for large rows on our pinned Windows build.
                    # Count UTF-8 newline bytes instead; no Point is allocated.
                    "line": raw.count(b"\n", 0, node.start_byte) + 1,
                }
            )
        pending.extend((child, namespace, container) for child in reversed(node.named_children))
    return sorted(namespaces), types, "PARSED"


def _python_source(raw: bytes, path: Path) -> tuple[list[str], list[dict[str, Any]], str]:
    try:
        tree = ast.parse(raw, filename=path.as_posix())
    except (SyntaxError, ValueError, RecursionError):
        return [], [], "SYNTAX_ERROR"
    namespace = ".".join(path.with_suffix("").parts)
    types = []
    pending: list[tuple[ast.AST, str]] = [(tree, namespace)]
    visited = 0
    while pending:
        node, scope = pending.pop()
        visited += 1
        if visited + len(pending) > 100_000:
            return [], [], "NODE_LIMIT"
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scope += "." + node.name
            if isinstance(node, ast.ClassDef):
                types.append(
                    {
                        "qualified_name": scope,
                        "kind": "class",
                        "partial": False,
                        "line": node.lineno,
                    }
                )
        pending.extend((child, scope) for child in reversed(list(ast.iter_child_nodes(node))))
    return [namespace], types, "PARSED"


def _source_observations(
    policy: WorkspacePolicy, inventory: list[dict[str, Any]]
) -> dict[str, Any]:
    scripts: list[dict[str, Any]] = []
    risks: list[dict[str, Any]] = []
    definitions: dict[tuple[str, str], list[dict[str, Any]]] = {}
    namespace_paths: dict[str, set[str]] = {}
    parsers = {".cs": "tree-sitter-c-sharp==0.23.5", ".py": "python.ast"}
    for row in inventory:
        path = Path(row["path"])
        suffix = path.suffix.lower()
        if suffix not in {".cs", ".py", ".js", ".boo"}:
            continue
        script: dict[str, Any] = {
            "path": row["path"],
            "parser": parsers.get(suffix),
            "namespaces": [],
            "types": [],
            "analysis": "PARSER_UNAVAILABLE",
        }
        if row["bytes"] > 1_048_576:
            script["analysis"] = "READ_LIMIT"
        elif suffix in parsers:
            with policy.path(path).open("rb") as stream:
                raw = stream.read(1_048_577)
            if hashlib.sha256(raw).hexdigest() != row["sha256"]:
                raise InputError("Project changed before static source analysis")
            try:
                # Tree-sitter input is UTF-8; Python's AST handles encoding cookies itself.
                if suffix == ".cs":
                    raw = raw.decode("utf-8-sig").encode("utf-8")
                    namespaces, types, analysis = _csharp_source(raw)
                else:
                    namespaces, types, analysis = _python_source(raw, path)
                script.update(namespaces=namespaces, types=types, analysis=analysis)
            except UnicodeDecodeError:
                script["analysis"] = "ENCODING_UNSUPPORTED"
        scripts.append(script)
        risks.append(
            {"kind": "unexecuted_source", "path": row["path"], "execution_safety": "NOT_ASSESSED"}
        )
        for declaration in script["types"]:
            definitions.setdefault((suffix, declaration["qualified_name"]), []).append(
                {**declaration, "path": row["path"]}
            )
        if suffix == ".cs":
            for namespace in script["namespaces"]:
                parts = namespace.split(".")
                for count in range(1, len(parts) + 1):
                    namespace_paths.setdefault(".".join(parts[:count]), set()).add(row["path"])
    clashes = []
    for (suffix, qualified_name), declarations in sorted(definitions.items()):
        if suffix == ".cs" and qualified_name in namespace_paths:
            clashes.append(
                {
                    "kind": "namespace_type_candidate",
                    "qualified_name": qualified_name,
                    "paths": sorted(
                        namespace_paths[qualified_name] | {row["path"] for row in declarations}
                    ),
                    "semantic_resolution": "NOT_RUN",
                }
            )
        if len(declarations) < 2:
            continue
        paths = sorted({row["path"] for row in declarations})
        if (
            all(row["partial"] for row in declarations)
            and len({row["kind"] for row in declarations}) == 1
        ):
            risks.append(
                {
                    "kind": "partial_type_merge_unverified",
                    "qualified_name": qualified_name,
                    "paths": paths,
                }
            )
        else:
            clashes.append(
                {
                    "kind": "duplicate_type_candidate",
                    "qualified_name": qualified_name,
                    "paths": paths,
                    "semantic_resolution": "NOT_RUN",
                }
            )
    return {
        "known_scripts": scripts,
        "namespace_clashes": clashes,
        "source_analysis_incomplete": [
            row["path"] for row in scripts if row["analysis"] != "PARSED"
        ],
        "risk_observations": risks,
        "semantic_resolution": "NOT_RUN",
        "source_limits": {"max_file_bytes": 1_048_576, "max_nodes": 100_000},
        "proposed_managed_mutations": [],
        "mutation_authorization": "NOT_REQUESTED",
    }


def inspect_project(
    project: Path,
    *,
    max_files: int = 100_000,
    max_total_bytes: int = 17_179_869_184,
    max_file_bytes: int = 1_073_741_824,
) -> Result:
    """Never open Unity or write any original file, metadata, cache or log."""
    if any(
        type(value) is not int or value < 1
        for value in (max_files, max_total_bytes, max_file_bytes)
    ):
        raise InputError("Static inspection budgets must be positive integers")
    policy = WorkspacePolicy(project)
    limits = dict(
        max_files=max_files, max_total_bytes=max_total_bytes, max_file_bytes=max_file_bytes
    )
    before = inventory_project(policy, **limits)
    version_file = policy.path("ProjectSettings/ProjectVersion.txt")
    packages_file = policy.path("Packages/manifest.json")
    version = None
    if version_file.is_file():
        with version_file.open("rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise InputError("ProjectVersion metadata exceeds 4 KiB")
        try:
            match = re.search(r"^m_EditorVersion:\s*([^\s]+)\s*$", raw.decode("utf-8-sig"), re.M)
        except UnicodeDecodeError as exc:
            raise InputError("Invalid ProjectVersion encoding") from exc
        if match is None:
            raise InputError("Missing native m_EditorVersion metadata")
        version = match.group(1)
    packages: dict[str, str] = {}
    if packages_file.is_file():
        metadata = load_json(packages_file)
        if not isinstance(metadata, dict) or not isinstance(metadata.get("dependencies"), dict):
            raise InputError("Package manifest needs a dependencies object")
        for name, value in metadata["dependencies"].items():
            if not isinstance(value, str) or not value.strip():
                raise InputError("Package dependency values must be nonempty strings")
            packages[name] = redact(value)
    lock_file = policy.path("Packages/packages-lock.json")
    resolved_packages: dict[str, str] = {}
    if lock_file.is_file():
        lock = load_json(lock_file)
        if not isinstance(lock, dict) or not isinstance(lock.get("dependencies"), dict):
            raise InputError("Package lock needs a dependencies object")
        for name, entry in lock["dependencies"].items():
            value = entry.get("version") if isinstance(entry, dict) else None
            if not isinstance(value, str) or not value.strip():
                raise InputError("Resolved package versions must be nonempty strings")
            resolved_packages[name] = redact(value)
    issues, incomplete = _guid_observations(policy, before)
    sources = _source_observations(policy, before)
    after = inventory_project(policy, **limits)
    unchanged = before == after
    data = {
        "inspection_mode": "STATIC",
        "application_execution": "NOT_RUN",
        "code_execution": "NOT_RUN",
        "api_compatibility": "UNKNOWN",
        "original_unchanged": unchanged,
        "before_digest": canonical_digest(before),
        "after_digest": canonical_digest(after),
        "inventory": before,
        "assets": [row["path"] for row in before if row["path"].startswith("Assets/")],
        "path_diffs": _path_diffs(before, after),
        "unity_version": version,
        "packages": packages,
        "resolved_packages": resolved_packages,
        "package_resolution": "OBSERVED_LOCK_DATA_ONLY" if lock_file.is_file() else "NOT_AVAILABLE",
        "guid_issues": issues,
        "metadata_analysis_incomplete": incomplete,
        "network": "DISABLED",
        "trust_mode": "STATIC_UNTRUSTED_DATA_ONLY",
        "limits": limits,
        **sources,
    }
    if not unchanged:
        return Result(status="FAIL", exit_code=6, error_code="PF-INSPECTION-CHANGED", data=data)
    if version is None or not packages_file.is_file():
        return Result(
            status="BLOCKED",
            exit_code=int(ErrorKind.MISSING_DEPENDENCY),
            error_code="PF-INSPECTION-NOT-PROJECT",
            data=data,
        )
    if (
        issues
        or incomplete
        or sources["source_analysis_incomplete"]
        or sources["namespace_clashes"]
    ):
        return Result(status="REVIEW", exit_code=4, error_code="PF-INSPECTION-REVIEW", data=data)
    return Result(data=data)
