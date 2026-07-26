from dataclasses import dataclass
from typing import Iterable

import pytest

from app.schemas.requests import DiagnoseRequest
from app.services import pipeline


DOMAIN_LABELS = {
    "sw": "software",
    "cn": "networking",
    "ai": "ai",
}


@dataclass(frozen=True)
class DiagnosticQualityCase:
    case_id: str
    problem_text: str
    predicted_domain: str
    ranked_tags: tuple[tuple[str, float], ...]
    expected_public_domain: str
    primary_path_keywords: tuple[str, ...]
    first_step_keywords: tuple[str, ...]
    reference_keywords: tuple[str, ...]
    forbidden_drift: tuple[str, ...] = ()


QUALITY_CASES = [
    DiagnosticQualityCase(
        case_id="auth_jwt_401",
        problem_text=(
            "FastAPI API returns 401 unauthorized after deploy. Bearer JWT is present, "
            "but backend logs invalid audience and expired token for the login request."
        ),
        predicted_domain="sw",
        ranked_tags=(("jwt", 0.95), ("authentication", 0.9), ("fastapi", 0.75)),
        expected_public_domain="software",
        primary_path_keywords=("auth", "token", "jwt", "artifact", "validation"),
        first_step_keywords=("identity", "artifact", "token", "jwt"),
        reference_keywords=("jwt", "oauth", "security", "fastapi", "auth"),
        forbidden_drift=("dns", "cuda", "embedding", "vector store"),
    ),
    DiagnosticQualityCase(
        case_id="auth_scope_403",
        problem_text=(
            "Admin endpoint returns 403 forbidden for users with the new role. "
            "JWT claims show missing scope and the authorization policy denies permission."
        ),
        predicted_domain="sw",
        ranked_tags=(("authorization", 0.95), ("jwt", 0.86), ("oauth-2.0", 0.72)),
        expected_public_domain="software",
        primary_path_keywords=("scope", "role", "policy", "403", "permission"),
        first_step_keywords=("policy", "scope", "role", "protected"),
        reference_keywords=("jwt", "oauth", "auth", "security", "fastapi"),
        forbidden_drift=("cors", "dns", "cuda", "postgresql"),
    ),
    DiagnosticQualityCase(
        case_id="cors_preflight_proxy",
        problem_text=(
            "Browser preflight OPTIONS request is blocked by CORS policy after moving behind nginx. "
            "Access-Control-Allow-Headers does not include Authorization."
        ),
        predicted_domain="cn",
        ranked_tags=(("cors", 0.95), ("http", 0.82), ("nginx", 0.72)),
        expected_public_domain="networking",
        primary_path_keywords=("preflight", "cors", "origin", "proxy", "ingress"),
        first_step_keywords=("preflight", "origin", "allowlist", "cors"),
        reference_keywords=("cors", "http", "nginx", "proxy", "origin"),
        forbidden_drift=("jwt claim", "postgresql", "cuda", "embedding"),
    ),
    DiagnosticQualityCase(
        case_id="react_browser_request_shape",
        problem_text=(
            "React fetch succeeds in Postman but fails only in the browser with credentials included. "
            "The request sends cookies and an Authorization header from a different origin."
        ),
        predicted_domain="sw",
        ranked_tags=(("reactjs", 0.9), ("javascript", 0.78), ("cors", 0.7)),
        expected_public_domain="software",
        primary_path_keywords=("browser", "request", "origin", "credentials", "cookie"),
        first_step_keywords=("browser", "request", "origin", "credentials", "cookie"),
        reference_keywords=("react", "javascript", "cors", "http", "auth"),
        forbidden_drift=("dns resolver", "cuda", "postgresql schema", "vector"),
    ),
    DiagnosticQualityCase(
        case_id="django_csrf_cookie",
        problem_text=(
            "Django login POST fails with CSRF failed after the frontend moved domains. "
            "Session cookies are present but SameSite and credentials behavior changed."
        ),
        predicted_domain="sw",
        ranked_tags=(("django", 0.9), ("authentication", 0.78), ("authorization", 0.52)),
        expected_public_domain="software",
        primary_path_keywords=("csrf", "cookie", "session", "identity", "browser"),
        first_step_keywords=("cookie", "csrf", "session", "credentials"),
        reference_keywords=("django", "csrf", "auth", "security", "cookie"),
        forbidden_drift=("dns", "cuda", "embedding", "nginx upstream"),
    ),
    DiagnosticQualityCase(
        case_id="django_postgres_timeout_deploy",
        problem_text=(
            "Django app cannot connect to PostgreSQL after deployment. "
            "Requests time out while the live DSN points to the production database host and new secret."
        ),
        predicted_domain="sw",
        ranked_tags=(("postgresql", 0.9), ("django", 0.85), ("sql", 0.7)),
        expected_public_domain="software",
        primary_path_keywords=("database", "postgresql", "dsn", "host", "runtime"),
        first_step_keywords=("database", "dsn", "host", "secret", "runtime"),
        reference_keywords=("postgresql", "django", "sql", "database"),
        forbidden_drift=("cors", "cuda", "gpu", "vector"),
    ),
    DiagnosticQualityCase(
        case_id="fastapi_startup_dependency",
        problem_text=(
            "FastAPI service fails during startup after a package upgrade. "
            "The worker logs an import error and dependency conflict before the app initializes."
        ),
        predicted_domain="sw",
        ranked_tags=(("fastapi", 0.88), ("python", 0.8), ("debugging", 0.62)),
        expected_public_domain="software",
        primary_path_keywords=("startup", "runtime", "dependency", "initialization", "config"),
        first_step_keywords=("runtime", "startup", "dependency", "trace"),
        reference_keywords=("fastapi", "python", "package", "dependency"),
        forbidden_drift=("dns", "cors preflight", "cuda", "vector"),
    ),
    DiagnosticQualityCase(
        case_id="postgres_schema_migration",
        problem_text=(
            "After a PostgreSQL migration, production requests fail with relation does not exist "
            "and column does not exist errors while local queries still work."
        ),
        predicted_domain="sw",
        ranked_tags=(("postgresql", 0.92), ("sql", 0.85), ("django", 0.55)),
        expected_public_domain="software",
        primary_path_keywords=("postgresql", "schema", "migration", "database", "query"),
        first_step_keywords=("schema", "migration", "database", "query"),
        reference_keywords=("postgresql", "sql", "database", "schema"),
        forbidden_drift=("jwt", "cors", "dns resolver", "cuda"),
    ),
    DiagnosticQualityCase(
        case_id="mysql_privilege_target",
        problem_text=(
            "MySQL writes fail only in production with access denied after rotating credentials. "
            "The DSN points at a new database endpoint and the app can connect but cannot update rows."
        ),
        predicted_domain="sw",
        ranked_tags=(("mysql", 0.88), ("sql", 0.82), ("python", 0.48)),
        expected_public_domain="software",
        primary_path_keywords=("mysql", "database", "credential", "dsn", "target"),
        first_step_keywords=("database", "target", "dsn", "credential", "runtime"),
        reference_keywords=("mysql", "sql", "database", "credential"),
        forbidden_drift=("jwt", "cors", "cuda", "tls certificate"),
    ),
    DiagnosticQualityCase(
        case_id="redis_session_store",
        problem_text=(
            "Users are randomly logged out after Redis failover. "
            "Session state disappears from the cache and token refreshes create inconsistent state."
        ),
        predicted_domain="sw",
        ranked_tags=(("redis", 0.9), ("authentication", 0.65), ("authorization", 0.45)),
        expected_public_domain="software",
        primary_path_keywords=("redis", "session", "cache", "state", "store"),
        first_step_keywords=("cache", "session", "redis", "state"),
        reference_keywords=("redis", "auth", "session", "sql"),
        forbidden_drift=("dns resolver", "cuda", "embedding", "preflight"),
    ),
    DiagnosticQualityCase(
        case_id="nginx_upstream_502",
        problem_text=(
            "Nginx returns 502 bad gateway after moving the API behind a reverse proxy. "
            "The upstream prematurely closes the connection and forwarded host headers changed."
        ),
        predicted_domain="cn",
        ranked_tags=(("nginx", 0.92), ("reverse-proxy", 0.86), ("http", 0.7)),
        expected_public_domain="networking",
        primary_path_keywords=("upstream", "proxy", "route", "gateway", "header"),
        first_step_keywords=("upstream", "proxy", "route", "host", "header"),
        reference_keywords=("nginx", "proxy", "http", "upstream"),
        forbidden_drift=("jwt", "postgresql", "cuda", "embedding"),
    ),
    DiagnosticQualityCase(
        case_id="nginx_proxy_header_strip",
        problem_text=(
            "Nginx reverse proxy forwards the request but strips the Host and Authorization headers "
            "before the upstream service validates it."
        ),
        predicted_domain="cn",
        ranked_tags=(("nginx", 0.9), ("reverse-proxy", 0.85), ("http", 0.7)),
        expected_public_domain="networking",
        primary_path_keywords=("host", "authorization", "header", "proxy", "forward"),
        first_step_keywords=("upstream", "route", "host", "proxy"),
        reference_keywords=("nginx", "proxy", "http", "upstream"),
        forbidden_drift=("postgresql", "cuda", "embedding", "cors preflight"),
    ),
    DiagnosticQualityCase(
        case_id="dns_lookup_failure",
        problem_text=(
            "The service cannot resolve api.internal from the container. "
            "Logs show temporary failure in name resolution and DNS lookup failed after deployment."
        ),
        predicted_domain="cn",
        ranked_tags=(("dns", 0.96), ("networking", 0.82), ("routing", 0.62)),
        expected_public_domain="networking",
        primary_path_keywords=("dns", "resolve", "service", "answer", "resolver"),
        first_step_keywords=("dns", "resolve", "answer", "caller"),
        reference_keywords=("dns", "tcp", "routing", "protocol"),
        forbidden_drift=("jwt", "cors", "postgresql schema", "cuda"),
    ),
    DiagnosticQualityCase(
        case_id="kubernetes_dns_temporary_failure",
        problem_text=(
            "Kubernetes pod logs show temporary failure in name resolution for api.default.svc.cluster.local "
            "after deployment. DNS lookup fails from the caller namespace."
        ),
        predicted_domain="cn",
        ranked_tags=(("dns", 0.95), ("kubernetes", 0.9), ("networking", 0.7)),
        expected_public_domain="networking",
        primary_path_keywords=("dns", "resolve", "service", "caller", "answer"),
        first_step_keywords=("dns", "resolve", "answer", "caller"),
        reference_keywords=("kubernetes", "dns", "service", "routing"),
        forbidden_drift=("jwt", "auth", "react", "csrf", "gpu"),
    ),
    DiagnosticQualityCase(
        case_id="tls_certificate_handshake",
        problem_text=(
            "HTTPS clients fail with TLS handshake failure and certificate verify failed. "
            "The SNI hostname changed after the edge certificate was renewed."
        ),
        predicted_domain="cn",
        ranked_tags=(("tls", 0.95), ("ssl", 0.84), ("nginx", 0.58)),
        expected_public_domain="networking",
        primary_path_keywords=("tls", "certificate", "handshake", "trust", "hostname"),
        first_step_keywords=("tls", "certificate", "chain", "hostname", "sni"),
        reference_keywords=("tls", "ssl", "certificate", "nginx", "security"),
        forbidden_drift=("jwt", "postgresql", "cuda", "embedding"),
    ),
    DiagnosticQualityCase(
        case_id="network_timeout_budget",
        problem_text=(
            "Requests intermittently hit a 504 timeout after a network change. "
            "Latency exceeds the active timeout budget between the proxy and upstream service."
        ),
        predicted_domain="cn",
        ranked_tags=(("tcp", 0.82), ("proxy", 0.72), ("networking", 0.65)),
        expected_public_domain="networking",
        primary_path_keywords=("timeout", "latency", "budget", "hop", "upstream"),
        first_step_keywords=("timeout", "latency", "hop", "upstream"),
        reference_keywords=("tcp", "routing", "proxy", "http", "nginx"),
        forbidden_drift=("jwt", "postgresql schema", "cuda", "embedding"),
    ),
    DiagnosticQualityCase(
        case_id="docker_container_host_service",
        problem_text=(
            "Docker container cannot reach the host service on host.docker.internal port 8000. "
            "TCP connection is refused from inside the container."
        ),
        predicted_domain="cn",
        ranked_tags=(("docker", 0.9), ("tcp", 0.8), ("networking", 0.7)),
        expected_public_domain="networking",
        primary_path_keywords=("platform", "service", "reachability", "network", "container"),
        first_step_keywords=("service", "port", "network", "policy"),
        reference_keywords=("docker", "tcp", "routing", "kubernetes"),
        forbidden_drift=("jwt", "cors", "postgresql", "cuda"),
    ),
    DiagnosticQualityCase(
        case_id="firewall_security_group_port",
        problem_text=(
            "Security group firewall blocks TCP port 8443 after a network rule change. "
            "Clients time out before reaching the service listener."
        ),
        predicted_domain="cn",
        ranked_tags=(("tcp", 0.85), ("networking", 0.8), ("routing", 0.65)),
        expected_public_domain="networking",
        primary_path_keywords=("platform", "service", "reachability", "network", "port"),
        first_step_keywords=("port", "network", "policy", "service"),
        reference_keywords=("tcp", "routing", "network", "protocol"),
        forbidden_drift=("jwt", "cors", "postgresql schema", "cuda"),
    ),
    DiagnosticQualityCase(
        case_id="load_balancer_health_check_path",
        problem_text=(
            "Load balancer health checks fail after the health check path changed from /health to /ready. "
            "Healthy pods are marked unhealthy."
        ),
        predicted_domain="cn",
        ranked_tags=(("proxy", 0.75), ("http", 0.7), ("routing", 0.65)),
        expected_public_domain="networking",
        primary_path_keywords=("health", "check", "path", "upstream", "readiness"),
        first_step_keywords=("health", "check", "path", "route"),
        reference_keywords=("proxy", "nginx", "http", "load"),
        forbidden_drift=("jwt", "cors preflight", "postgresql", "cuda"),
    ),
    DiagnosticQualityCase(
        case_id="kubernetes_service_mapping",
        problem_text=(
            "Kubernetes ingress routes traffic to the wrong pod after a rollout. "
            "Service endpoints and selectors changed, and some pods are unreachable from the namespace."
        ),
        predicted_domain="cn",
        ranked_tags=(("kubernetes", 0.93), ("ingress", 0.82), ("routing", 0.64)),
        expected_public_domain="networking",
        primary_path_keywords=("kubernetes", "service", "ingress", "pod", "endpoint"),
        first_step_keywords=("service", "endpoint", "ingress", "pod", "namespace"),
        reference_keywords=("kubernetes", "ingress", "docker", "routing"),
        forbidden_drift=("jwt", "cors preflight", "postgresql", "cuda"),
    ),
    DiagnosticQualityCase(
        case_id="model_serving_tokenizer",
        problem_text=(
            "Hugging Face model-serving endpoint fails after a checkpoint update. "
            "The tokenizer config and model weights do not match and generation errors before inference completes."
        ),
        predicted_domain="ai",
        ranked_tags=(("model-serving", 0.92), ("huggingface-transformers", 0.84), ("inference", 0.7)),
        expected_public_domain="ai",
        primary_path_keywords=("model", "serving", "tokenizer", "checkpoint", "runtime"),
        first_step_keywords=("model", "tokenizer", "checkpoint", "serving"),
        reference_keywords=("model", "serving", "huggingface", "transformers", "inference"),
        forbidden_drift=("jwt", "cors", "dns resolver", "postgresql schema"),
    ),
    DiagnosticQualityCase(
        case_id="model_serving_stale_checkpoint",
        problem_text=(
            "Model serving endpoint still loads the old checkpoint after deployment. "
            "The served model version differs from the new artifact in storage."
        ),
        predicted_domain="ai",
        ranked_tags=(("model-serving", 0.9), ("inference", 0.72), ("huggingface-transformers", 0.65)),
        expected_public_domain="ai",
        primary_path_keywords=("model", "checkpoint", "version", "artifact", "serving"),
        first_step_keywords=("model", "artifact", "runtime", "serving"),
        reference_keywords=("model", "serving", "transformers", "inference"),
        forbidden_drift=("cors", "csrf", "sql schema", "tls"),
    ),
    DiagnosticQualityCase(
        case_id="rag_retrieval_empty_results",
        problem_text=(
            "RAG answers are empty after rebuilding the vector store. "
            "The retrieval pipeline returns no documents and embedding dimensions differ from the index."
        ),
        predicted_domain="ai",
        ranked_tags=(("rag", 0.94), ("embeddings", 0.86), ("vector-database", 0.8)),
        expected_public_domain="ai",
        primary_path_keywords=("retrieval", "embedding", "vector", "index", "rag"),
        first_step_keywords=("retrieval", "embedding", "vector", "index"),
        reference_keywords=("rag", "embedding", "vector", "sentence-transformers"),
        forbidden_drift=("jwt", "cors", "dns", "tls certificate"),
    ),
    DiagnosticQualityCase(
        case_id="pytorch_tensor_shape",
        problem_text=(
            "PyTorch inference crashes with tensor shape mismatch. "
            "The batch input has unexpected dimensions and mat1 and mat2 shapes cannot be multiplied."
        ),
        predicted_domain="ai",
        ranked_tags=(("pytorch", 0.93), ("numpy", 0.72), ("machine-learning", 0.55)),
        expected_public_domain="ai",
        primary_path_keywords=("tensor", "shape", "dimension", "input", "pytorch"),
        first_step_keywords=("tensor", "shape", "dimension", "input", "batch"),
        reference_keywords=("pytorch", "tensor", "gpu", "inference"),
        forbidden_drift=("jwt", "cors", "dns", "postgresql"),
    ),
    DiagnosticQualityCase(
        case_id="cuda_gpu_oom",
        problem_text=(
            "Inference job fails with CUDA out of memory on the GPU. "
            "VRAM spikes when batch size increases and the model server falls back under load."
        ),
        predicted_domain="ai",
        ranked_tags=(("cuda", 0.96), ("gpu", 0.9), ("pytorch", 0.72)),
        expected_public_domain="ai",
        primary_path_keywords=("gpu", "cuda", "memory", "vram", "batch"),
        first_step_keywords=("gpu", "cuda", "memory", "vram", "batch"),
        reference_keywords=("cuda", "gpu", "pytorch", "tensorflow"),
        forbidden_drift=("jwt", "cors", "dns resolver", "postgresql"),
    ),
]


def _stage_1_for(case: DiagnosticQualityCase) -> dict:
    return {
        "predicted_domain": case.predicted_domain,
        "top_tags": [tag for tag, _confidence in case.ranked_tags],
        "tag_confidences": {tag: confidence for tag, confidence in case.ranked_tags},
        "ranked_tags": [
            {"tag": tag, "confidence": confidence}
            for tag, confidence in case.ranked_tags
        ],
    }


def _as_dict(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(keyword.lower() in lowered for keyword in keywords)


def _result_text(result) -> str:
    result_data = _as_dict(result)
    parts = [
        result_data.get("primary_path", ""),
        " ".join(result_data.get("alternative_paths", [])),
        " ".join(result_data.get("possible_causes", [])),
    ]
    for step in result_data.get("diagnostic_checklist", []):
        parts.extend(
            [
                step.get("title", ""),
                step.get("action", ""),
                step.get("expected", ""),
                step.get("if_this_fails", ""),
                step.get("reference", {}).get("title", ""),
                step.get("reference", {}).get("url", ""),
            ]
        )
    for reference in result_data.get("references_summary", []):
        parts.extend([reference.get("title", ""), reference.get("url", ""), reference.get("source_type", "")])
    return " ".join(parts).lower()


@pytest.mark.parametrize("case", QUALITY_CASES, ids=[case.case_id for case in QUALITY_CASES])
def test_diagnostic_quality_cases_cover_expected_paths(monkeypatch, case):
    monkeypatch.setattr(pipeline, "predict_top_3_tags", lambda _problem_text: _stage_1_for(case))

    from app.services.presentation import adapt_result_for_display
    output = pipeline.run_existing_pipeline(
        DiagnoseRequest(problem_text=case.problem_text, display_level="expert")
    )
    result = output["result"]
    display_result = adapt_result_for_display(result, output, display_level="expert", debug_mode=False)
    
    result_data = _as_dict(result)
    checklist = result_data["diagnostic_checklist"]
    references_summary = result_data["references_summary"]

    assert output["stage_1_interpretation"]["active_domain"] == case.predicted_domain
    assert display_result["domain"] == case.expected_public_domain

    assert _contains_any(result_data["primary_path"], case.primary_path_keywords)

    first_step = checklist[0]
    first_step_text = " ".join(
        [
            first_step["title"],
            first_step["action"],
            first_step["expected"],
            first_step["if_this_fails"],
        ]
    )
    assert _contains_any(first_step_text, case.first_step_keywords)

    distinct_causes = {" ".join(cause.lower().split()) for cause in result_data["possible_causes"]}
    assert len(distinct_causes) >= 3

    assert 4 <= len(checklist) <= 6
    assert 1 <= len(references_summary) <= 5

    reference_text = " ".join(
        [
            *(f"{item['title']} {item['url']} {item['source_type']}" for item in references_summary),
            *(f"{step['reference']['title']} {step['reference']['url']} {step['reference']['source_type']}" for step in checklist),
        ]
    )
    assert _contains_any(reference_text, case.reference_keywords)
    for reference in references_summary:
        assert reference["title"].strip()
        assert reference["url"].startswith(("http://", "https://"))
        assert reference["source_type"].strip()

    combined_output_text = _result_text(result)
    for forbidden in case.forbidden_drift:
        assert forbidden.lower() not in combined_output_text


def _strip_boundary_suffix(title: str) -> str:
    """Strip trailing boundary-label phrase for dedup comparison."""
    import re
    return re.sub(
        r'\s+(?:across|at|around|through)\s+the\s+[\w\s-]+?\s*boundary\s*$',
        '',
        title,
        flags=re.IGNORECASE,
    ).strip()


def test_cors_possible_causes_no_boundary_duplicates(monkeypatch):
    """CORS preflight cases must not contain near-duplicate causes that differ
    only by their trailing boundary label."""
    case = DiagnosticQualityCase(
        case_id="cors_react_fastapi_preflight",
        problem_text=(
            "React frontend gets blocked by CORS when calling a FastAPI backend. "
            "The browser sends an Authorization Bearer token, and the OPTIONS "
            "preflight returns 400 without Access-Control-Allow-Headers."
        ),
        predicted_domain="sw",
        ranked_tags=(("cors", 0.95), ("reactjs", 0.82), ("fastapi", 0.72)),
        expected_public_domain="software",
        primary_path_keywords=("cors", "preflight", "options", "origin"),
        first_step_keywords=("cors", "preflight", "origin", "allowlist"),
        reference_keywords=("cors", "http", "fastapi"),
        forbidden_drift=("gpu", "cuda", "embedding", "vector", "database", "postgresql"),
    )
    monkeypatch.setattr(pipeline, "predict_top_3_tags", lambda _problem_text: _stage_1_for(case))

    output = pipeline.run_existing_pipeline(
        DiagnoseRequest(problem_text=case.problem_text, display_level="expert")
    )
    result = output["result"]
    result_data = _as_dict(result)
    causes = result_data["possible_causes"]

    # At least 4 distinct causes.
    assert len(causes) >= 4

    # No two causes may differ only by boundary label.
    stripped = [_strip_boundary_suffix(c) for c in causes]
    stripped_lower = [" ".join(s.lower().split()) for s in stripped]
    assert len(set(stripped_lower)) == len(stripped_lower), (
        f"Near-duplicate boundary-only causes found: {causes}"
    )

    # At least 3 causes should be CORS-specific (mention cors, preflight,
    # origin, allowlist, access-control, or credentials).
    cors_keywords = {"cors", "preflight", "origin", "allowlist", "access-control", "credentials", "credentialed"}
    cors_count = sum(
        1 for c in causes
        if any(kw in c.lower() for kw in cors_keywords)
    )
    assert cors_count >= 3, (
        f"Expected >= 3 CORS-specific causes, got {cors_count}: {causes}"
    )

    # Forbidden: more than one auth-metadata boundary variant.
    auth_meta_causes = [c for c in causes if "auth metadata" in c.lower()]
    assert len(auth_meta_causes) <= 1, (
        f"Too many auth-metadata boundary variants: {auth_meta_causes}"
    )
