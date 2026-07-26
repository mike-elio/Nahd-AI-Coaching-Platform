"""Goal loading and eligibility filtering for the GPES expert system."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.expert_config import GOALS_DIR, GOALS_INDEX_FILE, SUPPORTED_OPS


_GOALS_CACHE: dict[str, list[dict[str, Any]]] = {}


@dataclass
class GoalVerdict:
    goal_id: str
    goal_name: str
    domain: str
    status: str
    reasons: list[str] = field(default_factory=list)
    base_score: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "goal_name": self.goal_name,
            "domain": self.domain,
            "status": self.status,
            "reasons": self.reasons,
            "base_score": self.base_score,
        }


@dataclass
class FilterResult:
    qualified: list[GoalVerdict] = field(default_factory=list)
    excluded: list[GoalVerdict] = field(default_factory=list)
    not_eligible: list[GoalVerdict] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "qualified": [goal.to_dict() for goal in self.qualified],
            "excluded": [goal.to_dict() for goal in self.excluded],
            "not_eligible": [goal.to_dict() for goal in self.not_eligible],
        }


def load_goals(domain: str) -> list[dict[str, Any]]:
    domain = domain.upper()
    if domain in _GOALS_CACHE:
        return _GOALS_CACHE[domain]

    index = _load_goals_index()
    domains = index.get("domains", {})
    if domain not in domains:
        raise ValueError(f"Domain '{domain}' not found in goals_index.json.")

    goals_path = GOALS_DIR / domains[domain]["file"]
    goals = _load_json_list(goals_path, label=f"goals for domain {domain}")
    _GOALS_CACHE[domain] = goals
    return goals


def invalidate_goal_cache(domain: str | None = None) -> None:
    if domain is None:
        _GOALS_CACHE.clear()
    else:
        _GOALS_CACHE.pop(domain.upper(), None)


def get_goal_index() -> dict[str, Any]:
    return _load_goals_index()


def filter_goals(facts: dict[str, Any], goals: list[dict[str, Any]]) -> FilterResult:
    result = FilterResult()

    for goal in goals:
        goal_id = goal.get("goal_id", "UNKNOWN")
        goal_name = goal.get("goal_name", "")
        domain = goal.get("domain", "")
        base_score = goal.get("base_score", 50)

        eligibility_failures: list[str] = []
        for condition in goal.get("eligibility_rules", []):
            fact_key = condition["fact"]
            operator = condition["op"]
            expected = condition["value"]
            fact_value = facts.get(fact_key)
            try:
                passes = _evaluate_condition(fact_value, operator, expected)
            except (TypeError, ValueError):
                passes = False
            if not passes:
                eligibility_failures.append(_condition_to_str(fact_key, operator, expected))

        disqualifier_hits: list[str] = []
        for disqualifier in goal.get("disqualifiers", []):
            fact_key = disqualifier["fact"]
            operator = disqualifier["op"]
            expected = disqualifier["value"]
            fact_value = facts.get(fact_key)
            try:
                fires = _evaluate_condition(fact_value, operator, expected)
            except (TypeError, ValueError):
                fires = False
            if fires:
                disqualifier_hits.append(
                    disqualifier.get("note", _condition_to_str(fact_key, operator, expected))
                )

        verdict = GoalVerdict(
            goal_id=goal_id,
            goal_name=goal_name,
            domain=domain,
            status="qualified",
            reasons=[],
            base_score=base_score,
        )
        if disqualifier_hits:
            verdict.status = "excluded"
            verdict.reasons = disqualifier_hits
            result.excluded.append(verdict)
        elif eligibility_failures:
            verdict.status = "not_eligible"
            verdict.reasons = eligibility_failures
            result.not_eligible.append(verdict)
        else:
            result.qualified.append(verdict)

    return result


def _load_goals_index() -> dict[str, Any]:
    if not GOALS_INDEX_FILE.exists():
        raise FileNotFoundError(f"goals_index.json not found at: {GOALS_INDEX_FILE}")
    try:
        with open(GOALS_INDEX_FILE, encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"goals_index.json contains invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("goals_index.json root must be a JSON object.")
    return data


def _load_json_list(path: Path, *, label: str) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Goals file not found: {path} (loading {label})")
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path.name} ({label}): {exc}") from exc
    if not isinstance(data, list):
        raise ValueError(f"{path.name} root must be a JSON array of goal objects.")
    return data


def _evaluate_condition(fact_value: Any, operator: str, expected: Any) -> bool:
    if operator not in SUPPORTED_OPS:
        raise ValueError(f"Unsupported operator: '{operator}'")
    if operator == "in":
        if not isinstance(expected, list):
            raise TypeError(f"'in' operator requires a list, got {type(expected)}")
        return fact_value in expected
    if operator in {">", ">=", "<", "<="}:
        try:
            fact_value = float(fact_value)
            expected = float(expected)
        except (TypeError, ValueError):
            pass
    if operator == "==":
        return fact_value == expected
    if operator == "!=":
        return fact_value != expected
    if operator == ">":
        return fact_value > expected  # type: ignore[operator]
    if operator == ">=":
        return fact_value >= expected  # type: ignore[operator]
    if operator == "<":
        return fact_value < expected  # type: ignore[operator]
    if operator == "<=":
        return fact_value <= expected  # type: ignore[operator]
    return False


def _condition_to_str(fact: str, operator: str, expected: Any) -> str:
    return f"{fact} {operator} {expected}"


__all__ = [
    "FilterResult",
    "GoalVerdict",
    "filter_goals",
    "get_goal_index",
    "invalidate_goal_cache",
    "load_goals",
]
