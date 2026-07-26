from typing import Any

from app.repositories.registries import CLUSTER_REGISTRY, ISSUE_FAMILY_REGISTRY
from app.repositories.symptoms import ISSUE_FAMILY_SYMPTOM_HINTS


def _looks_like_software_database_runtime_case(active_domain: str, text_features: dict[str, Any], tag_items: list[dict] | None = None, boundary_confidence: dict[str, float] | None = None) -> bool:
    if active_domain != "sw":
        return False
    tokens = set(text_features.get("tokens", set()))
    symptom_names = set(text_features.get("symptom_names", set()))
    trusted_or_supported_tags = {
        item["tag"]
        for item in (tag_items or [])
        if item.get("routing_allowed", True) and item.get("confidence_tier") in {"trusted", "supporting"}
    }
    db_stack_tags = {"django", "fastapi", "flask", "python", "postgresql", "mysql", "sql", "redis"}
    db_text_cues = {"django", "postgresql", "mysql", "database", "startup", "initialization", "initialisation", "hostname", "secret", "secrets", "manager", "environment", "production", "locally"}
    has_stack = bool(trusted_or_supported_tags & db_stack_tags) or len(tokens & db_text_cues) >= 2
    has_boundary = bool((boundary_confidence or {}).get("database_boundary", 0.0) >= 0.28 or (boundary_confidence or {}).get("runtime_boundary", 0.0) >= 0.22)
    has_signal = bool({"connection_refused", "dns_failure", "runtime_startup_failure", "config_or_secret_drift", "database_target_change", "production_only_regression"} & symptom_names)
    return has_stack and has_boundary and has_signal


def _family_constraints_for_symptoms(active_domain: str, text_features: dict[str, Any]) -> set[str]:
    all_families = {
        family_name
        for family_name, family_rule in ISSUE_FAMILY_REGISTRY.items()
        if active_domain in family_rule["domains"]
    }
    symptom_names = set(text_features["symptom_names"])
    tokens = set(text_features.get("tokens", set()))
    constraint_sets = []

    if {"preflight_failure", "missing_cors_headers"} & symptom_names:
        allowed = {"cors_proxy_boundary"}
        if "csrf_or_cookie_failure" in symptom_names or "browser_only_failure" in symptom_names:
            allowed.add("session_identity_boundary")
        constraint_sets.append(allowed)
    if "authz_failure" in symptom_names:
        allowed = {"authorization_policy"}
        if "authn_failure" in symptom_names:
            allowed.add("authentication")
        if "csrf_or_cookie_failure" in symptom_names:
            allowed.add("session_identity_boundary")
        constraint_sets.append(allowed)
    if "authn_failure" in symptom_names and "authz_failure" not in symptom_names:
        allowed = {"authentication"}
        if "csrf_or_cookie_failure" in symptom_names or "browser_only_failure" in symptom_names:
            allowed.add("session_identity_boundary")
        constraint_sets.append(allowed)
    if "csrf_or_cookie_failure" in symptom_names and not {"authn_failure", "authz_failure"} & symptom_names:
        constraint_sets.append({"session_identity_boundary", "authentication", "cors_proxy_boundary"})
    if "dns_failure" in symptom_names:
        allowed = {"dns_service_discovery", "container_networking"}
        if active_domain == "sw" and tokens & {"django", "postgresql", "mysql", "database", "startup", "initialization", "initialisation", "secret", "hostname"}:
            allowed.add("database_connectivity")
        if "upstream_failure" in symptom_names:
            allowed.add("http_routing_misconfiguration")
        constraint_sets.append(allowed)
    if "tls_failure" in symptom_names:
        allowed = {"tls_edge_termination"}
        if "upstream_failure" in symptom_names:
            allowed.add("http_routing_misconfiguration")
        constraint_sets.append(allowed)
    if "schema_contract_failure" in symptom_names:
        allowed = {"database_connectivity"}
        if "embedding_vector_mismatch" in symptom_names:
            allowed.add("retrieval_embeddings_pipeline")
        constraint_sets.append(allowed)
    if "embedding_vector_mismatch" in symptom_names:
        constraint_sets.append({"retrieval_embeddings_pipeline", "database_connectivity", "model_serving_runtime"})
    if "tokenizer_runtime_mismatch" in symptom_names:
        constraint_sets.append({"model_serving_runtime", "gpu_inference_runtime"})
    if "cuda_oom" in symptom_names:
        constraint_sets.append({"gpu_inference_runtime", "model_serving_runtime"})
    if "tensor_shape_mismatch" in symptom_names:
        constraint_sets.append({"gpu_inference_runtime", "model_serving_runtime"})
    if "upstream_failure" in symptom_names and not {"dns_failure", "tls_failure"} & symptom_names:
        constraint_sets.append({"http_routing_misconfiguration", "container_networking", "cors_proxy_boundary"})
    if active_domain == "sw" and ({"runtime_startup_failure", "config_or_secret_drift", "database_target_change", "production_only_regression"} & symptom_names):
        constraint_sets.append({"database_connectivity"})

    if not constraint_sets:
        return all_families

    allowed_families = set().union(*constraint_sets)
    return allowed_families & all_families if allowed_families else all_families


def _has_browser_state_symptom(symptom_names: set[str]) -> bool:
    return bool({"browser_only_failure", "csrf_or_cookie_failure", "preflight_failure", "missing_cors_headers"} & set(symptom_names))


def _symptom_seed_for_family(family_name: str, text_features: dict[str, Any]) -> float:
    primary_symptom = text_features.get("primary_symptom", "")
    symptom_names = set(text_features["symptom_names"])
    score = 0.0
    primary_bonus = {
        "preflight_failure": {"cors_proxy_boundary": 24.0},
        "missing_cors_headers": {"cors_proxy_boundary": 23.0, "session_identity_boundary": 5.0},
        "browser_only_failure": {"cors_proxy_boundary": 12.0, "session_identity_boundary": 10.0},
        "csrf_or_cookie_failure": {"session_identity_boundary": 22.0, "authentication": 6.0},
        "authn_failure": {"authentication": 22.0, "session_identity_boundary": 5.0},
        "authz_failure": {"authorization_policy": 24.0, "authentication": 3.0},
        "upstream_failure": {"http_routing_misconfiguration": 18.0, "container_networking": 7.0},
        "connection_refused": {"database_connectivity": 10.0, "dns_service_discovery": 10.0, "container_networking": 6.0},
        "timeout_failure": {"http_routing_misconfiguration": 10.0, "container_networking": 8.0, "model_serving_runtime": 7.0, "gpu_inference_runtime": 7.0},
        "tls_failure": {"tls_edge_termination": 24.0},
        "dns_failure": {"dns_service_discovery": 24.0, "container_networking": 8.0},
        "schema_contract_failure": {"database_connectivity": 22.0, "retrieval_embeddings_pipeline": 8.0},
        "runtime_startup_failure": {"database_connectivity": 20.0},
        "config_or_secret_drift": {"database_connectivity": 18.0, "model_serving_runtime": 9.0},
        "database_target_change": {"database_connectivity": 21.0},
        "production_only_regression": {"database_connectivity": 8.0, "http_routing_misconfiguration": 4.0},
        "tokenizer_runtime_mismatch": {"model_serving_runtime": 24.0},
        "embedding_vector_mismatch": {"retrieval_embeddings_pipeline": 25.0, "database_connectivity": 5.0},
        "cuda_oom": {"gpu_inference_runtime": 25.0, "model_serving_runtime": 6.0},
        "tensor_shape_mismatch": {"gpu_inference_runtime": 22.0, "model_serving_runtime": 18.0},
        "deployment_change": {"http_routing_misconfiguration": 6.0, "container_networking": 6.0, "model_serving_runtime": 6.0},
    }
    score += primary_bonus.get(primary_symptom, {}).get(family_name, 0.0)

    if family_name == "authorization_policy" and "authz_failure" in symptom_names:
        score += 9.0
    if family_name == "authentication" and "authn_failure" in symptom_names:
        score += 8.0
    if family_name == "session_identity_boundary" and _has_browser_state_symptom(symptom_names):
        score += 8.0
    if family_name == "cors_proxy_boundary" and {"preflight_failure", "missing_cors_headers"} & symptom_names:
        score += 8.0
    if family_name == "http_routing_misconfiguration" and "upstream_failure" in symptom_names:
        score += 7.0
    if family_name == "dns_service_discovery" and "dns_failure" in symptom_names:
        score += 8.0
    if family_name == "tls_edge_termination" and "tls_failure" in symptom_names:
        score += 8.0
    if family_name == "database_connectivity" and "schema_contract_failure" in symptom_names:
        score += 7.0
    if family_name == "database_connectivity" and {"runtime_startup_failure", "config_or_secret_drift", "database_target_change"} & symptom_names:
        score += 10.0
    if family_name == "retrieval_embeddings_pipeline" and "embedding_vector_mismatch" in symptom_names:
        score += 8.0
    if family_name == "model_serving_runtime" and "tokenizer_runtime_mismatch" in symptom_names:
        score += 8.0
    if family_name == "gpu_inference_runtime" and "cuda_oom" in symptom_names:
        score += 8.0
    if family_name == "gpu_inference_runtime" and "tensor_shape_mismatch" in symptom_names:
        score += 8.0
    if family_name == "model_serving_runtime" and "tensor_shape_mismatch" in symptom_names:
        score += 6.0

    return score


def _family_from_symptoms(
    primary_issue_family: str,
    text_features: dict[str, Any],
    *,
    prefer_database_runtime: bool = False,
) -> str:
    symptom_names = text_features["symptom_names"]
    if prefer_database_runtime and {"dns_failure", "connection_refused", "runtime_startup_failure", "config_or_secret_drift", "database_target_change"} & symptom_names and not {"authz_failure", "authn_failure"} & symptom_names:
        return "database_connectivity"
    if {"preflight_failure", "missing_cors_headers"} & symptom_names:
        return "cors_proxy_boundary"
    if "csrf_or_cookie_failure" in symptom_names and not {"authn_failure", "authz_failure"} & symptom_names:
        return "session_identity_boundary"
    if "authz_failure" in symptom_names:
        return "authorization_policy"
    if "authn_failure" in symptom_names:
        return "authentication"
    if "tls_failure" in symptom_names:
        return "tls_edge_termination"
    if "dns_failure" in symptom_names:
        return "dns_service_discovery"
    if "embedding_vector_mismatch" in symptom_names:
        return "retrieval_embeddings_pipeline"
    if "cuda_oom" in symptom_names:
        return "gpu_inference_runtime"
    if "schema_contract_failure" in symptom_names:
        return "database_connectivity"
    if "tokenizer_runtime_mismatch" in symptom_names:
        return "model_serving_runtime"
    if "tensor_shape_mismatch" in symptom_names:
        return "gpu_inference_runtime"
    if "upstream_failure" in symptom_names:
        return "http_routing_misconfiguration"
    return primary_issue_family


def _resolve_primary_issue_family(reasoning_bundle: dict[str, Any], case_bank: list[dict]) -> tuple[str, list[str], dict[str, float]]:
    family_scores = {}
    family_map = reasoning_bundle["family_map"]
    text_features = reasoning_bundle["text_features"]
    selected_cluster = reasoning_bundle["selected_cluster"]
    symptom_names = text_features["symptom_names"]
    allowed_families = _family_constraints_for_symptoms(reasoning_bundle["active_domain"], text_features)
    boundary_confidence = reasoning_bundle.get("boundary_confidence", {})
    prefer_database_runtime = _looks_like_software_database_runtime_case(
        reasoning_bundle["active_domain"],
        text_features,
        reasoning_bundle.get("tag_items", []),
        boundary_confidence,
    )

    for family_name, family_candidate in family_map.items():
        score = _symptom_seed_for_family(family_name, text_features)
        score += float(family_candidate.get("score", 0.0))
        score += float(family_candidate.get("confidence", 0.0)) * 8.0
        score += sum(boundary_confidence.get(boundary_name, 0.0) * 6.0 for boundary_name in family_candidate.get("boundary_hints", []))
        for symptom_name in ISSUE_FAMILY_SYMPTOM_HINTS.get(family_name, set()):
            score += float(text_features["symptom_score_map"].get(symptom_name, 0.0)) * 7.6
        if family_name not in allowed_families:
            score -= 16.0
        family_scores[family_name] = score

    for case in case_bank:
        case_weight = 1.0 if case["issue_family"] in allowed_families else 0.22
        family_scores[case["issue_family"]] = family_scores.get(case["issue_family"], 0.0) + case["score"] * case_weight

    if selected_cluster and selected_cluster in CLUSTER_REGISTRY:
        for family_name, bias in CLUSTER_REGISTRY[selected_cluster]["issue_families"].items():
            cluster_weight = 1.0 if family_name in allowed_families else 0.28
            family_scores[family_name] = family_scores.get(family_name, 0.0) + bias * 12.0 * cluster_weight

    if "auth" in text_features["symptom_bucket_scores"]:
        family_scores["authentication"] = family_scores.get("authentication", 0.0) + 4.0
        family_scores["authorization_policy"] = family_scores.get("authorization_policy", 0.0) + 2.5
    if "authz_failure" in symptom_names:
        family_scores["authorization_policy"] = family_scores.get("authorization_policy", 0.0) + 8.0
        family_scores["authentication"] = family_scores.get("authentication", 0.0) - 2.6
    if "authn_failure" in symptom_names:
        family_scores["authentication"] = family_scores.get("authentication", 0.0) + 8.0
    if "timeout" in text_features["symptom_bucket_scores"]:
        family_scores["http_routing_misconfiguration"] = family_scores.get("http_routing_misconfiguration", 0.0) + 2.5
        family_scores["gpu_inference_runtime"] = family_scores.get("gpu_inference_runtime", 0.0) + 2.0
        family_scores["model_serving_runtime"] = family_scores.get("model_serving_runtime", 0.0) + 2.0
    if "preflight_failure" in symptom_names or "missing_cors_headers" in symptom_names:
        family_scores["cors_proxy_boundary"] = family_scores.get("cors_proxy_boundary", 0.0) + 10.0
        family_scores["session_identity_boundary"] = family_scores.get("session_identity_boundary", 0.0) + 2.0
        family_scores["authentication"] = family_scores.get("authentication", 0.0) - 1.2
    if "connectivity" in text_features["symptom_bucket_scores"]:
        family_scores["dns_service_discovery"] = family_scores.get("dns_service_discovery", 0.0) + 3.0
        family_scores["container_networking"] = family_scores.get("container_networking", 0.0) + 2.0
    if "dns_failure" in symptom_names:
        family_scores["dns_service_discovery"] = family_scores.get("dns_service_discovery", 0.0) + 8.0
    if "schema_contract_failure" in symptom_names:
        family_scores["database_connectivity"] = family_scores.get("database_connectivity", 0.0) + 8.0
        family_scores["retrieval_embeddings_pipeline"] = family_scores.get("retrieval_embeddings_pipeline", 0.0) - 2.0
    if "tls" in text_features["symptom_bucket_scores"]:
        family_scores["tls_edge_termination"] = family_scores.get("tls_edge_termination", 0.0) + 3.5
    if "tls_failure" in symptom_names:
        family_scores["tls_edge_termination"] = family_scores.get("tls_edge_termination", 0.0) + 8.0
    if "embedding_vector_mismatch" in symptom_names:
        family_scores["retrieval_embeddings_pipeline"] = family_scores.get("retrieval_embeddings_pipeline", 0.0) + 10.0
        family_scores["database_connectivity"] = family_scores.get("database_connectivity", 0.0) - 2.6
        family_scores["gpu_inference_runtime"] = family_scores.get("gpu_inference_runtime", 0.0) - 1.6
    if "cuda_oom" in symptom_names:
        family_scores["gpu_inference_runtime"] = family_scores.get("gpu_inference_runtime", 0.0) + 10.0
        family_scores["model_serving_runtime"] = family_scores.get("model_serving_runtime", 0.0) + 1.5
    if "tokenizer_runtime_mismatch" in symptom_names:
        family_scores["model_serving_runtime"] = family_scores.get("model_serving_runtime", 0.0) + 9.0
    if "tensor_shape_mismatch" in symptom_names:
        family_scores["gpu_inference_runtime"] = family_scores.get("gpu_inference_runtime", 0.0) + 10.0
        family_scores["model_serving_runtime"] = family_scores.get("model_serving_runtime", 0.0) + 6.0
        family_scores["retrieval_embeddings_pipeline"] = family_scores.get("retrieval_embeddings_pipeline", 0.0) - 8.0
        family_scores["database_connectivity"] = family_scores.get("database_connectivity", 0.0) - 4.0
    if text_features["has_deployment_change"]:
        for family_name in ("container_networking", "model_serving_runtime", "http_routing_misconfiguration", "authentication"):
            family_scores[family_name] = family_scores.get(family_name, 0.0) + 1.5
    if prefer_database_runtime:
        family_scores["database_connectivity"] = family_scores.get("database_connectivity", 0.0) + 18.0
        family_scores["dns_service_discovery"] = family_scores.get("dns_service_discovery", 0.0) - 10.0
        family_scores["container_networking"] = family_scores.get("container_networking", 0.0) - 7.0
        family_scores["http_routing_misconfiguration"] = family_scores.get("http_routing_misconfiguration", 0.0) - 4.0

    for family_name in list(family_scores):
        if family_name not in allowed_families:
            family_scores[family_name] -= 8.0

    ranked_families = sorted(
        family_scores.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )

    if not ranked_families:
        fallback_family = "authentication" if reasoning_bundle["active_domain"] == "sw" else "dns_service_discovery" if reasoning_bundle["active_domain"] == "cn" else "model_serving_runtime"
        return fallback_family, [], {fallback_family: 1.0}

    primary_family = _family_from_symptoms(
        ranked_families[0][0],
        text_features,
        prefer_database_runtime=prefer_database_runtime,
    )
    if primary_family not in allowed_families and ranked_families:
        for family_name, _score in ranked_families:
            if family_name in allowed_families:
                primary_family = family_name
                break
    secondary_families = [family for family, _ in ranked_families[1:6] if family in allowed_families and family != primary_family]
    return primary_family, secondary_families, dict(ranked_families)


def _select_reasoning_cluster(reasoning_bundle: dict[str, Any], case_bank: list[dict], primary_issue_family: str) -> str:
    cluster_map = reasoning_bundle["cluster_map"]
    if not cluster_map:
        return "no_cluster_alignment"

    cluster_scores = {}
    primary_symptom = reasoning_bundle["text_features"].get("primary_symptom", "")
    for cluster_id, cluster in cluster_map.items():
        cluster_scores[cluster_id] = float(cluster.get("confidence", 0.0)) * 8.0
        if primary_issue_family in cluster.get("issue_family_bias", {}):
            cluster_scores[cluster_id] += float(cluster["issue_family_bias"][primary_issue_family]) * 8.0
        if primary_symptom and primary_symptom in set(cluster.get("matched_symptoms", [])):
            cluster_scores[cluster_id] += 9.0
        cluster_scores[cluster_id] += sum(
            reasoning_bundle.get("boundary_confidence", {}).get(boundary_name, 0.0) * 5.0
            for boundary_name in cluster.get("boundary_hints", [])
        )

    for case in case_bank:
        if case["cluster_id"] == "no_cluster_alignment":
            continue
        cluster_scores[case["cluster_id"]] = cluster_scores.get(case["cluster_id"], 0.0) + case["score"] * 0.78

    ranked_clusters = sorted(cluster_scores.items(), key=lambda item: (item[1], item[0]), reverse=True)
    return ranked_clusters[0][0] if ranked_clusters else "no_cluster_alignment"


__all__ = [
    "_family_constraints_for_symptoms",
    "_family_from_symptoms",
    "_resolve_primary_issue_family",
    "_select_reasoning_cluster",
    "_looks_like_software_database_runtime_case",
    "_has_browser_state_symptom",
    "_symptom_seed_for_family",
]
