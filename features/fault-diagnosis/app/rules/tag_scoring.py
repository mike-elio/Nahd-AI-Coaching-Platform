from typing import Any

from app.repositories.symptoms import TAG_SYMPTOM_HINTS
from app.repositories.tags import (
    ALL_SUPPORTED_TAGS,
    CONFIDENCE_TIER_THRESHOLDS,
    FRAMEWORK_COMPATIBILITY_GROUPS,
    TAG_TO_DOMAIN,
)
from app.rules.symptom_extraction import (
    _score_strict_tag_text_support,
    extract_symptom_evidence,
)
from app.rules.text_processing import (
    _build_tag_alias_terms,
    _top_unique,
    clamp_confidence,
    collapse_whitespace,
)


def _infer_explicit_text_tag_items(normalized_prediction: dict[str, Any], text_bundle: dict[str, Any]) -> list[dict]:
    existing_tags = {item["tag"] for item in normalized_prediction["tag_items"]}
    inferred = []
    candidate_tags = list(ALL_SUPPORTED_TAGS)

    for tag in candidate_tags:
        if tag in existing_tags:
            continue
        hit_count, hits = _score_strict_tag_text_support(tag, text_bundle)
        if hit_count <= 0:
            continue
        tag_domain = TAG_TO_DOMAIN[tag]
        base_confidence = 0.62 if tag_domain == normalized_prediction["active_domain"] else 0.46
        confidence = clamp_confidence(base_confidence + min(0.18, hit_count * 0.08))
        inferred.append(
            {
                "tag": tag,
                "confidence": confidence,
                "rank": len(normalized_prediction["tag_items"]) + len(inferred) + 1,
                "relative_weight": 0.0,
                "diagnostic_weight": round(0.9 + confidence * 3.2 + hit_count * 0.4, 4),
                "tag_domain": tag_domain,
                "text_inferred": True,
                "text_inferred_hits": hits,
            }
        )

    inferred.sort(
        key=lambda item: (
            item["tag_domain"] == normalized_prediction["active_domain"],
            item["confidence"],
            item["diagnostic_weight"],
        ),
        reverse=True,
    )
    return inferred[:4]


def _extract_text_signal_bundle(problem_text: str) -> dict[str, Any]:
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

    return {
        "text": symptom_evidence["text"],
        "keywords": symptom_evidence["keywords"],
        "symptom_evidence": symptom_evidence,
        "explicit_tag_mentions": _top_unique(explicit_tag_mentions, 12),
    }


def _find_keyword_hits(keyword_pool: set[str], candidates: set[str]) -> list[str]:
    return sorted(keyword_pool & {candidate.lower() for candidate in candidates})


def _find_phrase_hits(text: str, phrases: set[str]) -> list[str]:
    hits = []
    for phrase in phrases:
        normalized_phrase = collapse_whitespace(phrase).lower()
        if normalized_phrase and normalized_phrase in text:
            hits.append(normalized_phrase)
    return sorted(set(hits))


def _symptom_group_present(symptom_evidence: dict[str, Any], candidates: set[str]) -> bool:
    return bool(symptom_evidence.get("symptom_names", set()) & set(candidates))


def _tag_drift_penalty(tag: str, symptom_evidence: dict[str, Any]) -> tuple[float, list[str]]:
    symptom_names = symptom_evidence.get("symptom_names", set())
    penalty = 0.0
    reasons = []

    if "authz_failure" in symptom_names and tag in {"authentication", "cors", "reactjs", "javascript", "typescript"}:
        if not _symptom_group_present(symptom_evidence, {"browser_only_failure", "csrf_or_cookie_failure", "preflight_failure", "missing_cors_headers"}):
            penalty += 0.18 if tag == "authentication" else 0.24
            reasons.append("authz_without_matching_browser_or_authn_support")
    if "authn_failure" in symptom_names and tag == "authorization" and "authz_failure" not in symptom_names:
        penalty += 0.18
        reasons.append("authn_without_authz_support")
    if "dns_failure" in symptom_names and tag in {"routing", "http", "proxy", "reverse-proxy", "nginx", "apache"}:
        if not _symptom_group_present(symptom_evidence, {"upstream_failure", "preflight_failure", "missing_cors_headers", "tls_failure"}):
            penalty += 0.24
            reasons.append("dns_vs_routing_drift")
    if "upstream_failure" in symptom_names and tag == "dns" and "dns_failure" not in symptom_names:
        penalty += 0.18
        reasons.append("upstream_without_dns_support")
    if "schema_contract_failure" in symptom_names and tag in {"dns", "networking", "tls", "ssl", "tcp", "proxy", "routing"}:
        penalty += 0.22
        reasons.append("schema_vs_connectivity_drift")
    if "embedding_vector_mismatch" in symptom_names and tag in {"gpu", "cuda", "pytorch", "tensorflow"} and "cuda_oom" not in symptom_names:
        penalty += 0.26
        reasons.append("retrieval_vs_gpu_drift")
    if "cuda_oom" in symptom_names and tag in {"rag", "embeddings", "vector-database", "sentence-transformers"} and "embedding_vector_mismatch" not in symptom_names:
        penalty += 0.22
        reasons.append("gpu_vs_retrieval_drift")
    if "tokenizer_runtime_mismatch" in symptom_names and tag in {"rag", "embeddings", "vector-database"} and "embedding_vector_mismatch" not in symptom_names:
        penalty += 0.2
        reasons.append("serving_vs_retrieval_drift")

    return round(penalty, 4), reasons


def _boundary_drift_penalty(hint_name: str, symptom_evidence: dict[str, Any]) -> tuple[float, list[str]]:
    symptom_names = symptom_evidence.get("symptom_names", set())
    penalty = 0.0
    reasons = []

    if hint_name == "browser_boundary" and "authz_failure" in symptom_names:
        if not _symptom_group_present(symptom_evidence, {"browser_only_failure", "csrf_or_cookie_failure", "preflight_failure", "missing_cors_headers"}):
            penalty += 0.16
            reasons.append("authz_without_browser_boundary_support")
    if hint_name == "proxy_boundary" and "dns_failure" in symptom_names:
        if not _symptom_group_present(symptom_evidence, {"upstream_failure", "tls_failure", "preflight_failure", "missing_cors_headers"}):
            penalty += 0.18
            reasons.append("dns_without_proxy_boundary_support")
    if hint_name == "network_transport_boundary" and "schema_contract_failure" in symptom_names:
        if not _symptom_group_present(symptom_evidence, {"dns_failure", "tls_failure", "connection_refused", "timeout_failure"}):
            penalty += 0.18
            reasons.append("schema_without_transport_support")
    if hint_name == "database_boundary" and "cuda_oom" in symptom_names and "embedding_vector_mismatch" not in symptom_names:
        penalty += 0.14
        reasons.append("gpu_without_database_support")
    if hint_name == "gpu_inference_boundary" and "embedding_vector_mismatch" in symptom_names and "cuda_oom" not in symptom_names:
        penalty += 0.2
        reasons.append("retrieval_without_gpu_support")
    if hint_name == "model_serving_boundary" and "schema_contract_failure" in symptom_names and "embedding_vector_mismatch" not in symptom_names:
        penalty += 0.16
        reasons.append("schema_without_model_serving_support")

    return round(penalty, 4), reasons


def _cluster_drift_penalty(cluster_id: str, symptom_evidence: dict[str, Any]) -> tuple[float, list[str]]:
    symptom_names = symptom_evidence.get("symptom_names", set())
    penalty = 0.0
    reasons = []

    if cluster_id == "auth_identity_flow" and _symptom_group_present(symptom_evidence, {"dns_failure", "tls_failure", "embedding_vector_mismatch", "cuda_oom"}):
        penalty += 0.24
        reasons.append("non_auth_primary_symptom")
    if cluster_id == "http_proxy_edge" and "dns_failure" in symptom_names and "upstream_failure" not in symptom_names and "preflight_failure" not in symptom_names:
        penalty += 0.22
        reasons.append("dns_over_edge_routing")
    if cluster_id == "database_connectivity_stack" and "embedding_vector_mismatch" in symptom_names and "schema_contract_failure" not in symptom_names:
        penalty += 0.22
        reasons.append("retrieval_over_database_connectivity")
    if cluster_id == "tls_dns_transport" and "upstream_failure" in symptom_names and not _symptom_group_present(symptom_evidence, {"tls_failure", "dns_failure"}):
        penalty += 0.18
        reasons.append("upstream_without_tls_or_dns")
    if cluster_id == "model_serving_pipeline" and "cuda_oom" in symptom_names and "tokenizer_runtime_mismatch" not in symptom_names and "embedding_vector_mismatch" not in symptom_names:
        penalty += 0.16
        reasons.append("gpu_over_model_serving")
    if cluster_id == "gpu_acceleration_stack" and "embedding_vector_mismatch" in symptom_names and "cuda_oom" not in symptom_names:
        penalty += 0.26
        reasons.append("retrieval_over_gpu")

    return round(penalty, 4), reasons


def _family_drift_penalty(family_name: str, symptom_evidence: dict[str, Any]) -> tuple[float, list[str]]:
    symptom_names = symptom_evidence.get("symptom_names", set())
    penalty = 0.0
    reasons = []

    if family_name == "authentication" and "authz_failure" in symptom_names and "authn_failure" not in symptom_names:
        penalty += 0.28
        reasons.append("authorization_over_authentication")
    if family_name == "authorization_policy" and "authn_failure" in symptom_names and "authz_failure" not in symptom_names:
        penalty += 0.24
        reasons.append("authentication_over_authorization")
    if family_name == "http_routing_misconfiguration" and "dns_failure" in symptom_names and "upstream_failure" not in symptom_names:
        penalty += 0.26
        reasons.append("dns_over_http_routing")
    if family_name == "dns_service_discovery" and "upstream_failure" in symptom_names and "dns_failure" not in symptom_names:
        penalty += 0.22
        reasons.append("upstream_over_dns")
    if family_name == "database_connectivity" and "schema_contract_failure" in symptom_names and not _symptom_group_present(symptom_evidence, {"connection_refused", "timeout_failure"}):
        penalty += 0.2
        reasons.append("schema_over_connectivity")
    if family_name == "retrieval_embeddings_pipeline" and "tokenizer_runtime_mismatch" in symptom_names and "embedding_vector_mismatch" not in symptom_names:
        penalty += 0.18
        reasons.append("serving_over_retrieval")
    if family_name == "model_serving_runtime" and "embedding_vector_mismatch" in symptom_names and "tokenizer_runtime_mismatch" not in symptom_names:
        penalty += 0.2
        reasons.append("retrieval_over_serving")
    if family_name == "gpu_inference_runtime" and "embedding_vector_mismatch" in symptom_names and "cuda_oom" not in symptom_names:
        penalty += 0.24
        reasons.append("retrieval_over_gpu")

    return round(penalty, 4), reasons


def determine_confidence_tier(
    confidence: float,
    symptom_support_score: float = 0.0,
    text_support_count: int = 0,
    domain_alignment: str = "direct",
) -> str:
    trusted_threshold = CONFIDENCE_TIER_THRESHOLDS["trusted"]
    supporting_threshold = CONFIDENCE_TIER_THRESHOLDS["supporting"]
    if symptom_support_score >= 0.65:
        trusted_threshold -= 0.08
        supporting_threshold -= 0.05
    elif symptom_support_score >= 0.35:
        trusted_threshold -= 0.04
        supporting_threshold -= 0.03
    if text_support_count >= 2:
        trusted_threshold -= 0.03
        supporting_threshold -= 0.02
    if domain_alignment in {"cross_domain_downweighted", "cross_domain_suppressed_candidate"} and symptom_support_score < 0.55 and text_support_count < 2:
        trusted_threshold += 0.08
        supporting_threshold += 0.1

    if confidence >= trusted_threshold:
        return "trusted"
    if confidence >= supporting_threshold:
        return "supporting"
    return "weak"


def _score_tag_text_support(tag: str, text_bundle: dict[str, Any]) -> tuple[int, list[str]]:
    alias_terms = _build_tag_alias_terms(tag)
    text_hits = []
    for term in alias_terms:
        if " " in term or "." in term or "-" in term or "#" in term:
            if term in text_bundle["text"]:
                text_hits.append(term)
            continue
        if term in text_bundle["keywords"]:
            text_hits.append(term)
    return len(set(text_hits)), sorted(set(text_hits))


def _score_tag_symptom_support(tag: str, symptom_evidence: dict[str, Any]) -> tuple[float, list[str]]:
    symptom_hits = []
    score = 0.0
    for symptom_name in TAG_SYMPTOM_HINTS.get(tag, set()):
        symptom_score = float(symptom_evidence["symptom_score_map"].get(symptom_name, 0.0))
        if symptom_score <= 0:
            continue
        score += 0.26 + symptom_score * 0.74
        symptom_hits.append(symptom_name)

    if tag in {"authentication", "authorization", "jwt", "oauth-2.0"}:
        for status_code in symptom_evidence["status_codes"]:
            if status_code in {"401", "403"}:
                score += 0.18
                symptom_hits.append(f"status_{status_code}")
    if tag in {"dns", "networking", "routing"}:
        for status_code in symptom_evidence["status_codes"]:
            if status_code in {"502", "503", "504"}:
                score += 0.08
                symptom_hits.append(f"status_{status_code}")

    return round(score, 4), _top_unique(symptom_hits, 8)


def _score_rule_symptom_alignment(rule_name: str, symptom_hints: dict[str, set[str]], symptom_evidence: dict[str, Any]) -> tuple[float, list[str]]:
    matched_symptoms = []
    score = 0.0
    for symptom_name in symptom_hints.get(rule_name, set()):
        symptom_score = float(symptom_evidence["symptom_score_map"].get(symptom_name, 0.0))
        if symptom_score <= 0:
            continue
        matched_symptoms.append(symptom_name)
        score += 0.22 + symptom_score * 0.88
    return round(score, 4), _top_unique(matched_symptoms, 6)


def _apply_framework_mixing_rules(
    tag_items: list[dict],
    stack_consistency_flags: list[dict],
    exclusion_decisions: list[dict],
) -> list[dict]:
    adjusted_items = [dict(item) for item in tag_items]

    for group_name, group_tags in FRAMEWORK_COMPATIBILITY_GROUPS.items():
        candidates = [
            item
            for item in adjusted_items
            if item["tag"] in group_tags and item["effective_confidence"] >= CONFIDENCE_TIER_THRESHOLDS["supporting"]
        ]
        if len(candidates) <= 1:
            continue

        candidates.sort(
            key=lambda item: (item["routing_confidence"], item["symptom_support_score"], item["text_support_count"], item["effective_confidence"], -item["rank"]),
            reverse=True,
        )
        primary = candidates[0]
        primary_has_explicit_text = bool(primary.get("text_support_count", 0) > 0 or primary.get("text_inferred"))

        stack_consistency_flags.append(
            {
                "flag": "framework_mix_detected",
                "severity": "warning",
                "group": group_name,
                "primary_tag": primary["tag"],
                "competing_tags": [item["tag"] for item in candidates[1:]],
            }
        )

        for item in candidates[1:]:
            preserve_competitor = item["text_support_count"] >= 2 or item["symptom_support_score"] >= 0.58
            if group_name in {"backend_web_framework", "proxy_server", "backing_store"} and primary_has_explicit_text:
                preserve_competitor = bool(item["text_support_count"] >= 1 or item.get("text_inferred"))

            if preserve_competitor:
                continue

            original_effective_confidence = item["effective_confidence"]
            item["effective_confidence"] = round(
                clamp_confidence(item["effective_confidence"] * 0.54),
                4,
            )
            item["routing_confidence"] = round(clamp_confidence(item["routing_confidence"] * 0.42), 4)
            item["routing_allowed"] = False
            item["forced_routing_disabled"] = True
            exclusion_decisions.append(
                {
                    "target": item["tag"],
                    "decision": "downweighted",
                    "reason": "potential_framework_mixing_without_text_support",
                    "group": group_name,
                    "kept_with": primary["tag"],
                    "previous_effective_confidence": original_effective_confidence,
                    "new_effective_confidence": item["effective_confidence"],
                }
            )

    for item in adjusted_items:
        item["confidence_tier"] = determine_confidence_tier(
            item["effective_confidence"],
            item.get("symptom_support_score", 0.0),
            item.get("text_support_count", 0),
            item.get("domain_alignment", "direct"),
        )
        item["routing_allowed"] = bool(
            not item.get("forced_routing_disabled", False)
            and item.get("domain_alignment") != "cross_domain_suppressed_candidate"
            and (
                item["confidence_tier"] != "weak"
                or item.get("symptom_support_score", 0.0) >= 0.58
                or (item.get("text_support_count", 0) >= 2 and item.get("effective_confidence", 0.0) >= 0.24)
            )
            and item.get("drift_penalty", 0.0) < 0.22
        )

    return adjusted_items


def _build_domain_aware_tag_items(
    normalized_prediction: dict[str, Any],
    text_bundle: dict[str, Any],
) -> tuple[list[dict], list[dict], list[dict]]:
    active_domain = normalized_prediction["active_domain"]
    symptom_evidence = text_bundle["symptom_evidence"]
    domain_biases = symptom_evidence.get("domain_biases", {})
    explicit_tag_mentions = set(text_bundle.get("explicit_tag_mentions", []))
    combined_items = list(normalized_prediction["tag_items"])
    combined_items.extend(_infer_explicit_text_tag_items(normalized_prediction, text_bundle))
    adjusted_items = []
    stack_consistency_flags: list[dict] = []
    exclusion_decisions: list[dict] = list(normalized_prediction["flagged_items"])

    for item in combined_items:
        tag_text_support_count, tag_text_support_terms = _score_tag_text_support(item["tag"], text_bundle)
        symptom_support_score, symptom_support_hits = _score_tag_symptom_support(item["tag"], symptom_evidence)
        drift_penalty, drift_penalty_reasons = _tag_drift_penalty(item["tag"], symptom_evidence)
        explicit_anchor_penalty = 0.0
        explicit_anchor_reasons = []
        for group_name, group_tags in FRAMEWORK_COMPATIBILITY_GROUPS.items():
            explicit_group_tags = explicit_tag_mentions & group_tags
            if item["tag"] not in group_tags or not explicit_group_tags or item["tag"] in explicit_group_tags:
                continue
            if group_name == "backing_store":
                explicit_anchor_penalty = max(explicit_anchor_penalty, 0.24)
                explicit_anchor_reasons.append("explicit_backing_store_anchor")
            elif group_name == "backend_web_framework":
                explicit_anchor_penalty = max(explicit_anchor_penalty, 0.2)
                explicit_anchor_reasons.append("explicit_backend_framework_anchor")
            elif group_name == "proxy_server":
                explicit_anchor_penalty = max(explicit_anchor_penalty, 0.16)
                explicit_anchor_reasons.append("explicit_proxy_anchor")
        is_direct_domain_match = item["tag_domain"] == active_domain
        domain_symptom_pressure = domain_biases.get(item["tag_domain"], 0.0)

        if is_direct_domain_match:
            domain_multiplier = 1.0 + min(0.16, symptom_support_score * 0.08 + tag_text_support_count * 0.02 + domain_symptom_pressure * 0.05)
            domain_alignment = "direct"
        elif symptom_support_score >= 0.65 or (domain_symptom_pressure >= 0.35 and (symptom_support_score >= 0.42 or tag_text_support_count > 0)):
            domain_multiplier = 0.88 + min(0.14, symptom_support_score * 0.08 + domain_symptom_pressure * 0.06)
            domain_alignment = "cross_domain_symptom_supported"
            stack_consistency_flags.append(
                {
                    "flag": "cross_domain_tag_retained",
                    "severity": "info",
                    "tag": item["tag"],
                    "tag_domain": item["tag_domain"],
                    "active_domain": active_domain,
                    "symptom_support_hits": symptom_support_hits,
                }
            )
        elif tag_text_support_count > 0:
            domain_multiplier = 0.72 + min(0.08, symptom_support_score * 0.04 + tag_text_support_count * 0.02)
            domain_alignment = "cross_domain_symptom_supported" if symptom_support_score >= 0.42 else "cross_domain_text_supported"
            stack_consistency_flags.append(
                {
                    "flag": "cross_domain_tag_retained",
                    "severity": "info",
                    "tag": item["tag"],
                    "tag_domain": item["tag_domain"],
                    "active_domain": active_domain,
                    "symptom_support_hits": symptom_support_hits,
                }
            )
        elif item["confidence"] >= CONFIDENCE_TIER_THRESHOLDS["trusted"] or symptom_support_score >= 0.18:
            domain_multiplier = 0.34 + min(0.12, symptom_support_score * 0.16)
            domain_alignment = "cross_domain_downweighted"
            exclusion_decisions.append(
                {
                    "target": item["tag"],
                    "decision": "downweighted",
                    "reason": "cross_domain_signal_without_problem_text_support",
                    "tag_domain": item["tag_domain"],
                    "active_domain": active_domain,
                }
            )
        else:
            domain_multiplier = 0.16
            domain_alignment = "cross_domain_suppressed_candidate"
            exclusion_decisions.append(
                {
                    "target": item["tag"],
                    "decision": "suppressed_bias",
                    "reason": "weak_cross_domain_signal",
                    "tag_domain": item["tag_domain"],
                    "active_domain": active_domain,
                }
            )

        if item.get("text_inferred"):
            domain_multiplier = max(domain_multiplier, 0.9 if is_direct_domain_match else 0.58)
            domain_alignment = "direct_text_inferred" if is_direct_domain_match else "cross_domain_text_inferred"
            stack_consistency_flags.append(
                {
                    "flag": "explicit_stack_tag_inferred_from_text",
                    "severity": "info",
                    "tag": item["tag"],
                    "tag_domain": item["tag_domain"],
                    "active_domain": active_domain,
                    "text_hits": item.get("text_inferred_hits", []),
                }
            )

        effective_confidence = round(
            clamp_confidence(
                item["confidence"] * domain_multiplier
                + min(0.12, symptom_support_score * 0.07)
                + min(0.06, domain_symptom_pressure * 0.04)
                - drift_penalty
                - explicit_anchor_penalty
            ),
            4,
        )
        routing_confidence = round(
            clamp_confidence(
                effective_confidence
                + min(0.12, symptom_support_score * 0.1)
                + min(0.06, tag_text_support_count * 0.02)
            ),
            4,
        )
        effective_diagnostic_weight = round(
            item["diagnostic_weight"] * domain_multiplier
            + symptom_support_score * 1.35
            + tag_text_support_count * 0.15
            + domain_symptom_pressure * 0.32
            - drift_penalty * 3.4
            - explicit_anchor_penalty * 2.6,
            4,
        )
        confidence_tier = determine_confidence_tier(
            effective_confidence,
            symptom_support_score,
            tag_text_support_count,
            domain_alignment,
        )

        adjusted_items.append(
            {
                **item,
                "domain_alignment": domain_alignment,
                "domain_multiplier": round(domain_multiplier, 4),
                "effective_confidence": effective_confidence,
                "effective_diagnostic_weight": effective_diagnostic_weight,
                "text_support_count": tag_text_support_count,
                "text_support_terms": tag_text_support_terms,
                "symptom_support_score": symptom_support_score,
                "symptom_support_hits": symptom_support_hits,
                "domain_symptom_pressure": round(domain_symptom_pressure, 4),
                "drift_penalty": drift_penalty,
                "drift_penalty_reasons": drift_penalty_reasons,
                "explicit_anchor_penalty": round(explicit_anchor_penalty, 4),
                "explicit_anchor_reasons": explicit_anchor_reasons,
                "routing_confidence": routing_confidence,
                "confidence_tier": confidence_tier,
                "text_inferred": bool(item.get("text_inferred")),
            }
        )

    adjusted_items = _apply_framework_mixing_rules(
        adjusted_items,
        stack_consistency_flags,
        exclusion_decisions,
    )
    adjusted_items.sort(key=lambda item: item["rank"])
    return adjusted_items, stack_consistency_flags, exclusion_decisions


__all__ = [
    "_find_keyword_hits",
    "_find_phrase_hits",
    "_symptom_group_present",
    "_extract_text_signal_bundle",
    "_infer_explicit_text_tag_items",
    "_tag_drift_penalty",
    "_boundary_drift_penalty",
    "_cluster_drift_penalty",
    "_family_drift_penalty",
    "_score_tag_text_support",
    "_score_tag_symptom_support",
    "_score_rule_symptom_alignment",
    "_apply_framework_mixing_rules",
    "_build_domain_aware_tag_items",
    "determine_confidence_tier",
]
