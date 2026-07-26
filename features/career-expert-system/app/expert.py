"""Compatibility exports for the GPES expert-system modules."""

from __future__ import annotations

from app.expert_config import DEFAULT_MAX_QUESTIONS, DOMAIN_METADATA, QUESTION_BANK_FILES
from app.expert_goals import (
    FilterResult,
    GoalVerdict,
    filter_goals,
    get_goal_index,
    invalidate_goal_cache,
    load_goals,
)
from app.expert_sessions import (
    ExpertSystemService,
    InterviewManager,
    QuestionLoader,
    SessionEntry,
    SessionNotFoundError,
    SessionState,
    SessionStateError,
    create_session,
    expert_service,
)
from app.expert_validation import KBValidator, ValidationReport


__all__ = [
    "DEFAULT_MAX_QUESTIONS",
    "DOMAIN_METADATA",
    "ExpertSystemService",
    "FilterResult",
    "GoalVerdict",
    "InterviewManager",
    "KBValidator",
    "QuestionLoader",
    "QUESTION_BANK_FILES",
    "SessionEntry",
    "SessionNotFoundError",
    "SessionState",
    "SessionStateError",
    "ValidationReport",
    "create_session",
    "expert_service",
    "filter_goals",
    "get_goal_index",
    "invalidate_goal_cache",
    "load_goals",
]
