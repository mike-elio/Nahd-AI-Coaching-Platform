import re
from typing import Any

from app.config import VALID_DOMAINS
from app.repositories.registries import CLUSTER_REGISTRY, ISSUE_FAMILY_REGISTRY
from app.repositories.scenarios import (
    BOUNDARY_LABELS,
    FAMILY_ALTERNATIVE_PATHS,
    MAJOR_TAGS,
    SCENARIO_LIBRARY,
    TAG_CATEGORY_RULES,
    TAG_CONTEXT_OVERRIDES,
)
from app.rules.family_resolution import (
    _family_constraints_for_symptoms,
    _family_from_symptoms,
    _has_browser_state_symptom,
)
from app.rules.tag_interpretation import normalize_tag_signals
from app.rules.text_processing import (
    clamp_confidence,
    collapse_whitespace,
    normalize_issue_family,
    normalize_title_key,
    tokenize_keywords,
)


def _humanize_slug(value: str) -> str:
    return collapse_whitespace(str(value).replace("_", " ").replace("-", " ").replace(".", " "))


def _humanize_tag(tag: str) -> str:
    normalized = str(tag).strip().lower()
    if normalized in TAG_CONTEXT_OVERRIDES:
        return TAG_CONTEXT_OVERRIDES[normalized]

    parts = _humanize_slug(normalized).split()
    words = []
    for part in parts:
        if part in {"jwt", "dns", "tls", "ssl", "http", "tcp", "gpu", "cuda", "rag"}:
            words.append(part.upper())
        elif part == "oauth":
            words.append("OAuth")
        elif part == "fastapi":
            words.append("FastAPI")
        elif part == "django":
            words.append("Django")
        elif part == "nginx":
            words.append("Nginx")
        elif part == "kubernetes":
            words.append("Kubernetes")
        elif part == "postgresql":
            words.append("PostgreSQL")
        elif part == "mysql":
            words.append("MySQL")
        elif part == "reactjs":
            words.append("React")
        elif part == "pytorch":
            words.append("PyTorch")
        elif part == "scikit":
            words.append("scikit")
        else:
            words.append(part.capitalize())
    return collapse_whitespace(" ".join(words))


def _top_unique(values: list[str], limit: int) -> list[str]:
    seen = set()
    ordered = []
    for value in values:
        normalized = normalize_title_key(value)
        if not normalized or normalized in seen:
            continue
        ordered.append(value)
        seen.add(normalized)
        if len(ordered) >= limit:
            break
    return ordered


def _tag_categories(tag: str) -> set[str]:
    categories = set()
    for category, category_tags in TAG_CATEGORY_RULES.items():
        if tag in category_tags:
            categories.add(category)
    if not categories:
        categories.add("runtime")
    return categories


def _build_tag_profile(tag_item: dict, active_domain: str, family_map: dict[str, dict], boundary_map: dict[str, dict]) -> dict[str, Any]:
    tag = tag_item["tag"]
    categories = _tag_categories(tag)
    default_boundaries = {
        boundary_name
        for boundary_name, boundary_rule in {
            "browser_boundary": {"tags": {"cors", "reactjs", "javascript", "typescript", "authentication", "authorization"}},
            "proxy_boundary": {"tags": {"proxy", "reverse-proxy", "nginx", "apache", "ingress", "http"}},
            "runtime_boundary": {"tags": {"python", "java", "node.js", "fastapi", "django", "flask", "express", "spring-boot", "asp.net-core", "debugging", "logging"}},
            "database_boundary": {"tags": {"sql", "postgresql", "mysql", "redis", "vector-database"}},
            "network_transport_boundary": {"tags": {"networking", "dns", "ssl", "tls", "tcp", "routing", "firewall", "vpn"}},
            "model_serving_boundary": {"tags": {"model-serving", "large-language-model", "rag", "embeddings", "inference", "huggingface-transformers", "sentence-transformers"}},
            "gpu_inference_boundary": {"tags": {"gpu", "cuda", "pytorch", "tensorflow", "inference"}},
            "deployment_change_hint": {"tags": {"docker", "kubernetes", "ingress", "mlops", "debugging"}},
        }.items()
        if tag in boundary_rule["tags"]
    }

    related_families = [
        family_name
        for family_name, family_rule in ISSUE_FAMILY_REGISTRY.items()
        if active_domain in family_rule["domains"] and tag in family_rule["tags"]
    ]

    candidate_families = _top_unique(
        [family_name for family_name in related_families if family_name in family_map] + related_families,
        4,
    )

    candidate_boundaries = _top_unique(
        [boundary_name for boundary_name in default_boundaries if boundary_name in boundary_map]
        + [boundary_name for boundary_name in boundary_map if boundary_name in default_boundaries]
        + list(default_boundaries),
        4,
    )

    scenarios = set()
    for scenario_name, scenario_rule in SCENARIO_LIBRARY.items():
        if categories & scenario_rule["categories"]:
            scenarios.add(scenario_name)
    if active_domain == "sw":
        scenarios.update({"config_alignment", "boundary_propagation"})
    elif active_domain == "cn":
        scenarios.update({"transport_resolution", "proxy_forwarding"})
    else:
        scenarios.update({"artifact_loading", "capacity_exhaustion"})

    return {
        "tag": tag,
        "tag_context": _humanize_tag(tag),
        "active_domain": active_domain,
        "categories": categories,
        "candidate_families": candidate_families,
        "candidate_boundaries": candidate_boundaries or list(boundary_map)[:3],
        "scenarios": sorted(scenarios),
        "target_case_count": 36 if tag in MAJOR_TAGS else 30,
        "effective_confidence": float(tag_item["effective_confidence"]),
        "confidence_tier": tag_item["confidence_tier"],
        "domain_alignment": tag_item["domain_alignment"],
    }


def _family_score(family_name: str, family_map: dict[str, dict]) -> float:
    family = family_map.get(family_name)
    if not family:
        return 0.0
    return float(family.get("score", 0.0))


def _boundary_score(boundary_name: str, boundary_map: dict[str, dict]) -> float:
    boundary = boundary_map.get(boundary_name)
    if not boundary:
        return 0.0
    return float(boundary.get("score", 0.0))


def _cluster_candidates_for_tag(tag: str, cluster_map: dict[str, dict]) -> list[str]:
    candidates = []
    for cluster_id, cluster in cluster_map.items():
        if tag in cluster.get("matched_tags", []):
            candidates.append(cluster_id)
    if not candidates:
        for cluster_id, cluster_rule in CLUSTER_REGISTRY.items():
            if tag in cluster_rule["tags"] and cluster_id in cluster_map:
                candidates.append(cluster_id)
    return _top_unique(candidates, 3)


def _symptom_modes_for_profile(profile: dict[str, Any], text_features: dict[str, Any]) -> list[str]:
    modes = list(text_features["sorted_symptom_buckets"])
    if profile["categories"] & {"auth", "frontend"}:
        modes += ["auth", "boundary"]
    if profile["categories"] & {"proxy_edge", "network", "infra"}:
        modes += ["connectivity", "timeout"]
    if profile["categories"] & {"database"}:
        modes += ["data", "config"]
    if profile["categories"] & {"ai_serving", "gpu_compute", "ml_framework"}:
        modes += ["ai_runtime", "timeout"]
    if text_features["has_deployment_change"]:
        modes.append("deployment")
    modes.append("general")
    return _top_unique(modes, 4)


def _scenario_is_plausible(
    scenario_name: str,
    family_name: str,
    boundary_name: str,
    profile: dict[str, Any],
    text_features: dict[str, Any],
) -> bool:
    symptom_names = text_features["symptom_names"]
    allowed_families = _family_constraints_for_symptoms(active_domain=profile.get("active_domain", "sw"), text_features=text_features)
    if family_name not in allowed_families:
        return False
    if scenario_name == "retrieval_pipeline" and family_name != "retrieval_embeddings_pipeline":
        return False
    if scenario_name == "capacity_exhaustion" and family_name != "gpu_inference_runtime":
        if "cuda_oom" in symptom_names:
            return False
    if scenario_name == "schema_contract" and family_name == "retrieval_embeddings_pipeline":
        return "embedding_vector_mismatch" in symptom_names
    if family_name == "authorization_policy" and "authz_failure" not in symptom_names and "scope" not in text_features["tokens"]:
        return False
    if family_name == "authentication" and "authz_failure" in symptom_names and "authn_failure" not in symptom_names:
        return False
    if family_name == "cors_proxy_boundary" and "api_base_url_mismatch" in symptom_names and not ({"preflight_failure", "missing_cors_headers"} & symptom_names):
        return False
    if family_name == "cors_proxy_boundary" and not ({"preflight_failure", "missing_cors_headers", "browser_only_failure"} & symptom_names):
        if {"api_base_url_mismatch", "authorization_header_stripped"} & symptom_names:
            return False
        return "frontend" in profile["categories"] or "boundary" in text_features["sorted_symptom_buckets"]
    if family_name == "tls_edge_termination" and "tls_failure" not in symptom_names:
        return "tls" in text_features["sorted_symptom_buckets"]
    if family_name == "dns_service_discovery" and "dns_failure" not in symptom_names and "resolve" not in text_features["tokens"]:
        return "connectivity" in text_features["sorted_symptom_buckets"]
    if family_name == "database_connectivity" and "embedding_vector_mismatch" in symptom_names:
        return "schema_contract_failure" in symptom_names and "database" in text_features["tokens"]
    if family_name == "retrieval_embeddings_pipeline" and "embedding_vector_mismatch" not in symptom_names:
        return "ai_serving" in profile["categories"] and "database" in profile["categories"]
    if boundary_name == "gpu_inference_boundary" and "cuda_oom" not in symptom_names:
        return "gpu_compute" in profile["categories"]
    if family_name == "session_identity_boundary" and not _has_browser_state_symptom(symptom_names):
        return False
    if family_name == "http_routing_misconfiguration" and "dns_failure" in symptom_names and "upstream_failure" not in symptom_names:
        return False
    if family_name == "dns_service_discovery" and "upstream_failure" in symptom_names and "dns_failure" not in symptom_names:
        return False
    if family_name == "model_serving_runtime" and "embedding_vector_mismatch" in symptom_names and "tokenizer_runtime_mismatch" not in symptom_names:
        return False
    if family_name == "gpu_inference_runtime" and "embedding_vector_mismatch" in symptom_names and "cuda_oom" not in symptom_names and "tensor_shape_mismatch" not in symptom_names:
        return False
    if family_name == "gpu_inference_runtime" and "model_endpoint_unavailable" in symptom_names and "cuda_oom" not in symptom_names and "tensor_shape_mismatch" not in symptom_names:
        return False
    if family_name == "retrieval_embeddings_pipeline" and "tensor_shape_mismatch" in symptom_names and "embedding_vector_mismatch" not in symptom_names:
        return False
    if family_name == "retrieval_embeddings_pipeline" and "tensor_shape_mismatch" in symptom_names:
        return "embedding_vector_mismatch" in symptom_names and "ai_serving" in profile["categories"]
    return True


def _family_specific_alternative_paths(primary_issue_family: str, text_features: dict[str, Any], boundary_label: str) -> list[str]:
    symptom_names = set(text_features["symptom_names"])
    if primary_issue_family == "database_connectivity":
        if "schema_contract_failure" in symptom_names:
            return [
                "Confirm the runtime points to the intended database and schema search path",
                "Confirm the live migration state matches the failing code path",
                "Confirm the query contract still matches the live relations, columns, and result shape",
            ]
        candidates = [
            "Resolve the configured database hostname from the failing runtime and compare the live answer set",
            "Test TCP reachability from the running service to the configured database host and port",
            "Verify secret injection and environment-variable expansion produce the expected DSN at startup",
        ]
        if "timeout_failure" in symptom_names and not ({"config_or_secret_drift", "database_target_change", "dns_failure", "connection_refused"} & symptom_names):
            candidates.append("Check whether connection pool saturation or exhausted workers are masking the primary data-path failure")
        return candidates
    if primary_issue_family == "dns_service_discovery":
        return [
            "Resolve the configured service name from each failing caller context and compare search-domain expansion",
            "Compare live resolver answers, TTL behavior, and endpoint registration across replicas",
            "Verify transport failures happen after, not before, correct name resolution on the failing hop",
        ]
    if primary_issue_family == "tls_edge_termination":
        return [
            "Inspect certificate chain, SNI, and hostname coverage from the failing caller context",
            "Compare edge TLS termination with the backend TLS mode expected by the service",
            "Confirm certificate rotation did not change trust roots, key material, or hostname mapping",
        ]
    if primary_issue_family == "authentication":
        return [
            "Confirm the Authorization header, bearer token, cookie, or session artifact reaches backend validation unchanged",
            "Decode the failing token and compare issuer, audience, expiry, and signature validation inputs",
            "Verify recent secret, callback, or trusted-host changes did not alter token validation behavior",
        ]
    if primary_issue_family == "authorization_policy":
        return [
            "Trace the exact role, scope, and permission check that rejects the protected operation",
            "Compare token claims with the route-level policy mapping used by the failing request",
            "Verify cached policy state or role assignments are not stale for the affected identity",
        ]
    if primary_issue_family == "http_routing_misconfiguration":
        if "api_base_url_mismatch" in symptom_names:
            return [
                "Inspect the deployed client configuration and confirm the API base URL used by the failing request",
                "Compare the browser network target with the intended backend host, scheme, and route",
                "Confirm build-time and runtime environment injection did not leave the client pointing at localhost or a stale endpoint",
            ]
        if "missing_runtime_env_var" in symptom_names:
            return [
                "Confirm every required runtime environment variable and secret is present in the failing service process",
                "Trace startup configuration loading before the application chooses downstream endpoints or dependencies",
                "Compare the failing runtime configuration with the last known-good deployment state",
            ]
        if "authorization_header_stripped" in symptom_names:
            return [
                f"Confirm Host and Authorization header forwarding across the {boundary_label}",
                "Compare direct backend validation with the proxy-mediated request seen by the upstream service",
                "Verify route rewrite and upstream target selection do not alter the protected request context",
            ]
        return [
            f"Confirm the active upstream target, preserved host, and path rewrite across the {boundary_label}",
            "Compare direct service routing with the ingress or proxy path used by the failing request",
            "Verify edge timeout and retry behavior do not hide the first failing upstream hop",
        ]
    if primary_issue_family == "model_serving_runtime":
        if "model_endpoint_unavailable" in symptom_names:
            return [
                f"Confirm the configured model-serving base URL and endpoint availability across the {boundary_label}",
                "Compare the failing serving endpoint with the active deployment target and last known-good model route",
                "Verify disabled, stale, or fallback inference endpoints are not receiving the live request",
            ]
        return [
            f"Confirm the live serving endpoint, model revision, and tokenizer assets across the {boundary_label}",
            "Compare the failing request path with the last known-good deployment or model revision",
            "Verify request size and concurrency do not trigger a degraded serving mode or fallback path",
        ]
    if primary_issue_family == "gpu_inference_runtime":
        if "tensor_shape_mismatch" in symptom_names:
            return [
                "Compare the tensor shape entering the model with the shape the first layer expects",
                "Confirm batch dimension, sequence length, and feature count remain consistent across preprocessing",
                "Verify NumPy-to-PyTorch conversion preserves dtype, layout, and dimension order",
            ]
        return [
            "Measure GPU memory headroom against the current batch shape and concurrency",
            "Confirm CUDA, driver, and framework versions are compatible on the failing worker",
            "Verify the workload does not switch unexpectedly between CPU and GPU execution paths",
        ]
    return list(FAMILY_ALTERNATIVE_PATHS.get(primary_issue_family, []))


def _path_is_substep_of_primary(candidate: str, primary_path: str) -> bool:
    candidate_signature = _path_signature(candidate)
    primary_signature = _path_signature(primary_path)
    if not candidate_signature or not primary_signature:
        return False
    if candidate_signature <= primary_signature:
        return True

    db_focus_tokens = {"database", "hostname", "host", "secret", "dsn", "credential", "credentials", "runtime", "startup"}
    if primary_signature & db_focus_tokens and candidate_signature & db_focus_tokens:
        overlap = len(candidate_signature & primary_signature)
        if overlap >= max(2, len(candidate_signature) - 1):
            return True
    return False


def _path_title_for_family(family_name: str, boundary_label: str, text_features: dict[str, Any]) -> str:
    symptom_names = text_features["symptom_names"]
    tokens = set(text_features.get("tokens", set()))
    if family_name == "cors_proxy_boundary":
        if "preflight_failure" in symptom_names:
            return f"Verify CORS preflight handling across the {boundary_label}"
        return f"Verify cross-origin headers and credential handling across the {boundary_label}"
    if family_name == "authorization_policy":
        return "Verify role, scope, and policy evaluation on the protected operation"
    if family_name == "authentication":
        return f"Verify token validation and identity propagation across the {boundary_label}"
    if family_name == "session_identity_boundary":
        return f"Verify session, cookie, and CSRF continuity across the {boundary_label}"
    if family_name == "cache_session_store":
        return f"Verify Redis/cache session state continuity across the {boundary_label}"
    if family_name == "http_routing_misconfiguration":
        if {"dependency_mismatch", "runtime_startup_failure"} <= symptom_names and not (tokens & {"database", "db", "postgres", "postgresql", "mysql", "sql", "dsn", "schema", "migration"}):
            return f"Trace startup dependency and runtime configuration across the {boundary_label}"
        if "upstream_health_check_mismatch" in symptom_names:
            return f"Verify load balancer health-check path and upstream readiness across the {boundary_label}"
        if "authorization_header_stripped" in symptom_names:
            return f"Verify Host and Authorization header forwarding across the {boundary_label}"
        if "upstream_failure" in symptom_names:
            return f"Verify the upstream target and route rewrite across the {boundary_label}"
        return f"Trace request routing across the {boundary_label}"
    if family_name == "database_connectivity":
        if {"dependency_mismatch", "runtime_startup_failure"} <= symptom_names and not (tokens & {"database", "db", "postgres", "postgresql", "mysql", "sql", "dsn", "schema", "migration"}):
            return f"Trace startup dependency and runtime configuration across the {boundary_label}"
        if {"config_or_secret_drift", "database_target_change", "runtime_startup_failure"} & symptom_names and {"dns_failure", "connection_refused"} & symptom_names:
            return "Verify the configured database host, secret, and connection path from the application runtime"
        if "schema_contract_failure" in symptom_names:
            return f"Verify schema and query contract alignment across the {boundary_label}"
        return f"Verify database connectivity and target selection across the {boundary_label}"
    if family_name == "dns_service_discovery":
        return "Verify DNS resolution and service discovery from the failing caller"
    if family_name == "tls_edge_termination":
        return f"Verify TLS termination and certificate trust across the {boundary_label}"
    if family_name == "model_serving_runtime":
        if "stale_model_checkpoint" in symptom_names:
            return f"Verify model-serving checkpoint version and artifact selection across the {boundary_label}"
        if {"tokenizer_runtime_mismatch", "tokenizer_checkpoint_mismatch"} & symptom_names:
            return f"Verify model and tokenizer runtime alignment across the {boundary_label}"
        return f"Verify model-serving runtime behavior across the {boundary_label}"
    if family_name == "retrieval_embeddings_pipeline":
        return f"Verify embedding and vector-store contract alignment across the {boundary_label}"
    if family_name == "gpu_inference_runtime":
        return f"Verify GPU memory headroom and execution pressure across the {boundary_label}"
    if family_name == "container_networking":
        return f"Verify platform routing and service reachability across the {boundary_label}"
    return f"Validate the dominant failure path across the {boundary_label}"


def _ranked_family_path_options(primary_issue_family: str, secondary_families: list[str], text_features: dict[str, Any], boundary_label: str) -> list[str]:
    family_order = [primary_issue_family, *secondary_families]
    family_order = [_family_from_symptoms(family_name, text_features) for family_name in family_order]
    return _top_unique([_path_title_for_family(family_name, boundary_label, text_features) for family_name in family_order], 5)


_TENSOR_SHAPE_CAUSE_TITLES = (
    "Input tensor feature count does not match the first linear layer or model input contract",
    "Loaded checkpoint, model head, or preprocessing pipeline expects a different feature dimension",
    "Batch dimension, sequence length, or padding changes between requests",
    "NumPy-to-PyTorch conversion changes dtype, layout, or dimension order",
)


_CORS_CAUSE_ROTATION = (
    "CORS allowlist or response headers are incomplete across the {boundary_label}",
    "The preflight allowlist omits the method, header, or origin used by the failing browser request",
    "The edge proxy or ingress returns different CORS headers than the backend intends",
    "Credentialed cross-origin requests fail because Origin and Access-Control-Allow-Credentials handling is inconsistent",
)


def _build_case_specific_cause_title(case: dict, text_features: dict[str, Any]) -> str:
    boundary_label = case["boundary_label"]
    family_name = case["issue_family"]
    scenario_name = case.get("scenario", "")
    symptom_names = text_features["symptom_names"]
    if family_name == "cors_proxy_boundary":
        if "missing_cors_headers" in symptom_names:
            return _CORS_CAUSE_ROTATION[0].format(boundary_label=boundary_label)
        if scenario_name == "proxy_forwarding":
            return _CORS_CAUSE_ROTATION[2]
        if scenario_name == "boundary_propagation":
            return _CORS_CAUSE_ROTATION[3]
        return _CORS_CAUSE_ROTATION[1]
    if family_name == "authorization_policy":
        return "A valid identity reaches the service, but role, scope, or policy mapping rejects the operation"
    if family_name == "authentication":
        return f"Token, cookie, or auth metadata is altered before validation across the {boundary_label}"
    if family_name == "session_identity_boundary":
        return "Cookie scope, SameSite, or CSRF settings break session continuity on the live path"
    if family_name == "http_routing_misconfiguration":
        if "api_base_url_mismatch" in symptom_names:
            return "The deployed client is using the wrong API base URL, stale endpoint, or localhost target after deployment"
        if "missing_runtime_env_var" in symptom_names:
            return "A required runtime environment variable or secret is missing, so startup cannot select the intended dependency target"
        if "authorization_header_stripped" in symptom_names:
            return "Proxy forwarding strips or rewrites Host or Authorization headers before upstream validation"
        return f"Proxy routing or upstream targeting is misaligned across the {boundary_label}"
    if family_name == "database_connectivity":
        if scenario_name in {"config_alignment", "deployment_regression"} and {"config_or_secret_drift", "database_target_change", "runtime_startup_failure"} & symptom_names:
            return "The deployed runtime is using the wrong database hostname, secret, or connection target after the recent change"
        if scenario_name == "transport_resolution" and "dns_failure" in symptom_names:
            return "The failing caller resolves the wrong host or cannot resolve the intended internal service name"
        if scenario_name in {"transport_resolution", "service_availability"} and {"connection_refused", "timeout_failure"} & symptom_names:
            return "The connection path from the application runtime to the configured database endpoint is blocked, misrouted, or terminated on the wrong hop"
        if scenario_name in {"latency_budget", "capacity_exhaustion"} and "timeout_failure" in symptom_names and not ({"config_or_secret_drift", "database_target_change", "dns_failure", "connection_refused"} & symptom_names):
            return "Connection pool saturation or timeout budget pressure is surfacing as intermittent database-path failure"
        if scenario_name == "schema_contract" or "schema_contract_failure" in symptom_names:
            return "The live schema, migration state, or query contract no longer matches the failing request"
        return f"The runtime points at the wrong database target or cannot reach it across the {boundary_label}"
    if family_name == "dns_service_discovery":
        return "The failing caller resolves the wrong host or cannot resolve the intended internal service name"
    if family_name == "tls_edge_termination":
        return f"Certificate trust, hostname, or TLS termination is inconsistent across the {boundary_label}"
    if family_name == "model_serving_runtime":
        if "model_endpoint_unavailable" in symptom_names:
            return "The configured model-serving base URL points to a disabled, stale, or unavailable inference endpoint"
        if "missing_runtime_env_var" in symptom_names:
            return "A required model-serving environment variable or secret is missing from the runtime"
        if "tokenizer_runtime_mismatch" in symptom_names:
            return "The deployed model artifacts or tokenizer assets do not match the live serving runtime"
        if "tensor_shape_mismatch" in symptom_names:
            return _TENSOR_SHAPE_CAUSE_TITLES[0]
        return f"The serving runtime or endpoint branch is inconsistent across the {boundary_label}"
    if family_name == "retrieval_embeddings_pipeline":
        return "Embeddings, vector dimensions, or retrieval assumptions no longer match the active index"
    if family_name == "gpu_inference_runtime":
        if "tensor_shape_mismatch" in symptom_names:
            return _TENSOR_SHAPE_CAUSE_TITLES[0]
        return "GPU memory pressure or batch shape exceeds the live inference runtime budget"
    if family_name == "container_networking":
        return f"Service discovery, selectors, or network policy broke the live platform path across the {boundary_label}"
    return collapse_whitespace(case["hypothesis_title"])


def _case_score(
    scenario_name: str,
    tag_item: dict,
    family_name: str,
    boundary_name: str,
    symptom_mode: str,
    family_map: dict[str, dict],
    boundary_map: dict[str, dict],
    cluster_confidence: float,
    text_features: dict[str, Any],
) -> float:
    scenario = SCENARIO_LIBRARY[scenario_name]
    score = scenario["base_weight"]
    score += float(tag_item["effective_diagnostic_weight"]) * 0.8
    score += _family_score(family_name, family_map) * 0.12
    score += _boundary_score(boundary_name, boundary_map) * 0.55
    score += cluster_confidence * 0.8

    if symptom_mode != "general" and symptom_mode in scenario["symptoms"]:
        score += 0.55
    elif symptom_mode == "general":
        score += 0.18
    else:
        score -= 0.08

    if text_features["has_deployment_change"] and boundary_name == "deployment_change_hint":
        score += 0.32
    if tag_item["confidence_tier"] == "trusted":
        score += 0.42
    elif tag_item["confidence_tier"] == "supporting":
        score += 0.18
    else:
        score -= 0.25

    if tag_item["domain_alignment"] != "direct":
        score -= 0.18
    return round(score, 4)


def _build_reasoning_cases_for_tag(
    tag_item: dict,
    active_domain: str,
    family_map: dict[str, dict],
    boundary_map: dict[str, dict],
    cluster_map: dict[str, dict],
    text_features: dict[str, Any],
) -> list[dict]:
    profile = _build_tag_profile(tag_item, active_domain, family_map, boundary_map)
    cases = []
    cluster_candidates = _cluster_candidates_for_tag(tag_item["tag"], cluster_map)
    if not cluster_candidates and cluster_map:
        cluster_candidates = list(cluster_map)[:2]
    if not cluster_candidates:
        cluster_candidates = ["no_cluster_alignment"]

    family_candidates = profile["candidate_families"] or list(family_map)[:3]
    if not family_candidates:
        family_candidates = ["authentication"] if active_domain == "sw" else ["dns_service_discovery"] if active_domain == "cn" else ["model_serving_runtime"]

    boundary_candidates = profile["candidate_boundaries"] or list(boundary_map)[:3]
    if not boundary_candidates:
        boundary_candidates = ["runtime_boundary"]

    symptom_modes = _symptom_modes_for_profile(profile, text_features)

    for scenario_name in profile["scenarios"]:
        scenario = SCENARIO_LIBRARY[scenario_name]
        for family_name in family_candidates:
            if family_name not in scenario["families"]:
                continue
            for boundary_name in boundary_candidates:
                if boundary_name not in scenario["boundaries"]:
                    continue
                if not _scenario_is_plausible(scenario_name, family_name, boundary_name, profile, text_features):
                    continue
                for symptom_mode in symptom_modes:
                    if symptom_mode != "general" and scenario["symptoms"] and symptom_mode not in scenario["symptoms"]:
                        continue
                    for cluster_id in cluster_candidates:
                        cluster_confidence = float(cluster_map.get(cluster_id, {}).get("confidence", 0.0))
                        boundary_label = BOUNDARY_LABELS.get(boundary_name, _humanize_slug(boundary_name))
                        score = _case_score(
                            scenario_name,
                            tag_item,
                            family_name,
                            boundary_name,
                            symptom_mode,
                            family_map,
                            boundary_map,
                            cluster_confidence,
                            text_features,
                        )
                        case_key = "|".join(
                            [
                                tag_item["tag"],
                                scenario_name,
                                family_name,
                                boundary_name,
                                symptom_mode,
                                cluster_id,
                            ]
                        )
                        cases.append(
                            {
                                "case_key": case_key,
                                "tag": tag_item["tag"],
                                "tag_context": profile["tag_context"],
                                "scenario": scenario_name,
                                "issue_family": family_name,
                                "boundary": boundary_name,
                                "boundary_label": boundary_label,
                                "symptom_mode": symptom_mode,
                                "cluster_id": cluster_id,
                                "cluster_confidence": cluster_confidence,
                                "score": score,
                                "path_title": collapse_whitespace(
                                    scenario["path_template"].format(
                                        tag_context=profile["tag_context"],
                                        boundary_label=boundary_label,
                                    )
                                ),
                                "hypothesis_title": collapse_whitespace(
                                    scenario["cause_template"].format(
                                        tag_context=profile["tag_context"],
                                        boundary_label=boundary_label,
                                    )
                                ),
                            }
                        )

    cases.sort(key=lambda item: (item["score"], item["scenario"], item["issue_family"]), reverse=True)
    deduped = []
    seen_case_keys = set()
    for case in cases:
        if case["case_key"] in seen_case_keys:
            continue
        deduped.append(case)
        seen_case_keys.add(case["case_key"])
        if len(deduped) >= profile["target_case_count"]:
            break
    return deduped


def _build_case_bank(reasoning_bundle: dict[str, Any]) -> tuple[list[dict], dict[str, Any]]:
    tag_items = reasoning_bundle["tag_items"]
    family_map = reasoning_bundle["family_map"]
    boundary_map = reasoning_bundle["boundary_map"]
    cluster_map = reasoning_bundle["cluster_map"]
    text_features = reasoning_bundle["text_features"]
    active_domain = reasoning_bundle["active_domain"]

    all_cases = []
    tag_case_coverage = {}

    for tag_item in tag_items:
        if not tag_item.get("routing_allowed", True):
            tag_case_coverage[tag_item["tag"]] = {
                "generated_cases": 0,
                "confidence_tier": tag_item["confidence_tier"],
            }
            continue
        tag_cases = _build_reasoning_cases_for_tag(
            tag_item,
            active_domain,
            family_map,
            boundary_map,
            cluster_map,
            text_features,
        )
        all_cases.extend(tag_cases)
        tag_case_coverage[tag_item["tag"]] = {
            "generated_cases": len(tag_cases),
            "confidence_tier": tag_item["confidence_tier"],
        }

    all_cases.sort(key=lambda item: (item["score"], item["tag"], item["scenario"]), reverse=True)
    return all_cases, tag_case_coverage


def _build_primary_path(primary_issue_family: str, selected_cluster: str, reasoning_bundle: dict[str, Any]) -> str:
    text_features = reasoning_bundle["text_features"]
    strongest_boundary = _strongest_boundary_name(reasoning_bundle)
    boundary_label = BOUNDARY_LABELS.get(strongest_boundary, _humanize_slug(strongest_boundary))
    primary_symptom = text_features.get("primary_symptom", "")

    symptom_first_paths = {
        "preflight_failure": f"Replay the failing OPTIONS preflight across the {boundary_label} and compare the returned CORS policy",
        "missing_cors_headers": f"Compare Access-Control headers across the {boundary_label} for the failing browser request",
        "browser_only_failure": f"Compare browser-only request behavior across the {boundary_label} against the working server-side path",
        "api_base_url_mismatch": "Verify the deployed client API base URL and browser request target before backend debugging",
        "csrf_or_cookie_failure": f"Verify cookie, SameSite, and CSRF continuity across the {boundary_label}",
        "authn_failure": f"Inspect the live auth artifact as it crosses the {boundary_label} before backend validation",
        "authz_failure": "Trace the exact scope, role, and policy decision that produces the 403 denial",
        "authorization_header_stripped": f"Verify Host and Authorization header forwarding across the {boundary_label}",
        "upstream_failure": f"Trace upstream target selection and request rewriting across the {boundary_label}",
        "connection_refused": f"Test the failing hop directly across the {boundary_label} and confirm which endpoint refuses the connection",
        "timeout_failure": f"Measure where latency exceeds the active timeout budget across the {boundary_label}",
        "tls_failure": f"Inspect certificate trust and TLS handshake behavior across the {boundary_label}",
        "dns_failure": "Resolve the failing service name from the caller context and compare the live answer set",
        "schema_contract_failure": f"Validate schema and request-contract alignment before testing end-to-end reachability across the {boundary_label}",
        "missing_runtime_env_var": f"Verify required runtime environment variables and secret injection across the {boundary_label}",
        "tokenizer_runtime_mismatch": f"Verify model, tokenizer, and runtime artifact alignment across the {boundary_label}",
        "model_endpoint_unavailable": f"Verify model-serving endpoint selection and availability across the {boundary_label}",
        "embedding_vector_mismatch": f"Verify embedding shape and vector-store contract alignment across the {boundary_label}",
        "tensor_shape_mismatch": f"Verify tensor shape and feature-dimension alignment across the model input path at the {boundary_label}",
        "cuda_oom": "Measure GPU memory headroom and batch pressure on the failing workload before serving-level tuning",
    }
    if "authorization_header_stripped" in text_features["symptom_names"] and primary_issue_family == "http_routing_misconfiguration":
        return collapse_whitespace(f"Verify Host and Authorization header forwarding across the {boundary_label}")
    if primary_symptom in symptom_first_paths:
        return collapse_whitespace(symptom_first_paths[primary_symptom])
    return collapse_whitespace(_path_title_for_family(primary_issue_family, boundary_label, text_features))


def _build_alternative_paths(
    primary_issue_family: str,
    secondary_families: list[str],
    selected_cluster: str,
    reasoning_bundle: dict[str, Any],
    case_bank: list[dict],
) -> list[str]:
    boundary_name = _strongest_boundary_name(reasoning_bundle)
    boundary_label = BOUNDARY_LABELS.get(boundary_name, _humanize_slug(boundary_name))
    primary_path = _build_primary_path(primary_issue_family, selected_cluster, reasoning_bundle)
    text_features = reasoning_bundle["text_features"]
    candidates = _family_specific_alternative_paths(primary_issue_family, text_features, boundary_label)
    candidates.extend(_ranked_family_path_options(primary_issue_family, secondary_families, reasoning_bundle["text_features"], boundary_label))

    for case in case_bank[:12]:
        if case["issue_family"] == primary_issue_family:
            continue
        candidate = _path_title_for_family(case["issue_family"], case["boundary_label"], reasoning_bundle["text_features"])
        candidates.append(candidate)

    if selected_cluster == "http_proxy_edge":
        candidates.append(f"Confirm edge proxy rewrites do not alter host, origin, or upstream path across the {boundary_label}")
    elif selected_cluster == "container_network_surface":
        candidates.append("Confirm service discovery and network policy remain aligned with the direct service path")
    elif selected_cluster == "model_serving_pipeline":
        if "model_endpoint_unavailable" in text_features["symptom_names"]:
            candidates.append("Confirm serving endpoint health and enablement before artifact-level debugging")
        else:
            candidates.append("Confirm retrieval and serving-branch selection do not diverge before inference completes")
    elif selected_cluster == "gpu_acceleration_stack":
        candidates.append("Confirm batch shape and concurrency do not push workloads onto a degraded accelerator path")

    filtered = []
    primary_signature = _path_signature(primary_path)
    for candidate in candidates:
        normalized_candidate = collapse_whitespace(candidate)
        key = normalize_title_key(normalized_candidate)
        if not key:
            continue
        if _is_low_signal_path_title(normalized_candidate):
            continue
        if _path_is_substep_of_primary(normalized_candidate, primary_path):
            continue
        if _alternative_path_conflicts_with_primary(normalized_candidate, primary_issue_family, text_features):
            continue
        candidate_signature = _path_signature(normalized_candidate)
        if candidate_signature == primary_signature:
            continue
        if any(_path_signature(existing) == candidate_signature for existing in filtered):
            continue
        overlap = len(primary_signature & candidate_signature)
        if primary_signature and overlap / max(1, min(len(primary_signature), len(candidate_signature) or 1)) >= 0.55:
            continue
        filtered.append(normalized_candidate)
        if len(filtered) >= 4:
            break

    if len(filtered) >= 2:
        return filtered[:4]

    for sec_family in secondary_families[:3]:
        title = _path_title_for_family(sec_family, boundary_label, text_features)
        if _is_low_signal_path_title(title):
            continue
        if _path_is_substep_of_primary(title, primary_path):
            continue
        if _alternative_path_conflicts_with_primary(title, primary_issue_family, text_features):
            continue
        if title not in filtered:
            filtered.append(title)
        if len(filtered) >= 2:
            break

    return filtered[:4]


def _aggregate_hypothesis_candidates(
    case_bank: list[dict],
    primary_issue_family: str,
    selected_cluster: str,
    text_features: dict[str, Any],
) -> list[dict]:
    aggregated = {}
    for case in case_bank:
        cause_title = _build_case_specific_cause_title(case, text_features)
        key = "|".join([case["issue_family"], case["scenario"], "|".join(sorted(_cause_signature(cause_title)))])
        entry = aggregated.setdefault(
            key,
            {
                "title": cause_title,
                "score": 0.0,
                "families": set(),
                "boundaries": set(),
                "clusters": set(),
                "tags": set(),
                "representative_case": case,
            },
        )
        entry["score"] += case["score"]
        entry["families"].add(case["issue_family"])
        entry["boundaries"].add(case["boundary"])
        if case["cluster_id"] != "no_cluster_alignment":
            entry["clusters"].add(case["cluster_id"])
        entry["tags"].add(case["tag"])
        if case["score"] > entry["representative_case"]["score"]:
            entry["representative_case"] = case
            entry["title"] = _build_case_specific_cause_title(case, text_features)

        if case["issue_family"] == primary_issue_family:
            entry["score"] += 1.8
        if case["cluster_id"] == selected_cluster:
            entry["score"] += 1.2

    ranked = sorted(
        aggregated.values(),
        key=lambda item: (item["score"], item["title"]),
        reverse=True,
    )
    return ranked


def _build_hypothesis_explanation(candidate: dict, primary_issue_family: str, selected_cluster: str) -> str:
    family_text = _humanize_slug(primary_issue_family)
    boundary_text = _humanize_slug(next(iter(candidate["boundaries"]), "runtime boundary"))
    tag_text = ", ".join(sorted(_humanize_tag(tag) for tag in list(candidate["tags"])[:2]))
    cluster_text = _humanize_slug(selected_cluster) if selected_cluster != "no_cluster_alignment" else "dominant signal cluster"
    return collapse_whitespace(
        f"Trusted signals around {tag_text} align with the {family_text} direction, and the strongest evidence concentrates around the {boundary_text} within the {cluster_text}."
    )


def _strongest_boundary_name(reasoning_bundle: dict[str, Any]) -> str:
    boundary_confidence = reasoning_bundle.get("boundary_confidence", {})
    if boundary_confidence:
        return max(boundary_confidence.items(), key=lambda item: (item[1], item[0]))[0]
    boundary_map = reasoning_bundle.get("boundary_map", {})
    return next(iter(boundary_map), "runtime_boundary")


def _path_signature(path: str) -> set[str]:
    stopwords = {"the", "and", "with", "from", "into", "that", "this", "across", "before", "after", "check", "verify", "trace", "validate", "inspect", "compare", "failing", "path", "request", "runtime", "live"}
    return {token for token in tokenize_keywords(path) if token not in stopwords}


_BOUNDARY_SUFFIX_RE = re.compile(
    r'\s+(?:across|at|around|through)\s+the\s+[\w\s-]+?\s*boundary\s*$',
    re.IGNORECASE,
)


def _strip_boundary_suffix(title: str) -> str:
    """Remove trailing boundary-label phrases so cause titles that differ only
    by boundary label produce the same normalized form for dedup."""
    return _BOUNDARY_SUFFIX_RE.sub('', title).strip()


def _cause_signature(title: str) -> set[str]:
    normalized = _strip_boundary_suffix(title)
    stopwords = {"the", "and", "with", "from", "into", "that", "this", "across", "before", "after", "live", "runtime", "boundary", "path", "request", "service", "failing", "failure"}
    return {token for token in tokenize_keywords(normalized) if token not in stopwords}


def _is_low_signal_path_title(title: str) -> bool:
    normalized = normalize_title_key(title)
    if not normalized:
        return True
    low_signal_markers = {
        "check the environment",
        "verify the path",
        "inspect the system",
        "validate behavior",
        "validate the dominant failure path",
    }
    if normalized in low_signal_markers:
        return True
    if any(fragment in normalized for fragment in ("generic", "general troubleshooting", "dominant failure path")):
        return True

    required_tokens = {
        "auth", "token", "scope", "cookie", "csrf", "cors", "origin", "preflight",
        "proxy", "ingress", "upstream", "route", "dns", "resolver", "resolve", "service", "discovery", "hostname", "nameserver", "tls", "ssl",
        "certificate", "postgresql", "mysql", "redis", "database", "schema", "dsn",
        "secret", "kubernetes", "docker", "model", "serving", "embedding", "vector",
        "api", "url", "baseurl", "localhost", "environment", "variable", "env",
        "gpu", "cuda", "memory", "batch", "latency",
        "tensor", "shape", "dimension",
    }
    return not bool(tokenize_keywords(normalized) & required_tokens)


def _alternative_path_conflicts_with_primary(candidate: str, primary_issue_family: str, text_features: dict[str, Any]) -> bool:
    candidate_tokens = tokenize_keywords(candidate)
    symptom_names = set(text_features["symptom_names"])
    if primary_issue_family == "authorization_policy" and candidate_tokens & {"origin", "cors", "preflight"}:
        return True
    if primary_issue_family == "database_connectivity" and candidate_tokens & {"schema", "migration"} and "schema_contract_failure" not in symptom_names:
        return True
    if primary_issue_family == "database_connectivity" and candidate_tokens & {"pool", "saturation", "worker", "workers"} and "timeout_failure" not in symptom_names:
        return True
    if primary_issue_family == "cors_proxy_boundary" and candidate_tokens & {"session", "cookie", "csrf"} and "csrf_or_cookie_failure" not in symptom_names:
        return True
    if primary_issue_family == "dns_service_discovery" and candidate_tokens & {"proxy", "upstream", "cors"} and "upstream_failure" not in symptom_names:
        return True
    if primary_issue_family == "tls_edge_termination" and candidate_tokens & {"auth", "token", "scope", "role", "cors", "origin"} and not ({"authn_failure", "authz_failure", "preflight_failure"} & symptom_names):
        return True
    if primary_issue_family == "authentication" and candidate_tokens & {"cors", "origin", "preflight"} and not ({"preflight_failure", "missing_cors_headers", "browser_only_failure"} & symptom_names):
        return True
    if primary_issue_family == "http_routing_misconfiguration" and {"api_base_url_mismatch", "authorization_header_stripped"} & symptom_names:
        if candidate_tokens & {"cors", "origin", "preflight", "credentialed", "credentials"} and not ({"preflight_failure", "missing_cors_headers", "browser_only_failure"} & symptom_names):
            return True
    if primary_issue_family == "authorization_policy" and candidate_tokens & {"cookie", "csrf", "session"} and "csrf_or_cookie_failure" not in symptom_names:
        return True
    if primary_issue_family == "retrieval_embeddings_pipeline" and candidate_tokens & {"gpu", "cuda"} and "cuda_oom" not in symptom_names:
        return True
    if primary_issue_family == "gpu_inference_runtime" and candidate_tokens & {"retrieval", "vector", "embedding"} and "embedding_vector_mismatch" not in symptom_names:
        return True
    return False


def _family_fallback_cause_titles(primary_issue_family: str, text_features: dict[str, Any]) -> list[str]:
    symptom_names = text_features["symptom_names"]
    fallback_map = {
        "authentication": [
            "Issuer, audience, expiry, or signature validation is stricter on the failing path than expected",
            "Auth headers, cookies, or forwarded identity metadata are dropped or rewritten before backend validation",
            "Recent deployment changed trusted host, callback, or secret configuration used during token validation",
            "A stale session or cache-backed identity record diverges from the artifact presented on the request",
        ],
        "authorization_policy": [
            "The token is valid, but the role or scope set does not satisfy the protected operation",
            "Claim names or claim values no longer map cleanly into the policy middleware expectations",
            "Policy middleware evaluates a different route, action, or permission context than the caller expects",
            "A cached or stale policy snapshot denies an identity that should now be allowed",
        ],
        "session_identity_boundary": [
            "SameSite, secure, domain, or path cookie settings break session continuity on the live browser flow",
            "CSRF validation rejects the request because trusted-origin or token expectations changed",
            "Proxy or forwarded-header handling changes secure detection or cookie scope on the live path",
            "Browser credential mode no longer matches the backend session mechanism used by the route",
        ],
        "cors_proxy_boundary": [
            "The preflight allowlist omits the method, header, or origin used by the failing browser request",
            "The edge proxy returns different CORS headers than the application intends to return",
            "Credentialed cross-origin requests fail because origin and Access-Control-Allow-Credentials handling is inconsistent",
            "Route-specific CORS handling diverges from the global policy after the proxy or ingress change",
        ],
        "http_routing_misconfiguration": [
            "Upstream target, service port, or host preservation no longer matches the intended backend route",
            "A rewrite, ingress rule, or path mapping sends the failing request to the wrong upstream",
            "Recent deployment changed edge mapping, readiness, or service registration for the affected route",
            "Timeout or retry behavior at the edge hides the real upstream hop that is failing",
        ],
        "database_connectivity": [
            "Migration state or live schema no longer matches the query path used by the failing request",
            "The runtime points to a stale database target, wrong schema, or outdated secret after the recent change",
            "The ORM or query contract no longer matches renamed relations, columns, or expected result shape",
            "Connection pool, network path, or credential drift isolates only the failing data path",
        ],
        "cache_session_store": [
            "Redis or cache-backed state is stale, partially written, or missing on the live path",
            "The application expects session continuity that the current cache topology no longer provides",
            "Recent failover or restart behavior invalidated the state contract used by auth or request handling",
            "One runtime reads different cached identity or feature state than the writer updates",
        ],
        "container_networking": [
            "Service selectors, exposed ports, or network policy changed on the platform path after deployment",
            "Ingress, mesh, or load-balancer behavior differs from direct service-to-service routing",
            "Service discovery or endpoint registration lags behind the current rollout state",
            "Namespace, security-group, or policy boundaries block only the affected traffic path",
        ],
        "dns_service_discovery": [
            "The caller resolves a stale or wrong service name for the failing hop",
            "Search domains, namespace, or resolver policy differ from the expected caller context",
            "Service registration or endpoint publishing lags behind the current deployment state",
            "A downstream proxy or ingress failure is triggered by the initial name-resolution mismatch",
        ],
        "tls_edge_termination": [
            "Certificate trust chain or hostname coverage no longer matches the public edge name",
            "Ingress or proxy terminates TLS with the wrong certificate, SNI route, or trust bundle",
            "Backend and edge now expect different TLS modes or verification behavior on the same path",
            "Recent certificate rotation changed key material, trust roots, or hostname mapping at the edge",
        ],
        "model_serving_runtime": [
            "Model weights, tokenizer assets, or runtime mode are out of sync on the live serving target",
            "Recent deployment changed the endpoint branch, model revision, or mounted artifacts for the failing path",
            "Serving runtime fallback, precision mode, or dependency drift changed startup or inference behavior",
            "Request size or concurrency exposes a serving-mode mismatch that smaller requests do not hit",
        ],
        "retrieval_embeddings_pipeline": [
            "Embedding model and vector index disagree on dimension, normalization, or contract assumptions",
            "The retrieval path queries the wrong collection, namespace, or stale index after the recent change",
            "Chunking, ingestion, or metadata filters no longer match the embeddings stored in the active index",
            "Serving and retrieval stages use different embedding models or vector-store namespaces on the live path",
        ],
        "gpu_inference_runtime": [
            "Batch shape or concurrency now exceeds available GPU memory headroom on the live workload",
            "CUDA, driver, or framework builds are no longer aligned on the serving node",
            "Worker placement or mixed CPU/GPU fallback creates unstable latency and memory pressure",
            "Recent deployment changed precision, context length, or batch defaults enough to trigger OOM",
        ],
    }
    if primary_issue_family == "gpu_inference_runtime" and "tensor_shape_mismatch" in symptom_names:
        titles = [
            "Model input tensor shape does not match the expected dimensions for the first linear layer",
            "Preprocessing or tokenization produces inconsistent tensor shapes across different input batches",
            "NumPy-to-PyTorch conversion introduces a dtype or dimension-order mismatch before the forward pass",
            "Model output head or classifier layer expects a different feature dimension than the encoder provides",
            "Batch dimension or sequence-length padding is inconsistent between training and inference",
        ]
        return titles
    titles = list(fallback_map.get(primary_issue_family, []))
    if primary_issue_family == "database_connectivity":
        if "schema_contract_failure" in symptom_names:
            titles = [
                "The live schema, migration state, or query contract no longer matches the failing request",
                "The runtime points at the intended database host, but the wrong schema or search path is active",
                "A renamed relation, column, or query contract now breaks the failing code path",
                "Migration rollout and deployed code are no longer aligned on the live database target",
            ]
        elif {"config_or_secret_drift", "database_target_change", "runtime_startup_failure"} & symptom_names:
            titles = [
                "The deployed runtime is using the wrong database hostname, secret, or connection target after the recent change",
                "The failing caller resolves the wrong host or cannot resolve the intended internal service name",
                "Service discovery, selectors, or network policy broke the live platform path between the application runtime and the database target",
                "A refused socket or timeout is exposing the first failing hop between the application runtime and the configured database endpoint",
            ]
        else:
            titles = [
                "The runtime points to the wrong database target, host, or credential for the failing path",
                "The database hostname or endpoint resolves differently from the environment the engineers expect",
                "The network path from the deployed runtime to the database target is blocked, misrouted, or filtered",
                "Connection pool pressure or worker starvation is surfacing as an intermittent database-path failure",
            ]
    if primary_issue_family == "http_routing_misconfiguration":
        if "api_base_url_mismatch" in symptom_names:
            titles = [
                "Build-time environment injection left the browser bundle with a stale API target",
                "Missing API_BASE_URL makes the client fall back to localhost or a default development endpoint",
                "The browser request target differs from the backend route, scheme, or host exposed in production",
                "A recent deployment changed endpoint configuration without rebuilding the client artifact",
            ]
        elif "missing_runtime_env_var" in symptom_names:
            titles = [
                "A required runtime environment variable or secret is missing from the failing service process",
                "Startup configuration loading falls back to an empty, stale, or disabled dependency target",
                "The deployed runtime no longer receives the secret values expected by the application startup path",
                "The last deployment changed configuration injection before the service initialized dependencies",
            ]
        elif "authorization_header_stripped" in symptom_names:
            titles = [
                "Host or scheme preservation changes the auth context used by the upstream service",
                "The direct backend path works, but the proxy branch alters protected request metadata",
                "Route rewrite or upstream selection sends authenticated traffic through the wrong validation path",
                "Proxy configuration does not pass the same bearer metadata as the direct backend call",
            ]
    if primary_issue_family == "model_serving_runtime" and "tokenizer_runtime_mismatch" not in symptom_names:
        titles[0] = "Serving endpoint selection or runtime mode no longer matches the model path used by the failing request"
    if primary_issue_family == "model_serving_runtime" and "model_endpoint_unavailable" in symptom_names:
        titles = [
            "The configured model-serving base URL points to a disabled, stale, or unavailable inference endpoint",
            "The live request reaches a serving endpoint that differs from the intended deployment target",
            "A recent deployment changed MODEL_BASE_URL or endpoint routing before inference starts",
            "Serving health or endpoint enablement fails before model execution begins",
        ]
    if primary_issue_family == "model_serving_runtime" and "missing_runtime_env_var" in symptom_names:
        titles = [
            "A required model-serving environment variable or secret is missing from the runtime",
            "Model startup falls back to an empty, stale, or disabled artifact or endpoint target",
            "Deployment configuration injection no longer matches the serving process expectations",
            "The model client initializes before required runtime secrets are available",
        ]
    return titles


def _build_ranked_hypotheses(
    case_bank: list[dict],
    primary_issue_family: str,
    selected_cluster: str,
    text_features: dict[str, Any],
) -> list[dict]:
    aggregated = _aggregate_hypothesis_candidates(case_bank, primary_issue_family, selected_cluster, text_features)

    # Deterministic tensor-shape override: when tensor_shape_mismatch is active,
    # replace aggregated candidates with the four distinct tensor-specific causes.
    # This avoids mutable global state and ensures identical output on every call.
    if "tensor_shape_mismatch" in text_features["symptom_names"] and primary_issue_family in ("gpu_inference_runtime", "model_serving_runtime"):
        tensor_ranked = []
        for idx, title in enumerate(_TENSOR_SHAPE_CAUSE_TITLES):
            confidence = clamp_confidence(0.88 - idx * 0.04)
            tensor_ranked.append(
                {
                    "id": idx + 1,
                    "title": title,
                    "why_likely": _build_hypothesis_explanation(
                        {
                            "boundaries": {"gpu_inference_boundary"},
                            "tags": {case["tag"] for case in case_bank[:4] if case.get("tag")},
                        },
                        primary_issue_family,
                        selected_cluster,
                    ),
                    "confidence": confidence,
                    "families": [primary_issue_family],
                    "boundaries": ["gpu_inference_boundary"],
                    "clusters": [selected_cluster] if selected_cluster != "no_cluster_alignment" else [],
                    "tags": sorted({case["tag"] for case in case_bank[:4] if case.get("tag")}),
                }
            )
        return tensor_ranked
    if not aggregated:
        aggregated = [
            {
                "title": "The dominant runtime path is misaligned with the strongest trusted signals",
                "score": 1.0,
                "families": {primary_issue_family},
                "boundaries": {"runtime_boundary"},
                "clusters": {selected_cluster} if selected_cluster != "no_cluster_alignment" else set(),
                "tags": set(),
                "representative_case": {
                    "issue_family": primary_issue_family,
                    "boundary_label": "runtime configuration boundary",
                    "score": 1.0,
                },
            }
        ]

    # When CORS preflight symptoms dominate, suppress generic auth-metadata
    # boundary variants so CORS-specific causes get priority.
    cors_symptoms = {"preflight_failure", "missing_cors_headers", "browser_only_failure"}
    is_cors_primary = primary_issue_family == "cors_proxy_boundary" and bool(cors_symptoms & set(text_features["symptom_names"]))
    auth_boundary_count = 0

    top_score = max(item["score"] for item in aggregated) or 1.0
    ranked = []
    seen_signatures = []
    for candidate in aggregated:
        if _is_generic_cause_title(candidate["title"], primary_issue_family, text_features):
            continue
        # In CORS-primary cases, allow at most one auth-metadata boundary cause.
        if is_cors_primary and "authentication" in candidate.get("families", set()):
            if auth_boundary_count >= 1:
                continue
            auth_boundary_count += 1
        candidate_signature = _cause_signature(candidate["title"])
        if any(candidate_signature == signature or (candidate_signature and signature and len(candidate_signature & signature) / max(1, min(len(candidate_signature), len(signature))) >= 0.65) for signature in seen_signatures):
            continue
        relative = candidate["score"] / top_score
        confidence = clamp_confidence(0.38 + relative * 0.5 + min(candidate["score"], 14.0) * 0.01)
        ranked.append(
            {
                "id": len(ranked) + 1,
                "title": collapse_whitespace(candidate["title"]),
                "why_likely": _build_hypothesis_explanation(candidate, primary_issue_family, selected_cluster),
                "confidence": confidence,
                "families": sorted(candidate["families"]),
                "boundaries": sorted(candidate["boundaries"]),
                "clusters": sorted(candidate["clusters"]),
                "tags": sorted(candidate["tags"]),
            }
        )
        seen_signatures.append(candidate_signature)
        if len(ranked) >= 6:
            break

    if len(ranked) < 4:
        fallback_titles = [
            _build_case_specific_cause_title(case, text_features)
            for case in case_bank
            if case["issue_family"] == primary_issue_family or case["cluster_id"] == selected_cluster
        ]
        fallback_titles.extend(_family_fallback_cause_titles(primary_issue_family, text_features))
        for title in fallback_titles:
            normalized_title = collapse_whitespace(title)
            if not normalized_title:
                continue
            if _is_generic_cause_title(normalized_title, primary_issue_family, text_features):
                continue
            candidate_signature = _cause_signature(normalized_title)
            if any(candidate_signature == signature for signature in seen_signatures):
                continue
            ranked.append(
                {
                    "id": len(ranked) + 1,
                    "title": normalized_title,
                    "why_likely": _build_hypothesis_explanation(
                        {
                            "boundaries": {"runtime_boundary"},
                            "tags": set(),
                        },
                        primary_issue_family,
                        selected_cluster,
                    ),
                    "confidence": clamp_confidence(0.42 - len(ranked) * 0.02),
                    "families": [primary_issue_family],
                    "boundaries": ["runtime_boundary"],
                    "clusters": [selected_cluster] if selected_cluster != "no_cluster_alignment" else [],
                    "tags": [],
                }
            )
            seen_signatures.append(candidate_signature)
            if len(ranked) >= 4:
                break
    return ranked


def _is_generic_cause_title(title: str, primary_issue_family: str, text_features: dict[str, Any]) -> bool:
    normalized = normalize_title_key(title)
    symptom_names = set(text_features["symptom_names"])
    generic_markers = {
        "check the environment",
        "verify the path",
        "inspect the system",
        "validate behavior",
        "validate the dominant failure path",
        "dominant runtime path is misaligned with the strongest trusted signals",
        "secondary dependency path fails before the primary service logic",
        "adjacent boundary is masking the dominant failure mode",
    }
    if normalized in generic_markers:
        return True
    if any(fragment in normalized for fragment in ("generic", "general troubleshooting")):
        return True

    # Reject boundary-only titles that contain no stack-specific terminology.
    stack_specific_tokens = {
        "jwt", "oauth", "cors", "preflight", "origin", "cookie", "csrf", "samesite",
        "nginx", "apache", "proxy", "ingress", "dns", "tls", "ssl", "certificate",
        "postgresql", "mysql", "redis", "database", "schema", "migration", "query",
        "django", "fastapi", "flask", "react", "kubernetes", "docker",
        "cuda", "gpu", "vram", "pytorch", "tensorflow", "tokenizer", "embedding",
        "vector", "retrieval", "rag", "model", "serving", "checkpoint",
        "hostname", "secret", "dsn", "connection", "startup", "initialization",
        "scope", "role", "permission", "claim", "bearer", "token",
        "upstream", "gateway", "502", "503", "504", "401", "403",
        "resolver", "resolve", "search", "forwarding", "registration", "endpoint", "service", "discovery",
        "ttl", "nameserver", "namespace", "selector", "sni", "cipher",
        "chain", "trust", "handshake", "oom", "memory", "batch", "precision",
        "stale", "pool", "credential", "issuer", "audience", "expiry", "allowlist", "hostname",
        "api", "url", "baseurl", "localhost", "environment", "variable", "env",
        "tensor", "shape", "dimension", "linear", "layer", "dtype", "preprocessing", "input", "output", "head", "classifier",
    }
    title_tokens = tokenize_keywords(normalized)
    if not (title_tokens & stack_specific_tokens):
        return True

    if primary_issue_family == "database_connectivity" and "schema" in normalized and "schema_contract_failure" not in symptom_names:
        return True
    if primary_issue_family == "authorization_policy" and any(token in normalized for token in ("cors", "origin", "preflight")):
        return True
    if primary_issue_family == "cors_proxy_boundary" and any(token in normalized for token in ("session", "csrf")) and "csrf_or_cookie_failure" not in symptom_names:
        return True
    if primary_issue_family == "dns_service_discovery" and any(token in normalized for token in ("proxy", "upstream", "cors")) and "upstream_failure" not in symptom_names:
        return True
    if primary_issue_family == "tls_edge_termination" and any(token in normalized for token in ("dns", "cors", "session")) and "dns_failure" not in symptom_names:
        return True
    if primary_issue_family == "retrieval_embeddings_pipeline" and any(token in normalized for token in ("cuda", "gpu", "vram")) and "cuda_oom" not in symptom_names:
        return True
    if primary_issue_family == "gpu_inference_runtime" and any(token in normalized for token in ("retrieval", "vector", "embedding")) and "embedding_vector_mismatch" not in symptom_names:
        return True
    return False


def validate_root_cause_output(data: dict) -> dict:
    case_summary = data.get("case_summary", {})
    domain = str(case_summary.get("domain", "")).strip().lower()
    if domain not in VALID_DOMAINS:
        raise ValueError("Stage 2 response has an invalid domain.")

    compatibility_issue_family = normalize_issue_family(case_summary.get("issue_family", ""))
    primary_issue_family = normalize_issue_family(case_summary.get("primary_issue_family", compatibility_issue_family))
    selected_reasoning_cluster = case_summary.get("selected_reasoning_cluster", data.get("selected_reasoning_cluster", "no_cluster_alignment"))
    tag_signals = normalize_tag_signals(case_summary.get("tag_signals", []) or case_summary.get("top_tags", []))
    normalized_top_tags = [item["tag"] for item in tag_signals]

    hypotheses = []
    seen_titles = set()
    for item in data.get("root_cause_hypotheses", []):
        if not isinstance(item, dict):
            continue
        title = collapse_whitespace(item.get("title", ""))
        why_likely = collapse_whitespace(item.get("why_likely", ""))
        if not title or not why_likely:
            continue
        title_key = normalize_title_key(title)
        if title_key in seen_titles:
            continue
        hypotheses.append(
            {
                "id": len(hypotheses) + 1,
                "title": title,
                "why_likely": why_likely,
                "confidence": clamp_confidence(item.get("confidence", 0.0)),
            }
        )
        seen_titles.add(title_key)

    hypotheses.sort(key=lambda item: item["confidence"], reverse=True)
    if len(hypotheses) < 4:
        raise ValueError("Stage 2 response produced fewer than 4 usable hypotheses.")

    hypotheses = hypotheses[:6]
    possible_causes = _top_unique([item["title"] for item in hypotheses], 6)
    if len(possible_causes) < 4:
        raise ValueError("Stage 2 response produced fewer than 4 usable possible causes.")

    alternative_paths = _top_unique([str(path).strip() for path in data.get("alternative_paths", []) if str(path).strip()], 4)
    if len(alternative_paths) < 2:
        raise ValueError("Stage 2 response produced fewer than 2 usable alternative paths.")

    primary_path = collapse_whitespace(data.get("primary_path", ""))
    if not primary_path:
        raise ValueError("Stage 2 response is missing a usable primary_path.")

    return {
        "case_summary": {
            "domain": domain,
            "issue_family": compatibility_issue_family,
            "primary_issue_family": primary_issue_family,
            "top_tags": normalized_top_tags,
            "tag_signals": tag_signals,
            "trusted_tags": list(case_summary.get("trusted_tags", [])),
            "supporting_tags": list(case_summary.get("supporting_tags", [])),
            "weak_tags": list(case_summary.get("weak_tags", [])),
            "selected_reasoning_cluster": selected_reasoning_cluster,
            "boundary_hints": case_summary.get("boundary_hints", []),
            "boundary_confidence": case_summary.get("boundary_confidence", {}),
            "symptom_evidence": case_summary.get("symptom_evidence", {}),
            "deployment_change_cues": case_summary.get("deployment_change_cues", []),
        },
        "primary_path": primary_path,
        "alternative_paths": alternative_paths,
        "possible_causes": possible_causes[:6],
        "primary_issue_family": primary_issue_family,
        "selected_reasoning_cluster": selected_reasoning_cluster,
        "ranked_hypotheses": data.get("ranked_hypotheses", hypotheses),
        "root_cause_hypotheses": hypotheses,
        "top_signal_tags": tag_signals,
        "reasoning_trace_internal": data.get("reasoning_trace_internal", {}),
        "reasoning_summary": collapse_whitespace(data.get("reasoning_summary", "")),
    }


__all__ = [
    "_build_case_bank",
    "_build_reasoning_cases_for_tag",
    "_case_score",
    "_aggregate_hypothesis_candidates",
    "_build_ranked_hypotheses",
    "_build_primary_path",
    "_build_alternative_paths",
    "_build_case_specific_cause_title",
    "_path_signature",
    "_cause_signature",
    "_is_low_signal_path_title",
    "validate_root_cause_output",
    "_build_tag_profile",
    "_cluster_candidates_for_tag",
    "_symptom_modes_for_profile",
    "_scenario_is_plausible",
    "_humanize_slug",
    "_family_score",
    "_boundary_score",
    "_build_hypothesis_explanation",
    "_family_fallback_cause_titles",
    "_is_generic_cause_title",
    "_strongest_boundary_name",
    "_family_specific_alternative_paths",
    "_ranked_family_path_options",
    "_path_title_for_family",
    "_path_is_substep_of_primary",
    "_alternative_path_conflicts_with_primary",
    "_top_unique",
    "_humanize_tag",
    "_tag_categories",
]
