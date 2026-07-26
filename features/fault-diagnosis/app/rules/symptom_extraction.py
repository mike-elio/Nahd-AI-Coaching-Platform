import re
from typing import Any

from app.repositories.symptoms import (
    BOUNDARY_SYMPTOM_HINTS,
    DIRECT_SYMPTOM_RULES,
    STATUS_CODE_HINTS,
)
from app.rules.text_processing import (
    _build_strict_tag_alias_terms,
    _top_unique,
    clamp_confidence,
    collapse_whitespace,
    tokenize_keywords,
)


def _match_symptom_rule(text: str, keywords: set[str], rule: dict[str, set[str]]) -> tuple[int, list[str]]:
    hits = set()
    for keyword in rule.get("keywords", set()):
        normalized = keyword.lower()
        if normalized in keywords:
            hits.add(normalized)
    for phrase in rule.get("phrases", set()):
        normalized = collapse_whitespace(phrase).lower()
        if normalized and normalized in text:
            hits.add(normalized)
    return len(hits), sorted(hits)


def _score_strict_tag_text_support(tag: str, text_bundle: dict[str, Any]) -> tuple[int, list[str]]:
    if isinstance(text_bundle, str):
        tag, text_bundle = text_bundle, {
            "text": collapse_whitespace(tag).lower(),
            "keywords": tokenize_keywords(tag),
        }

    alias_terms = _build_strict_tag_alias_terms(tag)
    hits = []
    for term in alias_terms:
        if not term:
            continue
        if " " in term or "." in term or "-" in term or "#" in term:
            if term in text_bundle["text"]:
                hits.append(term)
        elif term in text_bundle["keywords"]:
            hits.append(term)
    hits = sorted(set(hits))
    return len(hits), hits


def extract_symptom_evidence(problem_text: str) -> dict[str, Any]:
    normalized_text = collapse_whitespace(problem_text).lower()
    keywords = tokenize_keywords(problem_text)
    status_codes = sorted(set(re.findall(r"\b(?:[1-5]\d{2})\b", normalized_text)))
    direct_symptoms = []
    symptom_names = set()
    symptom_hits_by_name: dict[str, list[str]] = {}

    for symptom_name, rule in DIRECT_SYMPTOM_RULES.items():
        hit_count, hits = _match_symptom_rule(normalized_text, keywords, rule)
        if hit_count <= 0:
            continue
        weighted_score = round(min(1.0, 0.24 + hit_count * 0.18), 4)
        direct_symptoms.append(
            {
                "name": symptom_name,
                "score": weighted_score,
                "hits": hits,
            }
        )
        symptom_names.add(symptom_name)
        symptom_hits_by_name[symptom_name] = hits

    for status_code in status_codes:
        for symptom_name in STATUS_CODE_HINTS.get(status_code, set()):
            if symptom_name not in symptom_names:
                direct_symptoms.append(
                    {
                        "name": symptom_name,
                        "score": 0.32,
                        "hits": [status_code],
                    }
                )
                symptom_names.add(symptom_name)
                symptom_hits_by_name[symptom_name] = [status_code]
            elif status_code not in symptom_hits_by_name[symptom_name]:
                symptom_hits_by_name[symptom_name].append(status_code)

    direct_symptoms.sort(key=lambda item: (item["score"], item["name"]), reverse=True)
    symptom_score_map = {
        item["name"]: max(item["score"], clamp_confidence(len(item["hits"]) * 0.18))
        for item in direct_symptoms
    }

    explicit_boundary_expectations = _top_unique(
        [
            boundary_name
            for boundary_name, hints in BOUNDARY_SYMPTOM_HINTS.items()
            if hints & symptom_names
        ],
        5,
    )
    signal_strength = round(
        sum(symptom_score_map.values()) + len(status_codes) * 0.08,
        4,
    )
    domain_biases = {
        "sw": 0.0,
        "cn": 0.0,
        "ai": 0.0,
    }
    for symptom_name in symptom_names:
        symptom_score = symptom_score_map.get(symptom_name, 0.0)
        if symptom_name in {"preflight_failure", "missing_cors_headers", "browser_only_failure", "csrf_or_cookie_failure", "authn_failure", "authz_failure"}:
            domain_biases["sw"] += 0.38 + symptom_score * 0.58
            domain_biases["cn"] += 0.12 if symptom_name in {"preflight_failure", "missing_cors_headers"} else 0.0
        if symptom_name in {"upstream_failure", "connection_refused", "timeout_failure", "tls_failure", "dns_failure"}:
            domain_biases["cn"] += 0.34 + symptom_score * 0.62
            domain_biases["sw"] += 0.1 if symptom_name in {"upstream_failure", "timeout_failure"} else 0.0
        if symptom_name in {"schema_contract_failure", "dependency_mismatch"}:
            domain_biases["sw"] += 0.26 + symptom_score * 0.42
        if symptom_name in {"runtime_startup_failure", "config_or_secret_drift", "database_target_change", "production_only_regression"}:
            domain_biases["sw"] += 0.34 + symptom_score * 0.52
        if symptom_name in {"tokenizer_runtime_mismatch", "embedding_vector_mismatch", "cuda_oom"}:
            domain_biases["ai"] += 0.42 + symptom_score * 0.64
        if symptom_name == "embedding_vector_mismatch":
            domain_biases["sw"] += 0.06
        if symptom_name == "deployment_change":
            for domain_name in domain_biases:
                domain_biases[domain_name] += 0.08
    domain_biases = {
        domain_name: round(clamp_confidence(score / 2.6), 4)
        for domain_name, score in domain_biases.items()
    }
    primary_symptom = direct_symptoms[0]["name"] if direct_symptoms else ""
    secondary_symptoms = [item["name"] for item in direct_symptoms[1:4]]

    return {
        "text": normalized_text,
        "keywords": keywords,
        "status_codes": status_codes,
        "direct_symptoms": direct_symptoms,
        "symptom_names": symptom_names,
        "symptom_score_map": symptom_score_map,
        "symptom_hits_by_name": symptom_hits_by_name,
        "explicit_boundary_expectations": explicit_boundary_expectations,
        "signal_strength": signal_strength,
        "primary_symptom": primary_symptom,
        "secondary_symptoms": secondary_symptoms,
        "domain_biases": domain_biases,
        "has_deployment_change": "deployment_change" in symptom_names,
    }


__all__ = [
    "_match_symptom_rule",
    "_score_strict_tag_text_support",
    "extract_symptom_evidence",
]
