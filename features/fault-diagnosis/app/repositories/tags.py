SOFTWARE_TAGS = {
    "python", "javascript", "typescript", "java", "c#", "sql", "html", "css", "git",
    "django", "flask", "fastapi", "node.js", "express", "spring-boot", "asp.net-core",
    "reactjs", "rest", "authentication", "authorization", "jwt", "oauth-2.0",
    "debugging", "logging", "postgresql", "mysql", "redis",
}

NETWORK_TAGS = {
    "networking", "linux", "ubuntu", "docker", "kubernetes", "nginx", "apache", "http",
    "dns", "ssl", "tls", "cors", "ssh", "tcp", "proxy", "reverse-proxy", "load-balancing",
    "firewall", "ingress", "routing", "vpn", "bash", "azure",
}

AI_TAGS = {
    "machine-learning", "deep-learning", "tensorflow", "pytorch", "scikit-learn",
    "pandas", "numpy", "opencv", "computer-vision", "nlp", "huggingface-transformers",
    "large-language-model", "rag", "embeddings", "vector-database", "model-serving",
    "gpu", "cuda", "inference", "mlops", "fine-tuning", "sentence-transformers",
}

ALL_SUPPORTED_TAGS = SOFTWARE_TAGS | NETWORK_TAGS | AI_TAGS
TAG_DOMAIN_MEMBERSHIP = {
    "sw": SOFTWARE_TAGS,
    "cn": NETWORK_TAGS,
    "ai": AI_TAGS,
}
TAG_TO_DOMAIN = {
    tag: domain
    for domain, domain_tags in TAG_DOMAIN_MEMBERSHIP.items()
    for tag in domain_tags
}

TAG_TEXT_ALIASES = {
    "node.js": {"node", "nodejs"},
    "oauth-2.0": {"oauth", "oauth2", "oauth 2", "oauth2.0"},
    "c#": {"csharp", "c sharp", ".net", "dotnet"},
    "asp.net-core": {"asp.net", "asp net", "aspnetcore", "dotnet", ".net"},
    "large-language-model": {"llm", "large language model", "language model"},
    "model-serving": {"model serving", "serving", "inference server", "endpoint"},
    "vector-database": {"vector db", "vectordb", "vector database"},
    "machine-learning": {"ml", "machine learning"},
    "deep-learning": {"dl", "deep learning"},
    "huggingface-transformers": {"huggingface", "transformers"},
    "sentence-transformers": {"sentence transformers", "sentence encoder"},
    "computer-vision": {"computer vision", "vision"},
    "load-balancing": {"load balancer", "load balancing"},
    "reverse-proxy": {"reverse proxy"},
}

FRAMEWORK_COMPATIBILITY_GROUPS = {
    "backend_web_framework": {"django", "flask", "fastapi", "express", "spring-boot", "asp.net-core"},
    "frontend_stack": {"javascript", "typescript", "reactjs"},
    "proxy_server": {"nginx", "apache"},
    "ml_framework": {"tensorflow", "pytorch", "scikit-learn"},
    "backing_store": {"postgresql", "mysql", "redis", "vector-database"},
}

CONFIDENCE_TIER_THRESHOLDS = {
    "trusted": 0.72,
    "supporting": 0.42,
    "minimum_supported": 0.08,
}

__all__ = [
    "SOFTWARE_TAGS",
    "NETWORK_TAGS",
    "AI_TAGS",
    "ALL_SUPPORTED_TAGS",
    "TAG_DOMAIN_MEMBERSHIP",
    "TAG_TO_DOMAIN",
    "TAG_TEXT_ALIASES",
    "FRAMEWORK_COMPATIBILITY_GROUPS",
    "CONFIDENCE_TIER_THRESHOLDS",
]
