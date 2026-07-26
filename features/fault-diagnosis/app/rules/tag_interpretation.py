from typing import Any

from app.repositories.registries import (
    BOUNDARY_HINT_REGISTRY,
    CLUSTER_REGISTRY,
    ISSUE_FAMILY_REGISTRY,
)
from app.repositories.symptoms import (
    BOUNDARY_SYMPTOM_HINTS,
    CLUSTER_SYMPTOM_HINTS,
    ISSUE_FAMILY_SYMPTOM_HINTS,
)
from app.repositories.tags import (
    ALL_SUPPORTED_TAGS,
    CONFIDENCE_TIER_THRESHOLDS,
    TAG_TO_DOMAIN,
)
from app.rules.symptom_extraction import (
    _score_strict_tag_text_support,
    extract_symptom_evidence,
)
from app.rules.tag_scoring import (
    _boundary_drift_penalty,
    _build_domain_aware_tag_items,
    _cluster_drift_penalty,
    _family_drift_penalty,
    _find_keyword_hits,
    _find_phrase_hits,
    _score_rule_symptom_alignment,
    determine_confidence_tier,
)
from app.rules.text_processing import (
    _fallback_confidence_for_rank,
    _top_unique,
    clamp_confidence,
    collapse_whitespace,
    normalize_domain_label,
    normalize_tag_label,
)


def _resolve_ranked_prediction_items(top_tags: list, tag_confidences: Any = None) -> tuple[list[dict], list[dict]]:
    if not isinstance(top_tags, list) or not top_tags:
        raise ValueError("top_tags must be a non-empty ranked list.")

    flagged_items: list[dict] = []
    resolved_items: list[dict] = []

    confidence_by_tag = None
    confidence_by_rank = None
    if isinstance(tag_confidences, dict):
        confidence_by_tag = {
            normalize_tag_label(tag): value
            for tag, value in tag_confidences.items()
        }
    elif isinstance(tag_confidences, list):
        confidence_by_rank = tag_confidences
    elif tag_confidences is not None:
        raise ValueError("tag_confidences must be a dictionary, a list, or None.")

    for rank, raw_item in enumerate(top_tags, start=1):
        if isinstance(raw_item, dict):
            tag = normalize_tag_label(raw_item.get("tag", ""))
            confidence = raw_item.get("confidence")
        else:
            tag = normalize_tag_label(raw_item)
            confidence = None

        if not tag:
            flagged_items.append(
                {
                    "rank": rank,
                    "tag": "",
                    "reason": "missing_tag",
                }
            )
            continue

        if confidence is None and confidence_by_tag is not None:
            confidence = confidence_by_tag.get(tag)
        if confidence is None and confidence_by_rank is not None and rank - 1 < len(confidence_by_rank):
            confidence = confidence_by_rank[rank - 1]

        if confidence is None:
            flagged_items.append(
                {
                    "rank": rank,
                    "tag": tag,
                    "reason": "missing_confidence",
                }
            )
            continue

        resolved_items.append(
            {
                "rank": rank,
                "tag": tag,
                "confidence": clamp_confidence(confidence),
            }
        )

    return resolved_items, flagged_items


def validate_model_prediction_output(
    predicted_domain: str | dict,
    top_tags: list | None = None,
    tag_confidences: Any = None,
) -> dict[str, Any]:
    if isinstance(predicted_domain, dict) and top_tags is None:
        prediction_payload = predicted_domain
        predicted_domain = prediction_payload.get("predicted_domain", "")
        top_tags = prediction_payload.get("top_3_tags", prediction_payload.get("top_tags", []))
        if tag_confidences is None:
            tag_confidences = prediction_payload.get("tag_confidences")

    canonical_domain = normalize_domain_label(predicted_domain, strict_canonical=True)
    resolved_items, flagged_items = _resolve_ranked_prediction_items(top_tags, tag_confidences)

    supported_items = []
    seen_tags = set()
    for item in resolved_items:
        tag = item["tag"]
        if tag in seen_tags:
            flagged_items.append(
                {
                    "rank": item["rank"],
                    "tag": tag,
                    "reason": "duplicate_tag",
                }
            )
            continue
        if tag not in ALL_SUPPORTED_TAGS:
            flagged_items.append(
                {
                    "rank": item["rank"],
                    "tag": tag,
                    "reason": "unsupported_tag",
                }
            )
            continue

        supported_items.append(
            {
                **item,
                "tag_domain": TAG_TO_DOMAIN[tag],
            }
        )
        seen_tags.add(tag)

    if not supported_items:
        raise ValueError("top_tags must contain at least one supported tag with a confidence score.")

    return {
        "predicted_domain": canonical_domain,
        "supported_items": supported_items,
        "flagged_items": flagged_items,
    }


def normalize_prediction_output(
    problem_text: str | dict,
    predicted_domain: str | None = None,
    top_tags: list | None = None,
    tag_confidences: Any = None,
) -> dict[str, Any]:
    if isinstance(problem_text, dict):
        prediction_payload = problem_text
        problem_text = prediction_payload.get("problem_text", "")
        predicted_domain = prediction_payload.get("predicted_domain", "")
        top_tags = prediction_payload.get("top_3_tags", prediction_payload.get("top_tags", []))
        if tag_confidences is None:
            tag_confidences = prediction_payload.get("tag_confidences")

    validation = validate_model_prediction_output(predicted_domain, top_tags, tag_confidences)
    supported_items = validation["supported_items"]
    total_confidence = sum(item["confidence"] for item in supported_items) or 1.0

    normalized_tags = []
    for normalized_rank, item in enumerate(supported_items, start=1):
        confidence = clamp_confidence(item["confidence"])
        relative_weight = confidence / total_confidence
        normalized_tags.append(
            {
                "tag": item["tag"],
                "confidence": confidence,
                "rank": normalized_rank,
                "relative_weight": round(relative_weight, 4),
                "diagnostic_weight": round(1.0 + confidence * 4.0 + relative_weight * 2.5, 4),
                "tag_domain": item["tag_domain"],
            }
        )

    return {
        "problem_text": collapse_whitespace(problem_text),
        "predicted_domain": validation["predicted_domain"],
        "active_domain": validation["predicted_domain"],
        "top_tags": [item["tag"] for item in normalized_tags],
        "tag_confidences": {
            item["tag"]: item["confidence"]
            for item in normalized_tags
        },
        "ranked_tags": [
            {
                "tag": item["tag"],
                "confidence": item["confidence"],
            }
            for item in normalized_tags
        ],
        "tag_items": normalized_tags,
        "flagged_items": validation["flagged_items"],
    }


def _build_tag_confidence_profile(tag_items: list[dict]) -> dict[str, Any]:
    trusted_tags = [item["tag"] for item in tag_items if item["confidence_tier"] == "trusted"]
    supporting_tags = [item["tag"] for item in tag_items if item["confidence_tier"] == "supporting"]
    weak_tags = [item["tag"] for item in tag_items if item["confidence_tier"] == "weak"]
    symptom_backed_tags = [item["tag"] for item in tag_items if item.get("symptom_support_score", 0.0) >= 0.42]
    routing_tags = [item["tag"] for item in tag_items if item.get("routing_allowed")]

    effective_confidences = [item["effective_confidence"] for item in tag_items]
    average_effective_confidence = sum(effective_confidences) / len(effective_confidences)
    confidence_spread = max(effective_confidences) - min(effective_confidences)

    return {
        "thresholds": dict(CONFIDENCE_TIER_THRESHOLDS),
        "trusted_tags": trusted_tags,
        "supporting_tags": supporting_tags,
        "weak_tags": weak_tags,
        "trusted_count": len(trusted_tags),
        "supporting_count": len(supporting_tags),
        "weak_count": len(weak_tags),
        "symptom_backed_tags": symptom_backed_tags,
        "routing_tags": routing_tags,
        "average_effective_confidence": round(average_effective_confidence, 4),
        "confidence_spread": round(confidence_spread, 4),
        "dominant_tag": tag_items[0]["tag"] if tag_items else None,
        "ranked_tags": [
            {
                "tag": item["tag"],
                "rank": item["rank"],
                "confidence": item["confidence"],
                "effective_confidence": item["effective_confidence"],
                "confidence_tier": item["confidence_tier"],
                "tag_domain": item["tag_domain"],
                "domain_alignment": item["domain_alignment"],
                "symptom_support_score": item.get("symptom_support_score", 0.0),
                "routing_allowed": item.get("routing_allowed", False),
                "routing_confidence": item.get("routing_confidence", 0.0),
            }
            for item in tag_items
        ],
    }


def _infer_boundary_hints(
    active_domain: str,
    tag_items: list[dict],
    text_bundle: dict[str, Any],
) -> list[dict]:
    boundary_hints = []
    symptom_evidence = text_bundle["symptom_evidence"]

    for hint_name, hint_rule in BOUNDARY_HINT_REGISTRY.items():
        matched_tags = [
            item["tag"]
            for item in tag_items
            if item["tag"] in hint_rule["tags"] and item.get("routing_allowed") and item["effective_confidence"] >= CONFIDENCE_TIER_THRESHOLDS["minimum_supported"]
        ]
        tag_score = sum(
            item["routing_confidence"]
            for item in tag_items
            if item["tag"] in hint_rule["tags"] and item.get("routing_allowed")
        )
        keyword_hits = _find_keyword_hits(text_bundle["keywords"], hint_rule["keywords"])
        phrase_hits = _find_phrase_hits(text_bundle["text"], hint_rule["phrases"])
        symptom_score, symptom_hits = _score_rule_symptom_alignment(hint_name, BOUNDARY_SYMPTOM_HINTS, symptom_evidence)

        raw_score = tag_score * 0.82
        raw_score += len(keyword_hits) * 0.12
        raw_score += len(phrase_hits) * 0.18
        raw_score += symptom_score * 0.84
        if active_domain in hint_rule["domains"]:
            raw_score += 0.06
        if hint_name in symptom_evidence["explicit_boundary_expectations"]:
            raw_score += 0.22
        drift_penalty, drift_penalty_reasons = _boundary_drift_penalty(hint_name, symptom_evidence)
        raw_score -= drift_penalty

        if raw_score < 0.18:
            continue

        boundary_hints.append(
            {
                "name": hint_name,
                "score": min(1.0, round(raw_score / 2.2, 4)),
                "matched_tags": matched_tags,
                "matched_keywords": keyword_hits,
                "matched_phrases": phrase_hits,
                "matched_symptoms": symptom_hits,
                "drift_penalty_reasons": drift_penalty_reasons,
            }
        )

    boundary_hints.sort(key=lambda item: item["score"], reverse=True)
    return boundary_hints


def _infer_clusters(
    active_domain: str,
    tag_items: list[dict],
    text_bundle: dict[str, Any],
    boundary_hints: list[dict],
) -> list[dict]:
    boundary_map = {item["name"]: item for item in boundary_hints}
    candidates = []
    symptom_evidence = text_bundle["symptom_evidence"]

    for cluster_id, cluster_rule in CLUSTER_REGISTRY.items():
        if active_domain not in cluster_rule["domains"]:
            continue

        matched_items = [
            item
            for item in tag_items
            if item["tag"] in cluster_rule["tags"] and item.get("routing_allowed")
        ]
        matched_tags = [item["tag"] for item in matched_items]
        keyword_hits = _find_keyword_hits(text_bundle["keywords"], cluster_rule["keywords"])
        phrase_hits = _find_phrase_hits(text_bundle["text"], cluster_rule["phrases"])
        boundary_overlap = [
            boundary_name
            for boundary_name in cluster_rule["boundaries"]
            if boundary_name in boundary_map
        ]
        symptom_score, matched_symptoms = _score_rule_symptom_alignment(cluster_id, CLUSTER_SYMPTOM_HINTS, symptom_evidence)

        if not matched_tags and not keyword_hits and not phrase_hits:
            continue

        raw_score = sum(item["routing_confidence"] for item in matched_items) * 0.98
        raw_score += len(keyword_hits) * 0.12
        raw_score += len(phrase_hits) * 0.16
        raw_score += sum(boundary_map[name]["score"] for name in boundary_overlap) * 0.35
        raw_score += symptom_score * 1.08
        raw_score += 0.14
        if "embedding_vector_mismatch" in symptom_evidence["symptom_names"] and cluster_id == "gpu_acceleration_stack":
            raw_score -= 0.45
        if "cuda_oom" in symptom_evidence["symptom_names"] and cluster_id == "database_connectivity_stack":
            raw_score -= 0.38
        if {"preflight_failure", "missing_cors_headers"} & symptom_evidence["symptom_names"] and cluster_id == "auth_identity_flow":
            raw_score -= 0.18
        drift_penalty, drift_penalty_reasons = _cluster_drift_penalty(cluster_id, symptom_evidence)
        raw_score -= drift_penalty

        confidence = min(1.0, round(raw_score / 2.4, 4))
        if confidence < 0.18:
            continue

        candidates.append(
            {
                "cluster_id": cluster_id,
                "title": cluster_rule["title"],
                "confidence": confidence,
                "matched_tags": matched_tags,
                "matched_keywords": keyword_hits,
                "matched_phrases": phrase_hits,
                "boundary_hints": boundary_overlap,
                "matched_symptoms": matched_symptoms,
                "issue_family_bias": dict(cluster_rule["issue_families"]),
                "drift_penalty_reasons": drift_penalty_reasons,
            }
        )

    if not candidates:
        candidates.append(
            {
                "cluster_id": f"{active_domain}_general_signal_cluster",
                "title": f"{active_domain.upper()} general signal cluster",
                "confidence": 0.2,
                "matched_tags": [item["tag"] for item in tag_items[:2]],
                "matched_keywords": [],
                "matched_phrases": [],
                "boundary_hints": [item["name"] for item in boundary_hints[:2]],
                "issue_family_bias": {},
            }
        )

    candidates.sort(key=lambda item: item["confidence"], reverse=True)
    return candidates


def _generate_issue_family_candidates(
    active_domain: str,
    tag_items: list[dict],
    text_bundle: dict[str, Any],
    inferred_clusters: list[dict],
    boundary_hints: list[dict],
) -> list[dict]:
    cluster_map = {cluster["cluster_id"]: cluster for cluster in inferred_clusters}
    boundary_map = {hint["name"]: hint for hint in boundary_hints}
    candidates = []
    symptom_evidence = text_bundle["symptom_evidence"]

    for family_name, family_rule in ISSUE_FAMILY_REGISTRY.items():
        if active_domain not in family_rule["domains"]:
            continue

        matched_items = [
            item
            for item in tag_items
            if item["tag"] in family_rule["tags"] and item.get("routing_allowed")
        ]
        matched_tags = [item["tag"] for item in matched_items]
        keyword_hits = _find_keyword_hits(text_bundle["keywords"], family_rule["keywords"])
        phrase_hits = _find_phrase_hits(text_bundle["text"], family_rule["phrases"])
        cluster_hits = [
            cluster_id
            for cluster_id in family_rule["clusters"]
            if cluster_id in cluster_map
        ]
        boundary_hits = [
            boundary_name
            for boundary_name in family_rule["boundaries"]
            if boundary_name in boundary_map
        ]
        anti_tag_hits = sorted({item["tag"] for item in tag_items if item["tag"] in family_rule["anti_tags"]})
        symptom_score, matched_symptoms = _score_rule_symptom_alignment(family_name, ISSUE_FAMILY_SYMPTOM_HINTS, symptom_evidence)

        if not matched_tags and not keyword_hits and not cluster_hits and not phrase_hits:
            continue

        raw_score = sum(item["routing_confidence"] for item in matched_items) * 1.08
        raw_score += len(keyword_hits) * 0.14
        raw_score += len(phrase_hits) * 0.18
        raw_score += symptom_score * 1.26
        raw_score += sum(
            cluster_map[cluster_id]["confidence"] * family_rule["clusters"][cluster_id]
            for cluster_id in cluster_hits
        )
        raw_score += sum(
            boundary_map[boundary_name]["score"] * family_rule["boundaries"][boundary_name]
            for boundary_name in boundary_hits
        )
        raw_score -= len(anti_tag_hits) * 0.24
        if family_name == "authentication" and "authz_failure" in symptom_evidence["symptom_names"]:
            raw_score -= 0.22
        if family_name == "authorization_policy" and "authn_failure" in symptom_evidence["symptom_names"] and "authz_failure" not in symptom_evidence["symptom_names"]:
            raw_score -= 0.2
        if family_name == "database_connectivity" and "embedding_vector_mismatch" in symptom_evidence["symptom_names"]:
            raw_score -= 0.28
        if family_name == "retrieval_embeddings_pipeline" and "schema_contract_failure" in symptom_evidence["symptom_names"] and "embedding_vector_mismatch" not in symptom_evidence["symptom_names"]:
            raw_score -= 0.26
        if family_name == "gpu_inference_runtime" and "tokenizer_runtime_mismatch" in symptom_evidence["symptom_names"] and "cuda_oom" not in symptom_evidence["symptom_names"]:
            raw_score -= 0.22
        drift_penalty, drift_penalty_reasons = _family_drift_penalty(family_name, symptom_evidence)
        raw_score -= drift_penalty
        raw_score += 0.15

        if raw_score < 0.24:
            continue

        candidates.append(
            {
                "issue_family": family_name,
                "score": round(raw_score, 4),
                "confidence": min(1.0, round(raw_score / 2.7, 4)),
                "matched_tags": matched_tags,
                "matched_keywords": keyword_hits,
                "matched_phrases": phrase_hits,
                "clusters": cluster_hits,
                "boundary_hints": boundary_hits,
                "matched_symptoms": matched_symptoms,
                "anti_tag_hits": anti_tag_hits,
                "drift_penalty_reasons": drift_penalty_reasons,
            }
        )

    if not candidates:
        candidates.append(
            {
                "issue_family": f"{active_domain}_general_diagnostic",
                "score": 0.2,
                "confidence": 0.2,
                "matched_tags": [item["tag"] for item in tag_items[:2]],
                "matched_keywords": [],
                "matched_phrases": [],
                "clusters": [cluster["cluster_id"] for cluster in inferred_clusters[:1]],
                "boundary_hints": [hint["name"] for hint in boundary_hints[:1]],
                "anti_tag_hits": [],
            }
        )

    candidates.sort(key=lambda item: item["score"], reverse=True)
    for rank, item in enumerate(candidates, start=1):
        item["rank"] = rank
    return candidates


def interpret_prediction_output(
    problem_text: str | dict,
    predicted_domain: str | None = None,
    top_tags: list | None = None,
    tag_confidences: Any = None,
) -> dict[str, Any]:
    if isinstance(problem_text, dict):
        prediction_payload = problem_text
        problem_text = predicted_domain or prediction_payload.get("problem_text", "")
        predicted_domain = prediction_payload.get("predicted_domain", "")
        top_tags = prediction_payload.get("top_3_tags", prediction_payload.get("top_tags", []))
        if tag_confidences is None:
            tag_confidences = prediction_payload.get("tag_confidences")

    normalized_prediction = normalize_prediction_output(
        problem_text,
        predicted_domain,
        top_tags,
        tag_confidences,
    )
    symptom_evidence = extract_symptom_evidence(problem_text)
    explicit_tag_mentions = []
    for tag in ALL_SUPPORTED_TAGS:
        hit_count, _ = _score_strict_tag_text_support(
            tag,
            {
                "text": symptom_evidence["text"],
                "keywords": symptom_evidence["keywords"],
            },
        )
        if hit_count > 0:
            explicit_tag_mentions.append(tag)

    text_bundle = {
        "text": symptom_evidence["text"],
        "keywords": symptom_evidence["keywords"],
        "symptom_evidence": symptom_evidence,
        "explicit_tag_mentions": _top_unique(explicit_tag_mentions, 12),
    }
    domain_aware_tag_items, stack_consistency_flags, exclusion_decisions = _build_domain_aware_tag_items(
        normalized_prediction,
        text_bundle,
    )
    tag_confidence_profile = _build_tag_confidence_profile(domain_aware_tag_items)
    boundary_hints = _infer_boundary_hints(
        normalized_prediction["active_domain"],
        domain_aware_tag_items,
        text_bundle,
    )
    inferred_clusters = _infer_clusters(
        normalized_prediction["active_domain"],
        domain_aware_tag_items,
        text_bundle,
        boundary_hints,
    )
    issue_family_candidates = _generate_issue_family_candidates(
        normalized_prediction["active_domain"],
        domain_aware_tag_items,
        text_bundle,
        inferred_clusters,
        boundary_hints,
    )

    return {
        "active_domain": normalized_prediction["active_domain"],
        "trusted_tags": tag_confidence_profile["trusted_tags"],
        "supporting_tags": tag_confidence_profile["supporting_tags"],
        "weak_tags": tag_confidence_profile["weak_tags"],
        "symptom_evidence": text_bundle["symptom_evidence"],
        "tag_confidence_profile": tag_confidence_profile,
        "inferred_clusters": inferred_clusters,
        "issue_family_candidates": issue_family_candidates,
        "boundary_hints": boundary_hints,
        "stack_consistency_flags": stack_consistency_flags,
        "exclusion_decisions": exclusion_decisions,
        "normalized_prediction": {
            **normalized_prediction,
            "tag_items": domain_aware_tag_items,
        },
    }


def normalize_top_tags(top_tags: list[str]) -> list[str]:
    return [item["tag"] for item in normalize_tag_signals(top_tags)]


def normalize_tag_signals(tag_items: list) -> list[dict]:
    if not isinstance(tag_items, list):
        raise ValueError("tag_items must be a list.")

    cleaned = []
    seen_tags = set()
    for raw_index, item in enumerate(tag_items, start=1):
        if isinstance(item, dict):
            tag = normalize_tag_label(item.get("tag", ""))
            confidence = clamp_confidence(item.get("confidence", _fallback_confidence_for_rank(raw_index)))
        else:
            tag = normalize_tag_label(item)
            confidence = _fallback_confidence_for_rank(raw_index)

        if not tag or tag in seen_tags:
            continue

        cleaned.append(
            {
                "tag": tag,
                "confidence": confidence,
            }
        )
        seen_tags.add(tag)

    if not cleaned:
        raise ValueError("tag_items must contain at least one usable tag.")

    cleaned.sort(key=lambda item: item["confidence"], reverse=True)
    total_confidence = sum(item["confidence"] for item in cleaned) or 1.0

    normalized = []
    for rank, item in enumerate(cleaned, start=1):
        confidence = clamp_confidence(item["confidence"])
        relative_weight = confidence / total_confidence
        normalized.append(
            {
                "tag": item["tag"],
                "confidence": confidence,
                "rank": rank,
                "relative_weight": round(relative_weight, 4),
                "diagnostic_weight": round(1.0 + confidence * 4.0 + relative_weight * 2.5, 4),
                "path_role": "primary" if rank == 1 else "alternative",
            }
        )

    return normalized


def build_tag_signal_map(tag_signals: list[dict]) -> dict[str, dict]:
    return {
        str(item.get("tag", "")).strip().lower(): item
        for item in normalize_tag_signals(tag_signals)
    }


def extract_case_tag_signals(case_summary: dict, fallback_tag_items: list | None = None) -> list[dict]:
    if not isinstance(case_summary, dict):
        raise ValueError("case_summary must be a dictionary.")

    if isinstance(case_summary.get("tag_signals"), list) and case_summary["tag_signals"]:
        return normalize_tag_signals(case_summary["tag_signals"])

    if fallback_tag_items is not None:
        return normalize_tag_signals(fallback_tag_items)

    return normalize_tag_signals(case_summary.get("top_tags", []))


__all__ = [
    "_resolve_ranked_prediction_items",
    "validate_model_prediction_output",
    "normalize_prediction_output",
    "_build_tag_confidence_profile",
    "_infer_boundary_hints",
    "_infer_clusters",
    "_generate_issue_family_candidates",
    "interpret_prediction_output",
    "normalize_top_tags",
    "normalize_tag_signals",
    "build_tag_signal_map",
    "extract_case_tag_signals",
]
