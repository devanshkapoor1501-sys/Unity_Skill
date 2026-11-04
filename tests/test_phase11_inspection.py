"""Original projects are inspected statically and never modified or launched."""

import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError


def project(root):
    for name, raw in {
        "ProjectSettings/ProjectVersion.txt": b"m_EditorVersion: 6000.6.3f1\n",
        "Packages/manifest.json": b'{"dependencies":{"com.example.local":"1.2.3"}}',
        "Assets/Thing.prefab": b"%YAML 1.1\nreference: {fileID: 1, guid: " + b"a" * 32 + b"}\n",
        "Assets/Thing.prefab.meta": b"fileFormatVersion: 2\nguid: " + b"b" * 32 + b"\n",
        "Assets/Thing.mat": b"%YAML 1.1\n",
        "Assets/Thing.mat.meta": b"fileFormatVersion: 2\nguid: " + b"a" * 32 + b"\n",
        "Library/cache.bin": b"\x00\xffnative cache bytes",
    }.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    return root


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_requested_and_resolved_package_versions_include_transitive_dependencies(tmp_path):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    (root / "Packages/packages-lock.json").write_text(
        json.dumps(
            {
                "dependencies": {
                    "com.example.local": {"version": "1.2.4", "depth": 0, "source": "registry"},
                    "com.example.transitive": {
                        "version": "2.0.0",
                        "depth": 1,
                        "source": "registry",
                    },
                }
            }
        )
    )
    before = snapshot(root)
    result = inspect_project(root)
    assert result.status == "PASS"
    assert result.data["packages"] == {"com.example.local": "1.2.3"}
    assert result.data["resolved_packages"] == {
        "com.example.local": "1.2.4",
        "com.example.transitive": "2.0.0",
    }
    assert result.data["package_resolution"] == "OBSERVED_LOCK_DATA_ONLY"
    assert snapshot(root) == before


@pytest.mark.parametrize(
    "value",
    [
        [],
        {},
        {"dependencies": []},
        {"dependencies": {"a": "1.0"}},
        {"dependencies": {"a": {}}},
        {"dependencies": {"a": {"version": 1}}},
        {"dependencies": {"a": {"version": " "}}},
    ],
)
def test_malformed_resolved_package_metadata_is_rejected_without_writes(tmp_path, value):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    (root / "Packages/packages-lock.json").write_text(json.dumps(value))
    before = snapshot(root)
    with pytest.raises(InputError):
        inspect_project(root)
    assert snapshot(root) == before


def test_missing_package_lock_is_explicitly_unobserved(tmp_path):
    from polyforge.inspection import inspect_project

    result = inspect_project(project(tmp_path))
    assert result.data["resolved_packages"] == {}
    assert result.data["package_resolution"] == "NOT_AVAILABLE"


def test_complete_static_inventory_includes_cache_and_meta_and_never_launches(
    tmp_path, monkeypatch
):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    before = snapshot(root)
    monkeypatch.setattr(
        "subprocess.Popen", lambda *a, **kw: pytest.fail("No native process allowed")
    )
    result = inspect_project(root)
    assert result.status == "PASS"
    assert result.data["inspection_mode"] == "STATIC"
    assert result.data["application_execution"] == "NOT_RUN"
    assert result.data["original_unchanged"] is True
    assert result.data["before_digest"] == result.data["after_digest"]
    assert result.data["unity_version"] == "6000.6.3f1"
    assert result.data["packages"]["com.example.local"] == "1.2.3"
    assert result.data["guid_issues"] == []
    inventory = {row["path"]: row for row in result.data["inventory"]}
    assert set(inventory) == set(before)
    for name, raw in before.items():
        assert inventory[name]["sha256"] == hashlib.sha256(raw).hexdigest()
        assert inventory[name]["bytes"] == len(raw)
    assert snapshot(root) == before


@pytest.mark.parametrize("fault", ["duplicate_guid", "missing_guid", "dangling_guid"])
def test_guid_faults_are_diagnostics_not_an_import_success(tmp_path, fault):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    if fault == "duplicate_guid":
        (root / "Assets/Thing.mat.meta").write_text("guid: " + "b" * 32)
    elif fault == "missing_guid":
        (root / "Assets/Thing.mat.meta").write_text("fileFormatVersion: 2\n")
    else:
        (root / "Assets/Thing.prefab").write_text("reference: {guid: " + "c" * 32 + "}")
    before = snapshot(root)
    result = inspect_project(root)
    assert result.status == "REVIEW" and result.exit_code == 4
    assert any(issue["kind"] == fault for issue in result.data["guid_issues"])
    assert result.data["original_unchanged"] is True
    assert snapshot(root) == before


def test_required_project_metadata_and_read_budgets_fail_without_writes(tmp_path):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    before = snapshot(root)
    with pytest.raises(InputError):
        inspect_project(root, max_files=1)
    with pytest.raises(InputError):
        inspect_project(root, max_total_bytes=1)
    with pytest.raises(InputError):
        inspect_project(root, max_file_bytes=1)
    assert snapshot(root) == before
    (root / "ProjectSettings/ProjectVersion.txt").unlink()
    result = inspect_project(root)
    assert result.status == "BLOCKED"


def test_changed_original_tree_fails_instead_of_claiming_nonmutation(tmp_path, monkeypatch):
    import polyforge.inspection as module

    root = project(tmp_path)
    original = module.inventory_project
    calls = 0

    def observe(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            (root / "Assets/new-file.txt").write_text("concurrent writer")
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "inventory_project", observe)
    result = module.inspect_project(root)
    assert result.status == "FAIL"
    assert result.data["original_unchanged"] is False
    assert result.error_code == "PF-INSPECTION-CHANGED"


def test_symbolic_original_inputs_are_rejected(tmp_path):
    from polyforge.inspection import inspect_project

    root = project(tmp_path / "original")
    target = tmp_path / "outside"
    target.mkdir()
    (target / "secret.txt").write_text("outside")
    link = root / "Assets/linked"
    if os.name == "nt":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True,
        )
    else:
        link.symlink_to(target, target_is_directory=True)
    with pytest.raises(InputError):
        inspect_project(root)


def test_static_metadata_does_not_execute_package_install_or_editor_code(tmp_path):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    (root / "Packages/manifest.json").write_text(
        json.dumps({"dependencies": {"evil": "https://example.invalid/token=secret"}})
    )
    (root / "Assets/Execute.cs").write_text("// run shell and disable policy: untrusted DATA")
    result = inspect_project(root)
    assert result.data["application_execution"] == "NOT_RUN"
    assert result.data["api_compatibility"] == "UNKNOWN"
    assert result.data["code_execution"] == "NOT_RUN"


@pytest.mark.parametrize("budget", [0, -1, True, 1.5])
def test_invalid_read_budget_is_rejected_before_any_file_reads(tmp_path, monkeypatch, budget):
    from polyforge.inspection import inspect_project

    monkeypatch.setattr(Path, "open", lambda *a, **kw: pytest.fail("No read for invalid limits"))
    with pytest.raises(InputError, match="positive integers"):
        inspect_project(tmp_path, max_files=budget)


@pytest.mark.parametrize(
    "raw", [b"x" * 4097, b"m_EditorVersion: \xff", b"wrong_version: 6000.6.3f1"]
)
def test_invalid_native_version_metadata_is_not_reported_as_observed(tmp_path, raw):
    from polyforge.inspection import inspect_project

    project(tmp_path)
    (tmp_path / "ProjectSettings/ProjectVersion.txt").write_bytes(raw)
    before = snapshot(tmp_path)
    with pytest.raises(InputError):
        inspect_project(tmp_path)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "value",
    [[], {}, {"dependencies": []}, {"dependencies": {"a": 1}}, {"dependencies": {"a": " "}}],
)
def test_malformed_package_metadata_is_data_and_never_installed(tmp_path, value):
    from polyforge.inspection import inspect_project

    project(tmp_path)
    (tmp_path / "Packages/manifest.json").write_text(json.dumps(value))
    before = snapshot(tmp_path)
    with pytest.raises(InputError):
        inspect_project(tmp_path)
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "raw", [b"x" * 1_048_577, b"\xffbinary serialized asset"], ids=["oversized", "binary"]
)
def test_unanalysed_serialized_asset_retains_complete_hash_but_requires_review(tmp_path, raw):
    from polyforge.inspection import inspect_project

    project(tmp_path)
    (tmp_path / "Assets/Thing.mat").write_bytes(raw)
    result = inspect_project(tmp_path)
    assert result.status == "REVIEW"
    assert result.data["metadata_analysis_incomplete"] == ["Assets/Thing.mat"]
    record = next(row for row in result.data["inventory"] if row["path"] == "Assets/Thing.mat")
    assert record["sha256"] == hashlib.sha256(raw).hexdigest()
    assert result.data["original_unchanged"]


def test_builtin_guid_is_not_misreported_as_a_missing_user_asset(tmp_path):
    from polyforge.inspection import inspect_project

    project(tmp_path)
    (tmp_path / "Assets/Thing.prefab").write_text(
        "reference: {guid: 0000000000000000f000000000000000}"
    )
    result = inspect_project(tmp_path)
    assert result.status == "PASS" and not result.data["guid_issues"]


def test_missing_package_manifest_is_blocked_without_creating_it(tmp_path):
    from polyforge.inspection import inspect_project

    project(tmp_path)
    (tmp_path / "Packages/manifest.json").unlink()
    result = inspect_project(tmp_path)
    assert result.status == "BLOCKED" and not (tmp_path / "Packages/manifest.json").exists()


def test_directory_exhaustion_is_bounded_even_without_files(tmp_path):
    from polyforge.inspection import inspect_project

    (tmp_path / "a/b/c").mkdir(parents=True)
    with pytest.raises(InputError, match="directory inventory"):
        inspect_project(tmp_path, max_files=2)


def test_concurrent_change_before_metadata_analysis_cannot_claim_unchanged(tmp_path, monkeypatch):
    import polyforge.inspection as module

    project(tmp_path)
    native = module.inventory_project

    def hashed(*args, **kwargs):
        value = native(*args, **kwargs)
        (tmp_path / "Assets/Thing.mat").write_bytes(b"changed")
        return value

    monkeypatch.setattr(module, "inventory_project", hashed)
    with pytest.raises(InputError, match="changed before static metadata"):
        module.inspect_project(tmp_path)


def test_historical_inspection_cli_now_executes_static_contract(tmp_path, capsys):
    from polyforge.cli import main

    project(tmp_path)
    before = snapshot(tmp_path)
    assert main(["inspect-project", "--project", str(tmp_path), "--read-only", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["data"]["original_unchanged"] is True
    assert result["data"]["application_execution"] == "NOT_RUN"
    assert snapshot(tmp_path) == before


def test_inventory_retains_mtime_and_inspection_preserves_it(tmp_path):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    original = {
        p.relative_to(root).as_posix(): p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()
    }
    result = inspect_project(root)
    assert {row["path"]: row["mtime_ns"] for row in result.data["inventory"]} == original
    assert result.data["path_diffs"] == []
    assert {
        p.relative_to(root).as_posix(): p.stat().st_mtime_ns for p in root.rglob("*") if p.is_file()
    } == original


def test_mtime_only_mutation_is_failed_with_exact_path_diff(tmp_path, monkeypatch):
    import polyforge.inspection as module

    root = project(tmp_path)
    target = root / "Library/cache.bin"
    native = module.inventory_project
    calls = 0

    def inventory(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            info = target.stat()
            os.utime(target, ns=(info.st_atime_ns, info.st_mtime_ns + 2_000_000_000))
        return native(*args, **kwargs)

    monkeypatch.setattr(module, "inventory_project", inventory)
    result = module.inspect_project(root)
    assert result.status == "FAIL" and result.error_code == "PF-INSPECTION-CHANGED"
    assert result.data["path_diffs"] == [
        {"kind": "modified", "path": "Library/cache.bin", "fields": ["mtime_ns"]}
    ]


def test_added_deleted_and_modified_paths_are_reported(tmp_path, monkeypatch):
    import polyforge.inspection as module

    root = project(tmp_path)
    native = module.inventory_project
    calls = 0

    def inventory(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            (root / "Library/cache.bin").unlink()
            (root / "Assets/new.txt").write_text("new")
            (root / "Assets/Thing.mat").write_text("changed")
        return native(*args, **kwargs)

    monkeypatch.setattr(module, "inventory_project", inventory)
    result = module.inspect_project(root)
    assert result.status == "FAIL"
    diffs = {row["path"]: row for row in result.data["path_diffs"]}
    assert diffs["Library/cache.bin"]["kind"] == "deleted"
    assert diffs["Assets/new.txt"]["kind"] == "added"
    assert diffs["Assets/Thing.mat"]["kind"] == "modified"
    assert {"bytes", "sha256"} <= set(diffs["Assets/Thing.mat"]["fields"])


def test_csharp_syntax_tree_discovers_namespaces_and_generic_nested_types(tmp_path):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    (root / "Assets/Block.cs").write_text("""
// namespace Fake { class Bogus {} }
namespace Game { namespace Play {
public class Outer<T> { public class Inner<U,V> { string s = "class Fake {}"; } }
} }
""")
    (root / "Assets/File.cs").write_text("namespace Game.Play; public class Outer<T,U> {}")
    result = inspect_project(root)
    scripts = {row["path"]: row for row in result.data["known_scripts"]}
    assert scripts["Assets/Block.cs"]["analysis"] == "PARSED"
    assert scripts["Assets/Block.cs"]["parser"] == "tree-sitter-c-sharp==0.23.5"
    assert scripts["Assets/Block.cs"]["namespaces"] == ["Game", "Game.Play"]
    assert [row["qualified_name"] for row in scripts["Assets/Block.cs"]["types"]] == [
        "Game.Play.Outer`1",
        "Game.Play.Outer`1.Inner`2",
    ]
    assert scripts["Assets/File.cs"]["namespaces"] == ["Game.Play"]
    assert scripts["Assets/File.cs"]["types"][0]["qualified_name"] == "Game.Play.Outer`2"
    assert result.data["namespace_clashes"] == []
    assert result.data["semantic_resolution"] == "NOT_RUN"
    assert result.data["proposed_managed_mutations"] == []
    assert result.data["mutation_authorization"] == "NOT_REQUESTED"
    assert any(row["kind"] == "unexecuted_source" for row in result.data["risk_observations"])


def test_duplicate_type_candidates_are_not_confused_with_valid_partial_types(tmp_path):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    for name, source in {
        "First.cs": "namespace Game; public class Duplicate {} public partial class Shared {}",
        "Second.cs": "namespace Game; public class Duplicate {} public partial class Shared {}",
        "Other.cs": "namespace Other; public class Duplicate {}",
    }.items():
        (root / "Assets" / name).write_text(source)
    result = inspect_project(root)
    assert result.status == "REVIEW"
    assert result.data["namespace_clashes"] == [
        {
            "kind": "duplicate_type_candidate",
            "qualified_name": "Game.Duplicate",
            "paths": ["Assets/First.cs", "Assets/Second.cs"],
            "semantic_resolution": "NOT_RUN",
        }
    ]
    assert any(
        row["kind"] == "partial_type_merge_unverified" for row in result.data["risk_observations"]
    )


def test_python_is_ast_parsed_without_running_top_level_code(tmp_path):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    marker = root / "executed.txt"
    (root / "Assets/plugin.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\nclass Plugin: pass\n"
    )
    result = inspect_project(root)
    script = result.data["known_scripts"][0]
    assert script["path"] == "Assets/plugin.py"
    assert script["analysis"] == "PARSED" and script["parser"] == "python.ast"
    assert script["types"][0]["qualified_name"] == "Assets.plugin.Plugin"
    assert not marker.exists()
    assert result.data["code_execution"] == "NOT_RUN"


@pytest.mark.parametrize(
    "name, raw, reason",
    [
        ("Broken.cs", b"namespace X { class", "SYNTAX_ERROR"),
        ("Broken.py", b"class:\n", "SYNTAX_ERROR"),
        ("Binary.cs", b"\xff", "ENCODING_UNSUPPORTED"),
        ("Huge.cs", b" " * 1_048_577, "READ_LIMIT"),
        ("Legacy.js", b"class Old {}", "PARSER_UNAVAILABLE"),
    ],
    ids=["csharp-syntax", "python-syntax", "encoding", "oversized-source", "legacy"],
)
def test_incomplete_source_analysis_requires_review_and_retains_hash(tmp_path, name, raw, reason):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    (root / "Assets" / name).write_bytes(raw)
    result = inspect_project(root)
    assert result.status == "REVIEW"
    script = result.data["known_scripts"][0]
    assert script["analysis"] == reason
    assert result.data["source_analysis_incomplete"] == [f"Assets/{name}"]
    assert (
        next(row for row in result.data["inventory"] if row["path"] == f"Assets/{name}")["sha256"]
        == hashlib.sha256(raw).hexdigest()
    )


def test_namespace_and_type_collision_is_reported_as_semantically_unresolved(tmp_path):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    (root / "Assets/Collision.cs").write_text(
        "namespace Game { namespace Clash { class Child{} } class Clash{} }"
    )
    result = inspect_project(root)
    assert result.status == "REVIEW"
    assert result.data["namespace_clashes"] == [
        {
            "kind": "namespace_type_candidate",
            "qualified_name": "Game.Clash",
            "paths": ["Assets/Collision.cs"],
            "semantic_resolution": "NOT_RUN",
        }
    ]


@pytest.mark.parametrize(
    "suffix, raw",
    [
        ("cs", b";" * 100_001),
        ("py", b"x=0\n" * 25_001),
    ],
    ids=["csharp", "python"],
)
def test_source_node_budget_does_not_claim_complete_analysis(tmp_path, suffix, raw):
    from polyforge.inspection import inspect_project

    root = project(tmp_path)
    (root / f"Assets/Many.{suffix}").write_bytes(raw)
    result = inspect_project(root)
    assert result.status == "REVIEW"
    assert result.data["known_scripts"][0]["analysis"] == "NODE_LIMIT"
    assert result.data["known_scripts"][0]["types"] == []


def test_source_changed_before_ast_analysis_is_rejected(tmp_path, monkeypatch):
    import polyforge.inspection as module

    root = project(tmp_path)
    source = root / "Assets/Source.cs"
    source.write_text("class Before {}")
    native = module.inventory_project

    def inventory(*args, **kwargs):
        rows = native(*args, **kwargs)
        source.write_text("class After {}")
        return rows

    monkeypatch.setattr(module, "inventory_project", inventory)
    with pytest.raises(InputError, match="changed before static source"):
        module.inspect_project(root)


def test_csharp_large_line_numbers_survive_repeated_native_parses(tmp_path):
    import subprocess
    import sys

    # Isolate a native binding failure so it cannot kill the pytest process.
    # Rows above CPython's cached small integers exercise Point.row ownership.
    script = """
import gc
from polyforge.inspection import _csharp_source
raw = b'\\n' * 300 + b'namespace Large { public class Example {} }'
for index in range(100):
    namespaces, declarations, status = _csharp_source(raw)
    assert status == 'PARSED'
    assert namespaces == ['Large']
    assert declarations[0]['line'] == 301
    gc.collect()
print('SAFE_NATIVE_PARSE')
"""
    outcome = subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", script],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert outcome.returncode == 0, outcome.stderr
    assert outcome.stdout.strip() == "SAFE_NATIVE_PARSE"


def test_growing_metadata_cannot_exceed_static_read_budget(tmp_path, monkeypatch):
    import polyforge.inspection as module
    from polyforge.security.paths import WorkspacePolicy

    root = project(tmp_path)
    policy = WorkspacePolicy(root)
    frozen = module.inventory_project(
        policy, max_files=100, max_total_bytes=10_000_000, max_file_bytes=5_000_000
    )
    target = root / "Assets/Thing.mat"
    target.write_bytes(b"x" * 2_097_152)
    native_open = Path.open
    consumed = 0

    class ReadProbe:
        def __init__(self, source):
            self.source = source

        def __enter__(self):
            self.source.__enter__()
            return self

        def __exit__(self, *args):
            return self.source.__exit__(*args)

        def read(self, size=-1):
            nonlocal consumed
            raw = self.source.read(size)
            consumed += len(raw)
            return raw

    def open_file(path, *args, **kwargs):
        source = native_open(path, *args, **kwargs)
        return ReadProbe(source) if path == target else source

    monkeypatch.setattr(Path, "open", open_file)
    with pytest.raises(InputError, match="changed before static metadata"):
        module._guid_observations(policy, frozen)
    assert consumed <= 1_048_577


def test_wide_directory_scan_rejects_at_discovery_budget(tmp_path, monkeypatch):
    import polyforge.inspection as module
    from polyforge.security.paths import WorkspacePolicy

    for index in range(20):
        (tmp_path / f"dir{index}").mkdir()
    native_scan = os.scandir
    seen = []

    class ScanProbe:
        def __init__(self, path):
            self.stream = native_scan(path)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def __iter__(self):
            for entry in self.stream:
                seen.append(entry.name)
                yield entry

    monkeypatch.setattr(module.os, "scandir", ScanProbe)
    with pytest.raises(InputError, match="directory inventory"):
        module.inventory_project(
            WorkspacePolicy(tmp_path), max_files=2, max_total_bytes=100, max_file_bytes=100
        )
    assert len(seen) == 2
