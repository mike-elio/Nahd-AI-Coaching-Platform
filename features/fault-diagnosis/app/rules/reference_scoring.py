from typing import Any

from app.config import VALID_DOMAINS
from app.repositories.references import (
    BASELINE_ALLOWED_REFERENCE_TAGS,
    BOUNDARY_REFERENCE_ALIASES,
    CLUSTER_REFERENCE_ALIASES,
    DOMAIN_REFERENCE_TAG_ALIASES,
    DOMAIN_SOURCE_BONUS,
    ISSUE_FAMILY_REFERENCE_ALIASES,
    REFERENCE_SOURCE_PRIORITY,
    SEMANTIC_KEY_REFERENCE_ALIASES,
    SEMANTIC_REQUIRED_REFERENCE_TAGS,
    SEMANTIC_TITLE_HINTS,
    STEP_PURPOSE_SOURCE_BONUS,
    SYMPTOM_REFERENCE_ALIASES,
    SYMPTOM_SOURCE_HINTS,
)
from app.rules.text_processing import (
    collapse_whitespace,
    normalize_reference_source_type,
    tokenize_keywords,
)


def _resolve_reference_context(case_context: dict) -> tuple[dict, dict]:
    if not isinstance(case_context, dict):
        raise ValueError("case_context must be a dictionary.")

    if "case_summary" in case_context and isinstance(case_context["case_summary"], dict):
        stage_context = case_context
        case_summary = case_context["case_summary"]
    else:
        stage_context = {"case_summary": case_context}
        case_summary = case_context

    domain = str(case_summary.get("domain", "")).strip().lower()
    if domain not in VALID_DOMAINS:
        raise ValueError("attach_step_references requires a valid case_summary.domain.")

    return stage_context, case_summary


def build_case_tag_weights(case_summary: dict) -> dict[str, float]:
    weighted_tags = {}
    for item in case_summary.get("tag_signals", []):
        if not isinstance(item, dict):
            continue
        tag = str(item.get("tag", "")).strip().lower()
        if not tag:
            continue
        try:
            confidence = float(item.get("confidence", 0.0))
        except Exception:
            confidence = 0.0
        weighted_tags[tag] = max(confidence, weighted_tags.get(tag, 0.0))

    if weighted_tags:
        return weighted_tags

    top_tags = [str(tag).strip().lower() for tag in case_summary.get("top_tags", []) if str(tag).strip()]
    fallback_by_rank = [0.95, 0.78, 0.61]
    for index, tag in enumerate(top_tags):
        weighted_tags[tag] = fallback_by_rank[min(index, len(fallback_by_rank) - 1)]
    return weighted_tags


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


def _resolve_visible_domain(case_summary: dict) -> str:
    domain = str(case_summary.get("domain", "")).strip().lower()
    if domain not in VALID_DOMAINS:
        raise ValueError("Invalid case_summary domain for reference selection.")
    to_reasoning = {
        "sw": "software",
        "cn": "networking",
        "ai": "ai",
        "software": "software",
        "networking": "networking",
    }
    return to_reasoning.get(domain, domain)


def _boundary_names(case_summary: dict) -> list[str]:
    names = []
    for hint in case_summary.get("boundary_hints", []):
        if not isinstance(hint, dict):
            continue
        name = str(hint.get("name", "")).strip().lower()
        if name:
            names.append(name)
    return _top_unique(names, 6)


def _secondary_families(stage_context: dict) -> list[str]:
    ranked = stage_context.get("ranked_hypotheses", []) or stage_context.get("root_cause_hypotheses", [])
    families = []
    for item in ranked[:6]:
        if not isinstance(item, dict):
            continue
        for family in item.get("families", []):
            families.append(str(family).strip().lower())
    return _top_unique(families, 5)


def _ordered_unique_filter(
    values: list[str],
    *,
    allowed: set[str] | None = None,
    banned: set[str] | None = None,
    limit: int = 24,
) -> list[str]:
    allowed = set(allowed or []) if allowed is not None else None
    banned = set(banned or [])
    ordered = []
    seen = set()
    for value in values:
        normalized = collapse_whitespace(value).lower()
        if not normalized or normalized in seen:
            continue
        if allowed is not None and normalized not in allowed:
            continue
        if normalized in banned:
            continue
        ordered.append(normalized)
        seen.add(normalized)
        if len(ordered) >= limit:
            break
    return ordered


def _context_stack_tags(
    *,
    anchor_tag: str,
    trusted_tags: list[str],
    supporting_tags: list[str],
    contextual_terms: set[str],
    preferred_keywords: set[str],
    primary_issue_family: str,
    semantic_key: str,
    symptom_names: set[str],
) -> set[str]:
    explicit = set(trusted_tags) | set(supporting_tags)
    if anchor_tag:
        explicit.add(anchor_tag)

    known_terms = {
        "postgresql", "mysql", "redis", "django", "fastapi", "reactjs",
        "dns", "tls", "ssl", "kubernetes", "docker", "gpu", "cuda",
        "embedding", "retrieval", "vector", "rag", "model", "serving",
        "tokenizer", "jwt", "oauth", "cors", "proxy", "nginx",
    }
    for token in contextual_terms | preferred_keywords:
        if token in known_terms:
            explicit.add(token)

    if primary_issue_family in {"database_connectivity", "cache_session_store"}:
        explicit.add("database")
    if primary_issue_family == "cache_session_store":
        explicit.update({"redis", "cache", "session"})
    if semantic_key in {"cache_session_consistency", "redis_state_path"}:
        explicit.update({"redis", "cache", "session"})

    if semantic_key in {
        "database_target_runtime_config",
        "database_runtime_reachability",
        "database_contract_boundary",
        "postgresql_schema_state",
        "mysql_target_contract",
    }:
        explicit.add("database")

    if semantic_key in {"retrieval_vector_alignment", "rag_retrieval_path", "embedding_shape_profile"}:
        explicit.update({"embedding", "retrieval", "vector"})
    if semantic_key in {"gpu_runtime_pressure", "gpu_workload_shape", "cuda_capacity_check", "gpu_utilization_check"}:
        explicit.update({"gpu", "cuda"})
    if semantic_key in {
        "auth_artifact_integrity",
        "auth_claim_validation",
        "authorization_policy_check",
        "jwt_claim_integrity",
        "session_cookie_boundary",
    }:
        explicit.update({"auth", "jwt"})

    if "embedding_vector_mismatch" in symptom_names:
        explicit.update({"embedding", "retrieval", "vector", "rag"})
    if "cuda_oom" in symptom_names:
        explicit.update({"gpu", "cuda"})
    return explicit


def _specialize_reference_profile(
    *,
    domain: str,
    semantic_key: str,
    primary_issue_family: str,
    anchor_tag: str,
    trusted_tags: list[str],
    supporting_tags: list[str],
    symptom_names: set[str],
    primary_symptom: str,
    contextual_terms: set[str],
    preferred_keywords: set[str],
    preferred_reference_tags: list[str],
    allowed_reference_tags: list[str],
    required_reference_tags: set[str],
    title_hints: set[str],
    preferred_source_types: set[str],
) -> dict:
    retrieval_reference_tags = {
        "vector-database/embeddings",
        "sentence-transformers/embeddings",
        "rag/llm/nlp",
        "llm/embeddings/fine-tuning",
        "model-serving/inference",
        "huggingface-transformers/nlp/llm",
    }
    gpu_reference_tags = {"gpu/cuda/inference", "pytorch", "tensorflow"}

    explicit_stack_tags = _context_stack_tags(
        anchor_tag=anchor_tag,
        trusted_tags=trusted_tags,
        supporting_tags=supporting_tags,
        contextual_terms=contextual_terms,
        preferred_keywords=preferred_keywords,
        primary_issue_family=primary_issue_family,
        semantic_key=semantic_key,
        symptom_names=symptom_names,
    )

    banned_reference_tags: set[str] = set()

    sql_runtime_case = (
        domain == "software"
        and primary_issue_family == "database_connectivity"
        and "embedding_vector_mismatch" not in symptom_names
        and not ({"vector", "embedding", "retrieval", "rag"} & contextual_terms)
    )
    vector_case = (
        primary_issue_family == "retrieval_embeddings_pipeline"
        or semantic_key in {"retrieval_vector_alignment", "rag_retrieval_path", "embedding_shape_profile"}
        or "embedding_vector_mismatch" in symptom_names
        or bool({"vector", "embedding", "retrieval", "rag"} & explicit_stack_tags)
    )
    gpu_case = (
        primary_issue_family == "gpu_inference_runtime"
        or semantic_key in {
            "gpu_runtime_pressure",
            "gpu_workload_shape",
            "cuda_capacity_check",
            "gpu_utilization_check",
            "pytorch_runtime_alignment",
        }
        or "cuda_oom" in symptom_names
        or bool({"gpu", "cuda"} & explicit_stack_tags)
    )
    redis_session_case = (
        primary_issue_family == "cache_session_store"
        or semantic_key in {"cache_session_consistency", "redis_state_path"}
        or "cache_session_state_loss" in symptom_names
        or bool({"redis", "cache", "session", "ttl", "failover"} & contextual_terms)
    )
    auth_case = (
        primary_issue_family in {"authentication", "authorization_policy", "session_identity_boundary"}
        or semantic_key in {
            "auth_artifact_integrity",
            "auth_claim_validation",
            "authorization_policy_check",
            "jwt_claim_integrity",
            "session_cookie_boundary",
            "cluster_auth_flow_alignment",
        }
        or bool(symptom_names & {"authn_failure", "authz_failure", "csrf_or_cookie_failure"})
    )
    proxy_case = (
        primary_issue_family in {"cors_proxy_boundary", "http_routing_misconfiguration", "tls_edge_termination"}
        or semantic_key in {
            "replay_preflight_origin",
            "cors_origin_alignment",
            "proxy_forwarding_alignment",
            "proxy_header_boundary",
            "upstream_route_validation",
            "cluster_http_edge_alignment",
            "nginx_edge_directives",
        }
    )
    transport_case = (
        primary_issue_family in {"dns_service_discovery", "tls_edge_termination", "container_networking"}
        or semantic_key in {
            "runtime_dns_resolution",
            "dns_answer_validation",
            "tls_chain_validation",
            "transport_hop_validation",
            "platform_service_path",
            "cluster_container_surface",
        }
        or bool(symptom_names & {"dns_failure", "tls_failure"})
    )

    if sql_runtime_case:
        banned_reference_tags |= retrieval_reference_tags | gpu_reference_tags
        if not (symptom_names & {"authn_failure", "authz_failure", "csrf_or_cookie_failure"}):
            banned_reference_tags |= {"auth", "reactjs", "javascript"}
        preferred_reference_tags = ["sql", *preferred_reference_tags]
        allowed_reference_tags = ["sql", *allowed_reference_tags]
        required_reference_tags -= retrieval_reference_tags
        required_reference_tags -= gpu_reference_tags
        title_hints.update({"database", "connection", "hostname", "secret", "dsn", "schema", "query"})
        preferred_source_types.update({"vendor_docs", "official_docs"})

    if vector_case and not sql_runtime_case:
        banned_reference_tags |= {"sql", "auth", "reactjs", "javascript"}
        if "cuda_oom" not in symptom_names:
            banned_reference_tags |= {"gpu/cuda/inference", "pytorch", "tensorflow"}
        preferred_reference_tags = [
            "vector-database/embeddings",
            "sentence-transformers/embeddings",
            "rag/llm/nlp",
            *preferred_reference_tags,
        ]
        allowed_reference_tags = [
            "vector-database/embeddings",
            "sentence-transformers/embeddings",
            "rag/llm/nlp",
            *allowed_reference_tags,
        ]
        title_hints.update({"embedding", "vector", "retrieval", "index"})
        preferred_source_types.update({"library_docs", "vendor_docs"})

    if gpu_case and not vector_case:
        banned_reference_tags |= {
            "sql",
            "auth",
            "reactjs",
            "javascript",
            "vector-database/embeddings",
            "sentence-transformers/embeddings",
            "rag/llm/nlp",
        }
        preferred_reference_tags = ["gpu/cuda/inference", "pytorch", "tensorflow", *preferred_reference_tags]
        allowed_reference_tags = ["gpu/cuda/inference", "pytorch", "tensorflow", *allowed_reference_tags]
        title_hints.update({"gpu", "cuda", "memory", "vram", "batch"})
        preferred_source_types.update({"library_docs", "vendor_docs"})

    if redis_session_case:
        banned_reference_tags |= {
            "auth",
            "reactjs",
            "javascript",
            "fastapi",
            "django",
            "http/cors/proxy",
            "nginx/proxy/load-balancing/ssl",
            "proxy/reverse-proxy/load-balancing",
            "ssl/tls",
            "dns",
            "tcp/routing",
            "gpu/cuda/inference",
            "pytorch",
            "tensorflow",
            "vector-database/embeddings",
            "sentence-transformers/embeddings",
            "rag/llm/nlp",
        }
        preferred_reference_tags = ["redis", "database", "sql", *preferred_reference_tags]
        allowed_reference_tags = ["redis", "database", "sql", *allowed_reference_tags]
        required_reference_tags.update({"redis"})
        title_hints.update({"redis", "cache", "session", "ttl", "failover", "replication", "persistence"})
        preferred_source_types.update({"official_docs", "vendor_docs", "library_docs"})

    if auth_case and not redis_session_case and not sql_runtime_case and not vector_case and not gpu_case:
        banned_reference_tags |= retrieval_reference_tags | gpu_reference_tags
        preferred_reference_tags = ["auth", "fastapi", "django", *preferred_reference_tags]
        allowed_reference_tags = ["auth", "fastapi", "django", *allowed_reference_tags]
        title_hints.update({"auth", "token", "scope", "role", "cookie", "csrf"})
        preferred_source_types.update({"security_guidance", "library_docs"})

    if transport_case and not sql_runtime_case and not vector_case and not gpu_case and not redis_session_case:
        banned_reference_tags |= {"auth"}
        preferred_reference_tags = ["dns", "tcp/routing", "ssl/tls", *preferred_reference_tags]
        allowed_reference_tags = ["dns", "tcp/routing", "ssl/tls", *allowed_reference_tags]
        title_hints.update({"dns", "resolver", "tls", "certificate", "handshake", "routing"})
        preferred_source_types.update({"protocol_reference", "vendor_docs"})
        if primary_symptom == "dns_failure":
            banned_reference_tags |= {"http/cors/proxy", "reactjs", "javascript"}

    if proxy_case and not redis_session_case and not auth_case and not sql_runtime_case and not vector_case and not gpu_case:
        preferred_reference_tags = [
            "http/cors/proxy",
            "nginx/proxy/load-balancing/ssl",
            "proxy/reverse-proxy/load-balancing",
            *preferred_reference_tags,
        ]
        allowed_reference_tags = [
            "http/cors/proxy",
            "nginx/proxy/load-balancing/ssl",
            "proxy/reverse-proxy/load-balancing",
            *allowed_reference_tags,
        ]
        title_hints.update({"proxy", "cors", "origin", "upstream", "route"})
        preferred_source_types.update({"protocol_reference", "vendor_docs", "library_docs"})

    if primary_symptom == "schema_contract_failure":
        title_hints.update({"schema", "migration", "relation", "column"})
        preferred_source_types.update({"vendor_docs", "official_docs", "library_docs"})

    preferred_reference_tags = _ordered_unique_filter(preferred_reference_tags, banned=banned_reference_tags, limit=24)
    allowed_reference_tags = _ordered_unique_filter(allowed_reference_tags or preferred_reference_tags, banned=banned_reference_tags, limit=18)

    if not preferred_reference_tags:
        preferred_reference_tags = _ordered_unique_filter(BASELINE_ALLOWED_REFERENCE_TAGS.get(domain, []), limit=24)
    if not allowed_reference_tags:
        allowed_reference_tags = _ordered_unique_filter(BASELINE_ALLOWED_REFERENCE_TAGS.get(domain, []), limit=18)

    required_reference_tags = {tag for tag in required_reference_tags if tag not in banned_reference_tags}

    return {
        "preferred_reference_tags": preferred_reference_tags,
        "allowed_reference_tags": allowed_reference_tags,
        "required_reference_tags": required_reference_tags,
        "title_hints": title_hints,
        "preferred_source_types": preferred_source_types,
        "explicit_stack_tags": explicit_stack_tags,
        "sql_runtime_case": sql_runtime_case,
        "vector_case": vector_case,
        "gpu_case": gpu_case,
        "redis_session_case": redis_session_case,
        "auth_case": auth_case,
        "proxy_case": proxy_case,
        "transport_case": transport_case,
    }


def build_step_reference_profile(step: dict, case_context: dict) -> dict:
    stage_context, case_summary = _resolve_reference_context(case_context)
    domain = _resolve_visible_domain(case_summary)
    semantic_key = str(step.get("semantic_key", "")).strip().lower()
    title = str(step.get("title", "")).strip().lower()
    action = str(step.get("action", "")).strip().lower()
    reference_hint = str(step.get("reference_hint", "")).strip().lower()
    path_title = str(step.get("path_title", "")).strip().lower()
    anchor_tag = str(step.get("anchor_tag", "")).strip().lower()
    phase = str(step.get("phase", "")).strip().lower()
    step_family = str(step.get("step_family", "")).strip().lower()
    purpose = step_family.split(".")[0] if step_family else phase

    case_tag_weights = build_case_tag_weights(case_summary)
    trusted_tags = [str(tag).strip().lower() for tag in case_summary.get("trusted_tags", []) if str(tag).strip()]
    supporting_tags = [str(tag).strip().lower() for tag in case_summary.get("supporting_tags", []) if str(tag).strip()]
    weak_tags = [str(tag).strip().lower() for tag in case_summary.get("weak_tags", []) if str(tag).strip()]

    primary_issue_family = str(
        stage_context.get("primary_issue_family")
        or case_summary.get("primary_issue_family")
        or case_summary.get("issue_family", "")
    ).strip().lower()
    selected_reasoning_cluster = str(
        stage_context.get("selected_reasoning_cluster")
        or case_summary.get("selected_reasoning_cluster", "")
    ).strip().lower()

    boundary_names = _boundary_names(case_summary)
    secondary_families = _secondary_families(stage_context)
    possible_causes = [collapse_whitespace(item).lower() for item in stage_context.get("possible_causes", []) if collapse_whitespace(item)]
    alternative_paths = [collapse_whitespace(item).lower() for item in stage_context.get("alternative_paths", []) if collapse_whitespace(item)]
    primary_path = collapse_whitespace(stage_context.get("primary_path", "")).lower()
    symptom_evidence = (
        case_summary.get("symptom_evidence")
        or stage_context.get("reasoning_trace_internal", {}).get("symptom_evidence")
        or {}
    )
    symptom_names = {str(name).strip().lower() for name in symptom_evidence.get("symptom_names", []) if str(name).strip()}
    primary_symptom = str(symptom_evidence.get("primary_symptom", "")).strip().lower()
    boundary_confidence = case_summary.get("boundary_confidence") or stage_context.get("reasoning_trace_internal", {}).get("boundary_confidence", {})
    strongest_boundary = ""
    if boundary_confidence:
        strongest_boundary = max(boundary_confidence.items(), key=lambda item: (float(item[1]), item[0]))[0]

    preferred_reference_tags = []
    allowed_reference_tags = []

    if semantic_key in SEMANTIC_KEY_REFERENCE_ALIASES:
        preferred_reference_tags.extend(SEMANTIC_KEY_REFERENCE_ALIASES[semantic_key])

    if anchor_tag:
        preferred_reference_tags.extend(DOMAIN_REFERENCE_TAG_ALIASES.get(domain, {}).get(anchor_tag, []))

    for tag in trusted_tags:
        preferred_reference_tags.extend(DOMAIN_REFERENCE_TAG_ALIASES.get(domain, {}).get(tag, []))
        allowed_reference_tags.extend(DOMAIN_REFERENCE_TAG_ALIASES.get(domain, {}).get(tag, []))

    for tag in supporting_tags:
        preferred_reference_tags.extend(DOMAIN_REFERENCE_TAG_ALIASES.get(domain, {}).get(tag, []))

    if primary_issue_family:
        preferred_reference_tags.extend(ISSUE_FAMILY_REFERENCE_ALIASES.get(primary_issue_family, []))
        allowed_reference_tags.extend(ISSUE_FAMILY_REFERENCE_ALIASES.get(primary_issue_family, []))

    for family in secondary_families:
        preferred_reference_tags.extend(ISSUE_FAMILY_REFERENCE_ALIASES.get(family, []))

    if selected_reasoning_cluster:
        preferred_reference_tags.extend(CLUSTER_REFERENCE_ALIASES.get(selected_reasoning_cluster, []))
        allowed_reference_tags.extend(CLUSTER_REFERENCE_ALIASES.get(selected_reasoning_cluster, []))

    for boundary_name in boundary_names:
        preferred_reference_tags.extend(BOUNDARY_REFERENCE_ALIASES.get(boundary_name, []))

    for symptom_name in symptom_names:
        preferred_reference_tags.extend(SYMPTOM_REFERENCE_ALIASES.get(symptom_name, []))

    if not preferred_reference_tags:
        preferred_reference_tags.extend(BASELINE_ALLOWED_REFERENCE_TAGS.get(domain, []))
    if not allowed_reference_tags:
        allowed_reference_tags.extend(BASELINE_ALLOWED_REFERENCE_TAGS.get(domain, []))

    preferred_reference_tags = _top_unique(preferred_reference_tags, 24)
    allowed_reference_tags = _top_unique(allowed_reference_tags or preferred_reference_tags, 18)

    preferred_keywords = tokenize_keywords(
        step.get("title", ""),
        step.get("action", ""),
        step.get("why", ""),
        step.get("reference_hint", ""),
        stage_context.get("primary_path", ""),
        " ".join(stage_context.get("alternative_paths", [])),
        " ".join(stage_context.get("possible_causes", [])),
        " ".join(trusted_tags),
        " ".join(supporting_tags),
        primary_issue_family,
        selected_reasoning_cluster,
    )

    contextual_terms = tokenize_keywords(
        title,
        action,
        reference_hint,
        path_title,
        primary_path,
        " ".join(alternative_paths),
        " ".join(possible_causes),
    )

    desired_source_type = normalize_reference_source_type(step.get("reference_source_type", ""), domain)
    required_reference_tags = set(SEMANTIC_REQUIRED_REFERENCE_TAGS.get(semantic_key, set()))

    auth_semantic_keys = {
        "auth_artifact_integrity",
        "auth_claim_validation",
        "authorization_policy_check",
        "jwt_claim_integrity",
        "session_cookie_boundary",
        "cluster_auth_flow_alignment",
    }
    dns_semantic_keys = {
        "runtime_dns_resolution",
        "dns_answer_validation",
        "transport_hop_validation",
        "cluster_container_surface",
        "cluster_http_edge_alignment",
        "platform_service_path",
    }
    tls_semantic_keys = {
        "tls_chain_validation",
        "transport_hop_validation",
        "proxy_header_boundary",
        "upstream_route_validation",
        "cluster_http_edge_alignment",
    }
    retrieval_semantic_keys = {
        "retrieval_vector_alignment",
        "rag_retrieval_path",
        "embedding_shape_profile",
        "cluster_model_serving_pipeline",
        "model_serving_branch",
        "model_runtime_validation",
    }
    gpu_semantic_keys = {
        "gpu_runtime_pressure",
        "gpu_workload_shape",
        "cuda_capacity_check",
        "gpu_utilization_check",
        "pytorch_runtime_alignment",
        "cluster_model_serving_pipeline",
        "model_runtime_validation",
    }

    if "preflight_failure" in symptom_names or "missing_cors_headers" in symptom_names:
        if semantic_key in {"capture_primary_symptom", "cluster_http_edge_alignment", "upstream_route_validation"}:
            required_reference_tags.update({"fastapi", "auth", "rest"})
    if "embedding_vector_mismatch" in symptom_names and semantic_key in retrieval_semantic_keys:
        required_reference_tags.update({"sentence-transformers/embeddings", "vector-database/embeddings", "rag/llm/nlp"})
    if "cuda_oom" in symptom_names and semantic_key in gpu_semantic_keys:
        required_reference_tags.update({"gpu/cuda/inference", "pytorch"})
    if "tensor_shape_mismatch" in symptom_names and semantic_key in {"tensor_shape_capture", "tensor_conversion_validation", *gpu_semantic_keys}:
        required_reference_tags.update({"pytorch", "gpu/cuda/inference"})
    if primary_symptom == "authz_failure" and semantic_key in auth_semantic_keys:
        required_reference_tags.update({"auth", "fastapi", "django"})
    if "tls_failure" in symptom_names and semantic_key in tls_semantic_keys:
        required_reference_tags.update({"ssl/tls"})
    if "dns_failure" in symptom_names and semantic_key in dns_semantic_keys:
        required_reference_tags.update({"dns", "tcp/routing"})
    if (
        primary_issue_family == "cache_session_store"
        or semantic_key in {"cache_session_consistency", "redis_state_path"}
        or "cache_session_state_loss" in symptom_names
    ):
        required_reference_tags.update({"redis"})

    title_hints = set(SEMANTIC_TITLE_HINTS.get(semantic_key, set()))
    if "preflight_failure" in symptom_names:
        title_hints.update({"cors", "origin"})
    if "embedding_vector_mismatch" in symptom_names:
        title_hints.update({"embedding", "vector", "retrieval"})
    if "cuda_oom" in symptom_names:
        title_hints.update({"cuda", "gpu"})
    if "tensor_shape_mismatch" in symptom_names:
        title_hints.update({"tensor", "shape", "pytorch"})
    if (
        primary_issue_family == "cache_session_store"
        or semantic_key in {"cache_session_consistency", "redis_state_path"}
        or "cache_session_state_loss" in symptom_names
    ):
        title_hints.update({"redis", "cache", "session", "ttl", "failover", "replication", "persistence"})

    specialized = _specialize_reference_profile(
        domain=domain,
        semantic_key=semantic_key,
        primary_issue_family=primary_issue_family,
        anchor_tag=anchor_tag,
        trusted_tags=trusted_tags,
        supporting_tags=supporting_tags,
        symptom_names=symptom_names,
        primary_symptom=primary_symptom,
        contextual_terms=contextual_terms,
        preferred_keywords=preferred_keywords,
        preferred_reference_tags=preferred_reference_tags,
        allowed_reference_tags=allowed_reference_tags,
        required_reference_tags=required_reference_tags,
        title_hints=title_hints,
        preferred_source_types=set().union(*(SYMPTOM_SOURCE_HINTS.get(name, set()) for name in symptom_names)) if symptom_names else set(),
    )

    return {
        "domain": domain,
        "semantic_key": semantic_key,
        "phase": phase,
        "purpose": purpose,
        "anchor_tag": anchor_tag,
        "trusted_tags": trusted_tags,
        "supporting_tags": supporting_tags,
        "weak_tags": weak_tags,
        "case_tag_weights": case_tag_weights,
        "primary_issue_family": primary_issue_family,
        "secondary_families": secondary_families,
        "selected_reasoning_cluster": selected_reasoning_cluster,
        "boundary_names": boundary_names,
        "strongest_boundary": strongest_boundary,
        "preferred_reference_tags": specialized["preferred_reference_tags"],
        "allowed_reference_tags": specialized["allowed_reference_tags"],
        "preferred_keywords": preferred_keywords,
        "contextual_terms": contextual_terms,
        "desired_source_type": desired_source_type,
        "required_reference_tags": specialized["required_reference_tags"],
        "title_hints": specialized["title_hints"],
        "symptom_names": symptom_names,
        "primary_symptom": primary_symptom,
        "preferred_source_types": specialized["preferred_source_types"],
        "primary_path": primary_path,
        "alternative_paths": alternative_paths,
        "possible_causes": possible_causes,
        "redis_session_case": specialized["redis_session_case"],
    }


def _build_trace_profile(profile: dict) -> dict:
    return {
        "semantic_key": profile["semantic_key"],
        "anchor_tag": profile["anchor_tag"],
        "primary_issue_family": profile["primary_issue_family"],
        "selected_reasoning_cluster": profile["selected_reasoning_cluster"],
        "boundary_names": profile["boundary_names"],
    }


def _score_reference_row(row: dict, profile: dict, step: dict) -> tuple[float, dict]:
    score = 0.0
    reasons = []
    row_tag = row["tag"]
    row_source_type = row["source_type"]
    row_title_lower = row["title"].lower()
    row_title_tokens = tokenize_keywords(row["title"])

    if profile["required_reference_tags"] and row_tag not in profile["required_reference_tags"]:
        score -= 68.0
        reasons.append("required_reference_tag_mismatch")

    if row_tag in profile["allowed_reference_tags"]:
        score += 18.0
        reasons.append("allowed_reference_tag")
    elif profile["allowed_reference_tags"]:
        score -= 10.0

    if row_tag in profile["preferred_reference_tags"]:
        preferred_index = profile["preferred_reference_tags"].index(row_tag)
        score += max(0.0, 96.0 - preferred_index * 5.0)
        reasons.append("preferred_reference_tag")

    if profile["anchor_tag"]:
        anchor_mapped = DOMAIN_REFERENCE_TAG_ALIASES.get(profile["domain"], {}).get(profile["anchor_tag"], [])
        if row_tag in anchor_mapped:
            anchor_weight = profile["case_tag_weights"].get(profile["anchor_tag"], 0.0)
            score += 6.0 + anchor_weight * 4.0
            reasons.append("anchor_tag_alignment")

    for tag in profile["trusted_tags"]:
        if row_tag in DOMAIN_REFERENCE_TAG_ALIASES.get(profile["domain"], {}).get(tag, []):
            score += 8.0 + profile["case_tag_weights"].get(tag, 0.0) * 16.0
            reasons.append(f"trusted_tag:{tag}")

    for tag in profile["supporting_tags"]:
        if row_tag in DOMAIN_REFERENCE_TAG_ALIASES.get(profile["domain"], {}).get(tag, []):
            score += 4.0 + profile["case_tag_weights"].get(tag, 0.0) * 10.0
            reasons.append(f"supporting_tag:{tag}")

    keyword_overlap = len(profile["preferred_keywords"] & row["keywords"])
    if keyword_overlap:
        score += keyword_overlap * 7.5
        reasons.append("keyword_overlap")

    contextual_overlap = len(profile["contextual_terms"] & row["keywords"])
    if contextual_overlap:
        score += contextual_overlap * 5.0
        reasons.append("contextual_overlap")

    title_hint_overlap = len(profile["title_hints"] & row_title_tokens)
    if title_hint_overlap:
        score += title_hint_overlap * 9.0
        reasons.append("title_hint_overlap")

    score += REFERENCE_SOURCE_PRIORITY.get(row_source_type, 70)
    score += DOMAIN_SOURCE_BONUS.get(profile["domain"], {}).get(row_source_type, 0.0)
    score += STEP_PURPOSE_SOURCE_BONUS.get(profile["purpose"], {}).get(row_source_type, 0.0)

    if row_source_type == profile["desired_source_type"]:
        score += 16.0
        reasons.append("desired_source_type")
    elif profile["desired_source_type"] in {"security_guidance", "library_docs"} and row_source_type == "official_docs":
        score += 8.0
        reasons.append("official_fallback")

    if profile["preferred_source_types"]:
        if row_source_type in profile["preferred_source_types"]:
            score += 12.0
            reasons.append("symptom_source_alignment")
        else:
            score -= 8.0

    if profile["primary_issue_family"] in {"authentication", "authorization_policy", "session_identity_boundary"} and row_tag == "reactjs":
        if "browser" not in profile["contextual_terms"] and "frontend" not in profile["contextual_terms"]:
            score -= 26.0

    if profile["domain"] == "software" and row_tag in {
        "nginx/proxy/load-balancing/ssl",
        "proxy/reverse-proxy/load-balancing",
        "apache/proxy/ssl",
    }:
        if not {"proxy", "ingress", "upstream", "nginx"} & profile["contextual_terms"]:
            score -= 20.0

    if profile["domain"] == "software" and row_tag == "sql":
        if not {"database", "sql", "schema", "redis", "mysql", "postgresql", "query", "cache"} & profile["contextual_terms"]:
            score -= 16.0

    if profile["primary_issue_family"] == "cache_session_store" or profile["semantic_key"] in {"cache_session_consistency", "redis_state_path"}:
        if row_tag == "redis":
            score += 90.0
            reasons.append("redis_session_reference_alignment")
        elif "redis" in row_title_lower:
            score += 70.0
            reasons.append("redis_title_alignment")
        elif any(term in row_title_lower for term in {"cache", "session", "ttl", "replication", "persistence", "failover"}):
            score += 30.0
            reasons.append("redis_context_title_alignment")
        if row_tag in {"auth", "fastapi", "django", "reactjs", "javascript"}:
            score -= 80.0
            reasons.append("redis_session_auth_drift_penalty")
        if "jwt" in row_title_lower or "json web token" in row_title_lower or "oauth" in row_title_lower:
            score -= 120.0
            reasons.append("redis_session_jwt_drift_penalty")

    if profile["domain"] == "ai" and row_tag == "gpu/cuda/inference":
        if not {"gpu", "cuda", "memory", "vram", "inference"} & profile["contextual_terms"]:
            score -= 12.0

    if profile["primary_symptom"] == "authz_failure" and row_tag in {"reactjs", "javascript"}:
        score -= 24.0
    if profile["primary_symptom"] == "dns_failure" and row_tag in {"http/cors/proxy", "proxy/reverse-proxy/load-balancing"}:
        score -= 24.0
    if profile["primary_symptom"] == "upstream_failure" and row_tag in {"dns", "ssl/tls"}:
        if "dns" not in row_title_lower and "tls" not in row_title_lower and "certificate" not in row_title_lower:
            score -= 18.0
    if profile["primary_symptom"] == "schema_contract_failure" and row_tag in {"dns", "tcp/routing", "ssl/tls"}:
        score -= 24.0
    if profile["primary_issue_family"] == "database_connectivity" and row_tag in {"auth", "reactjs", "fastapi"}:
        if not {"authn_failure", "authz_failure", "csrf_or_cookie_failure"} & profile["symptom_names"]:
            score -= 20.0
    if profile["primary_symptom"] == "embedding_vector_mismatch" and row_tag not in {
        "sentence-transformers/embeddings",
        "vector-database/embeddings",
        "rag/llm/nlp",
    }:
        score -= 22.0
    if profile["primary_symptom"] == "cuda_oom" and row_tag not in {"gpu/cuda/inference", "pytorch", "tensorflow"}:
        score -= 22.0
    if profile["primary_symptom"] == "tokenizer_runtime_mismatch" and row_tag not in {
        "model-serving/inference",
        "huggingface-transformers/nlp/llm",
        "pytorch",
    }:
        score -= 20.0

    if profile["semantic_key"] == "capture_primary_symptom":
        if row_source_type not in {"official_docs", "vendor_docs", "protocol_reference"}:
            score -= 12.0
        if row_tag in {"fastapi", "python", "rest", "http/cors/proxy", "model-serving/inference"}:
            score += 14.0
        if row_tag == "auth":
            score -= 10.0

    if profile["semantic_key"] == "retest_after_change":
        if row_tag in {"fastapi", "python", "rest", "http/cors/proxy", "model-serving/inference", "dns", "tcp/routing"}:
            score += 10.0
        if row_tag == "auth":
            score -= 8.0
        if {"preflight_failure", "missing_cors_headers"} & profile["symptom_names"]:
            if "cors" in row_title_lower or "http overview" in row_title_lower or "http methods" in row_title_lower:
                score += 16.0
            if "javascript reference" in row_title_lower:
                score -= 18.0
        if "authz_failure" in profile["symptom_names"]:
            if "jwt" in row_title_lower or "authorization" in row_title_lower:
                score += 12.0
        if profile["primary_issue_family"] == "database_connectivity":
            if "postgresql" in row_title_lower or "database" in row_title_lower:
                score += 10.0

    if profile["semantic_key"] in {"auth_artifact_integrity", "auth_claim_validation", "jwt_claim_integrity"} and row_tag not in {"auth", "fastapi", "django"}:
        score -= 30.0
    if profile["semantic_key"] == "authorization_policy_check" and row_source_type not in {"security_guidance", "library_docs"}:
        score -= 18.0
    if profile["semantic_key"] in {"replay_preflight_origin", "cors_origin_alignment"} and row_tag not in {
        "http/cors/proxy",
        "fastapi",
        "reactjs",
        "nginx/proxy/load-balancing/ssl",
    }:
        score -= 28.0
    if profile["semantic_key"] in {"runtime_dns_resolution", "dns_answer_validation"} and row_tag not in {"dns", "tcp/routing"}:
        score -= 28.0
    if profile["semantic_key"] in {"tls_chain_validation"} and row_tag not in {
        "ssl/tls",
        "nginx/proxy/load-balancing/ssl",
        "apache/proxy/ssl",
    }:
        score -= 28.0
    if profile["semantic_key"] in {"database_target_runtime_config"} and row_tag not in {"sql", "django", "python"}:
        score -= 26.0
    if profile["semantic_key"] in {"database_contract_boundary", "postgresql_schema_state", "mysql_target_contract"} and row_tag not in {
        "sql",
        "vector-database/embeddings",
        "sentence-transformers/embeddings",
    }:
        score -= 26.0
    if profile["semantic_key"] in {"gpu_runtime_pressure", "gpu_workload_shape", "cuda_capacity_check", "gpu_utilization_check"} and row_tag not in {
        "gpu/cuda/inference",
        "pytorch",
        "tensorflow",
    }:
        score -= 26.0
    if profile["semantic_key"] in {"tensor_shape_capture", "tensor_conversion_validation"} and row_tag not in {
        "pytorch",
        "gpu/cuda/inference",
        "model-serving/inference",
        "numpy",
    }:
        score -= 26.0
    if profile["semantic_key"] in {"model_runtime_validation", "model_serving_branch", "serving_endpoint_mode"} and row_tag not in {
        "model-serving/inference",
        "huggingface-transformers/nlp/llm",
        "pytorch",
    }:
        score -= 24.0
    if profile["semantic_key"] in {"retrieval_vector_alignment", "rag_retrieval_path", "embedding_shape_profile"} and row_tag not in {
        "rag/llm/nlp",
        "sentence-transformers/embeddings",
        "vector-database/embeddings",
        "llm/embeddings/fine-tuning",
    }:
        score -= 24.0

    step_text = f"{step.get('title', '')} {step.get('action', '')}".lower()
    if "jwt" in step_text and "jwt" in row_title_lower:
        score += 18.0
    if "cors" in step_text and "cors" in row_title_lower:
        score += 18.0
    if "fastapi" in step_text and "fastapi" in row_title_lower:
        score += 18.0
    if "react" in step_text and "react" in row_title_lower:
        score += 18.0
    if "nginx" in step_text and "nginx" in row_title_lower:
        score += 18.0
    if "kubernetes" in step_text and "kubernetes" in row_title_lower:
        score += 18.0
    if "dns" in step_text and "dns" in row_title_lower:
        score += 18.0
    if "tls" in step_text or "ssl" in step_text:
        if "tls" in row_title_lower or "ssl" in row_title_lower or "certificate" in row_title_lower:
            score += 18.0

    stack_terms = set(profile["trusted_tags"]) | set(profile["supporting_tags"]) | set(profile["contextual_terms"])
    if "postgresql" in stack_terms:
        if "postgresql" in row_title_lower:
            score += 20.0
        if any(term in row_title_lower for term in {"mysql", "redis"}):
            score -= 24.0
    if "mysql" in stack_terms:
        if "mysql" in row_title_lower:
            score += 20.0
        if any(term in row_title_lower for term in {"postgresql", "redis"}):
            score -= 24.0
    if "redis" in stack_terms:
        if "redis" in row_title_lower:
            score += 18.0
        if any(term in row_title_lower for term in {"postgresql", "mysql"}):
            score -= 20.0

    if any(term in row_title_lower for term in {"async function", "promise", "useeffect", "usestate", " import", " export"}):
        if profile["semantic_key"] not in {"react_request_construction"}:
            score -= 24.0
    if "views" in row_title_lower and profile["semantic_key"] not in {"capture_primary_symptom"}:
        score -= 18.0
    if "models" in row_title_lower and profile["primary_issue_family"] != "database_connectivity":
        score -= 6.0
    if "sql injection" in row_title_lower and profile["primary_issue_family"] != "authentication":
        score -= 20.0
    if "logging" in row_title_lower and profile["semantic_key"] not in {"boundary_trace", "confirm_runtime_target"}:
        score -= 6.0

    return score, {
        "row_tag": row_tag,
        "source_type": row_source_type,
        "reasons": reasons,
        "keyword_overlap": keyword_overlap,
        "contextual_overlap": contextual_overlap,
        "title_hint_overlap": title_hint_overlap,
    }


def choose_reference_for_step(
    case_context: dict,
    step: dict,
    reference_rows: list[dict],
    used_urls: set[str] | None = None,
    used_tags: set[str] | None = None,
) -> tuple[dict, dict]:
    profile = build_step_reference_profile(step, case_context)
    used_urls = used_urls or set()
    used_tags = used_tags or set()

    scored_candidates = []
    for row in reference_rows:
        if row["domain"] != profile["domain"]:
            continue
        score, debug = _score_reference_row(row, profile, step)
        if row["url"] in used_urls:
            score -= 24.0
            debug["reasons"] = list(debug.get("reasons", [])) + ["url_reuse_penalty"]
        if row["tag"] in used_tags:
            score -= 8.0
            debug["reasons"] = list(debug.get("reasons", [])) + ["tag_reuse_penalty"]
        if score < 40.0:
            continue
        scored_candidates.append((score, row, debug))

    if not scored_candidates:
        fallback_candidates = []
        for row in reference_rows:
            if row["domain"] != profile["domain"]:
                continue
            fallback_score = REFERENCE_SOURCE_PRIORITY.get(row["source_type"], 70.0)
            if row["tag"] in BASELINE_ALLOWED_REFERENCE_TAGS.get(profile["domain"], []):
                fallback_score += 12.0
            if row["url"] in used_urls:
                fallback_score -= 18.0
            if row["tag"] in used_tags:
                fallback_score -= 6.0
            keyword_overlap = len(profile["preferred_keywords"] & row["keywords"])
            fallback_score += keyword_overlap * 3.0
            fallback_candidates.append(
                (
                    fallback_score,
                    row,
                    {
                        "row_tag": row["tag"],
                        "source_type": row["source_type"],
                        "reasons": ["credible_fallback"],
                        "keyword_overlap": keyword_overlap,
                        "contextual_overlap": 0,
                    },
                )
            )

        if not fallback_candidates:
            raise ValueError(f"No suitable reference found for checklist step '{step.get('title', '')}'.")
        fallback_candidates.sort(key=lambda item: (item[0], item[1]["title"]), reverse=True)
        chosen_score, chosen_row, chosen_debug = fallback_candidates[0]
        if used_urls and chosen_row["url"] in used_urls:
            for alt_score, alt_row, alt_debug in fallback_candidates[1:]:
                if alt_row["url"] in used_urls:
                    continue
                if alt_score >= chosen_score - 26.0:
                    chosen_score, chosen_row, chosen_debug = alt_score, alt_row, alt_debug
                    chosen_debug["reasons"] = list(chosen_debug.get("reasons", [])) + ["diversity_override"]
                    break
        return chosen_row, {
            "selected_score": round(chosen_score, 4),
            **chosen_debug,
            "profile": _build_trace_profile(profile),
        }

    scored_candidates.sort(key=lambda item: (item[0], item[1]["title"]), reverse=True)
    chosen_score, chosen_row, chosen_debug = scored_candidates[0]
    if used_urls and chosen_row["url"] in used_urls:
        for alt_score, alt_row, alt_debug in scored_candidates[1:]:
            if alt_row["url"] in used_urls:
                continue
            if alt_score >= chosen_score - 28.0:
                chosen_score, chosen_row, chosen_debug = alt_score, alt_row, alt_debug
                chosen_debug["reasons"] = list(chosen_debug.get("reasons", [])) + ["diversity_override"]
                break
    return chosen_row, {
        "selected_score": round(chosen_score, 4),
        **chosen_debug,
        "profile": _build_trace_profile(profile),
    }


def _build_references_summary(trace_entries: list[dict]) -> list[dict]:
    aggregated = {}
    for entry in trace_entries:
        ref = entry["selected_reference"]
        key = ref["url"]
        current = aggregated.setdefault(
            key,
            {
                "title": ref["title"],
                "url": ref["url"],
                "source_type": ref["source_type"],
                "tag": ref.get("tag", ""),
                "step_count": 0,
                "score": 0.0,
            },
        )
        current["step_count"] += 1
        current["score"] += float(entry.get("selected_score", 0.0))

    ranked = sorted(
        aggregated.values(),
        key=lambda item: (item["score"], item["step_count"], item["title"]),
        reverse=True,
    )

    summary = []
    seen_tags = set()
    seen_titles = set()
    seen_source_types: dict[str, int] = {}
    for item in ranked:
        title_key = collapse_whitespace(item["title"]).lower()
        if title_key in seen_titles:
            continue
        if item["tag"] and item["tag"] in seen_tags and len(summary) < 3:
            continue
        source_type = item.get("source_type", "official_docs")
        if seen_source_types.get(source_type, 0) >= 2 and len(summary) < 4:
            continue
        summary.append(
            {
                "title": item["title"],
                "url": item["url"],
                "source_type": source_type,
            }
        )
        seen_titles.add(title_key)
        if item["tag"]:
            seen_tags.add(item["tag"])
        seen_source_types[source_type] = seen_source_types.get(source_type, 0) + 1
        if len(summary) >= 5:
            break
    return summary


def _supplement_references_summary(
    domain: str,
    summary: list[dict],
    trace_entries: list[dict],
    reference_rows: list[dict],
) -> list[dict]:
    if len(summary) >= 2:
        return summary

    used_urls = {item["url"] for item in summary if item.get("url")}
    selected_tags = {
        entry.get("selected_reference", {}).get("tag", "")
        for entry in trace_entries
        if entry.get("selected_reference", {}).get("tag")
    }
    context_terms = tokenize_keywords(
        " ".join(entry.get("step_title", "") for entry in trace_entries),
        " ".join(entry.get("semantic_key", "") for entry in trace_entries),
        " ".join(entry.get("anchor_tag", "") for entry in trace_entries),
        " ".join(entry.get("primary_issue_family", "") for entry in trace_entries),
    )
    baseline_tags = set(BASELINE_ALLOWED_REFERENCE_TAGS.get(domain, []))
    existing_source_types = {item.get("source_type", "") for item in summary}

    candidates = []
    for row in reference_rows:
        if row["domain"] != domain or row["url"] in used_urls:
            continue
        score = REFERENCE_SOURCE_PRIORITY.get(row["source_type"], 70.0)
        if row["tag"] in selected_tags:
            score += 12.0
        if row["tag"] in baseline_tags:
            score += 10.0
        if row["source_type"] not in existing_source_types:
            score += 10.0
        score += len(context_terms & row.get("keywords", set())) * 4.0
        candidates.append((score, row))

    candidates.sort(key=lambda item: (item[0], item[1]["title"]), reverse=True)
    for _score, row in candidates:
        summary.append(
            {
                "title": row["title"],
                "url": row["url"],
                "source_type": row["source_type"],
            }
        )
        used_urls.add(row["url"])
        existing_source_types.add(row["source_type"])
        if len(summary) >= 2:
            break
    return summary


__all__ = [
    "_resolve_reference_context",
    "build_case_tag_weights",
    "_top_unique",
    "_resolve_visible_domain",
    "_boundary_names",
    "_secondary_families",
    "_ordered_unique_filter",
    "_context_stack_tags",
    "_specialize_reference_profile",
    "build_step_reference_profile",
    "_build_trace_profile",
    "_score_reference_row",
    "choose_reference_for_step",
    "_build_references_summary",
    "_supplement_references_summary",
]