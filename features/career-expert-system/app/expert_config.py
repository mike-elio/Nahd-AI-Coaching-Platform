"""Shared configuration for the GPES expert system."""

from __future__ import annotations

from pathlib import Path

from app.models import AIE_FACTS, CNE_FACTS, SE_FACTS, UNIVERSAL_FACTS


DEFAULT_MAX_QUESTIONS = 20

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUESTION_BANK_DIR = PROJECT_ROOT / "knowledge_base" / "question_bank"
GOALS_DIR = PROJECT_ROOT / "knowledge_base" / "goals"
GOALS_INDEX_FILE = GOALS_DIR / "goals_index.json"

DOMAIN_METADATA: dict[str, dict[str, str]] = {
    "SE": {
        "label": "Software Engineering",
        "description": "Interview flow for software, backend, frontend, cloud, and foundations paths.",
    },
    "AIE": {
        "label": "AI Engineering",
        "description": "Interview flow for machine learning, NLP, computer vision, data, and AI foundations.",
    },
    "CNE": {
        "label": "Communication Networks Engineering",
        "description": "Interview flow for networking operations, cloud networking, wireless, security, and foundations.",
    },
}

QUESTION_BANK_FILES: dict[str, Path] = {
    "SE": QUESTION_BANK_DIR / "se_questions.json",
    "AIE": QUESTION_BANK_DIR / "ai_questions.json",
    "CNE": QUESTION_BANK_DIR / "cn_questions.json",
}

SUPPORTED_OPS = {"==", "!=", ">", ">=", "<", "<=", "in"}

FACT_SCHEMAS: dict[str, str] = {
    **UNIVERSAL_FACTS,
    **SE_FACTS,
    **AIE_FACTS,
    **CNE_FACTS,
}


__all__ = [
    "DEFAULT_MAX_QUESTIONS",
    "DOMAIN_METADATA",
    "FACT_SCHEMAS",
    "GOALS_DIR",
    "GOALS_INDEX_FILE",
    "PROJECT_ROOT",
    "QUESTION_BANK_DIR",
    "QUESTION_BANK_FILES",
    "SUPPORTED_OPS",
]
