import os

APP_NAME: str = "Technical Fault Diagnosis API"
APP_VERSION: str = "1.0.0"


def _parse_cors_origins(raw_value: str) -> list[str]:
    origins = [item.strip() for item in str(raw_value).split(",") if item.strip()]
    return origins or ["*"]


CORS_ALLOW_ORIGINS: list[str] = _parse_cors_origins(os.getenv("CORS_ALLOW_ORIGINS", "*"))
CORS_ALLOW_CREDENTIALS: bool = CORS_ALLOW_ORIGINS != ["*"]

MODEL: str = "gemma4:e4b"
OLLAMA_URL: str = "http://localhost:11434/api/generate"

CANONICAL_DOMAINS: set[str] = {"ai", "sw", "cn"}
VALID_DOMAINS: set[str] = CANONICAL_DOMAINS | {"software", "networking"}
VALID_REFERENCE_SOURCE_TYPES: set[str] = {
    "official_docs",
    "protocol_reference",
    "security_guidance",
    "vendor_docs",
    "library_docs",
}

DOMAIN_ALIAS_TO_CANONICAL: dict[str, str] = {
    "ai": "ai",
    "sw": "sw",
    "software": "sw",
    "cn": "cn",
    "networking": "cn",
}

CANONICAL_TO_REASONING_DOMAIN: dict[str, str] = {
    "ai": "ai",
    "sw": "software",
    "cn": "networking",
}

__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "CORS_ALLOW_ORIGINS",
    "CORS_ALLOW_CREDENTIALS",
    "MODEL",
    "OLLAMA_URL",
    "CANONICAL_DOMAINS",
    "VALID_DOMAINS",
    "VALID_REFERENCE_SOURCE_TYPES",
    "DOMAIN_ALIAS_TO_CANONICAL",
    "CANONICAL_TO_REASONING_DOMAIN",
]
