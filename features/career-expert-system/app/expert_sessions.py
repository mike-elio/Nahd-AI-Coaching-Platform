"""Session, question flow, and API-facing service logic for the expert system."""

from __future__ import annotations

import json
import random
import re
import uuid
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.expert_config import (
    DEFAULT_MAX_QUESTIONS,
    DOMAIN_METADATA,
    FACT_SCHEMAS,
    QUESTION_BANK_FILES,
)
from app.expert_goals import FilterResult, filter_goals, load_goals
from app.models import QuestionNode, QuestionTypeEnum
from core.inference_engine import InferenceEngine
from core.output_formatter import build_final_output
from core.rules_loader import load_rules


class SessionNotFoundError(KeyError):
    """Raised when a client references an unknown session id."""


class SessionStateError(RuntimeError):
    """Raised when an operation is invalid for the current session state."""


class SessionState:
    """Holds all runtime data for a single interview session."""

    def __init__(
        self,
        session_id: str,
        domain: str,
        start_node_id: str,
        kb_path: str | Path | None = None,
        max_questions: int | None = DEFAULT_MAX_QUESTIONS,
    ) -> None:
        if max_questions is not None and max_questions < 1:
            raise ValueError("max_questions must be at least 1 when provided.")

        self.session_id = session_id
        self.domain = domain
        self.current_node_id = start_node_id
        self.kb_path = str(kb_path) if kb_path else None
        self.max_questions = max_questions
        self.answers: dict[str, Any] = {}
        self.facts: dict[str, Any] = {}
        self.history: list[str] = []
        self.presented_questions: dict[str, dict[str, Any]] = {}
        self.answer_log: list[dict[str, Any]] = []
        self.is_finished = False
        self.goal_result: FilterResult | None = None
        self.final_output: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "domain": self.domain,
            "current_node_id": self.current_node_id,
            "kb_path": self.kb_path,
            "max_questions": self.max_questions,
            "answers": self.answers,
            "facts": self.facts,
            "history": self.history,
            "presented_questions": self.presented_questions,
            "answer_log": self.answer_log,
            "is_finished": self.is_finished,
            "goal_filter": self.goal_result.to_dict() if self.goal_result else None,
            "final_output": self.final_output,
        }


@dataclass
class SessionEntry:
    manager: "InterviewManager"
    session: SessionState


class QuestionLoader:
    """Loads a question-bank JSON file and provides node lookup."""

    def __init__(self, kb_path: str | Path, domain: str | None = None) -> None:
        self.kb_path = Path(kb_path)
        self.nodes: dict[str, QuestionNode] = {}
        self._load(domain)

    def _load(self, domain: str | None) -> None:
        with open(self.kb_path, encoding="utf-8") as handle:
            raw: list[dict[str, Any]] = json.load(handle)
        for item in raw:
            node = QuestionNode.model_validate(item)
            if domain is None or node.domain.value == domain:
                self.nodes[node.id] = node

    def get_node(self, node_id: str) -> QuestionNode | None:
        return self.nodes.get(node_id)

    def get_start_node(self, domain: str | None = None) -> QuestionNode | None:
        for node in self.nodes.values():
            if domain is None or node.domain.value == domain:
                return node
        return None

    @staticmethod
    def pick_variant(node: QuestionNode) -> dict[str, Any]:
        variant = random.choice(node.pool_pair)
        payload: dict[str, Any] = {
            "node_id": node.id,
            "variant_id": variant.id,
            "text_ar": variant.text_ar,
            "text_en": variant.text_en,
            "type": node.type.value,
            "fact_key": node.fact_key,
        }
        if node.type == QuestionTypeEnum.SCALE:
            payload["scale_min"] = node.scale_min if node.scale_min is not None else 0
            payload["scale_max"] = node.scale_max if node.scale_max is not None else 5
        if node.type == QuestionTypeEnum.NUMERIC:
            numeric_min, numeric_max = _infer_numeric_bounds(node, variant.text_en, variant.text_ar)
            if numeric_min is not None:
                payload["numeric_min"] = numeric_min
            if numeric_max is not None:
                payload["numeric_max"] = numeric_max
        if node.type in (QuestionTypeEnum.CHOICE, QuestionTypeEnum.MULTI_CHOICE):
            payload["choices_ar"] = node.choices_ar or []
            payload["choices_en"] = node.choices_en or []
        return payload


class InterviewManager:
    """Manages the interview flow for a single session."""

    END = "END"

    def __init__(self, loader: QuestionLoader, session: SessionState) -> None:
        self.loader = loader
        self.session = session

    def get_current_question(self) -> dict[str, Any] | None:
        if self.session.is_finished:
            return None
        if self._has_reached_question_limit():
            self._finish_session()
            return None
        node = self.loader.get_node(self.session.current_node_id)
        if node is None:
            self.session.is_finished = True
            return None
        cached = self.session.presented_questions.get(node.id)
        if cached is not None:
            return cached
        question = QuestionLoader.pick_variant(node)
        self.session.presented_questions[node.id] = question
        return question

    def submit_answer(self, answer: Any) -> dict[str, Any]:
        if self.session.is_finished:
            return {"recorded": False, "reason": "session already finished"}
        if self._has_reached_question_limit():
            self._finish_session()
            return {
                "recorded": False,
                "reason": "question limit reached",
                "next_node": self.END,
                "is_finished": True,
            }

        node = self.loader.get_node(self.session.current_node_id)
        if node is None:
            self.session.is_finished = True
            return {"recorded": False, "reason": "current node not found"}

        question = self.get_current_question()
        self.session.answers[node.id] = answer
        fact_value = self._extract_fact(node, answer)
        self.session.facts[node.fact_key] = fact_value

        is_truthy = self._evaluate_truthy(node, fact_value)
        next_node = node.next_if_true if is_truthy else node.next_if_false
        self.session.history.append(node.id)
        self.session.answer_log.append(
            {
                "node_id": node.id,
                "question": question,
                "answer": answer,
                "fact_key": node.fact_key,
                "fact_value": fact_value,
            }
        )

        should_finish = next_node == self.END or self._has_reached_question_limit()
        resolved_next_node = self.END if should_finish else next_node
        if should_finish:
            self._finish_session()
        else:
            self.session.current_node_id = next_node

        return {
            "recorded": True,
            "fact_key": node.fact_key,
            "fact_value": fact_value,
            "next_node": resolved_next_node,
            "is_finished": self.session.is_finished,
        }

    def _run_final_analysis(self) -> None:
        try:
            goals = load_goals(self.session.domain)
            self.session.goal_result = filter_goals(self.session.facts, goals)
        except Exception as exc:
            warnings.warn(f"GoalFilter failed for domain {self.session.domain}: {exc}")

        try:
            rules = load_rules(self.session.domain)
            inference_result = InferenceEngine.run(self.session.domain, self.session.facts, rules)
            self.session.final_output = build_final_output(
                self.session.domain,
                self.session.facts,
                inference_result,
            )
        except Exception as exc:
            warnings.warn(f"Final expert output failed for domain {self.session.domain}: {exc}")

    def _has_reached_question_limit(self) -> bool:
        limit = self.session.max_questions
        return limit is not None and len(self.session.history) >= limit

    def _finish_session(self) -> None:
        self.session.is_finished = True
        self.session.current_node_id = self.END
        if self.session.final_output is None or self.session.goal_result is None:
            self._run_final_analysis()

    @staticmethod
    def _extract_fact(node: QuestionNode, answer: Any) -> Any:
        if node.type == QuestionTypeEnum.BOOLEAN:
            if isinstance(answer, bool):
                return answer
            if isinstance(answer, str):
                return answer.lower() in {"true", "yes", "1"}
            return bool(answer)
        if node.type == QuestionTypeEnum.SCALE:
            return int(answer)
        if node.type == QuestionTypeEnum.NUMERIC:
            return float(answer) if "." in str(answer) else int(answer)
        if node.type == QuestionTypeEnum.CHOICE:
            return str(answer)
        if node.type == QuestionTypeEnum.MULTI_CHOICE:
            return answer if isinstance(answer, list) else [str(answer)]
        return answer

    @staticmethod
    def _evaluate_truthy(node: QuestionNode, fact_value: Any) -> bool:
        if node.type == QuestionTypeEnum.BOOLEAN:
            return bool(fact_value)
        if node.type == QuestionTypeEnum.SCALE:
            threshold = _parse_threshold(node.truthy_rule)
            if threshold is None:
                lo = node.scale_min if node.scale_min is not None else 0
                hi = node.scale_max if node.scale_max is not None else 5
                threshold = (lo + hi) / 2
            return float(fact_value) >= threshold
        if node.type == QuestionTypeEnum.NUMERIC:
            threshold = _parse_threshold(node.truthy_rule)
            return True if threshold is None else float(fact_value) >= threshold
        return True


def create_session(
    kb_path: str | Path,
    domain: str,
    session_id: str | None = None,
    max_questions: int | None = DEFAULT_MAX_QUESTIONS,
) -> tuple[InterviewManager, SessionState]:
    loader = QuestionLoader(kb_path, domain=domain)
    start = loader.get_start_node(domain)
    if start is None:
        raise ValueError(f"No start node found for domain '{domain}' in {kb_path}")
    session = SessionState(
        session_id=session_id or uuid.uuid4().hex[:12],
        domain=domain,
        start_node_id=start.id,
        kb_path=kb_path,
        max_questions=max_questions,
    )
    return InterviewManager(loader, session), session


class ExpertSystemService:
    """Coordinates sessions and exposes interview operations to FastAPI."""

    def __init__(self) -> None:
        self.sessions: dict[str, SessionEntry] = {}
        self.max_questions = DEFAULT_MAX_QUESTIONS

    def list_domains(self) -> list[dict[str, str]]:
        return [
            {
                "code": code,
                "label": meta["label"],
                "description": meta["description"],
            }
            for code, meta in DOMAIN_METADATA.items()
        ]

    def start_session(self, domain: str, kb_path: str | None = None) -> dict[str, Any]:
        normalized_domain = self._normalize_domain(domain)
        resolved_kb_path = self._resolve_kb_path(normalized_domain, kb_path)
        manager, session = create_session(
            resolved_kb_path,
            normalized_domain,
            max_questions=self.max_questions,
        )
        self.sessions[session.session_id] = SessionEntry(manager=manager, session=session)
        return {
            "session_id": session.session_id,
            "domain": session.domain,
            "start_node": session.current_node_id,
        }

    def get_current_question(self, session_id: str) -> dict[str, Any]:
        entry = self._get_entry(session_id)
        question = entry.manager.get_current_question()
        return {
            "session_id": session_id,
            "finished": question is None,
            "question": question,
            "progress": self._build_progress(entry),
            "previous_answer": None,
        }

    def submit_answer(self, session_id: str, answer: Any) -> dict[str, Any]:
        entry = self._get_entry(session_id)
        question = entry.manager.get_current_question()
        if question is None:
            raise SessionStateError("This interview session is already finished.")
        normalized_answer = self._validate_answer(question, answer)
        result = entry.manager.submit_answer(normalized_answer)
        result["progress"] = self._build_progress(entry)
        return result

    def go_back(self, session_id: str) -> dict[str, Any]:
        entry = self._get_entry(session_id)
        session = entry.session
        if not session.answer_log:
            raise SessionStateError("There is no previous question to go back to.")
        if not session.kb_path:
            raise SessionStateError("The session cannot be rewound because its KB path is missing.")

        previous_step = session.answer_log[-1]
        replay_steps = list(session.answer_log[:-1])
        manager, rebuilt_session = create_session(
            session.kb_path,
            session.domain,
            session_id=session.session_id,
            max_questions=session.max_questions,
        )
        for step in replay_steps:
            rebuilt_session.presented_questions[step["node_id"]] = step["question"]
            manager.submit_answer(step["answer"])
        rebuilt_session.presented_questions[previous_step["node_id"]] = previous_step["question"]
        rebuilt_entry = SessionEntry(manager=manager, session=rebuilt_session)
        self.sessions[session_id] = rebuilt_entry
        return {
            "session_id": session_id,
            "finished": False,
            "question": manager.get_current_question(),
            "progress": self._build_progress(rebuilt_entry),
            "previous_answer": previous_step["answer"],
        }

    def get_session_state(self, session_id: str) -> dict[str, Any]:
        entry = self._get_entry(session_id)
        state = entry.session.to_dict()
        state["progress"] = self._build_progress(entry)
        return state

    def get_final_result(self, session_id: str) -> dict[str, Any]:
        entry = self._get_entry(session_id)
        session = entry.session
        if not session.is_finished:
            raise SessionStateError("The interview is not finished yet.")
        result = session.final_output or {}
        ranked_goals = result.get("ranked_goals", []) if result else []
        top_goal = result.get("top_goal") if result else None
        alternative_goal = ranked_goals[1] if len(ranked_goals) > 1 else None
        return {
            "session_id": session.session_id,
            "domain": session.domain,
            "selected_goal": self._goal_summary(top_goal),
            "fit_score": top_goal.get("fit_score_percent") if top_goal else None,
            "why_selected": result.get("why_selected", []) if result else [],
            "strengths": result.get("strengths", []) if result else [],
            "alternative_goal": self._goal_summary(alternative_goal),
            "gaps": result.get("gaps", []) if result else [],
            "gap_resolution_plan": result.get("gap_resolution_plan", []) if result else [],
            "next_steps": result.get("next_steps", []) if result else [],
            "result": result,
        }

    def _get_entry(self, session_id: str) -> SessionEntry:
        entry = self.sessions.get(session_id)
        if entry is None:
            raise SessionNotFoundError(session_id)
        return entry

    def _resolve_kb_path(self, domain: str, kb_path: str | None) -> Path:
        path = Path(kb_path) if kb_path else QUESTION_BANK_FILES[domain]
        if not path.exists():
            raise FileNotFoundError(f"KB file not found: {path}")
        return path

    @staticmethod
    def _normalize_domain(domain: str) -> str:
        normalized = domain.strip().upper()
        if normalized not in DOMAIN_METADATA:
            raise ValueError("Unsupported domain. Expected SE, AIE, or CNE.")
        return normalized

    @staticmethod
    def _build_progress(entry: SessionEntry) -> dict[str, Any]:
        answered_count = len(entry.session.history)
        raw_total = len(entry.manager.loader.nodes)
        limit = entry.session.max_questions
        estimated_total = min(raw_total, limit) if limit is not None else raw_total
        estimated_total = max(estimated_total, 1)
        question_number = answered_count if entry.session.is_finished else answered_count + 1
        question_number = min(question_number, estimated_total)
        percent = 100.0 if entry.session.is_finished else round((answered_count / estimated_total) * 100, 2)
        return {
            "answered_count": answered_count,
            "question_number": question_number,
            "estimated_total": estimated_total,
            "percent": percent,
            "can_go_back": answered_count > 0,
        }

    @staticmethod
    def _goal_summary(goal: dict[str, Any] | None) -> dict[str, Any] | None:
        if not goal:
            return None
        return {
            "goal_id": goal.get("goal_id", ""),
            "goal_name": goal.get("goal_name", ""),
            "fit_score_percent": float(goal.get("fit_score_percent", 0.0)),
        }

    @staticmethod
    def _validate_answer(question: dict[str, Any], answer: Any) -> Any:
        question_type = question["type"]
        if question_type == "boolean":
            if isinstance(answer, bool):
                return answer
            if isinstance(answer, str):
                normalized = answer.strip().lower()
                if normalized in {"true", "yes", "1"}:
                    return True
                if normalized in {"false", "no", "0"}:
                    return False
            raise ValueError("Boolean questions accept only true or false.")
        if question_type == "choice":
            choices = set(question.get("choices_en", [])) | set(question.get("choices_ar", []))
            if isinstance(answer, str) and answer in choices:
                return answer
            raise ValueError("Please select one of the available options.")
        if question_type == "multi_choice":
            if not isinstance(answer, list) or not answer:
                raise ValueError("Please select at least one option.")
            choices = set(question.get("choices_en", [])) | set(question.get("choices_ar", []))
            invalid = [item for item in answer if item not in choices]
            if invalid:
                raise ValueError("One or more selected options are invalid.")
            deduped: list[str] = []
            for item in answer:
                if item not in deduped:
                    deduped.append(item)
            return deduped
        if question_type == "numeric":
            try:
                numeric = float(answer)
            except (TypeError, ValueError) as exc:
                raise ValueError("Numeric questions require a valid number.") from exc
            minimum = question.get("numeric_min")
            maximum = question.get("numeric_max")
            if minimum is not None and numeric < float(minimum):
                raise ValueError(f"Value must be greater than or equal to {minimum}.")
            if maximum is not None and numeric > float(maximum):
                raise ValueError(f"Value must be less than or equal to {maximum}.")
            return int(numeric) if numeric.is_integer() else numeric
        if question_type == "scale":
            try:
                numeric = int(answer)
            except (TypeError, ValueError) as exc:
                raise ValueError("Scale questions require a whole number.") from exc
            minimum = question.get("scale_min")
            maximum = question.get("scale_max")
            if minimum is not None and numeric < minimum:
                raise ValueError(f"Value must be greater than or equal to {minimum}.")
            if maximum is not None and numeric > maximum:
                raise ValueError(f"Value must be less than or equal to {maximum}.")
            return numeric
        if answer in (None, "", []):
            raise ValueError("Please provide an answer before continuing.")
        return answer


def _parse_threshold(truthy_rule: str | None) -> float | None:
    if not truthy_rule:
        return None
    match = re.search(r">=?\s*([\d.]+)", truthy_rule)
    if match:
        return float(match.group(1))
    match = re.search(r"(\d+)\s*أو أكثر", truthy_rule)
    if match:
        return float(match.group(1))
    return None


def _infer_numeric_bounds(
    node: QuestionNode,
    text_en: str,
    text_ar: str,
) -> tuple[int | float | None, int | float | None]:
    if node.numeric_min is not None or node.numeric_max is not None:
        return node.numeric_min, node.numeric_max

    fact_schema = FACT_SCHEMAS.get(node.fact_key, "")
    schema_match = re.search(r"\(([-\d.]+)\.\.([-\d.]+)\)", fact_schema)
    if schema_match:
        return _coerce_number(schema_match.group(1)), _coerce_number(schema_match.group(2))

    text_match = re.search(r"\(([-\d.]+)\s*-\s*([-\d.]+)\)", f"{text_en} {text_ar}")
    if text_match:
        return _coerce_number(text_match.group(1)), _coerce_number(text_match.group(2))

    return None, None


def _coerce_number(value: str) -> int | float:
    numeric = float(value)
    return int(numeric) if numeric.is_integer() else numeric


expert_service = ExpertSystemService()


__all__ = [
    "ExpertSystemService",
    "InterviewManager",
    "QuestionLoader",
    "SessionEntry",
    "SessionNotFoundError",
    "SessionState",
    "SessionStateError",
    "create_session",
    "expert_service",
]
