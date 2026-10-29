"""The portable skill is concise, linked, current and limited to implemented commands."""

from pathlib import Path

import pytest

from polyforge.contracts.validation import InputError

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / ".agents/skills/polyforge"


def test_portable_skill_format_links_and_domain_map_are_valid():
    from tools.validate_skill import validate_skill

    result = validate_skill(SKILL)
    assert result["name"] == "polyforge"
    assert result["body_words"] < 1400
    assert result["references"] >= 10
    assert result["domains"] == [
        "blender",
        "game_design",
        "quality",
        "security",
        "unity",
        "workforce",
    ]


@pytest.mark.parametrize("damage", ["name", "description", "link", "permission", "historical"])
def test_missing_reference_unsupported_claim_or_permission_field_fails_validation(tmp_path, damage):
    import shutil

    from tools.validate_skill import validate_skill

    target = tmp_path / "polyforge"
    shutil.copytree(SKILL, target)
    path = target / "SKILL.md"
    text = path.read_text(encoding="utf-8")
    if damage == "name":
        text = text.replace("name: polyforge", "name: WRONG_NAME")
    elif damage == "description":
        text = text.replace("description:", "missing-description:")
    elif damage == "link":
        text += "\n[secret](../../private.md)\n"
    elif damage == "permission":
        text = text.replace("license:", "allowed-tools: shell\nlicense:")
    else:
        text += "\nHistorical Appendix A overrides Appendix G.\n"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(InputError):
        validate_skill(target)


def test_references_cover_decisions_fallbacks_precedence_and_contribution_gates():
    references = "\n".join(p.read_text(encoding="utf-8") for p in SKILL.rglob("*.md"))
    for term in [
        "Geometry Nodes",
        "manual mesh",
        "Animator",
        "Timeline",
        "Shader Graph",
        "SAFE_DISCOVERY",
        "REFERENCE_ONLY",
        "VERSION_PROBED",
        "VERIFIED_IN_WORKFLOW",
        "UNKNOWN",
        "Appendix G",
        "negative",
        "owner approval",
        "DATA_ONLY",
    ]:
        assert term in references
    for host in ["codex", "claude"]:
        assert (ROOT / "docs/hosts" / (host + ".md")).is_file()


def test_inline_and_multiline_reference_commands_are_validated(tmp_path):
    import shutil

    from tools.validate_skill import skill_commands, validate_skill

    target = tmp_path / "polyforge"
    shutil.copytree(SKILL, target)
    reference = target / "references/unity/overview.md"
    with reference.open("a", encoding="utf-8") as stream:
        stream.write(
            "\n`polyforge knowledge list --json`\n```console\n"
            "polyforge knowledge probe \\\n"
            "  --workspace ROOT --tool unity-ui --dry-run --json\n```\n"
        )
    commands = skill_commands(target)
    assert [
        "knowledge",
        "probe",
        "--workspace",
        "ROOT",
        "--tool",
        "unity-ui",
        "--dry-run",
        "--json",
    ] in commands
    validate_skill(target)
    with reference.open("a", encoding="utf-8") as stream:
        stream.write("\n`polyforge unsupported-alias --json`\n")
    with pytest.raises(InputError):
        validate_skill(target)


def test_every_runnable_skill_reference_example_executes(tmp_path):
    import json
    import subprocess
    import sys

    from tools.validate_skill import skill_commands

    (tmp_path / "request.json").write_text(
        json.dumps(
            {"schema_version": "1.0.0", "query": "Explain Geometry Nodes", "output": "EXPLAIN"}
        ),
        encoding="utf-8",
    )
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    commands = skill_commands(SKILL)
    assert commands
    for command in commands:
        args = [str(tmp_path) if arg == "ROOT" else arg for arg in command]
        service = args[:2] == ["mcp", "serve"]
        payload = (
            '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"test","version":"1"}}}\n'
            if service
            else None
        )
        result = subprocess.run(
            [sys.executable, "-m", "polyforge", *args],
            input=payload,
            capture_output=True,
            text=True,
            timeout=20,
            cwd=ROOT,
        )
        assert result.returncode == 0, (args, result.stdout, result.stderr)
        response = json.loads(result.stdout)
        assert response.get("result") if service else response["status"] == "PASS"
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before
