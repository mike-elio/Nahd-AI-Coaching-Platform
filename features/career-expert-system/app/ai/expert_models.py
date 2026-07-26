from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class DomainOption(BaseModel):
    code: str
    label: str
    description: str


class StartSessionRequest(BaseModel):
    domain: str = Field(..., description="Expert-system domain code: SE, AIE, or CNE")
    kb_path: str | None = Field(
        default=None,
        description="Optional question-bank override path",
    )


class SubmitAnswerRequest(BaseModel):
    answer: Any


class QuestionPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    node_id: str
    variant_id: str
    text_ar: str
    text_en: str
    type: str
    fact_key: str
    scale_min: int | None = None
    scale_max: int | None = None
    numeric_min: int | float | None = None
    numeric_max: int | float | None = None
    choices_ar: list[str] = Field(default_factory=list)
    choices_en: list[str] = Field(default_factory=list)


class ProgressPayload(BaseModel):
    answered_count: int
    question_number: int
    estimated_total: int
    percent: float
    can_go_back: bool


class StartSessionResponse(BaseModel):
    session_id: str
    domain: str
    start_node: str


class QuestionEnvelopeResponse(BaseModel):
    session_id: str
    finished: bool
    question: QuestionPayload | None
    progress: ProgressPayload
    previous_answer: Any = None


class SubmitAnswerResponse(BaseModel):
    recorded: bool
    fact_key: str | None = None
    fact_value: Any = None
    next_node: str | None = None
    is_finished: bool
    progress: ProgressPayload


class SessionStateResponse(BaseModel):
    session_id: str
    domain: str
    current_node_id: str
    kb_path: str | None = None
    max_questions: int | None = None
    answers: dict[str, Any]
    facts: dict[str, Any]
    history: list[str]
    presented_questions: dict[str, dict[str, Any]]
    answer_log: list[dict[str, Any]]
    is_finished: bool
    goal_filter: dict[str, Any] | None = None
    final_output: dict[str, Any] | None = None
    progress: ProgressPayload


class GoalSummary(BaseModel):
    goal_id: str
    goal_name: str
    fit_score_percent: float


class GapResolutionItem(BaseModel):
    title: str
    action: str


class FinalResultResponse(BaseModel):
    session_id: str
    domain: str
    selected_goal: GoalSummary | None = None
    fit_score: float | None = None
    why_selected: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    alternative_goal: GoalSummary | None = None
    gaps: list[str] = Field(default_factory=list)
    gap_resolution_plan: list[GapResolutionItem] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
