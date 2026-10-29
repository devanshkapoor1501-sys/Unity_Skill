"""Validate PolyForge's portable single-line YAML subset and local reference graph.

This is a strict authoring-profile validator, not a general YAML parser. The
profile deliberately uses only the four simple Agent Skills scalar fields.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from polyforge.cli import build_parser
from polyforge.contracts.validation import InputError


def validate_skill(root: Path) -> dict[str, Any]:
    root = root.resolve()
    source = (root / "SKILL.md").read_text(encoding="utf-8")
    parts = source.split("---\n", 2)
    if len(parts) != 3 or parts[0] != "":
        raise InputError("Skill needs YAML frontmatter")
    metadata = {}
    for line in parts[1].splitlines():
        match = re.fullmatch(
            r"(name|description|license|compatibility): ([^\[\]{}&*!|>#\n]+)", line
        )
        if not match or match[1] in metadata or ": " in match[2]:
            raise InputError(
                "Skill frontmatter must use the portable simple scalar authoring profile"
            )
        metadata[match[1]] = match[2]
    name = metadata.get("name", "")
    if (
        not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name)
        or len(name) > 64
        or name != root.name
        or not 1 <= len(metadata.get("description", "")) <= 1024
        or len(metadata.get("compatibility", "")) > 500
    ):
        raise InputError(
            "Skill name, description or compatibility violates Agent Skills constraints"
        )
    if len(parts[2].split()) >= 1400:
        raise InputError("Skill body exceeds its progressive-disclosure budget")
    documents = sorted(root.rglob("*.md"))
    if len(documents) > 64:
        raise InputError("Skill reference graph exceeds 64 documents")
    targets = set()
    parser = build_parser()
    for path in documents:
        content = path.read_text(encoding="utf-8")
        if len(content) > 65536 or "Historical Appendix A overrides Appendix G" in content:
            raise InputError("Reference exceeds budget or reverses normative precedence")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", content):
            if target.startswith(("https://", "#")):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            if not resolved.is_relative_to(root) or not resolved.is_file() or resolved.is_symlink():
                raise InputError("Missing or escaping skill reference: " + target)
            targets.add(resolved)
        for block in re.findall(r"```console\n(.*?)```", content, re.S):
            import shlex

            for line in block.splitlines():
                if line.startswith("polyforge "):
                    parser.parse_args(shlex.split(line)[1:])
    domains = sorted(p.name for p in (root / "references").iterdir() if p.is_dir())
    if domains != ["blender", "game_design", "quality", "security", "unity", "workforce"]:
        raise InputError("Incomplete domain reference coverage")
    return {
        "name": name,
        "body_words": len(parts[2].split()),
        "references": len(targets),
        "domains": domains,
        "profile": "AGENT_SKILLS_SIMPLE_SCALARS",
        "execution_status": "NOT_RUN",
    }


if __name__ == "__main__":
    print(validate_skill(Path(".agents/skills/polyforge")))
