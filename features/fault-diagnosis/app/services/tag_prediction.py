from app.config import CANONICAL_DOMAINS
from app.llm.client import call_ollama_json
from app.llm.prompts import build_prompt
from app.repositories.tags import (
    ALL_SUPPORTED_TAGS,
    TAG_DOMAIN_MEMBERSHIP,
)
from app.rules.text_processing import clamp_confidence, normalize_domain_label
from app.schemas.internal import TAG_PREDICTION_JSON_SCHEMA

ALL_TAGS = ALL_SUPPORTED_TAGS


def infer_domain_from_ranked_tags(tag_items: list[dict], fallback_domain: str) -> str:
    domain_scores = {
        "sw": 0.0,
        "cn": 0.0,
        "ai": 0.0,
    }

    for rank, item in enumerate(tag_items, start=1):
        tag = str(item.get("tag", "")).strip().lower()
        confidence = clamp_confidence(item.get("confidence", 0.0))
        rank_bonus = max(0.0, 0.18 - (rank - 1) * 0.04)
        weighted_score = confidence + rank_bonus

        for domain, allowed_tags in TAG_DOMAIN_MEMBERSHIP.items():
            if tag in allowed_tags:
                domain_scores[domain] += weighted_score

    best_domain = max(domain_scores, key=domain_scores.get)
    fallback_score = domain_scores.get(fallback_domain, 0.0)
    best_score = domain_scores[best_domain]

    if best_score <= 0:
        return fallback_domain if fallback_domain in CANONICAL_DOMAINS else "sw"

    if fallback_domain in CANONICAL_DOMAINS and fallback_score >= best_score * 0.9:
        return fallback_domain
    return best_domain





def validate_and_fix_output(data: dict) -> dict:
    raw_domain = data.get("predicted_domain", data.get("domain", ""))
    try:
        domain = normalize_domain_label(raw_domain, strict_canonical=True)
    except ValueError:
        domain = "sw"

    raw_tags = data.get("top_tags", data.get("top_3_tags", []))

    cleaned = []
    seen = set()

    for item in raw_tags:
        if not isinstance(item, dict):
            continue

        tag = str(item.get("tag", "")).strip().lower()
        confidence = clamp_confidence(item.get("confidence", 0.0))

        if tag in ALL_TAGS and tag not in seen:
            cleaned.append(
                {
                    "tag": tag,
                    "confidence": confidence,
                }
            )
            seen.add(tag)

    for fallback in ["debugging", "logging", "python"]:
        if len(cleaned) >= 3:
            break
        if fallback not in seen:
            cleaned.append({"tag": fallback, "confidence": 0.01})
            seen.add(fallback)

    cleaned = sorted(cleaned[:3], key=lambda item: item["confidence"], reverse=True)
    domain = infer_domain_from_ranked_tags(cleaned, domain)

    return {
        "predicted_domain": domain,
        "top_tags": [item["tag"] for item in cleaned],
        "tag_confidences": {
            item["tag"]: item["confidence"]
            for item in cleaned
        },
        "ranked_tags": cleaned,
    }


def predict_top_3_tags(user_problem: str) -> dict:
    prompt = build_prompt(user_problem)
    data = call_ollama_json(prompt, TAG_PREDICTION_JSON_SCHEMA)
    return validate_and_fix_output(data)


__all__ = [
    "predict_top_3_tags",
    "validate_and_fix_output",
    "infer_domain_from_ranked_tags",
]
