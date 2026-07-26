import re
from typing import Any

from app.config import (
    CANONICAL_DOMAINS,
    CANONICAL_TO_REASONING_DOMAIN,
    DOMAIN_ALIAS_TO_CANONICAL,
    VALID_REFERENCE_SOURCE_TYPES,
)
from app.repositories.tags import TAG_TEXT_ALIASES


def clamp_confidence(value: Any) -> float:
    try:
        value = float(value)
    except Exception:
        value = 0.0
    return max(0.0, min(1.0, value))


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip())


def _top_unique(values: list[str], limit: int) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        normalized = collapse_whitespace(value).lower()
        if not normalized or normalized in seen:
            continue
        ordered.append(normalized)
        seen.add(normalized)
        if len(ordered) >= limit:
            break
    return ordered


def normalize_issue_family(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower())
    normalized = normalized.strip("_")
    if not normalized:
        raise ValueError("Stage 2 response is missing a usable issue_family.")
    return normalized


def normalize_title_key(title: str) -> str:
    return collapse_whitespace(title).lower()


def normalize_tag_label(value: str) -> str:
    return collapse_whitespace(value).lower()


def normalize_domain_label(value: str, *, strict_canonical: bool = False) -> str:
    cleaned = collapse_whitespace(value).lower()
    if cleaned not in DOMAIN_ALIAS_TO_CANONICAL:
        expected = ", ".join(sorted(CANONICAL_DOMAINS))
        raise ValueError(f"predicted_domain must be one of: {expected}.")

    canonical = DOMAIN_ALIAS_TO_CANONICAL[cleaned]
    if strict_canonical and canonical not in CANONICAL_DOMAINS:
        expected = ", ".join(sorted(CANONICAL_DOMAINS))
        raise ValueError(f"predicted_domain must be one of: {expected}.")
    return canonical


def to_reasoning_domain(value: str) -> str:
    return CANONICAL_TO_REASONING_DOMAIN[normalize_domain_label(value)]


def _fallback_confidence_for_rank(rank: int) -> float:
    fallback_by_rank = {
        1: 0.95,
        2: 0.78,
        3: 0.61,
    }
    return fallback_by_rank.get(rank, max(0.15, 0.61 - (rank - 3) * 0.12))


def _build_tag_alias_terms(tag: str) -> set[str]:
    normalized_tag = normalize_tag_label(tag)
    aliases = {normalized_tag}
    aliases.update(TAG_TEXT_ALIASES.get(normalized_tag, set()))
    tokens = [token for token in re.findall(r"[a-z0-9]+", normalized_tag) if len(token) >= 3]
    aliases.update(tokens)
    return {alias.lower() for alias in aliases if alias}


def _build_strict_tag_alias_terms(tag: str) -> set[str]:
    normalized_tag = normalize_tag_label(tag)
    aliases = {normalized_tag}
    aliases.update(TAG_TEXT_ALIASES.get(normalized_tag, set()))
    if "-" in normalized_tag:
        aliases.add(normalized_tag.replace("-", " "))
    if "." in normalized_tag:
        aliases.add(normalized_tag.replace(".", " "))
    return {collapse_whitespace(alias).lower() for alias in aliases if alias}


def tokenize_keywords(*values: str) -> set[str]:
    keywords = set()
    for value in values:
        text = str(value).lower()
        for token in re.findall(r"[a-z0-9]+", text):
            if len(token) >= 3:
                keywords.add(token)
    return keywords


def normalize_reference_source_type(value: str, domain: str) -> str:
    cleaned = str(value).strip().lower()
    if cleaned in VALID_REFERENCE_SOURCE_TYPES:
        return cleaned

    canonical_domain = DOMAIN_ALIAS_TO_CANONICAL.get(cleaned, DOMAIN_ALIAS_TO_CANONICAL.get(str(domain).strip().lower(), "sw"))
    if canonical_domain == "cn":
        return "protocol_reference"
    if canonical_domain == "ai":
        return "library_docs"
    return "official_docs"


__all__ = [
    "clamp_confidence",
    "collapse_whitespace",
    "_top_unique",
    "normalize_issue_family",
    "normalize_title_key",
    "normalize_tag_label",
    "normalize_domain_label",
    "to_reasoning_domain",
    "_fallback_confidence_for_rank",
    "tokenize_keywords",
    "_build_tag_alias_terms",
    "_build_strict_tag_alias_terms",
    "normalize_reference_source_type",
]
