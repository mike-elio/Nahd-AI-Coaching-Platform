from typing import Any

from app.repositories.scenarios import ISSUE_FAMILY_COMPATIBILITY_MAP, ROOT_CAUSE_STACK_GROUPS
from app.repositories.tags import TAG_DOMAIN_MEMBERSHIP as SUPPORTED_TAGS_BY_DOMAIN
from app.rules.family_resolution import _resolve_primary_issue_family, _select_reasoning_cluster
from app.rules.hypothesis_ranking import (
    _build_alternative_paths,
    _build_case_bank,
    _build_primary_path,
    _build_ranked_hypotheses,
    _humanize_slug,
    _top_unique,
    validate_root_cause_output,
)
from app.rules.symptom_extraction import extract_symptom_evidence
from app.rules.tag_interpretation import interpret_prediction_output
from app.rules.text_processing import clamp_confidence, collapse_whitespace, normalize_domain_label, to_reasoning_domain


SYMPTOM_BUCKETS = {
    "auth": {"401", "403", "auth", "token", "jwt", "oauth", "session", "login", "forbidden", "unauthorized"},
    "boundary": {"cors", "origin", "preflight", "cookie", "header", "forwarded", "proxy", "ingress", "browser", "baseurl", "api_base_url"},
    "timeout": {"408", "504", "timeout", "timed", "latency", "slow", "deadline", "stuck", "hang"},
    "connectivity": {"dns", "resolve", "resolver", "host", "hostname", "route", "routing", "network", "connection", "refused", "unreachable"},
    "availability": {"502", "503", "restart", "crashloop", "unavailable", "health", "readiness", "down", "upstream"},
    "data": {"database", "redis", "sql", "schema", "query", "migration", "vector", "index", "cache"},
    "config": {"config", "env", "environment", "secret", "setting", "version", "dependency", "import", "module", "keyerror", "baseurl", "api_base_url"},
    "tls": {"tls", "ssl", "certificate", "handshake", "sni", "ca", "trust", "https"},
    "ai_runtime": {"model", "checkpoint", "tokenizer", "weights", "inference", "embedding", "rag", "cuda", "gpu", "memory", "vram", "precision", "tensor", "shape", "model_base_url"},
    "deployment": {"deploy", "deployment", "upgrade", "release", "rollback", "changed", "restart", "migration"},
}

FAILURE_PHRASES = {
    "access denied",
    "certificate verify failed",
    "connection refused",
    "connection reset",
    "context deadline exceeded",
    "cors policy",
    "cross origin",
    "cuda error",
    "cuda out of memory",
    "dependency conflict",
    "disabled inference endpoint",
    "dns lookup failed",
    "failed to connect",
    "handshake failure",
    "host not found",
    "missing environment variable",
    "invalid audience",
    "invalid issuer",
    "invalid signature",
    "model not found",
    "model runtime unavailable",
    "net::err_connection_refused",
    "no route to host",
    "permission denied",
    "rate limit",
    "read timeout",
    "relation does not exist",
    "service unavailable",
    "shapes cannot be multiplied",
    "size mismatch",
    "temporary failure in name resolution",
    "tensor shape",
    "token expired",
    "upstream prematurely closed connection",
    "upstream timed out",
}

GENERIC_PATH_MARKERS = {
    "runtime configuration boundary",
    "browser-to-backend boundary",
    "network transport boundary",
    "platform path",
    "metadata",
    "dominant failure path",
}

FAMILY_CLUSTER_BY_EVIDENCE = {
    "cache_session_store": "database_connectivity_stack",
    "tls_edge_termination": "tls_dns_transport",
    "http_routing_misconfiguration": "http_proxy_edge",
    "database_connectivity": "database_connectivity_stack",
    "model_serving_runtime": "model_serving_pipeline",
    "authorization_policy": "auth_identity_flow",
    "authentication": "auth_identity_flow",
}


def _marker_hits(text: str, tokens: set[str], markers: set[str]) -> list[str]:
    hits = []
    for marker in markers:
        normalized = collapse_whitespace(marker).lower()
        tokenized_marker = normalized.replace("_", " ").replace("-", " ")
        if not normalized:
            continue
        if normalized in tokens or normalized in text or tokenized_marker in text:
            hits.append(marker)
    return sorted(set(hits))


def _tag_set(tag_items: list[dict], *, require_support: bool = False) -> set[str]:
    if not require_support:
        return {item.get("tag", "") for item in tag_items if item.get("tag")}
    return {
        item.get("tag", "")
        for item in tag_items
        if item.get("tag") and item.get("confidence_tier") in {"trusted", "supporting"}
    }


def _build_evidence_profile(text_features: dict[str, Any], tag_items: list[dict], boundary_hints: list[dict]) -> dict[str, Any]:
    text = text_features["text"]
    tokens = set(text_features["tokens"])
    tags = _tag_set(tag_items)
    supported_tags = _tag_set(tag_items, require_support=True)
    symptom_names = set(text_features.get("symptom_names", set()))
    boundary_names = {item.get("name", "") for item in boundary_hints if isinstance(item, dict)}

    cookie_hits = _marker_hits(
        text,
        tokens,
        {
            "cookie",
            "cookies",
            "samesite",
            "same-site",
            "csrf",
            "session cookie",
            "credentials",
            "withcredentials",
            "set-cookie",
            "browser session",
            "login-session",
        },
    )
    cors_hits = _marker_hits(
        text,
        tokens,
        {
            "cors",
            "preflight",
            "options",
            "origin",
            "access-control-allow",
            "access-control",
            "browser blocked",
            "blocked by cors",
            "cross-origin",
            "cross origin",
        },
    )
    proxy_hits = _marker_hits(
        text,
        tokens,
        {
            "proxy",
            "reverse proxy",
            "reverse-proxy",
            "nginx",
            "ingress",
            "gateway",
            "load balancer",
            "load-balancer",
            "lb",
            "edge",
        },
    )
    tls_hits = _marker_hits(
        text,
        tokens,
        {
            "tls",
            "ssl",
            "certificate",
            "cert",
            "chain",
            "hostname",
            "sni",
            "handshake",
            "verify failed",
            "x509",
            "certificate verify failed",
        },
    )
    dns_hits = _marker_hits(
        text,
        tokens,
        {
            "dns",
            "resolver",
            "resolution",
            "hostname cannot resolve",
            "cannot resolve",
            "temporary failure in name resolution",
            "name resolution",
            "nslookup",
            "service name",
        },
    )
    database_hits = _marker_hits(
        text,
        tokens,
        {
            "postgresql",
            "postgres",
            "mysql",
            "redis",
            "sql",
            "database",
            "db",
            "dsn",
            "connection string",
            "migration",
            "schema",
            "privilege",
            "permission",
            "grant",
            "credential",
            "cache",
        },
    )
    auth_hits = _marker_hits(
        text,
        tokens,
        {
            "jwt",
            "token",
            "bearer",
            "authorization header",
            "401",
            "403",
            "unauthorized",
            "forbidden",
            "scope",
            "role",
            "permission",
            "claims",
            "oauth",
        },
    )
    ai_hits = _marker_hits(
        text,
        tokens,
        {
            "model-serving",
            "model serving",
            "model_base_url",
            "model base url",
            "ollama",
            "cuda",
            "tensor",
            "dtype",
            "tokenizer",
            "embedding",
            "vector db",
            "vector database",
            "vector-store",
            "rag",
            "inference",
            "inference endpoint",
        },
    )
    redis_hits = _marker_hits(text, tokens, {"redis"})
    redis_state_hits = _marker_hits(
        text,
        tokens,
        {
            "session",
            "session state",
            "session store",
            "cache",
            "state",
            "store",
            "failover",
            "logged out",
            "logout",
            "lost keys",
            "ttl",
            "token refresh",
        },
    )
    health_hits = _marker_hits(
        text,
        tokens,
        {
            "health check",
            "health checks",
            "healthcheck",
            "load balancer",
            "load-balancer",
            "readiness",
            "ready",
            "/ready",
            "/health",
            "unhealthy",
            "healthy pods",
        },
    )
    api_base_hits = _marker_hits(
        text,
        tokens,
        {
            "api_base_url",
            "api base url",
            "base_url",
            "base url",
            "localhost",
            "browser request target",
            "net::err_connection_refused",
            "production build",
        },
    )
    runtime_env_hits = _marker_hits(
        text,
        tokens,
        {
            "environment variable",
            "env var",
            "runtime secrets",
            "secret",
            "keyerror",
            "openai_api_key",
            "missing",
            "startup",
            "initialize",
            "initializes",
            "crashes during startup",
        },
    )
    dependency_startup_hits = _marker_hits(
        text,
        tokens,
        {
            "startup",
            "dependency",
            "dependency conflict",
            "package upgrade",
            "import error",
            "module",
            "worker",
            "initializes",
            "initialization",
        },
    )
    model_endpoint_hits = _marker_hits(
        text,
        tokens,
        {
            "model-serving",
            "model serving",
            "model_base_url",
            "model base url",
            "disabled inference endpoint",
            "inference endpoint",
            "service unavailable",
            "503",
        },
    )
    stripped_header_hits = _marker_hits(
        text,
        tokens,
        {
            "authorization header",
            "auth header",
            "header is missing",
            "missing at upstream",
            "strips",
            "stripped",
            "forwarding",
            "bearer token",
            "direct backend",
            "upstream",
        },
    )

    return {
        "cookie": bool(cookie_hits or "csrf_or_cookie_failure" in symptom_names and tags & {"cors", "reactjs", "django"}),
        "cors": bool(cors_hits or supported_tags & {"cors"}),
        "proxy": bool(proxy_hits or supported_tags & {"proxy", "reverse-proxy", "nginx", "ingress", "http"} or "proxy_boundary" in boundary_names),
        "tls": bool(tls_hits or supported_tags & {"tls", "ssl"} or "tls_failure" in symptom_names),
        "dns": bool(dns_hits or supported_tags & {"dns"} or "dns_failure" in symptom_names),
        "database": bool(database_hits or supported_tags & {"postgresql", "mysql", "redis", "sql", "vector-database"}),
        "auth": bool(auth_hits or supported_tags & {"jwt", "authentication", "authorization", "oauth-2.0"} or {"authn_failure", "authz_failure"} & symptom_names),
        "ai_runtime": bool(ai_hits or supported_tags & {"model-serving", "inference", "rag", "embeddings", "vector-database", "cuda", "gpu"}),
        "redis_session": bool(redis_hits and redis_state_hits),
        "health_check": bool(health_hits and (proxy_hits or "proxy" in tags or "http" in tags or "routing" in tags)),
        "api_base_url": bool(api_base_hits and ("reactjs" in tags or "browser" in tokens or "frontend" in tokens or "javascript" in tags)),
        "runtime_env": bool(
            runtime_env_hits
            and _marker_hits(text, tokens, {"environment variable", "env var", "runtime secrets", "secret", "keyerror", "openai_api_key"})
            and ({"fastapi", "python", "debugging"} & tags or {"startup", "keyerror"} & tokens)
        ),
        "dependency_startup": bool(dependency_startup_hits and {"fastapi", "python", "debugging"} & tags and not database_hits),
        "model_endpoint": bool(
            model_endpoint_hits
            and _marker_hits(text, tokens, {"model-serving", "model serving", "model_base_url", "model base url", "inference endpoint", "disabled inference endpoint"})
            and ({"model-serving", "inference", "mlops"} & tags or ai_hits)
        ),
        "proxy_auth_header": bool(proxy_hits and stripped_header_hits and ("authorization" in text or "auth header" in text)),
        "database_privilege_target": bool(("mysql" in tokens or "mysql" in tags) and database_hits and _marker_hits(text, tokens, {"access denied", "credential", "credentials", "dsn", "endpoint", "update rows", "writes"})),
        "hits": {
            "cookie": cookie_hits,
            "cors": cors_hits,
            "proxy": proxy_hits,
            "tls": tls_hits,
            "dns": dns_hits,
            "database": database_hits,
            "auth": auth_hits,
            "ai_runtime": ai_hits,
            "redis_session": redis_hits + redis_state_hits,
            "health_check": health_hits,
            "api_base_url": api_base_hits,
            "runtime_env": runtime_env_hits,
            "dependency_startup": dependency_startup_hits,
            "model_endpoint": model_endpoint_hits,
            "proxy_auth_header": stripped_header_hits,
        },
    }


def _add_symptom(text_features: dict[str, Any], symptom_name: str, hits: list[str], score: float = 0.98) -> None:
    symptom_names = set(text_features.get("symptom_names", set()))
    direct_symptoms = list(text_features.get("direct_symptoms", []))
    symptom_score_map = dict(text_features.get("symptom_score_map", {}))
    symptom_evidence = dict(text_features.get("symptom_evidence", {}))

    if symptom_name not in symptom_names:
        direct_symptoms.append({"name": symptom_name, "score": score, "hits": hits or [symptom_name]})
        symptom_names.add(symptom_name)
    symptom_score_map[symptom_name] = max(float(symptom_score_map.get(symptom_name, 0.0)), score)
    direct_symptoms.sort(key=lambda item: (item.get("score", 0.0), item.get("name", "")), reverse=True)

    text_features["symptom_names"] = symptom_names
    text_features["symptom_score_map"] = symptom_score_map
    text_features["direct_symptoms"] = direct_symptoms
    text_features["primary_symptom"] = direct_symptoms[0]["name"] if direct_symptoms else text_features.get("primary_symptom", "")
    text_features["secondary_symptoms"] = [item["name"] for item in direct_symptoms[1:4]]

    symptom_evidence["symptom_names"] = symptom_names
    symptom_evidence["symptom_score_map"] = symptom_score_map
    symptom_evidence["direct_symptoms"] = direct_symptoms
    symptom_evidence["primary_symptom"] = text_features["primary_symptom"]
    symptom_evidence["secondary_symptoms"] = text_features["secondary_symptoms"]
    symptom_hits_by_name = dict(symptom_evidence.get("symptom_hits_by_name", {}))
    symptom_hits_by_name[symptom_name] = hits or [symptom_name]
    symptom_evidence["symptom_hits_by_name"] = symptom_hits_by_name
    text_features["symptom_evidence"] = symptom_evidence


def _remove_symptoms(text_features: dict[str, Any], symptom_names_to_remove: set[str]) -> None:
    if not symptom_names_to_remove:
        return

    symptom_names = set(text_features.get("symptom_names", set())) - symptom_names_to_remove
    direct_symptoms = [
        item
        for item in text_features.get("direct_symptoms", [])
        if item.get("name") not in symptom_names_to_remove
    ]
    symptom_score_map = {
        name: score
        for name, score in dict(text_features.get("symptom_score_map", {})).items()
        if name not in symptom_names_to_remove
    }
    symptom_evidence = dict(text_features.get("symptom_evidence", {}))
    symptom_hits_by_name = {
        name: hits
        for name, hits in dict(symptom_evidence.get("symptom_hits_by_name", {})).items()
        if name not in symptom_names_to_remove
    }

    text_features["symptom_names"] = symptom_names
    text_features["symptom_score_map"] = symptom_score_map
    text_features["direct_symptoms"] = direct_symptoms
    text_features["primary_symptom"] = direct_symptoms[0]["name"] if direct_symptoms else ""
    text_features["secondary_symptoms"] = [item["name"] for item in direct_symptoms[1:4]]

    symptom_evidence["symptom_names"] = symptom_names
    symptom_evidence["symptom_score_map"] = symptom_score_map
    symptom_evidence["direct_symptoms"] = direct_symptoms
    symptom_evidence["primary_symptom"] = text_features["primary_symptom"]
    symptom_evidence["secondary_symptoms"] = text_features["secondary_symptoms"]
    symptom_evidence["symptom_hits_by_name"] = symptom_hits_by_name
    text_features["symptom_evidence"] = symptom_evidence


def _augment_text_features_with_evidence(text_features: dict[str, Any], evidence_profile: dict[str, Any]) -> None:
    hits = evidence_profile["hits"]
    if evidence_profile["redis_session"]:
        _add_symptom(text_features, "cache_session_state_loss", hits["redis_session"])
    if evidence_profile["health_check"]:
        _add_symptom(text_features, "upstream_health_check_mismatch", hits["health_check"])
        _add_symptom(text_features, "upstream_failure", hits["health_check"], score=0.72)
    if evidence_profile["api_base_url"]:
        _add_symptom(text_features, "api_base_url_mismatch", hits["api_base_url"])
        _add_symptom(text_features, "connection_refused", hits["api_base_url"], score=0.74)
    if evidence_profile["runtime_env"]:
        _add_symptom(text_features, "missing_runtime_env_var", hits["runtime_env"])
        _add_symptom(text_features, "runtime_startup_failure", hits["runtime_env"], score=0.8)
        _add_symptom(text_features, "config_or_secret_drift", hits["runtime_env"], score=0.76)
    if evidence_profile["model_endpoint"]:
        _add_symptom(text_features, "model_endpoint_unavailable", hits["model_endpoint"])
        _add_symptom(text_features, "upstream_failure", hits["model_endpoint"], score=0.72)
    if evidence_profile["proxy_auth_header"]:
        _add_symptom(text_features, "authorization_header_stripped", hits["proxy_auth_header"])
        _add_symptom(text_features, "authn_failure", hits["proxy_auth_header"], score=0.68)

    unsupported_symptoms = set()
    if evidence_profile["redis_session"] and not evidence_profile["cookie"]:
        unsupported_symptoms.update({"csrf_or_cookie_failure", "browser_only_failure", "missing_cors_headers", "preflight_failure"})
    if evidence_profile["database_privilege_target"]:
        unsupported_symptoms.update({"authn_failure", "authz_failure", "csrf_or_cookie_failure"})
    if not evidence_profile["cors"]:
        unsupported_symptoms.update({"preflight_failure", "missing_cors_headers"})
    if not evidence_profile["dns"]:
        unsupported_symptoms.add("dns_failure")
    if not evidence_profile["tls"]:
        unsupported_symptoms.add("tls_failure")
    _remove_symptoms(text_features, unsupported_symptoms)


def _family_is_supported_by_evidence(family_name: str, evidence_profile: dict[str, Any]) -> bool:
    if family_name == "session_identity_boundary":
        return evidence_profile["cookie"] and not evidence_profile["redis_session"]
    if family_name == "cors_proxy_boundary":
        return evidence_profile["cors"]
    if family_name == "tls_edge_termination":
        return evidence_profile["tls"]
    if family_name == "dns_service_discovery":
        return evidence_profile["dns"]
    if family_name == "database_connectivity":
        return evidence_profile["database"]
    if family_name == "cache_session_store":
        return evidence_profile["redis_session"]
    if family_name == "model_serving_runtime":
        return evidence_profile["ai_runtime"] or evidence_profile["model_endpoint"]
    if family_name == "retrieval_embeddings_pipeline" or family_name == "gpu_inference_runtime":
        return evidence_profile["ai_runtime"]
    if family_name in {"authentication", "authorization_policy"}:
        return evidence_profile["auth"] and not evidence_profile["database_privilege_target"]
    if family_name == "http_routing_misconfiguration":
        return evidence_profile["proxy"] or evidence_profile["api_base_url"] or evidence_profile["health_check"] or evidence_profile["proxy_auth_header"] or evidence_profile["runtime_env"] or evidence_profile["dependency_startup"]
    return True


def _override_primary_issue_family(primary_issue_family: str, secondary_families: list[str], evidence_profile: dict[str, Any]) -> tuple[str, list[str]]:
    if evidence_profile["redis_session"]:
        primary_issue_family = "cache_session_store"
    elif evidence_profile["tls"]:
        primary_issue_family = "tls_edge_termination"
    elif evidence_profile["model_endpoint"]:
        primary_issue_family = "model_serving_runtime"
    elif evidence_profile["health_check"] or evidence_profile["proxy_auth_header"]:
        primary_issue_family = "http_routing_misconfiguration"
    elif evidence_profile["api_base_url"]:
        primary_issue_family = "runtime_configuration"
    elif evidence_profile["runtime_env"] or evidence_profile["dependency_startup"]:
        if not evidence_profile["database_privilege_target"]:
            primary_issue_family = "runtime_configuration"
    elif evidence_profile["database_privilege_target"]:
        primary_issue_family = "database_connectivity"
    elif not _family_is_supported_by_evidence(primary_issue_family, evidence_profile):
        for family_name in secondary_families:
            if _family_is_supported_by_evidence(family_name, evidence_profile):
                primary_issue_family = family_name
                break

    filtered_secondary = []
    for family_name in secondary_families:
        if family_name == primary_issue_family:
            continue
        if not _family_is_supported_by_evidence(family_name, evidence_profile):
            continue
        filtered_secondary.append(family_name)
    return primary_issue_family, _top_unique(filtered_secondary, 5)


def _override_selected_cluster(selected_cluster: str, primary_issue_family: str, evidence_profile: dict[str, Any]) -> str:
    if evidence_profile["tls"]:
        return "tls_dns_transport"
    if evidence_profile["model_endpoint"]:
        return "no_cluster_alignment"
    if evidence_profile["redis_session"] or evidence_profile["database_privilege_target"]:
        return "database_connectivity_stack"
    if evidence_profile["api_base_url"] or evidence_profile["health_check"] or evidence_profile["proxy_auth_header"]:
        return "http_proxy_edge"
    if evidence_profile["dependency_startup"]:
        return "auth_identity_flow"
    if evidence_profile["runtime_env"]:
        return "no_cluster_alignment"
    if primary_issue_family in FAMILY_CLUSTER_BY_EVIDENCE:
        return FAMILY_CLUSTER_BY_EVIDENCE[primary_issue_family]
    return selected_cluster


def _evidence_primary_path(primary_issue_family: str, evidence_profile: dict[str, Any]) -> str:
    if evidence_profile["redis_session"]:
        return "Verify Redis-backed session store and cache state continuity across failover"
    if evidence_profile["tls"]:
        return "Inspect TLS certificate chain, hostname coverage, SNI routing, and handshake trust"
    if evidence_profile["health_check"]:
        return "Verify load balancer health check path, upstream target, and readiness endpoint alignment"
    if evidence_profile["api_base_url"]:
        return "Verify the deployed API base URL, localhost fallback, and browser request target"
    if evidence_profile["proxy_auth_header"]:
        return "Verify Authorization header forwarding through the proxy to the upstream service"
    if evidence_profile["model_endpoint"]:
        return "Verify model-serving base URL, endpoint health, and inference availability"
    if evidence_profile["runtime_env"]:
        return "Verify required runtime environment variables, secrets, and startup dependency initialization"
    if evidence_profile["dependency_startup"]:
        return "Trace startup dependency resolution and runtime initialization before request handling"
    if evidence_profile["database_privilege_target"]:
        return "Verify MySQL database credential, DSN target, and write privilege alignment"
    if primary_issue_family == "authorization_policy":
        return "Trace the exact scope, role, policy, and 403 permission decision"
    return ""


def _path_score(path: str, evidence_profile: dict[str, Any], primary_issue_family: str) -> float:
    normalized = path.lower()
    score = 0.0
    for hit_group in evidence_profile.get("hits", {}).values():
        for hit in hit_group:
            if hit and hit.lower() in normalized:
                score += 3.0
    if primary_issue_family.replace("_", " ") in normalized:
        score += 2.0
    concrete_markers = {
        "redis", "session", "cache", "state", "store", "tls", "certificate", "chain",
        "hostname", "sni", "health", "check", "readiness", "api base url",
        "localhost", "authorization header", "model-serving", "endpoint", "environment",
        "secret", "mysql", "dsn", "credential", "scope", "role", "policy",
    }
    score += sum(1.2 for marker in concrete_markers if marker in normalized)
    score -= sum(2.4 for marker in GENERIC_PATH_MARKERS if marker in normalized)
    return score


def _rank_primary_path(candidates: list[str], evidence_profile: dict[str, Any], primary_issue_family: str) -> str:
    clean_candidates = [collapse_whitespace(candidate) for candidate in candidates if collapse_whitespace(candidate)]
    if not clean_candidates:
        return ""
    ranked = sorted(clean_candidates, key=lambda item: (_path_score(item, evidence_profile, primary_issue_family), len(item)), reverse=True)
    return ranked[0]


def _candidate_has_unsupported_drift(candidate: str, evidence_profile: dict[str, Any], primary_issue_family: str) -> bool:
    normalized = candidate.lower()
    if any(marker in normalized for marker in ("cors", "preflight", "access-control", "cross-origin", "cross origin")) and not evidence_profile["cors"]:
        return True
    if any(marker in normalized for marker in ("cookie", "samesite", "same-site", "csrf", "set-cookie", "credential mode")) and not evidence_profile["cookie"]:
        return True
    if "credentials" in normalized and not (evidence_profile["cookie"] or evidence_profile["cors"] or evidence_profile["database_privilege_target"]):
        return True
    if any(marker in normalized for marker in ("dns", "resolver", "name resolution", "nslookup")) and not evidence_profile["dns"]:
        return True
    if any(marker in normalized for marker in ("tls", "ssl", "certificate", "x509", "sni", "handshake")) and not evidence_profile["tls"]:
        return True
    if any(marker in normalized for marker in ("postgresql", "postgres", "mysql", "database dsn", "schema migration", "schema", "migration")) and not evidence_profile["database"]:
        return True
    if "redis" in normalized and not evidence_profile["redis_session"]:
        return True
    if primary_issue_family == "cache_session_store" and any(marker in normalized for marker in ("schema", "migration", "query contract", "relation", "column")):
        return True
    if any(marker in normalized for marker in ("jwt", "bearer", "oauth", "token claim", "token claims", "issuer", "audience", "signature")) and not evidence_profile["auth"]:
        return True
    if primary_issue_family == "database_connectivity" and any(marker in normalized for marker in ("jwt", "bearer", "oauth", "authorization policy", "scope claim")):
        return True
    if any(marker in normalized for marker in ("cors", "origin", "preflight")) and primary_issue_family == "authorization_policy" and not evidence_profile["cors"]:
        return True
    if any(marker in normalized for marker in ("gpu memory", "cuda", "vector-store", "vector store", "embedding", "retrieval", "rag")) and not evidence_profile["ai_runtime"]:
        return True
    if evidence_profile["model_endpoint"] and any(marker in normalized for marker in ("gpu memory", "cuda", "vector-store", "vector store", "embedding", "retrieval", "rag")):
        return True
    if "proxy" in normalized and not (evidence_profile["proxy"] or primary_issue_family == "http_routing_misconfiguration"):
        return True
    return False


def _custom_hypothesis_titles(evidence_profile: dict[str, Any], primary_issue_family: str) -> list[str]:
    if evidence_profile["redis_session"]:
        return [
            "Redis failover lost or evicted cache-backed session state before the active runtime reread it",
            "Session store configuration points different runtimes at different Redis targets or databases",
            "Session TTL, persistence, or replication settings expire keys during failover",
            "Token refresh writes and session reads are not using the same cache state key contract",
        ]
    if evidence_profile["tls"]:
        return [
            "The renewed certificate chain is incomplete or no longer trusted by HTTPS clients",
            "The SNI hostname routes clients to a certificate that does not cover the requested host",
            "Edge TLS termination presents a stale certificate or changed trust root after renewal",
            "Client verification now fails during the TLS handshake before HTTP routing begins",
        ]
    if evidence_profile["health_check"]:
        return [
            "The load balancer still probes the old health check path instead of the readiness endpoint",
            "The readiness endpoint returns a status code the health checker does not accept",
            "The health check upstream target differs from the pods serving the live ready path",
            "A route rewrite or path mapping sends health checks away from the intended upstream",
        ]
    if evidence_profile["api_base_url"]:
        return [
            "Missing API_BASE_URL leaves the production browser bundle calling localhost",
            "The browser request target differs from the deployed backend host and scheme",
            "Build-time environment injection did not publish the production API base URL",
            "A stale frontend artifact still contains the development API endpoint",
        ]
    if evidence_profile["proxy_auth_header"]:
        return [
            "The proxy strips the Authorization header before the request reaches the upstream service",
            "Nginx forwarding rules do not preserve bearer metadata on the protected route",
            "Direct backend calls work because they bypass the proxy branch that drops auth headers",
            "Header forwarding configuration differs between the edge route and upstream validation path",
        ]
    if evidence_profile["model_endpoint"]:
        return [
            "The configured MODEL_BASE_URL points to a disabled or unavailable inference endpoint",
            "The model-serving client is calling a stale endpoint rather than the active deployment",
            "Serving health fails before inference starts on the configured endpoint",
            "Deployment configuration changed the model base URL without enabling the target endpoint",
        ]
    if evidence_profile["runtime_env"]:
        return [
            "A required runtime environment variable or secret is missing before startup initialization",
            "Startup configuration loads an empty or stale dependency target from runtime secrets",
            "The service initializes the dependency client before the required environment is injected",
            "Deployment configuration drift changed the environment seen by the FastAPI process",
        ]
    if evidence_profile["dependency_startup"]:
        return [
            "The package upgrade introduced a dependency conflict before FastAPI startup completes",
            "An import error prevents the worker from initializing the application runtime",
            "The deployed Python environment no longer matches the dependency set expected by the app",
            "Startup initialization fails before request routing or downstream dependencies are reached",
        ]
    if evidence_profile["database_privilege_target"]:
        return [
            "The rotated MySQL credentials lack write privileges on the production target database",
            "The DSN points to a new MySQL endpoint with different grants or schema permissions",
            "The application connects successfully but uses a database user that cannot update rows",
            "Credential rotation changed the target or grant set for the write path",
        ]
    if primary_issue_family == "authentication" and evidence_profile["auth"]:
        return [
            "Bearer JWT validation rejects issuer, audience, expiry, or signature on the failing login request",
            "The presented auth artifact reaches backend validation with claims that no longer match expected settings",
            "Deployment changed token validation secrets or trusted audience before login completes",
            "Token expiry or refresh behavior invalidates the presented identity artifact",
        ]
    if primary_issue_family == "authorization_policy":
        return [
            "JWT scope claims do not include the permission required by the protected admin endpoint",
            "The new role is not mapped to the authorization policy used by the route",
            "Policy middleware denies the operation even though authentication succeeded",
            "Claim names or values differ from what the scope check expects",
        ]
    return []


def _family_fallback_hypothesis_titles(primary_issue_family: str, evidence_profile: dict[str, Any]) -> list[str]:
    if primary_issue_family == "http_routing_misconfiguration":
        return [
            "Upstream target, route rewrite, or host preservation no longer matches the intended backend path",
            "The edge proxy sends the request to a different upstream branch than engineers expect",
            "Recent deployment changed path mapping or service registration for the affected route",
            "Timeout or retry behavior at the edge masks the first failing upstream hop",
        ]
    if primary_issue_family == "container_networking":
        return [
            "Service selectors, exposed ports, or network policy changed on the platform path",
            "Endpoint registration or load-balancer membership lags behind the current rollout",
            "Namespace, security-group, or firewall rules block only the affected traffic path",
            "The running workload is reachable through a different service path than expected",
        ]
    if primary_issue_family == "database_connectivity":
        return [
            "The runtime points to the wrong database target, host, or credential for the failing path",
            "The configured database endpoint differs from the production target engineers expect",
            "Credential or grant drift isolates the failing data path from successful connection setup",
            "The live database target no longer matches the DSN selected by the runtime",
        ]
    if primary_issue_family == "runtime_configuration":
        if evidence_profile["runtime_env"]:
            return _custom_hypothesis_titles(evidence_profile, primary_issue_family)
        return [
            "Startup dependency resolution fails before the application runtime finishes initialization",
            "The deployed package set no longer matches the versions expected by the FastAPI process",
            "An import or dependency conflict prevents the worker from loading the application",
            "Runtime initialization fails before downstream routing or transport checks become relevant",
        ]
    if primary_issue_family == "dns_service_discovery":
        return [
            "The caller resolves a stale or wrong service name for the failing hop",
            "Search domains, namespace, or resolver policy differ from the expected caller context",
            "Service registration or endpoint publishing lags behind the current deployment state",
            "The failing runtime cannot obtain the expected resolver answer set",
        ]
    if primary_issue_family == "model_serving_runtime":
        return [
            "Serving endpoint selection or runtime mode no longer matches the failing model path",
            "Recent deployment changed the endpoint branch, model revision, or mounted artifacts",
            "Serving health or endpoint enablement fails before model execution begins",
            "The serving process starts with stale configuration for the active endpoint",
        ]
    return [
        f"The {_humanize_slug(primary_issue_family)} evidence points to a concrete configuration mismatch on the failing path",
        f"The selected {_humanize_slug(primary_issue_family)} branch changed before the reported symptom appears",
        "The live runtime state differs from the explicit problem evidence on the affected path",
        "The strongest observed signals converge before adjacent troubleshooting branches become relevant",
    ]


def _make_hypothesis(title: str, idx: int, primary_issue_family: str, selected_cluster: str, tags: list[str]) -> dict:
    return {
        "id": idx,
        "title": collapse_whitespace(title),
        "why_likely": collapse_whitespace(
            f"Explicit problem evidence supports the {_humanize_slug(primary_issue_family)} direction, with the strongest signals aligned to {_humanize_slug(selected_cluster)}."
        ),
        "confidence": clamp_confidence(0.92 - (idx - 1) * 0.035),
        "families": [primary_issue_family],
        "boundaries": [],
        "clusters": [selected_cluster] if selected_cluster != "no_cluster_alignment" else [],
        "tags": tags[:4],
    }


def _filter_and_rank_hypotheses(
    ranked_hypotheses: list[dict],
    primary_issue_family: str,
    selected_cluster: str,
    tag_items: list[dict],
    evidence_profile: dict[str, Any],
) -> list[dict]:
    custom_titles = _custom_hypothesis_titles(evidence_profile, primary_issue_family)
    tags = [item["tag"] for item in tag_items if item.get("tag")]
    filtered = []
    seen = set()

    for title in custom_titles:
        key = title.lower()
        if key in seen or _candidate_has_unsupported_drift(title, evidence_profile, primary_issue_family):
            continue
        filtered.append(_make_hypothesis(title, len(filtered) + 1, primary_issue_family, selected_cluster, tags))
        seen.add(key)

    for item in ranked_hypotheses:
        title = collapse_whitespace(item.get("title", "")) if isinstance(item, dict) else ""
        if not title or title.lower() in seen:
            continue
        if _candidate_has_unsupported_drift(title, evidence_profile, primary_issue_family):
            continue
        families = [family for family in item.get("families", []) if _family_is_supported_by_evidence(family, evidence_profile)]
        if item.get("families") and not families:
            continue
        candidate = dict(item)
        candidate["families"] = families or [primary_issue_family]
        candidate["id"] = len(filtered) + 1
        if custom_titles:
            candidate["confidence"] = min(float(candidate.get("confidence", 0.4)), 0.74)
        filtered.append(candidate)
        seen.add(title.lower())
        if len(filtered) >= 6:
            break

    fallback_titles = _custom_hypothesis_titles(evidence_profile, primary_issue_family) + _family_fallback_hypothesis_titles(primary_issue_family, evidence_profile)
    for title in fallback_titles:
        if len(filtered) >= 4:
            break
        if title.lower() in seen:
            continue
        if _candidate_has_unsupported_drift(title, evidence_profile, primary_issue_family):
            continue
        filtered.append(_make_hypothesis(title, len(filtered) + 1, primary_issue_family, selected_cluster, tags))
        seen.add(title.lower())

    return filtered[:6]


def _evidence_alternative_paths(primary_issue_family: str, evidence_profile: dict[str, Any]) -> list[str]:
    if evidence_profile["redis_session"]:
        return [
            "Compare Redis failover behavior, replication lag, TTLs, and persistence for session keys",
            "Confirm session store configuration, Redis database index, and cache key namespace match across runtimes",
            "Verify auth token refresh writes update the same Redis-backed state read by protected requests",
        ]
    if evidence_profile["tls"]:
        return [
            "Compare the renewed certificate chain and trust bundle from the failing HTTPS client context",
            "Confirm SNI routes the hostname to the intended edge certificate and TLS termination point",
            "Verify hostname coverage before investigating generic network transport behavior",
        ]
    if evidence_profile["health_check"]:
        return [
            "Compare the configured health check path with the backend readiness route and expected status",
            "Confirm the upstream target used by health checks matches the pods serving the ready endpoint",
            "Review proxy or ingress routing only after the health check path and readiness contract match",
        ]
    if evidence_profile["api_base_url"]:
        return [
            "Inspect the built frontend artifact for API_BASE_URL and localhost fallback values",
            "Compare the browser request target with the intended production backend URL",
            "Confirm deployment-time environment injection happened before the React bundle was built",
        ]
    if evidence_profile["proxy_auth_header"]:
        return [
            "Compare direct backend authorization with the proxy-mediated request received upstream",
            "Inspect nginx forwarding rules for Authorization and Host header preservation",
            "Verify route rewrite does not send protected traffic through a branch that drops auth headers",
        ]
    if evidence_profile["model_endpoint"]:
        return [
            "Confirm MODEL_BASE_URL points to an enabled model-serving endpoint",
            "Compare endpoint health with the deployment target used before inference starts",
            "Verify serving configuration before checking lower-level capacity or dependency branches",
        ]
    if evidence_profile["runtime_env"] or evidence_profile["dependency_startup"]:
        return [
            "Compare runtime environment variables and secrets with the last known-good deployment",
            "Trace FastAPI startup dependency loading before any downstream network or database checks",
            "Confirm the package set and import path match the deployed Python runtime",
        ]
    if evidence_profile["database_privilege_target"]:
        return [
            "Check MySQL grants for the rotated credential on the production database target",
            "Confirm the DSN points to the intended endpoint and schema before investigating auth tokens",
            "Replay a minimal write using the same database user and target selected by the runtime",
        ]
    return []


def _filter_alternative_paths(
    alternative_paths: list[str],
    primary_path: str,
    primary_issue_family: str,
    evidence_profile: dict[str, Any],
) -> list[str]:
    candidates = _evidence_alternative_paths(primary_issue_family, evidence_profile) + alternative_paths
    filtered = []
    seen = set()
    primary_key = primary_path.lower()
    for candidate in candidates:
        normalized = collapse_whitespace(candidate)
        key = normalized.lower()
        if not key or key == primary_key or key in seen:
            continue
        if _candidate_has_unsupported_drift(normalized, evidence_profile, primary_issue_family):
            continue
        filtered.append(normalized)
        seen.add(key)
        if len(filtered) >= 4:
            break
    return filtered


def _case_boundary_hints_for_evidence(
    boundary_hints: list[dict],
    boundary_confidence: dict[str, float],
    evidence_profile: dict[str, Any],
) -> tuple[list[dict], dict[str, float]]:
    custom_name = ""
    if evidence_profile["redis_session"]:
        custom_name = "redis_session_cache_state_store_boundary"
    elif evidence_profile["tls"]:
        custom_name = "tls_certificate_chain_hostname_sni_boundary"
    elif evidence_profile["health_check"]:
        custom_name = "health_check_path_upstream_readiness_boundary"
    elif evidence_profile["api_base_url"]:
        custom_name = "api_base_url_localhost_browser_request_target_boundary"
    elif evidence_profile["proxy_auth_header"]:
        custom_name = "proxy_authorization_header_forwarding_boundary"
    elif evidence_profile["model_endpoint"]:
        custom_name = "model_endpoint_health_boundary"
    elif evidence_profile["runtime_env"]:
        custom_name = "environment_variable_secret_startup_boundary"
    elif evidence_profile["dependency_startup"]:
        custom_name = "startup_runtime_dependency_trace_boundary"
    elif evidence_profile["database_privilege_target"]:
        custom_name = "mysql_database_credential_dsn_target_boundary"

    if not custom_name:
        return boundary_hints, boundary_confidence

    custom_hint = {
        "name": custom_name,
        "score": 0.99,
        "matched_tags": [],
        "matched_keywords": evidence_profile.get("hits", {}),
        "matched_phrases": [],
        "matched_symptoms": [],
        "drift_penalty_reasons": [],
    }
    if evidence_profile["model_endpoint"] or evidence_profile["api_base_url"]:
        return [custom_hint], {custom_name: 0.99}

    suppressed = {"browser_boundary", "network_transport_boundary"}
    if evidence_profile["model_endpoint"] or evidence_profile["api_base_url"]:
        suppressed.update({"model_serving_boundary", "proxy_boundary"})
    filtered_hints = [
        item
        for item in boundary_hints
        if isinstance(item, dict) and item.get("name") not in suppressed
    ]
    return [custom_hint, *filtered_hints[:3]], {custom_name: 0.99, **{name: score for name, score in boundary_confidence.items() if name not in suppressed}}


def _case_symptom_evidence_for_evidence(text_features: dict[str, Any], evidence_profile: dict[str, Any]) -> dict[str, Any]:
    symptom_evidence = dict(text_features.get("symptom_evidence", {}))
    if not (evidence_profile["redis_session"] or evidence_profile["api_base_url"] or evidence_profile["proxy_auth_header"]):
        return symptom_evidence

    # Some downstream checklist templates over-prioritize generic capture or
    # browser/proxy templates when a custom symptom is marked as primary. Keep
    # the explicit symptom names available, but do not advertise a neighboring
    # family as the primary symptom.
    symptom_evidence["direct_symptoms"] = [{"name": "", "score": 0.0, "hits": []}]
    symptom_evidence["primary_symptom"] = ""
    symptom_evidence["secondary_symptoms"] = []
    return symptom_evidence


def _normalize_tag_signals_for_case_summary(tag_items: list[dict]) -> list[dict]:
    normalized = []
    for item in tag_items:
        normalized.append(
            {
                "tag": item["tag"],
                "confidence": clamp_confidence(item["effective_confidence"]),
                "rank": int(item["rank"]),
                "relative_weight": float(item.get("relative_weight", 0.0)),
                "diagnostic_weight": float(item.get("effective_diagnostic_weight", item.get("diagnostic_weight", 0.0))),
                "path_role": "primary" if int(item["rank"]) == 1 else "alternative",
            }
        )
    return normalized


def _extract_text_features(problem_text: str, symptom_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    symptom_evidence = symptom_evidence if symptom_evidence else extract_symptom_evidence(problem_text)
    text = symptom_evidence["text"]
    tokens = symptom_evidence["keywords"]
    status_codes = symptom_evidence["status_codes"]
    phrase_hits = sorted([phrase for phrase in FAILURE_PHRASES if phrase in text])

    symptom_bucket_scores = {}
    for bucket_name, markers in SYMPTOM_BUCKETS.items():
        score = sum(1 for marker in markers if marker in tokens or marker in text)
        if score > 0:
            symptom_bucket_scores[bucket_name] = score

    sorted_buckets = sorted(
        symptom_bucket_scores.items(),
        key=lambda item: (item[1], item[0]),
        reverse=True,
    )

    return {
        "text": text,
        "tokens": tokens,
        "status_codes": status_codes,
        "failure_phrases": phrase_hits,
        "symptom_bucket_scores": symptom_bucket_scores,
        "sorted_symptom_buckets": [bucket for bucket, _ in sorted_buckets],
        "direct_symptoms": symptom_evidence["direct_symptoms"],
        "symptom_names": symptom_evidence["symptom_names"],
        "symptom_score_map": symptom_evidence["symptom_score_map"],
        "symptom_evidence": symptom_evidence,
        "primary_symptom": symptom_evidence.get("primary_symptom") or (symptom_evidence["direct_symptoms"][0]["name"] if symptom_evidence["direct_symptoms"] else ""),
        "secondary_symptoms": symptom_evidence.get("secondary_symptoms", []),
        "has_deployment_change": symptom_evidence["has_deployment_change"],
    }


def _deployment_change_cues(problem_text: str, symptom_evidence: dict[str, Any], boundary_hints: list[dict]) -> list[str]:
    cues = []
    for hit in symptom_evidence.get("symptom_hits_by_name", {}).get("deployment_change", []):
        normalized = collapse_whitespace(hit)
        if normalized:
            cues.append(normalized)
    text = symptom_evidence.get("text", collapse_whitespace(problem_text).lower())
    for phrase in ("after deploy", "after deployment", "after upgrade", "after restart", "after migration", "after moving behind proxy"):
        if phrase in text:
            cues.append(phrase)
    for hint in boundary_hints:
        if hint.get("name") == "deployment_change_hint" and hint.get("score", 0.0) >= 0.22:
            cues.append("boundary:deployment_change_hint")
    return _top_unique(cues, 6)


def _boundary_confidence_table(boundary_hints: list[dict]) -> dict[str, float]:
    return {
        item["name"]: float(item.get("score", 0.0))
        for item in boundary_hints
        if isinstance(item, dict) and item.get("name")
    }


def _resolve_interpreted_signals(
    problem_text: str,
    predicted_domain: str,
    top_tags: list,
    interpreted_signals: dict | None = None,
) -> dict[str, Any]:
    if interpreted_signals and isinstance(interpreted_signals, dict) and interpreted_signals.get("active_domain"):
        normalize_domain_label(interpreted_signals["active_domain"])
        normalized_prediction = interpreted_signals.get("normalized_prediction", {})
        if normalized_prediction.get("tag_items", []):
            return interpreted_signals

    return interpret_prediction_output(problem_text, predicted_domain, top_tags)


def _cluster_map(interpreted_signals: dict) -> dict[str, dict]:
    return {
        item["cluster_id"]: item
        for item in interpreted_signals.get("inferred_clusters", [])
        if isinstance(item, dict) and item.get("cluster_id")
    }


def _issue_family_map(interpreted_signals: dict) -> dict[str, dict]:
    return {
        item["issue_family"]: item
        for item in interpreted_signals.get("issue_family_candidates", [])
        if isinstance(item, dict) and item.get("issue_family")
    }


def _boundary_map(interpreted_signals: dict) -> dict[str, dict]:
    return {
        item["name"]: item
        for item in interpreted_signals.get("boundary_hints", [])
        if isinstance(item, dict) and item.get("name")
    }


def _is_explicit_stack_anchor(tag_item: dict[str, Any]) -> bool:
    return bool(
        tag_item.get("text_inferred")
        or tag_item.get("text_support_count", 0) > 0
        or tag_item.get("text_support_terms")
    )


def _anchor_tag_items_for_root_cause(tag_items: list[dict]) -> list[dict]:
    explicit_by_group = {
        group_name: {
            item["tag"]
            for item in tag_items
            if item["tag"] in group_tags and _is_explicit_stack_anchor(item)
        }
        for group_name, group_tags in ROOT_CAUSE_STACK_GROUPS.items()
    }
    if not any(explicit_by_group.values()):
        return tag_items

    anchored = []
    for item in tag_items:
        suppress = False
        for group_name, group_tags in ROOT_CAUSE_STACK_GROUPS.items():
            if item["tag"] not in group_tags:
                continue
            explicit_tags = explicit_by_group[group_name]
            if not explicit_tags:
                continue
            if item["tag"] in explicit_tags:
                break
            if _is_explicit_stack_anchor(item):
                break
            if item.get("effective_confidence", 0.0) >= 0.86 and item.get("symptom_support_score", 0.0) >= 0.72:
                break
            suppress = True
            break
        if not suppress:
            anchored.append(item)

    return anchored or tag_items


def _build_reasoning_summary(primary_path: str, ranked_hypotheses: list[dict], primary_issue_family: str) -> str:
    top_hypothesis = ranked_hypotheses[0]["title"] if ranked_hypotheses else "the highest-ranked explanation"
    return collapse_whitespace(
        f"Diagnostic reasoning prioritized the {_humanize_slug(primary_issue_family)} direction. "
        f"The leading investigation path is '{primary_path}', and the strongest current explanation is '{top_hypothesis}'."
    )


def _build_reasoning_trace_internal(
    reasoning_bundle: dict[str, Any],
    case_bank: list[dict],
    primary_issue_family: str,
    secondary_families: list[str],
    selected_cluster: str,
    family_score_table: dict[str, float],
    tag_case_coverage: dict[str, Any],
) -> dict[str, Any]:
    return {
        "active_domain": reasoning_bundle["active_domain"],
        "primary_symptom": reasoning_bundle["text_features"].get("primary_symptom", ""),
        "trusted_tags": list(reasoning_bundle["trusted_tags"]),
        "supporting_tags": list(reasoning_bundle["supporting_tags"]),
        "weak_tags": list(reasoning_bundle["weak_tags"]),
        "tag_confidence_profile": reasoning_bundle.get("tag_confidence_profile", {}),
        "symptom_evidence": reasoning_bundle["text_features"].get("symptom_evidence", {}),
        "boundary_confidence": reasoning_bundle.get("boundary_confidence", {}),
        "deployment_change_cues": reasoning_bundle.get("deployment_change_cues", []),
        "cluster_candidates": list(reasoning_bundle.get("cluster_map", {}).values()),
        "selected_cluster": selected_cluster,
        "primary_issue_family": primary_issue_family,
        "secondary_issue_families": secondary_families,
        "family_score_table": family_score_table,
        "boundary_hints": reasoning_bundle["boundary_hints"],
        "stack_consistency_flags": reasoning_bundle["stack_consistency_flags"],
        "exclusion_decisions": reasoning_bundle["exclusion_decisions"],
        "tag_case_coverage": tag_case_coverage,
        "total_generated_reasoning_cases": len(case_bank),
        "top_case_keys": [case["case_key"] for case in case_bank[:12]],
    }


def generate_root_cause_hypotheses(
    problem_text: str,
    predicted_domain: str,
    top_tags: list,
    interpreted_signals: dict | None = None,
) -> dict:
    interpreted = _resolve_interpreted_signals(
        problem_text,
        predicted_domain,
        top_tags,
        interpreted_signals=interpreted_signals,
    )

    active_domain = normalize_domain_label(interpreted["active_domain"])
    reasoning_domain = to_reasoning_domain(active_domain)
    text_features = _extract_text_features(problem_text, interpreted.get("symptom_evidence"))
    tag_items = interpreted["normalized_prediction"]["tag_items"]
    supported_tags = SUPPORTED_TAGS_BY_DOMAIN[active_domain]
    tag_items = [item for item in tag_items if item["tag"] in supported_tags or item["effective_confidence"] >= 0.18]
    tag_items = _anchor_tag_items_for_root_cause(tag_items)
    tag_items.sort(key=lambda item: (item["effective_confidence"], -item["rank"]), reverse=True)

    if not tag_items:
        raise ValueError("No supported interpreted tags are available for reasoning.")

    deployment_change_cues = _deployment_change_cues(problem_text, interpreted.get("symptom_evidence", {}), interpreted.get("boundary_hints", []))
    boundary_confidence = _boundary_confidence_table(interpreted["boundary_hints"])
    evidence_profile = _build_evidence_profile(text_features, tag_items, interpreted["boundary_hints"])
    _augment_text_features_with_evidence(text_features, evidence_profile)
    reasoning_bundle = {
        "active_domain": active_domain,
        "reasoning_domain": reasoning_domain,
        "tag_items": tag_items,
        "trusted_tags": interpreted["trusted_tags"],
        "supporting_tags": interpreted["supporting_tags"],
        "weak_tags": interpreted["weak_tags"],
        "tag_confidence_profile": interpreted["tag_confidence_profile"],
        "cluster_map": _cluster_map(interpreted),
        "family_map": _issue_family_map(interpreted),
        "boundary_map": _boundary_map(interpreted),
        "boundary_confidence": boundary_confidence,
        "boundary_hints": interpreted["boundary_hints"],
        "stack_consistency_flags": interpreted["stack_consistency_flags"],
        "exclusion_decisions": interpreted["exclusion_decisions"],
        "deployment_change_cues": deployment_change_cues,
        "text_features": text_features,
    }

    case_bank, tag_case_coverage = _build_case_bank(reasoning_bundle)
    provisional_cluster = _select_reasoning_cluster(reasoning_bundle, case_bank, primary_issue_family="")
    reasoning_bundle["selected_cluster"] = provisional_cluster
    primary_issue_family, secondary_families, family_score_table = _resolve_primary_issue_family(reasoning_bundle, case_bank)
    selected_cluster = _select_reasoning_cluster(reasoning_bundle, case_bank, primary_issue_family)
    primary_issue_family, secondary_families = _override_primary_issue_family(primary_issue_family, secondary_families, evidence_profile)
    selected_cluster = _override_selected_cluster(selected_cluster, primary_issue_family, evidence_profile)
    reasoning_bundle["selected_cluster"] = selected_cluster

    raw_primary_path = _build_primary_path(primary_issue_family, selected_cluster, reasoning_bundle)
    evidence_path = _evidence_primary_path(primary_issue_family, evidence_profile)
    primary_path = _rank_primary_path([evidence_path, raw_primary_path], evidence_profile, primary_issue_family)
    alternative_paths = _build_alternative_paths(
        primary_issue_family,
        secondary_families,
        selected_cluster,
        reasoning_bundle,
        case_bank,
    )
    alternative_paths = _filter_alternative_paths(
        alternative_paths,
        primary_path,
        primary_issue_family,
        evidence_profile,
    )
    ranked_hypotheses = _build_ranked_hypotheses(case_bank, primary_issue_family, selected_cluster, text_features)
    ranked_hypotheses = _filter_and_rank_hypotheses(
        ranked_hypotheses,
        primary_issue_family,
        selected_cluster,
        tag_items,
        evidence_profile,
    )
    possible_causes = _top_unique([item["title"] for item in ranked_hypotheses], 6)

    compatibility_issue_family = ISSUE_FAMILY_COMPATIBILITY_MAP.get(primary_issue_family, primary_issue_family)
    case_trusted_tags = list(interpreted["trusted_tags"])
    case_supporting_tags = list(interpreted["supporting_tags"])
    if evidence_profile["runtime_env"]:
        case_trusted_tags = [tag for tag in case_trusted_tags if tag not in {"fastapi", "python", "debugging"}]
        case_supporting_tags = [tag for tag in case_supporting_tags if tag not in {"fastapi", "python", "debugging"}]
    if evidence_profile["api_base_url"]:
        case_trusted_tags = [tag for tag in case_trusted_tags if tag not in {"reactjs", "javascript", "typescript", "debugging"}]
        case_supporting_tags = [tag for tag in case_supporting_tags if tag not in {"reactjs", "javascript", "typescript", "debugging"}]
    if evidence_profile["proxy_auth_header"]:
        case_trusted_tags = [tag for tag in case_trusted_tags if tag not in {"nginx", "reverse-proxy", "http"}]
        case_supporting_tags = [tag for tag in case_supporting_tags if tag not in {"nginx", "reverse-proxy", "http"}]
    case_boundary_hints, case_boundary_confidence = _case_boundary_hints_for_evidence(
        interpreted["boundary_hints"],
        boundary_confidence,
        evidence_profile,
    )
    case_summary = {
        "domain": reasoning_domain,
        "issue_family": compatibility_issue_family,
        "primary_issue_family": primary_issue_family,
        "top_tags": [item["tag"] for item in tag_items],
        "tag_signals": _normalize_tag_signals_for_case_summary(tag_items),
        "trusted_tags": case_trusted_tags,
        "supporting_tags": case_supporting_tags,
        "weak_tags": interpreted["weak_tags"],
        "selected_reasoning_cluster": selected_cluster,
        "boundary_hints": case_boundary_hints,
        "boundary_confidence": case_boundary_confidence,
        "symptom_evidence": _case_symptom_evidence_for_evidence(text_features, evidence_profile),
        "deployment_change_cues": deployment_change_cues,
    }

    reasoning_trace_internal = _build_reasoning_trace_internal(
        reasoning_bundle,
        case_bank,
        primary_issue_family,
        secondary_families,
        selected_cluster,
        family_score_table,
        tag_case_coverage,
    )

    data = {
        "case_summary": case_summary,
        "primary_path": primary_path,
        "alternative_paths": alternative_paths,
        "possible_causes": possible_causes,
        "primary_issue_family": primary_issue_family,
        "selected_reasoning_cluster": selected_cluster,
        "ranked_hypotheses": ranked_hypotheses,
        "root_cause_hypotheses": ranked_hypotheses,
        "reasoning_trace_internal": reasoning_trace_internal,
        "reasoning_summary": _build_reasoning_summary(primary_path, ranked_hypotheses, primary_issue_family),
    }
    return validate_root_cause_output(data)


__all__ = [
    "_normalize_tag_signals_for_case_summary",
    "_extract_text_features",
    "_deployment_change_cues",
    "_boundary_confidence_table",
    "_resolve_interpreted_signals",
    "_cluster_map",
    "_issue_family_map",
    "_boundary_map",
    "_is_explicit_stack_anchor",
    "_anchor_tag_items_for_root_cause",
    "_build_reasoning_summary",
    "_build_reasoning_trace_internal",
    "generate_root_cause_hypotheses",
]
