"""Gap identification helpers for GPES output formatting."""

from __future__ import annotations

from typing import Any

from app.models import AIE_FACTS, CNE_FACTS, SE_FACTS, UNIVERSAL_FACTS
from core.output_copy import _number, gap_copy
from core.output_specs import GOAL_GAP_SPECS


_ALL_FACT_TYPES: dict[str, str] = {
    **UNIVERSAL_FACTS,
    **SE_FACTS,
    **AIE_FACTS,
    **CNE_FACTS,
}


def _build_gap_entries(
    top_goal: dict[str, Any] | None,
    normalized_facts: dict[str, Any],
    fc_result: dict[str, Any],
) -> list[dict[str, Any]]:
    if not top_goal:
        return []

    entries_by_fact: dict[str, dict[str, Any]] = {}
    goal_id = top_goal["goal_id"]
    for spec in GOAL_GAP_SPECS.get(goal_id, []):
        gap_entry = _gap_entry_from_spec(spec, normalized_facts, source="goal_gap_spec")
        if gap_entry:
            _store_gap_entry(entries_by_fact, gap_entry)

    for fact_key in top_goal.get("relevant_facts", []):
        gap_entry = _gap_entry_from_relevant_fact(fact_key, normalized_facts)
        if gap_entry:
            _store_gap_entry(entries_by_fact, gap_entry)

    for penalty in top_goal.get("penalties", []):
        gap_entry = _gap_entry_from_penalty(penalty, normalized_facts)
        if gap_entry:
            _store_gap_entry(entries_by_fact, gap_entry)

    for fact_key in ("weak_device", "weak_internet", "pressure_load", "hours_per_week"):
        gap_entry = _gap_entry_from_relevant_fact(fact_key, normalized_facts)
        if gap_entry:
            _store_gap_entry(entries_by_fact, gap_entry)

    gap_entries = list(entries_by_fact.values())
    gap_entries.sort(key=lambda item: (-item["priority"], item["fact"]))
    return gap_entries[:10]


def _store_gap_entry(entries_by_fact: dict[str, dict[str, Any]], gap_entry: dict[str, Any]) -> None:
    existing = entries_by_fact.get(gap_entry["fact"])
    if existing is None or gap_entry["priority"] > existing["priority"]:
        entries_by_fact[gap_entry["fact"]] = gap_entry


def _gap_entry_from_spec(
    spec: dict[str, Any],
    facts: dict[str, Any],
    source: str,
) -> dict[str, Any] | None:
    fact_key = spec["fact"]
    if fact_key not in facts:
        if spec["kind"] not in {"lt", "false", "true", "enum"}:
            return None
    actual = facts.get(fact_key)
    if not _gap_matches(spec, actual, fact_key in facts):
        return None
    summary, action = gap_copy(fact_key, actual, spec.get("value"))
    return {
        "fact": fact_key,
        "actual": actual,
        "expected": spec.get("value"),
        "priority": spec.get("priority", 50),
        "text": summary,
        "step_text": action,
        "facts": [fact_key],
        "source": source,
    }


def _gap_entry_from_relevant_fact(fact_key: str, facts: dict[str, Any]) -> dict[str, Any] | None:
    if fact_key not in facts:
        return None
    actual = facts[fact_key]
    fact_type = _ALL_FACT_TYPES.get(fact_key, "")

    if fact_key in {"hours_per_week"}:
        numeric = _number(actual)
        if numeric is None or numeric >= 8:
            return None
        summary, action = gap_copy(fact_key, actual, 8)
        return {
            "fact": fact_key,
            "actual": actual,
            "expected": 8,
            "priority": 70,
            "text": summary,
            "step_text": action,
            "facts": [fact_key],
            "source": "relevant_fact",
        }

    if fact_key in {"weak_device", "weak_internet"} and actual is True:
        summary, action = gap_copy(fact_key, actual, False)
        return {
            "fact": fact_key,
            "actual": actual,
            "expected": False,
            "priority": 70,
            "text": summary,
            "step_text": action,
            "facts": [fact_key],
            "source": "constraint_fact",
        }
    if fact_key in {"weak_device", "weak_internet"}:
        return None

    if fact_key == "pressure_load" and actual == "high":
        summary, action = gap_copy(fact_key, actual, "medium")
        return {
            "fact": fact_key,
            "actual": actual,
            "expected": "medium",
            "priority": 65,
            "text": summary,
            "step_text": action,
            "facts": [fact_key],
            "source": "constraint_fact",
        }

    if fact_key == "english_level" and actual == "basic":
        summary, action = gap_copy(fact_key, actual, "intermediate")
        return {
            "fact": fact_key,
            "actual": actual,
            "expected": "intermediate",
            "priority": 55,
            "text": summary,
            "step_text": action,
            "facts": [fact_key],
            "source": "relevant_fact",
        }

    if fact_type.startswith("scale"):
        numeric = _number(actual)
        if numeric is None:
            return None
        target = 3
        if fact_key in {"web_basics", "python_skill", "math_skill", "networking_theory"}:
            target = 3
        if fact_key in {"ml_exposure", "data_handling", "cisco_tools", "scripting_skill"}:
            target = 2
        if fact_key in {"linux_cli_net_tools_skill"}:
            target = 2
        if numeric >= target:
            return None
        summary, action = gap_copy(fact_key, actual, target)
        return {
            "fact": fact_key,
            "actual": actual,
            "expected": target,
            "priority": 60,
            "text": summary,
            "step_text": action,
            "facts": [fact_key],
            "source": "relevant_fact",
        }

    if fact_type == "boolean" and actual is False and not fact_key.startswith("prefers_"):
        summary, action = gap_copy(fact_key, actual, True)
        return {
            "fact": fact_key,
            "actual": actual,
            "expected": True,
            "priority": 55,
            "text": summary,
            "step_text": action,
            "facts": [fact_key],
            "source": "relevant_fact",
        }
    return None


def _gap_entry_from_penalty(penalty: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any] | None:
    fact_key = penalty.get("fact")
    if not fact_key:
        return None
    actual = facts.get(fact_key)
    expected = 8 if fact_key == "hours_per_week" else False
    if fact_key == "pressure_load":
        expected = "medium"
    summary, action = gap_copy(fact_key, actual, expected)
    return {
        "fact": fact_key,
        "actual": actual,
        "expected": expected,
        "priority": 65,
        "text": summary,
        "step_text": action,
        "facts": [fact_key],
        "source": "penalty",
    }


def _gap_matches(spec: dict[str, Any], actual: Any, fact_present: bool) -> bool:
    kind = spec["kind"]
    if kind == "false":
        return actual is False
    if kind == "true":
        return actual is True
    if kind == "lt":
        numeric = _number(actual)
        return numeric is not None and numeric < spec["value"]
    if kind == "enum":
        return not fact_present or actual not in spec["value"]
    return False
