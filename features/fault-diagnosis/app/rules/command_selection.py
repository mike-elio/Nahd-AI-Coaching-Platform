from typing import Any

from app.repositories.commands import COMMAND_CATALOG
from app.rules.text_processing import collapse_whitespace


def _normalize_domain(domain: Any) -> str:
    value = collapse_whitespace(domain).lower()
    if value in {"sw", "software"}:
        return "software"
    if value in {"cn", "network", "networking"}:
        return "networking"
    if value in {"ai", "ml", "machine_learning"}:
        return "ai"
    return "software"


def _normalize_tags(tags: Any) -> set[str]:
    if not isinstance(tags, (list, tuple, set)):
        return set()
    return {collapse_whitespace(tag).lower() for tag in tags if collapse_whitespace(tag)}


def _command_matches_context(item: dict[str, Any], context_tags: set[str]) -> bool:
    required_tags = _normalize_tags(item.get("requires_any_tag", []))
    if required_tags and not (required_tags & context_tags):
        return False
    excluded_tags = _normalize_tags(item.get("exclude_if_tag", []))
    if excluded_tags and excluded_tags & context_tags:
        return False
    return True


def select_commands_for_step(domain: str, semantic_key: str, context_tags: Any = None, limit: int = 3) -> list[dict[str, str]]:
    normalized_domain = _normalize_domain(domain)
    normalized_key = collapse_whitespace(semantic_key).lower()
    normalized_context_tags = _normalize_tags(context_tags)
    domain_catalog = COMMAND_CATALOG.get(normalized_domain, {})
    commands = [
        item
        for item in domain_catalog.get(normalized_key, [])
        if _command_matches_context(item, normalized_context_tags)
    ]

    normalized_commands = []
    for item in commands[:limit]:
        label = collapse_whitespace(item.get("label", ""))
        command = collapse_whitespace(item.get("command", ""))
        purpose = collapse_whitespace(item.get("purpose", ""))
        if not all([label, command, purpose]):
            continue
        normalized_commands.append(
            {
                "label": label,
                "command": command,
                "purpose": purpose,
            }
        )
    return normalized_commands


__all__ = ["select_commands_for_step"]
