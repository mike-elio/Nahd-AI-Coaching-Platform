DIRECT_SYMPTOM_RULES = {
    "preflight_failure": {
        "keywords": {"options", "preflight", "origin", "cors"},
        "phrases": {"preflight request", "options preflight", "blocked by cors policy"},
    },
    "missing_cors_headers": {
        "keywords": {"origin", "credentials", "authorization"},
        "phrases": {
            "access-control-allow-origin",
            "access-control-allow-credentials",
            "access-control-allow-headers",
            "access-control-allow-methods",
            "request header field authorization is not allowed",
        },
    },
    "browser_only_failure": {
        "keywords": {"browser", "frontend", "curl", "postman"},
        "phrases": {"works in curl", "fails only in browser", "works in postman", "only in browser"},
    },
    "csrf_or_cookie_failure": {
        "keywords": {"csrf", "cookie", "cookies", "session", "samesite", "credentials"},
        "phrases": {"csrf failed", "csrf token", "same site", "same-site", "credentials include"},
    },
    "authn_failure": {
        "keywords": {"401", "unauthorized", "issuer", "audience", "signature", "expired"},
        "phrases": {"invalid token", "token expired", "missing token", "invalid issuer", "invalid audience", "invalid signature"},
    },
    "authz_failure": {
        "keywords": {"403", "forbidden", "scope", "role", "permission", "claims"},
        "phrases": {"access denied", "insufficient scope", "missing scope", "permission denied"},
    },
    "upstream_failure": {
        "keywords": {"502", "503", "504", "upstream", "gateway", "backend"},
        "phrases": {"bad gateway", "service unavailable", "upstream timed out", "upstream prematurely closed connection"},
    },
    "connection_refused": {
        "keywords": {"refused", "econnrefused", "unreachable", "noroute"},
        "phrases": {"connection refused", "failed to connect", "no route to host", "connection reset by peer"},
    },
    "timeout_failure": {
        "keywords": {"408", "504", "timeout", "deadline", "timedout"},
        "phrases": {"read timeout", "context deadline exceeded", "timed out", "timeout exceeded"},
    },
    "tls_failure": {
        "keywords": {"tls", "ssl", "certificate", "handshake", "sni", "x509"},
        "phrases": {"tls handshake", "certificate verify failed", "handshake failure", "ssl error"},
    },
    "dns_failure": {
        "keywords": {"dns", "resolve", "resolver", "hostname", "lookup", "nameserver"},
        "phrases": {"dns lookup failed", "temporary failure in name resolution", "host not found", "name resolution"},
    },
    "schema_contract_failure": {
        "keywords": {"schema", "migration", "relation", "column", "contract"},
        "phrases": {"relation does not exist", "column does not exist", "schema mismatch"},
    },
    "tensor_shape_mismatch": {
        "keywords": {"tensor", "shape", "reshape", "broadcast"},
        "phrases": {
            "shape mismatch",
            "tensor shape",
            "size mismatch",
            "mat1 and mat2",
            "shapes cannot be multiplied",
            "expected input",
            "runtime error",
            "dimension mismatch",
        },
    },
    "dependency_mismatch": {
        "keywords": {"dependency", "module", "import", "requirement", "incompatible"},
        "phrases": {"dependency conflict", "module not found", "import error", "version mismatch"},
    },
    "cuda_oom": {
        "keywords": {"cuda", "gpu", "vram", "oom"},
        "phrases": {"cuda out of memory", "out of memory", "gpu memory"},
    },
    "tokenizer_runtime_mismatch": {
        "keywords": {"tokenizer", "checkpoint", "weights", "vocab", "tokenization"},
        "phrases": {"tokenizer mismatch", "checkpoint mismatch", "tokenizer config mismatch"},
    },
    "embedding_vector_mismatch": {
        "keywords": {"embedding", "vector", "retrieval", "index"},
        "phrases": {"vector store", "retrieval results are empty", "embedding model", "embedding dimension"},
    },
    "deployment_change": {
        "keywords": {"deploy", "deployment", "upgrade", "restart", "migration", "release", "rollback"},
        "phrases": {"after deploy", "after deployment", "after upgrade", "after restart", "after migration", "after moving behind proxy"},
    },
    "runtime_startup_failure": {
        "keywords": {"startup", "initialization", "initialisation", "bootstrap", "boot"},
        "phrases": {"fails during startup", "cannot finish initialization", "cannot finish initialisation", "startup failure"},
    },
    "config_or_secret_drift": {
        "keywords": {"environment", "secret", "config", "settings", "dsn", "vault", "credential"},
        "phrases": {"new environment variables", "secret manager", "moved secrets", "connection string", "environment variable"},
    },
    "database_target_change": {
        "keywords": {"hostname", "dsn", "endpoint", "port", "database"},
        "phrases": {"new database hostname", "database hostname", "database host", "database endpoint", "new hostname", "new dsn"},
    },
    "production_only_regression": {
        "keywords": {"production", "local", "locally"},
        "phrases": {"works locally", "works local", "only in production"},
    },
}

STATUS_CODE_HINTS = {
    "401": {"authn_failure"},
    "403": {"authz_failure"},
    "408": {"timeout_failure"},
    "429": {"timeout_failure"},
    "500": {"dependency_mismatch", "schema_contract_failure"},
    "502": {"upstream_failure"},
    "503": {"upstream_failure"},
    "504": {"timeout_failure", "upstream_failure"},
}

TAG_SYMPTOM_HINTS = {
    "cors": {"preflight_failure", "missing_cors_headers", "browser_only_failure"},
    "reactjs": {"browser_only_failure", "missing_cors_headers", "csrf_or_cookie_failure"},
    "javascript": {"browser_only_failure", "missing_cors_headers"},
    "typescript": {"browser_only_failure", "missing_cors_headers"},
    "authentication": {"authn_failure", "csrf_or_cookie_failure"},
    "authorization": {"authz_failure", "authn_failure"},
    "jwt": {"authn_failure", "authz_failure"},
    "oauth-2.0": {"authn_failure", "authz_failure"},
    "nginx": {"upstream_failure", "missing_cors_headers", "tls_failure", "timeout_failure"},
    "apache": {"upstream_failure", "missing_cors_headers", "tls_failure", "timeout_failure"},
    "proxy": {"upstream_failure", "missing_cors_headers", "timeout_failure", "tls_failure"},
    "reverse-proxy": {"upstream_failure", "missing_cors_headers", "timeout_failure", "tls_failure"},
    "http": {"upstream_failure", "missing_cors_headers", "timeout_failure"},
    "rest": {"upstream_failure", "timeout_failure"},
    "dns": {"dns_failure", "connection_refused", "timeout_failure"},
    "routing": {"dns_failure", "upstream_failure", "timeout_failure"},
    "networking": {"dns_failure", "connection_refused", "timeout_failure", "tls_failure"},
    "tls": {"tls_failure"},
    "ssl": {"tls_failure"},
    "tcp": {"connection_refused", "timeout_failure"},
    "postgresql": {"schema_contract_failure", "connection_refused", "timeout_failure", "runtime_startup_failure", "config_or_secret_drift", "database_target_change"},
    "mysql": {"schema_contract_failure", "connection_refused", "timeout_failure", "runtime_startup_failure", "config_or_secret_drift", "database_target_change"},
    "redis": {"connection_refused", "timeout_failure", "csrf_or_cookie_failure", "config_or_secret_drift"},
    "sql": {"schema_contract_failure", "connection_refused", "timeout_failure", "config_or_secret_drift", "database_target_change"},
    "vector-database": {"embedding_vector_mismatch", "schema_contract_failure", "timeout_failure"},
    "rag": {"embedding_vector_mismatch", "timeout_failure"},
    "embeddings": {"embedding_vector_mismatch", "timeout_failure"},
    "sentence-transformers": {"embedding_vector_mismatch", "tokenizer_runtime_mismatch"},
    "model-serving": {"tokenizer_runtime_mismatch", "timeout_failure", "upstream_failure"},
    "huggingface-transformers": {"tokenizer_runtime_mismatch", "timeout_failure"},
    "large-language-model": {"tokenizer_runtime_mismatch", "timeout_failure"},
    "inference": {"cuda_oom", "timeout_failure", "tokenizer_runtime_mismatch"},
    "gpu": {"cuda_oom", "timeout_failure"},
    "cuda": {"cuda_oom"},
    "pytorch": {"cuda_oom", "tokenizer_runtime_mismatch", "dependency_mismatch", "tensor_shape_mismatch"},
    "numpy": {"tensor_shape_mismatch", "dependency_mismatch"},
    "machine-learning": {"tensor_shape_mismatch"},
    "deep-learning": {"tensor_shape_mismatch"},
    "tensorflow": {"cuda_oom", "dependency_mismatch", "tensor_shape_mismatch"},
    "kubernetes": {"dns_failure", "upstream_failure", "deployment_change", "timeout_failure"},
    "docker": {"deployment_change", "connection_refused", "timeout_failure"},
    "ingress": {"upstream_failure", "tls_failure", "dns_failure", "deployment_change"},
    "fastapi": {"authn_failure", "authz_failure", "missing_cors_headers", "dependency_mismatch"},
    "django": {"authn_failure", "authz_failure", "csrf_or_cookie_failure", "schema_contract_failure", "runtime_startup_failure", "config_or_secret_drift"},
    "flask": {"authn_failure", "missing_cors_headers", "dependency_mismatch"},
    "python": {"dependency_mismatch", "schema_contract_failure", "runtime_startup_failure", "config_or_secret_drift"},
    "node.js": {"dependency_mismatch", "missing_cors_headers"},
    "debugging": {"deployment_change", "dependency_mismatch"},
    "logging": {"upstream_failure", "timeout_failure"},
}

BOUNDARY_SYMPTOM_HINTS = {
    "browser_boundary": {"preflight_failure", "missing_cors_headers", "browser_only_failure", "csrf_or_cookie_failure", "authn_failure", "authz_failure"},
    "proxy_boundary": {"preflight_failure", "missing_cors_headers", "upstream_failure", "tls_failure", "timeout_failure"},
    "runtime_boundary": {"authn_failure", "authz_failure", "dependency_mismatch", "schema_contract_failure", "tokenizer_runtime_mismatch", "runtime_startup_failure", "config_or_secret_drift", "production_only_regression", "tensor_shape_mismatch"},
    "database_boundary": {"schema_contract_failure", "connection_refused", "embedding_vector_mismatch", "database_target_change", "config_or_secret_drift"},
    "network_transport_boundary": {"dns_failure", "connection_refused", "timeout_failure", "tls_failure", "upstream_failure"},
    "model_serving_boundary": {"tokenizer_runtime_mismatch", "embedding_vector_mismatch", "timeout_failure"},
    "gpu_inference_boundary": {"cuda_oom", "timeout_failure", "tensor_shape_mismatch"},
    "deployment_change_hint": {"deployment_change", "config_or_secret_drift", "production_only_regression"},
}

CLUSTER_SYMPTOM_HINTS = {
    "auth_identity_flow": {"authn_failure", "authz_failure", "csrf_or_cookie_failure"},
    "http_proxy_edge": {"preflight_failure", "missing_cors_headers", "browser_only_failure", "upstream_failure", "timeout_failure"},
    "database_connectivity_stack": {"schema_contract_failure", "connection_refused", "runtime_startup_failure", "config_or_secret_drift", "database_target_change"},
    "container_network_surface": {"dns_failure", "upstream_failure", "deployment_change", "timeout_failure"},
    "tls_dns_transport": {"dns_failure", "tls_failure", "connection_refused", "timeout_failure"},
    "model_serving_pipeline": {"tokenizer_runtime_mismatch", "embedding_vector_mismatch", "timeout_failure", "cuda_oom", "tensor_shape_mismatch"},
    "gpu_acceleration_stack": {"cuda_oom", "timeout_failure", "tokenizer_runtime_mismatch", "tensor_shape_mismatch"},
}

ISSUE_FAMILY_SYMPTOM_HINTS = {
    "authentication": {"authn_failure", "csrf_or_cookie_failure"},
    "authorization_policy": {"authz_failure"},
    "session_identity_boundary": {"csrf_or_cookie_failure", "browser_only_failure"},
    "cors_proxy_boundary": {"preflight_failure", "missing_cors_headers", "browser_only_failure"},
    "http_routing_misconfiguration": {"upstream_failure", "timeout_failure", "connection_refused"},
    "database_connectivity": {"connection_refused", "timeout_failure", "runtime_startup_failure", "config_or_secret_drift", "database_target_change", "production_only_regression"},
    "cache_session_store": {"csrf_or_cookie_failure", "schema_contract_failure"},
    "container_networking": {"dns_failure", "upstream_failure", "deployment_change", "timeout_failure"},
    "dns_service_discovery": {"dns_failure", "timeout_failure", "connection_refused"},
    "tls_edge_termination": {"tls_failure", "upstream_failure"},
    "model_serving_runtime": {"tokenizer_runtime_mismatch", "timeout_failure", "tensor_shape_mismatch"},
    "retrieval_embeddings_pipeline": {"embedding_vector_mismatch", "schema_contract_failure", "timeout_failure"},
    "gpu_inference_runtime": {"cuda_oom", "timeout_failure", "tensor_shape_mismatch"},
}

__all__ = [
    "DIRECT_SYMPTOM_RULES",
    "STATUS_CODE_HINTS",
    "TAG_SYMPTOM_HINTS",
    "BOUNDARY_SYMPTOM_HINTS",
    "CLUSTER_SYMPTOM_HINTS",
    "ISSUE_FAMILY_SYMPTOM_HINTS",
]
