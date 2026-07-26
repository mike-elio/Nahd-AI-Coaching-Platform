import csv
import re
from functools import lru_cache
from pathlib import Path

from app.config import VALID_DOMAINS

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"

REFERENCE_FILE_BY_DOMAIN = {
    "software": DATA_DIR / "software_reference_links_100.csv",
    "networking": DATA_DIR / "networking_reference_links_100.csv",
    "ai": DATA_DIR / "ai_reference_links_100.csv",
}

DOMAIN_REFERENCE_TAG_ALIASES = {
    "software": {
        "authentication": ["auth", "fastapi", "django"],
        "authorization": ["auth", "fastapi", "django"],
        "jwt": ["auth", "fastapi", "django"],
        "oauth-2.0": ["auth", "fastapi", "django"],
        "fastapi": ["fastapi", "auth"],
        "django": ["django", "auth"],
        "flask": ["flask", "python"],
        "express": ["express", "node.js"],
        "spring-boot": ["spring-boot", "java"],
        "asp.net-core": ["asp.net-core", "c#"],
        "reactjs": ["reactjs", "javascript"],
        "javascript": ["javascript", "reactjs"],
        "typescript": ["typescript", "javascript", "reactjs"],
        "node.js": ["node.js", "javascript"],
        "python": ["python", "fastapi", "django"],
        "java": ["java", "spring-boot"],
        "c#": ["c#", "asp.net-core"],
        "html": ["html/css", "javascript"],
        "css": ["html/css", "javascript"],
        "cors": ["fastapi", "reactjs", "javascript", "auth", "rest"],
        "rest": ["rest", "fastapi", "reactjs"],
        "sql": ["sql"],
        "postgresql": ["sql", "fastapi", "django"],
        "mysql": ["sql", "fastapi", "django"],
        "redis": ["sql"],
        "git": ["git"],
        "logging": ["python"],
        "debugging": ["python"],
    },
    "networking": {
        "networking": ["tcp/routing", "linux/ubuntu/bash/ssh"],
        "dns": ["dns", "tcp/routing"],
        "ssl": ["ssl/tls", "nginx/proxy/load-balancing/ssl", "apache/proxy/ssl"],
        "tls": ["ssl/tls", "nginx/proxy/load-balancing/ssl", "apache/proxy/ssl"],
        "tcp": ["tcp/routing"],
        "http": ["http/cors/proxy", "nginx/proxy/load-balancing/ssl", "proxy/reverse-proxy/load-balancing"],
        "cors": ["http/cors/proxy", "nginx/proxy/load-balancing/ssl"],
        "proxy": ["proxy/reverse-proxy/load-balancing", "nginx/proxy/load-balancing/ssl", "apache/proxy/ssl", "http/cors/proxy"],
        "reverse-proxy": ["proxy/reverse-proxy/load-balancing", "nginx/proxy/load-balancing/ssl", "apache/proxy/ssl"],
        "nginx": ["nginx/proxy/load-balancing/ssl", "http/cors/proxy"],
        "apache": ["apache/proxy/ssl", "http/cors/proxy"],
        "load-balancing": ["nginx/proxy/load-balancing/ssl", "proxy/reverse-proxy/load-balancing"],
        "routing": ["tcp/routing", "proxy/reverse-proxy/load-balancing"],
        "firewall": ["firewall/security", "tcp/routing"],
        "ingress": ["kubernetes/ingress", "nginx/proxy/load-balancing/ssl"],
        "kubernetes": ["kubernetes/ingress", "docker"],
        "docker": ["docker", "kubernetes/ingress"],
        "linux": ["linux/ubuntu/bash/ssh"],
        "ubuntu": ["linux/ubuntu/bash/ssh"],
        "bash": ["linux/ubuntu/bash/ssh"],
        "ssh": ["linux/ubuntu/bash/ssh"],
        "vpn": ["vpn"],
        "azure": ["azure"],
    },
    "ai": {
        "pytorch": ["pytorch", "gpu/cuda/inference"],
        "tensorflow": ["tensorflow", "gpu/cuda/inference"],
        "scikit-learn": ["scikit-learn"],
        "numpy": ["numpy"],
        "pandas": ["pandas"],
        "opencv": ["opencv/computer-vision"],
        "computer-vision": ["opencv/computer-vision"],
        "nlp": ["huggingface-transformers/nlp/llm", "rag/llm/nlp"],
        "huggingface-transformers": ["huggingface-transformers/nlp/llm", "sentence-transformers/embeddings"],
        "large-language-model": ["huggingface-transformers/nlp/llm", "rag/llm/nlp", "llm/embeddings/fine-tuning"],
        "sentence-transformers": ["sentence-transformers/embeddings", "huggingface-transformers/nlp/llm"],
        "rag": ["rag/llm/nlp", "vector-database/embeddings", "llm/embeddings/fine-tuning"],
        "embeddings": ["sentence-transformers/embeddings", "vector-database/embeddings", "llm/embeddings/fine-tuning"],
        "vector-database": ["vector-database/embeddings", "rag/llm/nlp"],
        "model-serving": ["model-serving/inference", "huggingface-transformers/nlp/llm"],
        "inference": ["model-serving/inference", "gpu/cuda/inference", "pytorch"],
        "gpu": ["gpu/cuda/inference", "pytorch", "tensorflow"],
        "cuda": ["gpu/cuda/inference", "pytorch", "tensorflow"],
        "mlops": ["mlops", "model-serving/inference"],
        "fine-tuning": ["fine-tuning", "llm/embeddings/fine-tuning"],
        "machine-learning": ["scikit-learn", "tensorflow", "pytorch"],
        "deep-learning": ["tensorflow", "pytorch", "gpu/cuda/inference"],
        "misc-ai": ["misc-ai"],
    },
}

ISSUE_FAMILY_REFERENCE_ALIASES = {
    "authentication": ["auth", "fastapi", "django"],
    "authorization_policy": ["auth", "fastapi", "django"],
    "session_identity_boundary": ["auth", "reactjs", "javascript"],
    "cors_proxy_boundary": ["http/cors/proxy", "nginx/proxy/load-balancing/ssl", "fastapi", "reactjs"],
    "http_routing_misconfiguration": ["proxy/reverse-proxy/load-balancing", "nginx/proxy/load-balancing/ssl", "kubernetes/ingress", "rest"],
    "database_connectivity": ["sql", "vector-database/embeddings"],
    "cache_session_store": ["sql", "auth"],
    "container_networking": ["kubernetes/ingress", "docker", "tcp/routing"],
    "dns_service_discovery": ["dns", "tcp/routing"],
    "tls_edge_termination": ["ssl/tls", "nginx/proxy/load-balancing/ssl", "apache/proxy/ssl"],
    "model_serving_runtime": ["model-serving/inference", "huggingface-transformers/nlp/llm", "pytorch"],
    "retrieval_embeddings_pipeline": ["rag/llm/nlp", "sentence-transformers/embeddings", "vector-database/embeddings"],
    "gpu_inference_runtime": ["gpu/cuda/inference", "pytorch", "tensorflow"],
}

CLUSTER_REFERENCE_ALIASES = {
    "auth_identity_flow": ["auth", "fastapi", "django", "reactjs"],
    "http_proxy_edge": ["http/cors/proxy", "nginx/proxy/load-balancing/ssl", "proxy/reverse-proxy/load-balancing"],
    "database_connectivity_stack": ["sql", "vector-database/embeddings"],
    "container_network_surface": ["kubernetes/ingress", "docker", "tcp/routing"],
    "tls_dns_transport": ["dns", "ssl/tls", "tcp/routing"],
    "model_serving_pipeline": ["model-serving/inference", "huggingface-transformers/nlp/llm", "sentence-transformers/embeddings"],
    "gpu_acceleration_stack": ["gpu/cuda/inference", "pytorch", "tensorflow"],
}

BOUNDARY_REFERENCE_ALIASES = {
    "browser_boundary": ["reactjs", "javascript", "http/cors/proxy", "auth"],
    "proxy_boundary": ["nginx/proxy/load-balancing/ssl", "proxy/reverse-proxy/load-balancing", "apache/proxy/ssl", "http/cors/proxy"],
    "runtime_boundary": ["fastapi", "django", "python", "pytorch", "model-serving/inference"],
    "database_boundary": ["sql", "vector-database/embeddings"],
    "network_transport_boundary": ["dns", "tcp/routing", "ssl/tls"],
    "model_serving_boundary": ["model-serving/inference", "huggingface-transformers/nlp/llm", "sentence-transformers/embeddings"],
    "gpu_inference_boundary": ["gpu/cuda/inference", "pytorch", "tensorflow"],
    "deployment_change_hint": ["docker", "kubernetes/ingress", "mlops", "fastapi"],
}

SEMANTIC_KEY_REFERENCE_ALIASES = {
    "capture_primary_symptom": [],
    "confirm_runtime_target": ["fastapi", "django", "python", "docker", "kubernetes/ingress", "model-serving/inference"],
    "auth_artifact_integrity": ["auth", "fastapi", "django"],
    "auth_claim_validation": ["auth", "fastapi", "django"],
    "authorization_policy_check": ["auth", "fastapi", "django"],
    "session_cookie_boundary": ["auth", "reactjs", "javascript", "fastapi", "django"],
    "replay_preflight_origin": ["http/cors/proxy", "nginx/proxy/load-balancing/ssl", "fastapi", "reactjs"],
    "upstream_route_validation": ["nginx/proxy/load-balancing/ssl", "proxy/reverse-proxy/load-balancing", "kubernetes/ingress", "rest"],
    "database_runtime_reachability": ["sql", "vector-database/embeddings"],
    "database_target_runtime_config": ["sql", "django", "python"],
    "cache_session_consistency": ["auth", "sql"],
    "platform_service_path": ["kubernetes/ingress", "docker", "tcp/routing"],
    "runtime_dns_resolution": ["dns", "tcp/routing"],
    "tls_chain_validation": ["ssl/tls", "nginx/proxy/load-balancing/ssl", "apache/proxy/ssl"],
    "model_runtime_validation": ["model-serving/inference", "huggingface-transformers/nlp/llm", "pytorch"],
    "retrieval_vector_alignment": ["rag/llm/nlp", "sentence-transformers/embeddings", "vector-database/embeddings"],
    "gpu_runtime_pressure": ["gpu/cuda/inference", "pytorch", "tensorflow"],
    "browser_request_shape": ["reactjs", "javascript", "http/cors/proxy"],
    "proxy_forwarding_alignment": ["nginx/proxy/load-balancing/ssl", "proxy/reverse-proxy/load-balancing", "apache/proxy/ssl"],
    "database_contract_boundary": ["sql", "vector-database/embeddings"],
    "transport_hop_validation": ["dns", "tcp/routing", "ssl/tls"],
    "model_serving_branch": ["model-serving/inference", "huggingface-transformers/nlp/llm"],
    "gpu_workload_shape": ["gpu/cuda/inference", "pytorch", "tensorflow"],
    "deployment_regression_check": ["docker", "kubernetes/ingress", "mlops"],
    "fastapi_dependency_path": ["fastapi", "python", "auth"],
    "django_security_runtime": ["django", "auth"],
    "jwt_claim_integrity": ["auth", "fastapi", "django"],
    "cors_origin_alignment": ["http/cors/proxy", "fastapi", "reactjs"],
    "react_request_construction": ["reactjs", "javascript"],
    "nginx_edge_directives": ["nginx/proxy/load-balancing/ssl", "http/cors/proxy"],
    "proxy_header_boundary": ["proxy/reverse-proxy/load-balancing", "nginx/proxy/load-balancing/ssl", "apache/proxy/ssl"],
    "dns_answer_validation": ["dns", "tcp/routing"],
    "postgresql_schema_state": ["sql"],
    "mysql_target_contract": ["sql"],
    "redis_state_path": ["sql", "auth"],
    "docker_runtime_context": ["docker", "kubernetes/ingress"],
    "kubernetes_service_mapping": ["kubernetes/ingress", "docker"],
    "serving_endpoint_mode": ["model-serving/inference", "huggingface-transformers/nlp/llm"],
    "rag_retrieval_path": ["rag/llm/nlp", "vector-database/embeddings"],
    "embedding_shape_profile": ["sentence-transformers/embeddings", "vector-database/embeddings", "gpu/cuda/inference"],
    "pytorch_runtime_alignment": ["pytorch", "gpu/cuda/inference"],
    "tensor_shape_capture": ["pytorch", "gpu/cuda/inference", "model-serving/inference"],
    "tensor_conversion_validation": ["pytorch", "numpy"],
    "cuda_capacity_check": ["gpu/cuda/inference", "pytorch", "tensorflow"],
    "gpu_utilization_check": ["gpu/cuda/inference", "pytorch", "tensorflow"],
    "cluster_auth_flow_alignment": ["auth", "fastapi", "django", "reactjs"],
    "cluster_http_edge_alignment": ["http/cors/proxy", "nginx/proxy/load-balancing/ssl", "proxy/reverse-proxy/load-balancing"],
    "cluster_container_surface": ["kubernetes/ingress", "docker", "tcp/routing"],
    "cluster_model_serving_pipeline": ["model-serving/inference", "sentence-transformers/embeddings", "rag/llm/nlp"],
    "retest_after_change": [],
}

SEMANTIC_REQUIRED_REFERENCE_TAGS = {
    "replay_preflight_origin": {"fastapi", "auth", "rest"},
    "cors_origin_alignment": {"fastapi", "auth", "rest"},
    "react_request_construction": {"reactjs", "javascript"},
    "browser_request_shape": {"reactjs", "javascript"},
    "auth_artifact_integrity": {"auth", "fastapi", "django"},
    "auth_claim_validation": {"auth", "fastapi", "django"},
    "authorization_policy_check": {"auth", "fastapi", "django"},
    "jwt_claim_integrity": {"auth", "fastapi", "django"},
    "session_cookie_boundary": {"auth", "reactjs", "django", "fastapi"},
    "runtime_dns_resolution": {"dns", "tcp/routing"},
    "dns_answer_validation": {"dns", "tcp/routing"},
    "tls_chain_validation": {"ssl/tls", "nginx/proxy/load-balancing/ssl", "apache/proxy/ssl"},
    "postgresql_schema_state": {"sql"},
    "mysql_target_contract": {"sql"},
    "database_contract_boundary": {"sql", "vector-database/embeddings"},
    "database_target_runtime_config": {"sql", "django", "python"},
    "rag_retrieval_path": {"rag/llm/nlp", "vector-database/embeddings", "sentence-transformers/embeddings"},
    "retrieval_vector_alignment": {"rag/llm/nlp", "vector-database/embeddings", "sentence-transformers/embeddings"},
    "embedding_shape_profile": {"sentence-transformers/embeddings", "vector-database/embeddings", "gpu/cuda/inference"},
    "cuda_capacity_check": {"gpu/cuda/inference", "pytorch", "tensorflow"},
    "gpu_runtime_pressure": {"gpu/cuda/inference", "pytorch", "tensorflow"},
    "gpu_workload_shape": {"gpu/cuda/inference", "pytorch", "tensorflow"},
    "gpu_utilization_check": {"gpu/cuda/inference", "pytorch", "tensorflow"},
    "tensor_shape_capture": {"pytorch", "gpu/cuda/inference", "model-serving/inference"},
    "tensor_conversion_validation": {"pytorch", "numpy"},
    "model_runtime_validation": {"model-serving/inference", "huggingface-transformers/nlp/llm", "pytorch"},
    "serving_endpoint_mode": {"model-serving/inference", "huggingface-transformers/nlp/llm", "pytorch"},
    "model_serving_branch": {"model-serving/inference", "huggingface-transformers/nlp/llm"},
}

SEMANTIC_TITLE_HINTS = {
    "replay_preflight_origin": {"cors", "origin", "cross-origin"},
    "cors_origin_alignment": {"cors", "origin", "cross-origin"},
    "react_request_construction": {"react", "reference"},
    "browser_request_shape": {"react", "reference"},
    "auth_claim_validation": {"jwt", "oauth", "auth"},
    "jwt_claim_integrity": {"jwt", "oauth", "auth"},
    "authorization_policy_check": {"authorization", "auth"},
    "runtime_dns_resolution": {"dns"},
    "dns_answer_validation": {"dns"},
    "tls_chain_validation": {"tls", "ssl", "certificate"},
    "postgresql_schema_state": {"postgresql", "sql"},
    "mysql_target_contract": {"mysql", "sql"},
    "database_target_runtime_config": {"database", "hostname", "secret", "postgresql", "mysql"},
    "rag_retrieval_path": {"retrieval", "rag"},
    "retrieval_vector_alignment": {"retrieval", "vector", "embedding"},
    "embedding_shape_profile": {"embedding", "vector"},
    "cuda_capacity_check": {"cuda", "gpu"},
    "gpu_utilization_check": {"gpu", "cuda"},
    "model_runtime_validation": {"serving", "inference", "model"},
    "serving_endpoint_mode": {"serving", "inference", "model"},
    "tensor_shape_capture": {"tensor", "shape", "dimension", "forward", "layer"},
    "tensor_conversion_validation": {"numpy", "conversion", "dtype", "layout"},
}

REFERENCE_SOURCE_PRIORITY = {
    "official_docs": 100,
    "security_guidance": 95,
    "protocol_reference": 93,
    "vendor_docs": 90,
    "library_docs": 88,
}

DOMAIN_SOURCE_BONUS = {
    "software": {
        "official_docs": 18,
        "security_guidance": 16,
        "library_docs": 14,
        "vendor_docs": 8,
        "protocol_reference": 8,
    },
    "networking": {
        "protocol_reference": 18,
        "vendor_docs": 16,
        "official_docs": 12,
        "security_guidance": 12,
        "library_docs": 4,
    },
    "ai": {
        "library_docs": 18,
        "official_docs": 16,
        "vendor_docs": 10,
        "security_guidance": 8,
        "protocol_reference": 4,
    },
}

STEP_PURPOSE_SOURCE_BONUS = {
    "capture": {
        "official_docs": 10,
        "protocol_reference": 4,
        "vendor_docs": 4,
    },
    "boundary": {
        "protocol_reference": 14,
        "vendor_docs": 12,
        "official_docs": 8,
        "security_guidance": 8,
    },
    "hypothesis": {
        "official_docs": 12,
        "security_guidance": 12,
        "library_docs": 10,
        "vendor_docs": 8,
        "protocol_reference": 6,
    },
    "secondary": {
        "official_docs": 10,
        "vendor_docs": 10,
        "protocol_reference": 9,
        "library_docs": 9,
        "security_guidance": 8,
    },
    "runtime": {
        "vendor_docs": 12,
        "library_docs": 12,
        "official_docs": 10,
        "security_guidance": 8,
        "protocol_reference": 6,
    },
    "closure": {
        "official_docs": 10,
        "vendor_docs": 6,
        "protocol_reference": 4,
    },
}

BASELINE_ALLOWED_REFERENCE_TAGS = {
    "software": ["fastapi", "python", "auth", "rest"],
    "networking": ["http/cors/proxy", "dns", "tcp/routing", "nginx/proxy/load-balancing/ssl"],
    "ai": ["model-serving/inference", "pytorch", "huggingface-transformers/nlp/llm"],
}

SYMPTOM_REFERENCE_ALIASES = {
    "preflight_failure": ["http/cors/proxy", "fastapi", "reactjs", "nginx/proxy/load-balancing/ssl"],
    "missing_cors_headers": ["http/cors/proxy", "fastapi", "reactjs", "nginx/proxy/load-balancing/ssl"],
    "browser_only_failure": ["reactjs", "javascript", "http/cors/proxy"],
    "csrf_or_cookie_failure": ["auth", "reactjs", "fastapi", "django"],
    "authn_failure": ["auth", "fastapi", "django"],
    "authz_failure": ["auth", "fastapi", "django"],
    "upstream_failure": ["nginx/proxy/load-balancing/ssl", "proxy/reverse-proxy/load-balancing", "kubernetes/ingress"],
    "connection_refused": ["tcp/routing", "dns", "sql", "vector-database/embeddings"],
    "timeout_failure": ["tcp/routing", "dns", "nginx/proxy/load-balancing/ssl", "gpu/cuda/inference", "model-serving/inference"],
    "tls_failure": ["ssl/tls", "nginx/proxy/load-balancing/ssl", "apache/proxy/ssl"],
    "dns_failure": ["dns", "tcp/routing", "kubernetes/ingress"],
    "schema_contract_failure": ["sql", "vector-database/embeddings", "sentence-transformers/embeddings"],
    "tokenizer_runtime_mismatch": ["model-serving/inference", "huggingface-transformers/nlp/llm", "pytorch"],
    "embedding_vector_mismatch": ["sentence-transformers/embeddings", "vector-database/embeddings", "rag/llm/nlp"],
    "cuda_oom": ["gpu/cuda/inference", "pytorch", "tensorflow"],
    "tensor_shape_mismatch": ["pytorch", "gpu/cuda/inference", "model-serving/inference"],
}

SYMPTOM_SOURCE_HINTS = {
    "preflight_failure": {"protocol_reference", "library_docs"},
    "missing_cors_headers": {"protocol_reference", "library_docs"},
    "csrf_or_cookie_failure": {"security_guidance", "library_docs"},
    "authn_failure": {"security_guidance", "library_docs"},
    "authz_failure": {"security_guidance", "library_docs"},
    "upstream_failure": {"vendor_docs", "protocol_reference"},
    "timeout_failure": {"vendor_docs", "protocol_reference", "library_docs"},
    "tls_failure": {"protocol_reference", "vendor_docs", "security_guidance"},
    "dns_failure": {"protocol_reference", "vendor_docs"},
    "schema_contract_failure": {"official_docs", "library_docs", "vendor_docs"},
    "tokenizer_runtime_mismatch": {"library_docs"},
    "embedding_vector_mismatch": {"library_docs", "vendor_docs"},
    "cuda_oom": {"library_docs", "vendor_docs"},
    "tensor_shape_mismatch": {"library_docs"},
}


def collapse_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", str(value).strip())


def tokenize_keywords(*values: str) -> set[str]:
    keywords = set()
    for value in values:
        text = str(value).lower()
        for token in re.findall(r"[a-z0-9]+", text):
            if len(token) >= 3:
                keywords.add(token)
    return keywords


def infer_reference_source_type(reference_row: dict) -> str:
    title = str(reference_row.get("title", "")).lower()
    tag = str(reference_row.get("tag", "")).lower()
    url = str(reference_row.get("url", "")).lower()
    url_keywords = " ".join(part for part in tokenize_keywords(url.replace("https://", "").replace("http://", "")))
    haystack = " ".join([title, tag, url_keywords])

    if any(token in haystack for token in ("owasp", "security", "secure", "jwt", "auth", "oauth", "csrf", "xss")):
        return "security_guidance"
    if any(token in haystack for token in ("rfc", "ietf", "protocol", "dns", "tcp", "cors", "tls", "ssl", "certificate")):
        return "protocol_reference"
    if any(token in haystack for token in ("readthedocs", "pypi", "package", "sdk", "pytorch", "tensorflow", "huggingface", "transformers", "python", "fastapi", "django", "react")):
        return "library_docs"
    if any(token in haystack for token in ("nginx", "apache", "docker", "kubernetes", "redis", "postgresql", "mysql", "ubuntu", "azure", "vendor")):
        return "vendor_docs"
    return "official_docs"


@lru_cache(maxsize=None)
def load_reference_rows(domain: str) -> list[dict]:
    normalized_domain = str(domain).strip().lower()

    # Accept both canonical API codes and reasoning-domain names.
    domain_to_file_key = {
        "sw": "software",
        "software": "software",
        "cn": "networking",
        "networking": "networking",
        "ai": "ai",
    }

    file_key = domain_to_file_key.get(normalized_domain)
    if file_key is None:
        raise ValueError(f"Unsupported reference domain: {domain}")

    path = REFERENCE_FILE_BY_DOMAIN[file_key]
    if not path.exists():
        raise FileNotFoundError(f"Reference file not found for domain '{normalized_domain}'. Expected CSV at: {path}")

    rows = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row_domain = str(row.get("domain", "")).strip().lower()
            row_tag = str(row.get("tag", "")).strip().lower()
            row_title = collapse_whitespace(row.get("title", ""))
            row_url = collapse_whitespace(row.get("url", ""))

            if row_domain != file_key or not row_tag or not row_title or not row_url:
                continue

            source_type = infer_reference_source_type(row)
            rows.append(
                {
                    "domain": file_key,
                    "tag": row_tag,
                    "title": row_title,
                    "url": row_url,
                    "source_type": source_type,
                    "keywords": tokenize_keywords(row_title, row_tag, row_url),
                }
            )

    if not rows:
        raise ValueError(f"No usable references found in {path} for domain '{normalized_domain}'.")

    return rows


__all__ = [
    "BASE_DIR",
    "DATA_DIR",
    "REFERENCE_FILE_BY_DOMAIN",
    "DOMAIN_REFERENCE_TAG_ALIASES",
    "ISSUE_FAMILY_REFERENCE_ALIASES",
    "CLUSTER_REFERENCE_ALIASES",
    "BOUNDARY_REFERENCE_ALIASES",
    "SEMANTIC_KEY_REFERENCE_ALIASES",
    "SEMANTIC_REQUIRED_REFERENCE_TAGS",
    "SEMANTIC_TITLE_HINTS",
    "REFERENCE_SOURCE_PRIORITY",
    "DOMAIN_SOURCE_BONUS",
    "STEP_PURPOSE_SOURCE_BONUS",
    "BASELINE_ALLOWED_REFERENCE_TAGS",
    "SYMPTOM_REFERENCE_ALIASES",
    "SYMPTOM_SOURCE_HINTS",
    "collapse_whitespace",
    "tokenize_keywords",
    "infer_reference_source_type",
    "load_reference_rows",
]
