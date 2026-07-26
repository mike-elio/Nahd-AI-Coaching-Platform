from typing import Any

from app.config import VALID_DOMAINS
from app.repositories.registries import CLUSTER_REGISTRY
from app.repositories.step_templates import (
    BASE_STEP_TEMPLATES,
    BOUNDARY_LABELS,
    BOUNDARY_STEP_TEMPLATES,
    CLUSTER_STEP_TEMPLATES,
    DOMAIN_TAGS,
    FAMILY_STEP_SEQUENCE,
    FAMILY_STEP_TEMPLATES,
    PHASE_ORDER,
    TAG_STEP_TEMPLATES,
)
from app.rules.symptom_extraction import extract_symptom_evidence
from app.rules.tag_interpretation import build_tag_signal_map, extract_case_tag_signals
from app.rules.text_processing import (
    clamp_confidence,
    collapse_whitespace,
    normalize_domain_label,
    normalize_reference_source_type,
    normalize_title_key,
    tokenize_keywords,
)


def _humanize_slug(value: str) -> str:
    return collapse_whitespace(str(value).replace("_", " ").replace("-", " ").replace(".", " "))


def _humanize_tag(tag: str) -> str:
    normalized = str(tag).strip().lower()
    overrides = {
        "jwt": "JWT",
        "oauth-2.0": "OAuth 2.0",
        "fastapi": "FastAPI",
        "django": "Django",
        "reactjs": "React",
        "nginx": "Nginx",
        "kubernetes": "Kubernetes",
        "postgresql": "PostgreSQL",
        "mysql": "MySQL",
        "redis": "Redis",
        "pytorch": "PyTorch",
        "cuda": "CUDA",
        "gpu": "GPU",
        "dns": "DNS",
        "tls": "TLS",
        "ssl": "SSL",
        "rag": "RAG",
        "model-serving": "model serving",
    }
    if normalized in overrides:
        return overrides[normalized]
    return _humanize_slug(normalized)


def _top_unique(values: list[str], limit: int) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        key = normalize_title_key(value)
        if not key or key in seen:
            continue
        ordered.append(value)
        seen.add(key)
        if len(ordered) >= limit:
            break
    return ordered


def _flatten_text_values(value: Any) -> list[str]:
    if isinstance(value, str):
        cleaned = collapse_whitespace(value)
        return [cleaned] if cleaned else []
    if isinstance(value, dict):
        flattened = []
        for nested in value.values():
            flattened.extend(_flatten_text_values(nested))
        return flattened
    if isinstance(value, (list, tuple, set)):
        flattened = []
        for nested in value:
            flattened.extend(_flatten_text_values(nested))
        return flattened
    return []


def _phrase_candidates(text: str) -> set[str]:
    tokens = [token for token in tokenize_keywords(text) if token]
    phrases = set()
    for size in (2, 3, 4):
        for index in range(0, max(0, len(tokens) - size + 1)):
            phrases.add(" ".join(tokens[index:index + size]))
    return phrases


def _text_signature(value: str) -> set[str]:
    stopwords = {
        "the", "and", "with", "from", "that", "this", "runtime", "failing",
        "path", "request", "service", "verify", "confirm", "check", "inspect",
    }
    return {
        token
        for token in tokenize_keywords(value.replace("_", " "))
        if token not in stopwords
    }


def _is_near_duplicate_text(value: str, previous_values: list[str]) -> bool:
    current = _text_signature(value)
    if not current:
        return True
    for previous in previous_values:
        previous_signature = _text_signature(previous)
        if not previous_signature:
            continue
        overlap = len(current & previous_signature)
        if overlap / max(1, min(len(current), len(previous_signature))) >= 0.78:
            return True
    return False


def _dedupe_near_texts(values: list[str], limit: int = 6) -> list[str]:
    deduped = []
    for value in values:
        cleaned = collapse_whitespace(value)
        if not cleaned or _is_near_duplicate_text(cleaned, deduped):
            continue
        deduped.append(cleaned)
        if len(deduped) >= limit:
            break
    return deduped


def _dedupe_ranked_hypotheses(hypotheses: list[dict], limit: int = 6) -> list[dict]:
    deduped = []
    titles = []
    for hypothesis in hypotheses:
        if not isinstance(hypothesis, dict):
            continue
        title = collapse_whitespace(hypothesis.get("title", ""))
        if not title or _is_near_duplicate_text(title, titles):
            continue
        deduped.append(hypothesis)
        titles.append(title)
        if len(deduped) >= limit:
            break
    return deduped


def _boundary_map(items: list[dict]) -> dict[str, dict]:
    return {
        item["name"]: item
        for item in items
        if isinstance(item, dict) and item.get("name")
    }


def _cluster_map(items: list[dict]) -> dict[str, dict]:
    return {
        item["cluster_id"]: item
        for item in items
        if isinstance(item, dict) and item.get("cluster_id")
    }


def _build_evidence_profile(
    problem_text: str,
    case_summary: dict,
    reasoning_stage: dict,
    primary_issue_family: str,
    selected_reasoning_cluster: str,
    primary_path: str,
    possible_causes: list[str],
    ranked_hypotheses: list[dict],
    symptom_evidence: dict,
) -> dict[str, Any]:
    evidence_values = [
        problem_text,
        primary_issue_family,
        selected_reasoning_cluster,
        primary_path,
        " ".join(possible_causes),
    ]
    evidence_values.extend(_flatten_text_values(ranked_hypotheses[:4]))
    evidence_values.extend(_flatten_text_values(case_summary.get("boundary_hints", [])))
    evidence_values.extend(_flatten_text_values(reasoning_stage.get("boundary_hints", [])))
    evidence_values.extend(_flatten_text_values(symptom_evidence))
    evidence_text = collapse_whitespace(" ".join(evidence_values)).lower()
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "into", "used", "using",
        "before", "after", "current", "failing", "failure", "path", "request", "service",
        "runtime", "configured", "expected", "intended", "active", "dominant", "primary",
        "issue", "family", "cluster", "selected", "evidence", "diagnostic",
    }
    tokens = {token for token in tokenize_keywords(evidence_text) if token not in stopwords}
    phrases = {
        phrase
        for phrase in _phrase_candidates(evidence_text)
        if len(phrase) >= 7 and not all(token in stopwords for token in phrase.split())
    }
    return {
        "text": evidence_text,
        "tokens": tokens,
        "phrases": phrases,
    }


def _extract_text_features(problem_text: str, ctx_tokens: list[str]) -> dict[str, Any]:
    symptom_evidence = extract_symptom_evidence(problem_text)
    tokens = tokenize_keywords(problem_text, " ".join(ctx_tokens)) | set(symptom_evidence["keywords"])
    return {
        "text": symptom_evidence["text"],
        "tokens": tokens,
        "status_codes": symptom_evidence["status_codes"],
        "direct_symptoms": symptom_evidence["direct_symptoms"],
        "symptom_names": symptom_evidence["symptom_names"],
        "symptom_score_map": symptom_evidence["symptom_score_map"],
        "primary_symptom": symptom_evidence["direct_symptoms"][0]["name"] if symptom_evidence["direct_symptoms"] else "",
        "has_deployment_change": symptom_evidence["has_deployment_change"],
    }


def _semantic_symptom_bonus(template: dict, ctx: dict) -> float:
    semantic_key = template["semantic_key"]
    symptom_names = ctx["text_features"]["symptom_names"]
    primary_family = ctx["primary_issue_family"]
    bonus = 0.0

    if semantic_key in {"replay_preflight_origin", "cors_origin_alignment"} and {"preflight_failure", "missing_cors_headers"} & symptom_names:
        bonus += 34.0
    if semantic_key in {"browser_request_shape", "react_request_construction"} and "browser_only_failure" in symptom_names:
        bonus += 18.0
    if semantic_key in {"auth_claim_validation", "jwt_claim_integrity", "authorization_policy_check"} and "authz_failure" in symptom_names:
        bonus += 32.0
    if semantic_key == "auth_artifact_integrity" and "authn_failure" in symptom_names:
        bonus += 28.0
    if semantic_key in {"session_cookie_boundary", "django_security_runtime"} and "csrf_or_cookie_failure" in symptom_names:
        bonus += 28.0
    if semantic_key in {"postgresql_schema_state", "mysql_target_contract", "database_contract_boundary"} and "schema_contract_failure" in symptom_names:
        bonus += 34.0
    if semantic_key in {"database_target_runtime_config", "database_runtime_reachability"} and {"config_or_secret_drift", "database_target_change", "runtime_startup_failure"} & symptom_names:
        bonus += 30.0
    if semantic_key == "database_target_runtime_config" and "schema_contract_failure" in symptom_names and not ({"config_or_secret_drift", "database_target_change", "runtime_startup_failure"} & symptom_names):
        bonus -= 24.0
    if semantic_key == "database_runtime_reachability" and "schema_contract_failure" in symptom_names:
        bonus -= 12.0
    if semantic_key in {"rag_retrieval_path", "retrieval_vector_alignment", "embedding_shape_profile"} and "embedding_vector_mismatch" in symptom_names:
        bonus += 32.0
    if semantic_key in {"model_runtime_validation", "serving_endpoint_mode", "model_serving_branch"} and "embedding_vector_mismatch" in symptom_names:
        bonus -= 10.0
    if semantic_key in {"cuda_capacity_check", "gpu_runtime_pressure", "gpu_workload_shape", "gpu_utilization_check"} and "cuda_oom" in symptom_names:
        bonus += 34.0
    if semantic_key in {"model_runtime_validation", "serving_endpoint_mode"} and "cuda_oom" in symptom_names:
        bonus -= 8.0
    if semantic_key in {"tensor_shape_capture", "tensor_conversion_validation"} and "tensor_shape_mismatch" in symptom_names:
        bonus += 36.0
    if semantic_key in {"tensor_shape_capture", "tensor_conversion_validation"} and "tensor_shape_mismatch" not in symptom_names:
        bonus -= 42.0
    if semantic_key in {"cuda_capacity_check", "gpu_runtime_pressure", "gpu_workload_shape", "gpu_utilization_check"} and "tensor_shape_mismatch" in symptom_names and "cuda_oom" not in symptom_names:
        bonus -= 12.0
    if semantic_key in {"runtime_dns_resolution", "dns_answer_validation"} and "dns_failure" in symptom_names:
        bonus += 32.0
    if semantic_key == "tls_chain_validation" and "tls_failure" in symptom_names:
        bonus += 32.0
    if semantic_key in {"upstream_route_validation", "proxy_forwarding_alignment", "nginx_edge_directives"} and "upstream_failure" in symptom_names:
        bonus += 24.0

    if template["phase"] == "capture_baseline" and len(symptom_names) >= 2:
        bonus -= 8.0
    if primary_family == "cors_proxy_boundary" and semantic_key == "runtime_config_confirmation":
        bonus -= 6.0

    return bonus


def _build_context(problem_text: str, case_summary: dict, reasoning_stage: dict) -> dict[str, Any]:
    canonical_domain = normalize_domain_label(case_summary.get("domain", ""))
    if canonical_domain == "sw":
        reasoning_domain = "software"
    elif canonical_domain == "cn":
        reasoning_domain = "networking"
    else:
        reasoning_domain = "ai"
    tag_signals = extract_case_tag_signals(case_summary)
    tag_signal_map = build_tag_signal_map(tag_signals)
    top_tags = [item["tag"] for item in tag_signals]
    supported_domain_tags = DOMAIN_TAGS[reasoning_domain]
    top_tags = [tag for tag in top_tags if tag in supported_domain_tags]
    boundary_hints = case_summary.get("boundary_hints") or reasoning_stage.get("case_summary", {}).get("boundary_hints") or reasoning_stage.get("reasoning_trace_internal", {}).get("boundary_hints", [])
    boundary_scores = _boundary_map(boundary_hints)
    explicit_boundary_confidence = case_summary.get("boundary_confidence") or reasoning_stage.get("case_summary", {}).get("boundary_confidence") or reasoning_stage.get("reasoning_trace_internal", {}).get("boundary_confidence", {})
    for boundary_name, score in explicit_boundary_confidence.items():
        if boundary_name not in boundary_scores:
            boundary_scores[boundary_name] = {"name": boundary_name, "score": float(score)}
    inferred_clusters = reasoning_stage.get("reasoning_trace_internal", {}).get("cluster_candidates") or []
    if not inferred_clusters:
        selected_cluster = reasoning_stage.get("selected_reasoning_cluster", case_summary.get("selected_reasoning_cluster", "no_cluster_alignment"))
        if selected_cluster in CLUSTER_REGISTRY:
            inferred_clusters = [
                {
                    "cluster_id": selected_cluster,
                    "confidence": 0.6,
                    "matched_tags": [tag for tag in top_tags if tag in CLUSTER_REGISTRY[selected_cluster]["tags"]],
                }
            ]
    cluster_scores = _cluster_map(inferred_clusters)

    trusted_tags = [tag for tag in case_summary.get("trusted_tags", []) if tag in supported_domain_tags]
    supporting_tags = [tag for tag in case_summary.get("supporting_tags", []) if tag in supported_domain_tags]
    weak_tags = [tag for tag in case_summary.get("weak_tags", []) if tag in supported_domain_tags]

    primary_issue_family = collapse_whitespace(reasoning_stage.get("primary_issue_family") or case_summary.get("primary_issue_family") or case_summary.get("issue_family", ""))
    primary_issue_family = primary_issue_family or "authentication"
    selected_reasoning_cluster = collapse_whitespace(reasoning_stage.get("selected_reasoning_cluster") or case_summary.get("selected_reasoning_cluster", "no_cluster_alignment"))
    ranked_hypotheses = reasoning_stage.get("ranked_hypotheses") or reasoning_stage.get("root_cause_hypotheses") or []
    possible_causes = [collapse_whitespace(item) for item in reasoning_stage.get("possible_causes", []) if collapse_whitespace(item)]
    ranked_hypotheses = _dedupe_ranked_hypotheses(ranked_hypotheses, 6)
    possible_causes = _dedupe_near_texts(possible_causes, 6)
    if isinstance(reasoning_stage, dict):
        reasoning_stage["ranked_hypotheses"] = ranked_hypotheses
        reasoning_stage["root_cause_hypotheses"] = ranked_hypotheses
        reasoning_stage["possible_causes"] = possible_causes
    alternative_paths = [collapse_whitespace(item) for item in reasoning_stage.get("alternative_paths", []) if collapse_whitespace(item)]
    primary_path = collapse_whitespace(reasoning_stage.get("primary_path", "")) or "Validate the dominant failure path"

    text_features = _extract_text_features(
        problem_text,
        top_tags + trusted_tags + supporting_tags + weak_tags + [primary_issue_family, selected_reasoning_cluster],
    )
    symptom_evidence = (
        case_summary.get("symptom_evidence")
        or reasoning_stage.get("case_summary", {}).get("symptom_evidence")
        or reasoning_stage.get("reasoning_trace_internal", {}).get("symptom_evidence")
        or {}
    )
    if symptom_evidence:
        text_features["status_codes"] = symptom_evidence.get("status_codes", text_features["status_codes"])
        text_features["direct_symptoms"] = symptom_evidence.get("direct_symptoms", text_features["direct_symptoms"])
        text_features["symptom_names"] = symptom_evidence.get("symptom_names", text_features["symptom_names"])
        text_features["symptom_score_map"] = symptom_evidence.get("symptom_score_map", text_features["symptom_score_map"])
        if symptom_evidence.get("direct_symptoms"):
            text_features["primary_symptom"] = symptom_evidence["direct_symptoms"][0]["name"]
        text_features["has_deployment_change"] = symptom_evidence.get("has_deployment_change", text_features["has_deployment_change"])
        text_features["secondary_symptoms"] = symptom_evidence.get("secondary_symptoms", text_features.get("secondary_symptoms", []))

    evidence_profile = _build_evidence_profile(
        problem_text,
        case_summary,
        reasoning_stage,
        primary_issue_family,
        selected_reasoning_cluster,
        primary_path,
        possible_causes,
        ranked_hypotheses,
        symptom_evidence,
    )

    routing_tags = reasoning_stage.get("reasoning_trace_internal", {}).get("tag_confidence_profile", {}).get("routing_tags") or []
    deployment_change_cues = (
        case_summary.get("deployment_change_cues")
        or reasoning_stage.get("case_summary", {}).get("deployment_change_cues")
        or reasoning_stage.get("reasoning_trace_internal", {}).get("deployment_change_cues", [])
    )
    secondary_families = []
    for item in ranked_hypotheses[:5]:
        if not isinstance(item, dict):
            continue
        for family in item.get("families", []):
            if family and family != primary_issue_family and family not in secondary_families:
                secondary_families.append(family)

    return {
        "problem_text": problem_text,
        "canonical_domain": canonical_domain,
        "reasoning_domain": reasoning_domain,
        "tag_signals": tag_signals,
        "tag_signal_map": tag_signal_map,
        "top_tags": top_tags,
        "trusted_tags": trusted_tags,
        "supporting_tags": supporting_tags,
        "weak_tags": weak_tags,
        "tag_confidence_profile": reasoning_stage.get("reasoning_trace_internal", {}).get("tag_confidence_profile") or {},
        "routing_tags": routing_tags,
        "boundary_hints": boundary_hints,
        "boundary_scores": boundary_scores,
        "cluster_scores": cluster_scores,
        "primary_path": primary_path,
        "alternative_paths": alternative_paths,
        "possible_causes": possible_causes,
        "primary_issue_family": primary_issue_family,
        "secondary_families": secondary_families,
        "selected_reasoning_cluster": selected_reasoning_cluster,
        "ranked_hypotheses": ranked_hypotheses,
        "reasoning_trace_internal": reasoning_stage.get("reasoning_trace_internal", {}),
        "text_features": text_features,
        "symptom_evidence": symptom_evidence,
        "evidence_profile": evidence_profile,
        "deployment_change_cues": deployment_change_cues,
    }


def _compute_target_step_count(ctx: dict) -> int:
    branch_breadth = len(ctx["alternative_paths"]) + len(ctx["secondary_families"][:2])
    complexity = 0
    complexity += 1 if len(ctx["routing_tags"]) >= 2 else 0
    complexity += 1 if len(ctx["boundary_scores"]) >= 2 else 0
    complexity += 1 if ctx["text_features"]["has_deployment_change"] or bool(ctx["deployment_change_cues"]) else 0
    complexity += 1 if branch_breadth >= 2 else 0
    complexity += 1 if ctx["selected_reasoning_cluster"] != "no_cluster_alignment" else 0
    complexity += 1 if any(tag in {"gpu", "cuda", "kubernetes", "proxy", "dns", "jwt", "cors", "model-serving", "rag", "vector-database"} for tag in ctx["trusted_tags"] + ctx["routing_tags"]) else 0
    if complexity >= 6:
        return 6
    if complexity >= 3:
        return 5
    return 4


def _select_phase_sequence(ctx: dict, target_count: int) -> list[str]:
    base = FAMILY_STEP_SEQUENCE.get(ctx["primary_issue_family"], PHASE_ORDER)
    ordered = list(base)
    symptom_names = ctx["text_features"]["symptom_names"]
    primary_symptom = ctx["text_features"].get("primary_symptom", "")

    if {"preflight_failure", "missing_cors_headers"} & symptom_names:
        ordered = [
            "primary_hypothesis_test",
            "boundary_verification",
            "secondary_branch_test",
            "runtime_config_confirmation",
            "capture_baseline",
            "retest_and_closure",
        ]
    elif "authz_failure" in symptom_names:
        ordered = [
            "primary_hypothesis_test",
            "secondary_branch_test",
            "boundary_verification",
            "runtime_config_confirmation",
            "capture_baseline",
            "retest_and_closure",
        ]
    elif "embedding_vector_mismatch" in symptom_names:
        ordered = [
            "secondary_branch_test",
            "primary_hypothesis_test",
            "runtime_config_confirmation",
            "boundary_verification",
            "capture_baseline",
            "retest_and_closure",
        ]
    elif "tokenizer_runtime_mismatch" in symptom_names:
        ordered = [
            "primary_hypothesis_test",
            "runtime_config_confirmation",
            "secondary_branch_test",
            "boundary_verification",
            "capture_baseline",
            "retest_and_closure",
        ]
    elif {"config_or_secret_drift", "database_target_change", "runtime_startup_failure"} & symptom_names and ctx["primary_issue_family"] == "database_connectivity":
        ordered = [
            "primary_hypothesis_test",
            "runtime_config_confirmation",
            "boundary_verification",
            "secondary_branch_test",
            "capture_baseline",
            "retest_and_closure",
        ]
    elif "schema_contract_failure" in symptom_names:
        ordered = [
            "runtime_config_confirmation",
            "primary_hypothesis_test",
            "boundary_verification",
            "secondary_branch_test",
            "capture_baseline",
            "retest_and_closure",
        ]
    elif "tensor_shape_mismatch" in symptom_names:
        ordered = [
            "primary_hypothesis_test",
            "boundary_verification",
            "runtime_config_confirmation",
            "secondary_branch_test",
            "capture_baseline",
            "retest_and_closure",
        ]
    elif "cuda_oom" in symptom_names:
        ordered = [
            "runtime_config_confirmation",
            "primary_hypothesis_test",
            "secondary_branch_test",
            "boundary_verification",
            "capture_baseline",
            "retest_and_closure",
        ]
    elif primary_symptom in {"dns_failure", "tls_failure", "tokenizer_runtime_mismatch", "upstream_failure", "authn_failure"}:
        ordered = [
            "primary_hypothesis_test",
            "boundary_verification" if primary_symptom in {"dns_failure", "tls_failure", "upstream_failure"} else "runtime_config_confirmation",
            "secondary_branch_test",
            "runtime_config_confirmation" if primary_symptom in {"dns_failure", "tls_failure", "upstream_failure"} else "boundary_verification",
            "capture_baseline",
            "retest_and_closure",
        ]
    if ctx["selected_reasoning_cluster"] == "no_cluster_alignment":
        ordered = [phase for phase in ordered if phase != "secondary_branch_test"] + ["secondary_branch_test"]
    if not ctx["text_features"]["has_deployment_change"] and not any(name in ctx["boundary_scores"] for name in ("runtime_boundary", "deployment_change_hint", "model_serving_boundary", "gpu_inference_boundary", "database_boundary")):
        ordered = [phase for phase in ordered if phase != "runtime_config_confirmation"] + ["runtime_config_confirmation"]
    selected = _top_unique(ordered, target_count)
    if "retest_and_closure" not in selected:
        selected = selected[: max(0, target_count - 1)] + ["retest_and_closure"]
    return selected[:target_count]


def _template_libraries_for_context(ctx: dict) -> list[dict]:
    templates = list(BASE_STEP_TEMPLATES)
    templates.extend(FAMILY_STEP_TEMPLATES.get(ctx["primary_issue_family"], []))

    secondary_families = []
    for item in ctx["ranked_hypotheses"][:4]:
        if isinstance(item, dict):
            for family in item.get("families", []):
                secondary_families.append(family)
    for family_name in _top_unique(secondary_families, 3):
        templates.extend(FAMILY_STEP_TEMPLATES.get(family_name, []))

    ranked_boundaries = sorted(
        ctx["boundary_scores"].items(),
        key=lambda item: float(item[1].get("score", 0.0)),
        reverse=True,
    )
    for boundary_name, boundary_meta in ranked_boundaries[:2]:
        if float(boundary_meta.get("score", 0.0)) < 0.35:
            continue
        templates.extend(BOUNDARY_STEP_TEMPLATES.get(boundary_name, []))

    for tag in _top_unique(ctx["trusted_tags"] + ctx["supporting_tags"] + ctx["routing_tags"] + ctx["top_tags"], 8):
        templates.extend(TAG_STEP_TEMPLATES.get(tag, []))

    boundary_aliases = {
        "browser_boundary": {"api", "base", "url", "localhost", "browser", "frontend", "react"},
        "model_serving_boundary": {"model", "serving", "endpoint", "health", "inference", "unavailable"},
        "database_boundary": {"redis", "session", "cache", "state", "store", "ttl", "failover"},
    }
    evidence_tokens = ctx.get("evidence_profile", {}).get("tokens", set())
    for boundary_name, required_tokens in boundary_aliases.items():
        if len(evidence_tokens & required_tokens) >= 3:
            templates.extend(BOUNDARY_STEP_TEMPLATES.get(boundary_name, []))

    selected_cluster = ctx["selected_reasoning_cluster"]
    cluster_confidence = float(ctx["cluster_scores"].get(selected_cluster, {}).get("confidence", 0.0))
    if selected_cluster in CLUSTER_STEP_TEMPLATES and cluster_confidence >= 0.72:
        templates.extend(CLUSTER_STEP_TEMPLATES[selected_cluster])

    return templates


def _template_search_text(template: dict) -> str:
    values = [
        template.get("semantic_key", ""),
        template.get("step_family", ""),
        template.get("title", ""),
        template.get("why", ""),
        template.get("action", ""),
        template.get("expected_result", ""),
        template.get("if_failed", ""),
        template.get("reference_hint", ""),
        " ".join(sorted(template.get("keywords", set()))),
        " ".join(sorted(template.get("tags", set()))),
        " ".join(sorted(template.get("families", set()))),
        " ".join(sorted(template.get("boundaries", set()))),
        " ".join(sorted(template.get("clusters", set()))),
    ]
    return collapse_whitespace(" ".join(values).replace("_", " ").replace("-", " ")).lower()


def _semantic_evidence_targets(ctx: dict) -> set[str]:
    symptom_names = set(ctx["text_features"].get("symptom_names", set()))
    primary_path = normalize_title_key(ctx.get("primary_path", ""))
    possible_text = normalize_title_key(" ".join(ctx.get("possible_causes", [])))
    evidence_text = ctx.get("evidence_profile", {}).get("text", "")
    text = " ".join([primary_path, possible_text, evidence_text])
    targets = set()

    symptom_targets = {
        "api_base_url_mismatch": {"browser_request_shape", "react_request_construction", "upstream_route_validation", "proxy_forwarding_alignment"},
        "cache_session_state_loss": {"cache_session_consistency", "redis_state_path"},
        "model_endpoint_unavailable": {"model_runtime_validation", "serving_endpoint_mode", "model_serving_branch"},
        "missing_runtime_env_var": {"runtime_config_confirmation", "fastapi_dependency_path"},
    }
    for symptom_name in symptom_names:
        targets |= symptom_targets.get(symptom_name, set())

    if all(term in text for term in ("api", "base", "url")) and "browser" in text:
        targets |= {"browser_request_shape", "react_request_construction"}
    if "redis" in text and {"session", "cache", "state"} & set(text.split()):
        targets |= {"cache_session_consistency", "redis_state_path"}
    if "model" in text and "endpoint" in text and ("health" in text or "unavailable" in text):
        targets |= {"model_runtime_validation", "serving_endpoint_mode", "model_serving_branch"}

    return targets


def _evidence_alignment_score(template: dict, ctx: dict) -> float:
    evidence = ctx.get("evidence_profile", {})
    evidence_tokens = evidence.get("tokens", set())
    if not evidence_tokens:
        return 0.0
    template_text = _template_search_text(template)
    template_tokens = tokenize_keywords(template_text)
    token_matches = template_tokens & evidence_tokens
    phrase_matches = {
        phrase
        for phrase in evidence.get("phrases", set())
        if len(phrase) >= 7 and phrase in template_text
    }
    score = min(len(token_matches), 10) * 3.0 + min(len(phrase_matches), 5) * 4.0
    semantic_key = template.get("semantic_key", "")
    if semantic_key in _semantic_evidence_targets(ctx):
        score += 34.0
    if ctx["primary_issue_family"] in template.get("families", set()):
        score += 10.0
    if ctx["selected_reasoning_cluster"] in template.get("clusters", set()):
        score += 6.0
    return score


def _is_generic_fallback_candidate(candidate: dict, ctx: dict) -> bool:
    semantic_key = candidate.get("semantic_key", "")
    title = normalize_title_key(candidate.get("title", ""))
    action = normalize_title_key(candidate.get("action", ""))
    generic_keys = {"capture_primary_symptom", "boundary_trace", "runtime_config_confirmation"}
    generic_fragments = {
        "capture one exact failing transaction",
        "trace the request",
        "inspect the runtime boundary",
        "runtime configuration boundary",
        "network transport boundary",
        "generic configuration",
        "validate the dominant failure path",
        "validate path",
    }
    if semantic_key in generic_keys:
        return True
    return any(fragment in title or fragment in action for fragment in generic_fragments)


def _has_specialized_evidence_candidate(candidates: list[dict], ctx: dict) -> bool:
    for candidate in candidates:
        if _is_generic_fallback_candidate(candidate, ctx):
            continue
        if _step_has_stack_drift(candidate, ctx):
            continue
        if _evidence_alignment_score(candidate, ctx) >= 18.0:
            return True
    return False


def _keyword_match_score(template: dict, ctx: dict) -> int:
    keywords = set(template.get("keywords", set()))
    if not keywords:
        return 0
    matches = 0
    for keyword in keywords:
        if keyword in ctx["text_features"]["tokens"] or keyword in ctx["text_features"]["text"]:
            matches += 1
    return matches


def _anchor_tag_quality(template: dict, ctx: dict) -> float:
    tags = template.get("tags", set())
    if not tags:
        return 0.0
    routing_tags = ctx.get("routing_tags", [])
    trusted_tags = ctx["trusted_tags"]
    supporting_tags = ctx["supporting_tags"]
    score = 0.0
    if any(tag in routing_tags for tag in tags):
        score += 14.0
    if any(tag in trusted_tags for tag in tags):
        score += 10.0
    if any(tag in supporting_tags for tag in tags):
        score += 4.0
    if tags and all(tag in ctx["weak_tags"] for tag in tags):
        score -= 6.0
    return score


def _tag_match_score(template: dict, ctx: dict) -> float:
    score = 0.0
    for tag in template.get("tags", set()):
        if tag in ctx.get("routing_tags", []):
            signal = ctx["tag_signal_map"].get(tag)
            score += float(signal["diagnostic_weight"]) * 2.3 if signal else 10.0
        elif tag in ctx["trusted_tags"]:
            signal = ctx["tag_signal_map"].get(tag)
            score += float(signal["diagnostic_weight"]) * 2.1 if signal else 8.0
        elif tag in ctx["supporting_tags"]:
            signal = ctx["tag_signal_map"].get(tag)
            score += float(signal["diagnostic_weight"]) * 1.2 if signal else 4.0
        elif tag in ctx["weak_tags"]:
            score += 0.5
    return score


def _boundary_match_score(template: dict, ctx: dict) -> float:
    score = 0.0
    for boundary_name in template.get("boundaries", set()):
        boundary = ctx["boundary_scores"].get(boundary_name)
        if boundary is not None:
            score += float(boundary.get("score", 0.0)) * 20.0
    return score


def _cluster_match_score(template: dict, ctx: dict) -> float:
    score = 0.0
    selected_cluster = ctx["selected_reasoning_cluster"]
    if selected_cluster and selected_cluster in template.get("clusters", set()):
        cluster = ctx["cluster_scores"].get(selected_cluster, {})
        score += float(cluster.get("confidence", 0.0)) * 25.0 if cluster else 14.0
    return score


def _family_match_score(template: dict, ctx: dict) -> float:
    families = template.get("families", set())
    if not families:
        return 0.0
    if ctx["primary_issue_family"] in families:
        return 32.0
    secondary_families = set()
    for item in ctx["ranked_hypotheses"][:4]:
        if isinstance(item, dict):
            secondary_families |= set(item.get("families", []))
    if families & secondary_families:
        return 14.0
    return -3.0


def _discriminativeness_bonus(template: dict, ctx: dict) -> float:
    primary_symptom = ctx["text_features"].get("primary_symptom", "")
    semantic_key = template["semantic_key"]
    score = 0.0

    semantic_targets = {
        "preflight_failure": {"replay_preflight_origin", "cors_origin_alignment", "nginx_edge_directives", "proxy_forwarding_alignment"},
        "missing_cors_headers": {"replay_preflight_origin", "cors_origin_alignment", "nginx_edge_directives"},
        "browser_only_failure": {"browser_request_shape", "react_request_construction", "session_cookie_boundary"},
        "csrf_or_cookie_failure": {"session_cookie_boundary", "django_security_runtime", "auth_artifact_integrity"},
        "authn_failure": {"auth_artifact_integrity", "jwt_claim_integrity", "auth_claim_validation"},
        "authz_failure": {"authorization_policy_check", "auth_claim_validation", "jwt_claim_integrity"},
        "upstream_failure": {"upstream_route_validation", "proxy_forwarding_alignment", "nginx_edge_directives"},
        "dns_failure": {"runtime_dns_resolution", "dns_answer_validation", "platform_service_path"},
        "tls_failure": {"tls_chain_validation", "proxy_forwarding_alignment"},
        "schema_contract_failure": {"database_contract_boundary", "postgresql_schema_state", "mysql_target_contract", "retrieval_vector_alignment"},
        "runtime_startup_failure": {"database_target_runtime_config", "database_runtime_reachability", "postgresql_schema_state", "mysql_target_contract"},
        "config_or_secret_drift": {"database_target_runtime_config"},
        "database_target_change": {"database_target_runtime_config", "database_runtime_reachability", "runtime_dns_resolution"},
        "api_base_url_mismatch": {"browser_request_shape", "react_request_construction", "upstream_route_validation", "proxy_forwarding_alignment"},
        "cache_session_state_loss": {"cache_session_consistency", "redis_state_path"},
        "model_endpoint_unavailable": {"model_runtime_validation", "serving_endpoint_mode", "model_serving_branch"},
        "tokenizer_runtime_mismatch": {"model_runtime_validation", "serving_endpoint_mode", "model_serving_branch"},
        "embedding_vector_mismatch": {"retrieval_vector_alignment", "rag_retrieval_path", "embedding_shape_profile"},
        "cuda_oom": {"cuda_capacity_check", "gpu_runtime_pressure", "gpu_utilization_check", "gpu_workload_shape"},
        "tensor_shape_mismatch": {"tensor_shape_capture", "tensor_conversion_validation", "gpu_workload_shape", "pytorch_runtime_alignment"},
    }
    if semantic_key in semantic_targets.get(primary_symptom, set()):
        score += 22.0
    elif primary_symptom and semantic_key in {"capture_primary_symptom", "boundary_trace", "confirm_runtime_target"}:
        score -= 7.0

    if template["phase"] == "primary_hypothesis_test" and semantic_key in semantic_targets.get(primary_symptom, set()):
        score += 8.0
    if template["phase"] == "secondary_branch_test" and semantic_key in semantic_targets.get(primary_symptom, set()):
        score += 4.0
    if template["purpose"] == "capture" and primary_symptom:
        score -= 3.0
    if template["purpose"] == "runtime" and primary_symptom in {"preflight_failure", "missing_cors_headers", "authz_failure"}:
        score -= 4.0

    # Cross-symptom drift penalty: penalize steps that belong to a different symptom's
    # target set but not the primary symptom's, preventing wrong-domain steps from ranking.
    if primary_symptom and semantic_key not in semantic_targets.get(primary_symptom, set()):
        for other_symptom, other_keys in semantic_targets.items():
            if other_symptom != primary_symptom and semantic_key in other_keys:
                score -= 8.0
                break

    return score


def _stack_drift_penalty(template: dict, ctx: dict) -> float:
    tags = template.get("tags", set())
    if not tags:
        return 0.0
    symptom_names = ctx["text_features"]["symptom_names"]
    routing_tags = set(ctx.get("routing_tags", []))
    penalty = 0.0

    if routing_tags and not (tags & routing_tags) and not (tags & set(ctx["trusted_tags"])) and not template.get("families", set()) & {ctx["primary_issue_family"], *ctx["secondary_families"]}:
        penalty += 6.0
    if "embedding_vector_mismatch" in symptom_names and tags & {"gpu", "cuda", "pytorch", "tensorflow"}:
        penalty += 10.0
    if "cuda_oom" in symptom_names and tags & {"rag", "embeddings", "vector-database", "sentence-transformers"}:
        penalty += 9.0
    if "tensor_shape_mismatch" in symptom_names and "cuda_oom" not in symptom_names and tags & {"rag", "embeddings", "vector-database", "sentence-transformers"}:
        penalty += 10.0
    if "authz_failure" in symptom_names and tags & {"cors", "reactjs"} and "csrf_or_cookie_failure" not in symptom_names:
        penalty += 8.0
    if "dns_failure" in symptom_names and tags & {"http", "rest", "nginx", "apache"} and "upstream_failure" not in symptom_names:
        penalty += 8.0
    if "schema_contract_failure" in symptom_names and tags & {"dns", "tls", "tcp", "routing"}:
        penalty += 8.0
    return penalty


def _phase_priority_bonus(template: dict, selected_phases: list[str]) -> float:
    phase = template["phase"]
    if phase not in selected_phases:
        return -4.0
    index = selected_phases.index(phase)
    return max(0.0, 14.0 - index * 1.5)


def _score_template(template: dict, ctx: dict, selected_phases: list[str]) -> float | None:
    if ctx["reasoning_domain"] not in template["domains"]:
        return None

    score = float(template["base_priority"])
    score += _family_match_score(template, ctx)
    score += _tag_match_score(template, ctx)
    score += _anchor_tag_quality(template, ctx)
    score += _boundary_match_score(template, ctx)
    score += _cluster_match_score(template, ctx)
    score += _keyword_match_score(template, ctx) * 2.5
    score += _evidence_alignment_score(template, ctx)
    score += _semantic_symptom_bonus(template, ctx)
    score += _discriminativeness_bonus(template, ctx)
    score += _phase_priority_bonus(template, selected_phases)
    score -= _stack_drift_penalty(template, ctx)

    if template["phase"] == "secondary_branch_test" and not ctx["alternative_paths"]:
        score -= 6.0
    if template["phase"] == "runtime_config_confirmation" and not (
        ctx["text_features"]["has_deployment_change"] or ctx["boundary_scores"]
    ):
        score -= 2.0
    if template["purpose"] == "runtime" and ctx["reasoning_domain"] == "networking" and ctx["primary_issue_family"] == "dns_service_discovery":
        score -= 1.5
    if template["semantic_key"] == "capture_primary_symptom" and len(ctx["text_features"]["symptom_names"]) >= 3:
        score -= 10.0
    if template["semantic_key"] == "boundary_trace" and any(
        template_key in ctx["text_features"]["symptom_names"]
        for template_key in {"schema_contract_failure", "embedding_vector_mismatch", "cuda_oom"}
    ):
        score -= 6.0
    if template["semantic_key"] in {"capture_primary_symptom", "confirm_runtime_target"} and ctx["text_features"].get("primary_symptom"):
        score -= 4.0
    if template["semantic_key"] == "capture_primary_symptom" and _semantic_evidence_targets(ctx):
        score -= 28.0
    if template["semantic_key"] == "boundary_trace" and _semantic_evidence_targets(ctx):
        score -= 14.0
    if template["semantic_key"] == "runtime_config_confirmation" and _semantic_evidence_targets(ctx):
        score -= 8.0

    return score


def _render_template(template: dict, ctx: dict) -> dict:
    dominant_boundary = next(iter(ctx["boundary_scores"]), "runtime_boundary")
    boundary_label = BOUNDARY_LABELS.get(dominant_boundary, _humanize_slug(dominant_boundary))
    dominant_tag = _humanize_tag(ctx["trusted_tags"][0]) if ctx["trusted_tags"] else _humanize_tag(ctx["top_tags"][0]) if ctx["top_tags"] else "the dominant signal"
    primary_path = ctx["primary_path"]
    top_hypothesis = collapse_whitespace(ctx["ranked_hypotheses"][0]["title"]) if ctx["ranked_hypotheses"] else "the top current hypothesis"

    format_values = {
        "boundary_label": boundary_label,
        "dominant_tag": dominant_tag,
        "primary_path": primary_path,
        "top_hypothesis": top_hypothesis,
    }

    return {
        **template,
        "title": collapse_whitespace(template["title"].format(**format_values)),
        "why": collapse_whitespace(template["why"].format(**format_values)),
        "action": collapse_whitespace(template["action"].format(**format_values)),
        "expected_result": collapse_whitespace(template["expected_result"].format(**format_values)),
        "if_failed": collapse_whitespace(template["if_failed"].format(**format_values)),
    }


def _candidate_pool(ctx: dict, selected_phases: list[str]) -> list[dict]:
    templates = _template_libraries_for_context(ctx)
    candidates = []

    for template in templates:
        score = _score_template(template, ctx, selected_phases)
        if score is None:
            continue
        rendered = _render_template(template, ctx)
        candidates.append(
            {
                **rendered,
                "score": round(score, 4),
            }
        )

    if _has_specialized_evidence_candidate(candidates, ctx):
        for candidate in candidates:
            if _is_generic_fallback_candidate(candidate, ctx):
                candidate["score"] = round(candidate["score"] - 42.0, 4)

    candidates.sort(
        key=lambda item: (
            item["score"],
            -selected_phases.index(item["phase"]) if item["phase"] in selected_phases else -99,
            item["title"],
        ),
        reverse=True,
    )
    return candidates


def _is_candidate_duplicate(candidate: dict, selected: list[dict]) -> bool:
    candidate_title = normalize_title_key(candidate["title"])
    candidate_group = candidate["dedupe_group"]
    for existing in selected:
        if candidate["semantic_key"] == existing["semantic_key"]:
            return True
        if candidate_group == existing["dedupe_group"]:
            return True
        if candidate_title == normalize_title_key(existing["title"]):
            return True
    return False


def _select_steps(ctx: dict, target_count: int, selected_phases: list[str], candidates: list[dict]) -> list[dict]:
    selected = []
    specialized_exists = _has_specialized_evidence_candidate(candidates, ctx)

    for phase in selected_phases:
        phase_candidates = [candidate for candidate in candidates if candidate["phase"] == phase]
        for candidate in phase_candidates:
            if _is_candidate_duplicate(candidate, selected):
                continue
            if specialized_exists and _is_generic_fallback_candidate(candidate, ctx):
                continue
            selected.append(candidate)
            break

    if len(selected) < target_count:
        for candidate in candidates:
            if len(selected) >= target_count:
                break
            if _is_candidate_duplicate(candidate, selected):
                continue
            if specialized_exists and _is_generic_fallback_candidate(candidate, ctx):
                continue
            selected.append(candidate)

    selected.sort(key=lambda item: (selected_phases.index(item["phase"]) if item["phase"] in selected_phases else 99, -item["score"]))
    return selected[:target_count]


def _step_has_stack_drift(step: dict, ctx: dict) -> bool:
    tags = step.get("tags", set())
    if not tags:
        return False
    routing_tags = set(ctx.get("routing_tags", []))
    symptom_names = ctx["text_features"]["symptom_names"]
    if routing_tags and tags.isdisjoint(routing_tags) and tags.isdisjoint(set(ctx["trusted_tags"])) and step["purpose"] in {"secondary", "runtime"}:
        return True
    if "embedding_vector_mismatch" in symptom_names and tags & {"gpu", "cuda", "pytorch", "tensorflow"} and step["semantic_key"] not in {"gpu_runtime_pressure", "gpu_workload_shape"}:
        return True
    if "cuda_oom" in symptom_names and tags & {"rag", "embeddings", "vector-database"}:
        return True
    if "authz_failure" in symptom_names and tags & {"cors", "reactjs"} and "csrf_or_cookie_failure" not in symptom_names:
        return True
    if "schema_contract_failure" in symptom_names and step["semantic_key"] == "database_target_runtime_config" and not ({"config_or_secret_drift", "database_target_change", "runtime_startup_failure"} & symptom_names):
        return True
    if step["semantic_key"] in {"postgresql_schema_state", "mysql_target_contract", "database_contract_boundary"} and "schema_contract_failure" not in symptom_names:
        return True
    if step["semantic_key"] == "session_cookie_boundary" and "csrf_or_cookie_failure" not in symptom_names:
        return True
    if ctx["primary_issue_family"] == "database_connectivity" and step["semantic_key"] == "django_security_runtime" and not ({"csrf_or_cookie_failure", "authn_failure", "authz_failure"} & symptom_names):
        return True
    # DNS-vs-proxy drift: DNS failure should not surface proxy/nginx steps
    if "dns_failure" in symptom_names and tags & {"nginx", "apache", "cors", "http"} and "upstream_failure" not in symptom_names and step["semantic_key"] not in {"runtime_dns_resolution", "dns_answer_validation", "platform_service_path"}:
        return True
    # TLS-vs-auth drift: TLS failure should not surface auth/session steps
    if "tls_failure" in symptom_names and tags & {"authentication", "authorization", "jwt", "oauth-2.0"} and not ({"authn_failure", "authz_failure"} & symptom_names):
        return True
    # Upstream-vs-database drift: upstream failure should not surface database steps
    if "upstream_failure" in symptom_names and tags & {"postgresql", "mysql", "redis", "sql"} and not ({"schema_contract_failure", "connection_refused", "config_or_secret_drift"} & symptom_names):
        return True
    # Gate tensor shape steps to tensor_shape_mismatch symptom only
    if step["semantic_key"] in {"tensor_shape_capture", "tensor_conversion_validation"} and "tensor_shape_mismatch" not in symptom_names:
        return True
    if "model_endpoint_unavailable" in symptom_names and (
        step["semantic_key"] in {"cluster_model_serving_pipeline", "model_serving_branch", "rag_retrieval_path", "retrieval_vector_alignment"}
        or tags & {"rag", "embeddings", "vector-database"}
    ):
        return True
    return False


def _is_generic_step(step: dict, ctx: dict) -> bool:
    semantic_key = step["semantic_key"]
    symptom_names = set(ctx["text_features"]["symptom_names"])
    primary_symptom = ctx["text_features"].get("primary_symptom", "")
    title = normalize_title_key(step.get("title", ""))
    action = normalize_title_key(step.get("action", ""))
    why = normalize_title_key(step.get("why", ""))

    hard_generic_markers = {
        "check the environment",
        "verify the path",
        "inspect the system",
        "validate behavior",
        "validate the dominant failure path",
    }
    if title in hard_generic_markers or action in hard_generic_markers:
        return True
    low_signal_fragments = {"generic", "general troubleshooting", "dominant failure path"}
    if any(fragment in title for fragment in low_signal_fragments):
        return True
    if any(fragment in action for fragment in low_signal_fragments):
        return True
    forbidden_broadening = {"backing store", "state store", "index contract"}
    if any(fragment in title for fragment in forbidden_broadening):
        return True
    if any(fragment in action for fragment in forbidden_broadening):
        return True

    stack_specific_tokens = {
        "auth", "jwt", "oauth", "scope", "role", "permission", "cookie", "csrf", "samesite",
        "cors", "origin", "preflight", "proxy", "ingress", "upstream", "route", "host",
        "dns", "resolver", "ttl", "tls", "ssl", "certificate", "handshake", "sni",
        "database", "dsn", "schema", "migration", "postgresql", "mysql", "redis",
        "kubernetes", "docker", "selector", "endpoint", "namespace", "network", "policy",
        "model", "tokenizer", "embedding", "vector", "retrieval", "serving", "inference",
        "gpu", "cuda", "memory", "vram", "batch", "latency", "runtime", "secret",
    }
    if step["phase"] != "capture_baseline":
        if not (tokenize_keywords(title) & stack_specific_tokens):
            return True
        if not (tokenize_keywords(action) & stack_specific_tokens):
            return True
    if step["phase"] == "secondary_branch_test" and len(tokenize_keywords(why)) < 5:
        return True

    if semantic_key == "capture_primary_symptom":
        return True
    if semantic_key == "runtime_config_confirmation" and not ({"config_or_secret_drift", "database_target_change", "runtime_startup_failure", "deployment_change"} & symptom_names):
        return True
    if semantic_key in {"postgresql_schema_state", "mysql_target_contract", "database_contract_boundary"} and "schema_contract_failure" not in symptom_names:
        return True
    if semantic_key == "boundary_trace" and step["purpose"] == "boundary" and len(step.get("tags", set())) == 0:
        return True
    # Gate boundary_trace when a high-confidence primary symptom already exists
    if semantic_key == "boundary_trace" and primary_symptom:
        return True
    # Gate tensor shape steps to tensor_shape_mismatch symptom only
    if semantic_key in {"tensor_shape_capture", "tensor_conversion_validation"} and "tensor_shape_mismatch" not in symptom_names:
        return True
    return False


def _step_semantically_overlaps(step: dict, selected_steps: list[dict]) -> bool:
    semantic_key = step["semantic_key"]
    selected_keys = {existing["semantic_key"] for existing in selected_steps}
    overlap_groups = {
        "runtime_config_confirmation": {"database_target_runtime_config", "replay_preflight_origin", "authorization_policy_check", "retrieval_vector_alignment", "gpu_runtime_pressure", "model_runtime_validation"},
        "boundary_trace": {"replay_preflight_origin", "runtime_dns_resolution", "tls_chain_validation", "retrieval_vector_alignment", "gpu_runtime_pressure"},
        "cluster_http_edge_alignment": {"replay_preflight_origin", "proxy_forwarding_alignment"},
        "cluster_model_serving_pipeline": {"retrieval_vector_alignment", "model_runtime_validation", "gpu_runtime_pressure"},
    }
    return bool(selected_keys & overlap_groups.get(semantic_key, set()))


def _primary_step_priority(step: dict, ctx: dict) -> float:
    if step.get("phase") == "retest_and_closure":
        return -100.0
    score = _evidence_alignment_score(step, ctx)
    semantic_key = step.get("semantic_key", "")
    if semantic_key in _semantic_evidence_targets(ctx):
        score += 40.0
    if ctx["primary_issue_family"] in step.get("families", set()):
        score += 24.0
    if ctx["selected_reasoning_cluster"] in step.get("clusters", set()):
        score += 10.0
    if step.get("purpose") == "hypothesis":
        score += 18.0
    elif step.get("purpose") in {"boundary", "runtime", "secondary"}:
        score += 10.0
    if _is_generic_fallback_candidate(step, ctx):
        score -= 90.0
    return score


def _specialize_first_step_title(step: dict, ctx: dict) -> dict:
    primary_path = collapse_whitespace(ctx.get("primary_path", ""))
    if not primary_path:
        return step

    evidence_tokens = ctx.get("evidence_profile", {}).get("tokens", set())
    path_tokens = tokenize_keywords(primary_path)
    step_text = _template_search_text(step)
    step_tokens = tokenize_keywords(step_text)
    semantic_targets = _semantic_evidence_targets(ctx)

    has_path_overlap = bool(path_tokens & step_tokens)
    has_evidence_overlap = len(path_tokens & evidence_tokens) >= 2
    has_semantic_match = step.get("semantic_key") in semantic_targets
    is_generic = _is_generic_fallback_candidate(step, ctx) or _is_generic_step(step, ctx)

    if not (has_path_overlap or has_evidence_overlap or has_semantic_match or is_generic):
        return step

    specialized = dict(step)
    primary_key = normalize_title_key(primary_path)

    specialized["title"] = primary_path

    if "redis" in primary_key and {"session", "cache", "state", "store"} & set(primary_key.split()):
        specialized["action"] = (
            "Inspect the Redis-backed session store used by the failing runtime. "
            "Verify Redis target, database index, session key namespace, TTL, failover behavior, and whether session state survives the failover."
        )
        specialized["expected_result"] = (
            "The same Redis session/cache state is readable after failover, with expected TTL, key namespace, and store target."
        )
        specialized["if_failed"] = (
            "Fix Redis session-store configuration, failover persistence, TTL, replication, or cache namespace before investigating cookie or CSRF behavior."
        )
        specialized["semantic_key"] = specialized.get("semantic_key") or "redis_state_path"

    elif all(term in primary_key for term in ("api", "base", "url")) or "localhost" in primary_key:
        specialized["action"] = (
            "Inspect the browser request URL from the deployed frontend and compare it with the expected production API base URL. "
            "Check build-time environment injection, localhost fallback, and the actual endpoint called by the browser."
        )
        specialized["expected_result"] = (
            "The deployed browser client calls the intended backend API URL instead of localhost or a stale development endpoint."
        )
        specialized["if_failed"] = (
            "Fix the frontend API base URL configuration or rebuild the frontend with the correct production endpoint before backend debugging."
        )
        specialized["semantic_key"] = specialized.get("semantic_key") or "browser_request_shape"

    elif "model" in primary_key and ("endpoint" in primary_key or "serving" in primary_key or "health" in primary_key):
        specialized["action"] = (
            "Check the configured model-serving base URL and call the endpoint health route from the same runtime that performs inference."
        )
        specialized["expected_result"] = (
            "The model-serving endpoint is enabled, reachable, healthy, and matches the configured inference base URL."
        )
        specialized["if_failed"] = (
            "Fix MODEL_BASE_URL, endpoint enablement, service health, or deployment target before checking model logic."
        )
        specialized["semantic_key"] = specialized.get("semantic_key") or "serving_endpoint_mode"

    return specialized


def _order_selected_steps(ctx: dict, selected_steps: list[dict], selected_phases: list[str]) -> list[dict]:
    if not selected_steps:
        return selected_steps

    phase_sorted = sorted(
        selected_steps,
        key=lambda item: (
            selected_phases.index(item["phase"]) if item["phase"] in selected_phases else 99,
            -item["score"],
        ),
    )

    best = max(phase_sorted, key=lambda item: (_primary_step_priority(item, ctx), item["score"]))
    best_priority = _primary_step_priority(best, ctx)

    if best_priority >= 24.0:
        first = _specialize_first_step_title(best, ctx)
        rest = [item for item in phase_sorted if item is not best]
        return [first, *rest]

    first = _specialize_first_step_title(phase_sorted[0], ctx)
    return [first, *phase_sorted[1:]]


def _validate_selected_steps(ctx: dict, selected_steps: list[dict], candidates: list[dict], target_count: int, selected_phases: list[str]) -> list[dict]:
    refined = []
    specialized_exists = _has_specialized_evidence_candidate(candidates, ctx)
    for step in selected_steps:
        if _step_has_stack_drift(step, ctx):
            continue
        if _is_generic_step(step, ctx):
            continue
        if _step_semantically_overlaps(step, refined):
            continue
        if any(existing["dedupe_group"] == step["dedupe_group"] for existing in refined):
            continue
        refined.append(step)

    if len(refined) < target_count:
        for candidate in candidates:
            if len(refined) >= target_count:
                break
            if _is_candidate_duplicate(candidate, refined):
                continue
            if _step_has_stack_drift(candidate, ctx):
                continue
            if _step_semantically_overlaps(candidate, refined):
                continue
            if specialized_exists and _is_generic_fallback_candidate(candidate, ctx):
                continue
            if _is_generic_step(candidate, ctx) and len(refined) >= 4:
                continue
            refined.append(candidate)

    if len(refined) < target_count and len(refined) >= 4:
        for candidate in candidates:
            if len(refined) >= target_count:
                break
            if any(candidate["semantic_key"] == existing["semantic_key"] for existing in refined):
                continue
            if normalize_title_key(candidate["title"]) in {normalize_title_key(existing["title"]) for existing in refined}:
                continue
            if _step_has_stack_drift(candidate, ctx):
                continue
            if _is_generic_step(candidate, ctx):
                continue
            refined.append(candidate)

    if len(refined) < 4:
        for candidate in candidates:
            if len(refined) >= 4:
                break
            if _is_candidate_duplicate(candidate, refined):
                continue
            if _step_has_stack_drift(candidate, ctx):
                continue
            if _step_semantically_overlaps(candidate, refined):
                continue
            if _is_generic_step(candidate, ctx):
                continue
            refined.append(candidate)

    if len(refined) < 4:
        for candidate in candidates:
            if len(refined) >= 4:
                break
            if any(candidate["semantic_key"] == existing["semantic_key"] for existing in refined):
                continue
            if _step_has_stack_drift(candidate, ctx):
                continue
            if _is_generic_step(candidate, ctx):
                continue
            refined.append(candidate)

    if len(refined) < 4:
        for candidate in candidates:
            if len(refined) >= 4:
                break
            if any(candidate["semantic_key"] == existing["semantic_key"] for existing in refined):
                continue
            if normalize_title_key(candidate["title"]) in {normalize_title_key(existing["title"]) for existing in refined}:
                continue
            if _step_has_stack_drift(candidate, ctx):
                continue
            refined.append(candidate)

    refined = _order_selected_steps(ctx, refined, selected_phases)
    return refined[:target_count]


def _build_primary_path_summary(ctx: dict) -> dict:
    supporting = []
    for item in ctx["ranked_hypotheses"][:3]:
        if not isinstance(item, dict):
            continue
        supporting.append(
            {
                "title": collapse_whitespace(item.get("title", "")),
                "confidence": clamp_confidence(item.get("confidence", 0.0)),
            }
        )
    return {
        "title": ctx["primary_path"],
        "supporting_hypotheses": supporting,
    }


def _build_alternative_path_summaries(ctx: dict) -> list[dict]:
    alternatives = []
    fallback_hypotheses = ctx["ranked_hypotheses"][1:4]
    for index, path in enumerate(ctx["alternative_paths"][:4], start=1):
        supporting = []
        for hypothesis in fallback_hypotheses[index - 1:index + 1]:
            if isinstance(hypothesis, dict):
                supporting.append(
                    {
                        "title": collapse_whitespace(hypothesis.get("title", "")),
                        "confidence": clamp_confidence(hypothesis.get("confidence", 0.0)),
                    }
                )
        alternatives.append(
            {
                "title": path,
                "supporting_hypotheses": supporting,
            }
        )
    return alternatives


def _format_selected_steps(selected_steps: list[dict], ctx: dict) -> list[dict]:
    formatted = []
    alternative_index = 0
    for index, step in enumerate(selected_steps, start=1):
        anchor_tags = [tag for tag in step.get("tags", set()) if tag in ctx.get("routing_tags", []) or tag in ctx["trusted_tags"] or tag in ctx["supporting_tags"]]
        anchor_tag = anchor_tags[0] if anchor_tags else (ctx["routing_tags"][0] if ctx["routing_tags"] else ctx["trusted_tags"][0] if ctx["trusted_tags"] else ctx["top_tags"][0] if ctx["top_tags"] else "")
        if step["phase"] == "secondary_branch_test" and ctx["alternative_paths"]:
            path_title = ctx["alternative_paths"][min(alternative_index, len(ctx["alternative_paths"]) - 1)]
            alternative_index += 1
        else:
            path_title = ctx["primary_path"]

        formatted.append(
            {
                "step": index,
                "step_number": index,
                "title": step["title"],
                "why": step["why"],
                "action": step["action"],
                "expected_result": step["expected_result"],
                "expected": step["expected_result"],
                "if_failed": step["if_failed"],
                "if_this_fails": step["if_failed"],
                "reference_source_type": normalize_reference_source_type(step["reference_source_type"], ctx["reasoning_domain"]),
                "reference_hint": step["reference_hint"],
                "semantic_key": step["semantic_key"],
                "path_id": f"{step['phase']}_{index}",
                "path_kind": "primary" if step["phase"] != "secondary_branch_test" else "alternative",
                "path_title": path_title,
                "anchor_tag": anchor_tag,
                "anchor_confidence": ctx["tag_signal_map"].get(anchor_tag, {}).get("confidence", 0.0),
                "phase": step["phase"],
                "step_family": step["step_family"],
                "dedupe_group": step["dedupe_group"],
            }
        )
    return formatted


def validate_diagnostic_checklist_output(data: dict, case_summary: dict) -> dict:
    if not isinstance(case_summary, dict):
        raise ValueError("case_summary must be a dictionary.")

    domain = str(case_summary.get("domain", "")).strip().lower()
    if domain not in VALID_DOMAINS:
        raise ValueError("Stage 3 requires a valid case_summary.domain.")

    cleaned_steps = []
    seen_titles = set()
    for item in data.get("diagnostic_checklist", []):
        if not isinstance(item, dict):
            continue
        title = collapse_whitespace(item.get("title", ""))
        why = collapse_whitespace(item.get("why", ""))
        action = collapse_whitespace(item.get("action", ""))
        expected_result = collapse_whitespace(item.get("expected_result", item.get("expected", "")))
        if_failed = collapse_whitespace(item.get("if_failed", item.get("if_this_fails", "")))
        reference_hint = collapse_whitespace(item.get("reference_hint", ""))
        if not all([title, why, action, expected_result, if_failed, reference_hint]):
            continue
        title_key = normalize_title_key(title)
        if title_key in seen_titles:
            continue

        raw_step = item.get("step", item.get("step_number", 0))
        try:
            step_number = int(raw_step)
        except Exception:
            step_number = 0

        cleaned_steps.append(
            {
                "step": step_number,
                "step_number": step_number,
                "title": title,
                "why": why,
                "action": action,
                "expected_result": expected_result,
                "expected": expected_result,
                "if_failed": if_failed,
                "if_this_fails": if_failed,
                "reference_source_type": normalize_reference_source_type(item.get("reference_source_type", ""), domain),
                "reference_hint": reference_hint,
                "semantic_key": collapse_whitespace(item.get("semantic_key", "")),
                "path_id": collapse_whitespace(item.get("path_id", "")),
                "path_kind": collapse_whitespace(item.get("path_kind", "")),
                "path_title": collapse_whitespace(item.get("path_title", "")),
                "anchor_tag": collapse_whitespace(item.get("anchor_tag", "")).lower(),
                "anchor_confidence": item.get("anchor_confidence", 0.0),
                "phase": collapse_whitespace(item.get("phase", "")),
                "step_family": collapse_whitespace(item.get("step_family", "")),
            }
        )
        seen_titles.add(title_key)

    cleaned_steps.sort(key=lambda item: item["step"] if item["step"] > 0 else 10**9)
    target_count = int(data.get("target_display_count", 5))
    target_count = max(4, min(target_count, 6))
    cleaned_steps = cleaned_steps[:target_count]
    if len(cleaned_steps) < 4:
        raise ValueError("Stage 3 response produced fewer than 4 usable checklist steps.")

    for index, step in enumerate(cleaned_steps, start=1):
        step["step"] = index
        step["step_number"] = index

    top_signal_tags = extract_case_tag_signals(
        {
            "tag_signals": data.get("top_signal_tags") or case_summary.get("tag_signals"),
            "top_tags": case_summary.get("top_tags", []),
        }
    )

    primary_path = data.get("primary_diagnostic_path", {}) or {}
    alternative_paths = data.get("alternative_paths", []) or []

    return {
        "diagnostic_checklist": cleaned_steps,
        "target_display_count": target_count,
        "top_signal_tags": top_signal_tags,
        "primary_diagnostic_path": primary_path,
        "alternative_paths": alternative_paths,
        "selected_step_family_sequence": data.get("selected_step_family_sequence", []),
        "checklist_trace_internal": data.get("checklist_trace_internal", {}),
        "checklist_generation_metadata": data.get("checklist_generation_metadata", {}),
        "reasoning_summary": collapse_whitespace(data.get("reasoning_summary", "")),
    }


__all__ = [
    "_humanize_slug",
    "_humanize_tag",
    "_top_unique",
    "_boundary_map",
    "_cluster_map",
    "_extract_text_features",
    "_semantic_symptom_bonus",
    "_build_context",
    "_compute_target_step_count",
    "_select_phase_sequence",
    "_template_libraries_for_context",
    "_keyword_match_score",
    "_anchor_tag_quality",
    "_tag_match_score",
    "_boundary_match_score",
    "_cluster_match_score",
    "_family_match_score",
    "_discriminativeness_bonus",
    "_stack_drift_penalty",
    "_phase_priority_bonus",
    "_score_template",
    "_render_template",
    "_candidate_pool",
    "_is_candidate_duplicate",
    "_select_steps",
    "_step_has_stack_drift",
    "_is_generic_step",
    "_step_semantically_overlaps",
    "_validate_selected_steps",
    "_build_primary_path_summary",
    "_build_alternative_path_summaries",
    "_format_selected_steps",
    "validate_diagnostic_checklist_output",
]
