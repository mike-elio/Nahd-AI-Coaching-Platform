TAG_PREDICTION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "predicted_domain": {
            "type": "string",
            "enum": ["ai", "cn", "sw"],
        },
        "top_tags": {
            "type": "array",
            "minItems": 3,
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["tag", "confidence"],
            },
        },
    },
    "required": ["predicted_domain", "top_tags"],
}

ROOT_CAUSE_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "case_summary": {
            "type": "object",
            "properties": {
                "domain": {"type": "string", "enum": ["software", "networking", "ai"]},
                "issue_family": {"type": "string"},
                "top_tags": {
                    "type": "array",
                    "minItems": 1,
                    "items": {"type": "string"},
                },
                "tag_signals": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "properties": {
                            "tag": {"type": "string"},
                            "confidence": {"type": "number"},
                            "rank": {"type": "integer"},
                        },
                    },
                },
            },
            "required": ["domain", "issue_family", "top_tags"],
        },
        "root_cause_hypotheses": {
            "type": "array",
            "minItems": 4,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "title": {"type": "string"},
                    "why_likely": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["id", "title", "why_likely", "confidence"],
            },
        },
    },
    "required": ["case_summary", "root_cause_hypotheses"],
}

__all__ = ["TAG_PREDICTION_JSON_SCHEMA", "ROOT_CAUSE_JSON_SCHEMA"]
