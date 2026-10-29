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
