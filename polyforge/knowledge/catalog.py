"""Bounded curated summaries, source provenance and verified capability identities."""

from __future__ import annotations

import json
from importlib.resources import files
from typing import Any
from urllib.parse import urlsplit

from polyforge.capabilities.registry import catalog
from polyforge.contracts.validation import InputError, canonical_digest, validate_schema

SOURCE_HOSTS = frozenset(
    {
        "docs.blender.org",
        "docs.unity3d.com",
        "docs.unity.com",
        "agentskills.io",
        "learn.chatgpt.com",
        "developers.openai.com",
        "code.claude.com",
        "modelcontextprotocol.io",
    }
)


def validate_cards(cards: Any) -> list[dict[str, Any]]:
    if not isinstance(cards, list) or not 1 <= len(cards) <= 128:
        raise InputError("Knowledge catalog requires 1..128 typed cards")
    canonical_digest(cards)
    if len(json.dumps(cards, ensure_ascii=True).encode()) > 1_048_576:
        raise InputError("Knowledge catalog exceeds bounded context budget")
    registered = {entry["id"] for entry in catalog()}
    seen = set()
    for card in cards:
        validate_schema(card, "knowledge_card.schema.json")
        if card["knowledge_id"] in seen:
            raise InputError("Duplicate knowledge identity")
        seen.add(card["knowledge_id"])
        if canonical_digest(card["reference_text"]) != card["doc_digest"]:
            raise InputError("Cached reference text differs from its digest")
        for source in card["sources"]:
            try:
                uri = urlsplit(source["uri"])
                port = uri.port
            except ValueError as exc:
                raise InputError("Malformed official reference URL") from exc
            if (
                uri.scheme != "https"
                or uri.hostname not in SOURCE_HOSTS
                or uri.username
                or uri.password
                or port not in {None, 443}
                or uri.query
                or uri.fragment
            ):
                raise InputError("Reference source is outside the curated official HTTPS allowlist")
        for identifier in card["capability_ids"]:
            if identifier not in registered:
                raise InputError(f"Unknown or unavailable capability: {identifier}")
        if (card["support_state"] == "VERIFIED_EXECUTABLE") != bool(card["capability_ids"]):
            raise InputError(
                "Executable support needs a registered capability, not a documentation claim"
            )
    result: list[dict[str, Any]] = cards
    return result


def catalog_cards() -> list[dict[str, Any]]:
    resource = files("polyforge").joinpath("data/knowledge.json")
    payload = resource.read_bytes()
    if len(payload) > 1_048_576:
        raise InputError("Knowledge catalog exceeds bounded byte budget")
    return validate_cards(json.loads(payload))
