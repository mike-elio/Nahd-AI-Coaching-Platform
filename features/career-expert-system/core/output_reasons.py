"""Why-selected and strength helpers for GPES output formatting."""

from __future__ import annotations

from typing import Any

from app.models import AIE_FACTS, CNE_FACTS, SE_FACTS, UNIVERSAL_FACTS
from core.output_copy import (
    _fact_label,
    _format_number,
    _join_text,
    _natural_scale,
    _number,
    _sentence_case,
    _strip_trailing_period,
    _take_unique_strings,
)
from core.output_validation import _take_unique_entries


_ALL_FACT_TYPES: dict[str, str] = {
    **UNIVERSAL_FACTS,
    **SE_FACTS,
    **AIE_FACTS,
    **CNE_FACTS,
}


def _build_why_entries(
    top_goal: dict[str, Any] | None,
    selected_goal_trace: dict[str, Any],
    fc_result: dict[str, Any],
) -> list[dict[str, Any]]:
    if not top_goal:
        return []

    firing_map = {
        record["rule_id"]: record
        for record in fc_result.get("rule_firings", [])
    }
    qualifying_rules = set(selected_goal_trace.get("qualifying_rules", []))
    support_rules = [
        rule_id
        for rule_id in selected_goal_trace.get("triggered_rules", [])
        if rule_id not in qualifying_rules
    ]
    clause_entries: list[dict[str, Any]] = []

    for rule_id in support_rules[:2]:
        rule_record = firing_map.get(rule_id)
        if not rule_record:
            continue
        text = _build_support_reason(top_goal, rule_record)
        if not text:
            continue
        clause_entries.append(
            {
                "text": text,
                "facts": [item["fact"] for item in rule_record.get("matched_conditions", [])],
                "rules": [rule_id],
                "kind": "fit",
            }
        )

    primary_qualifying_rules = _prioritize_qualifying_rules(
        selected_goal_trace.get("qualifying_rules", []),
        firing_map,
    )
    for rule_id in primary_qualifying_rules[:1]:
        rule_record = firing_map.get(rule_id)
        if not rule_record:
            continue
        text = _build_goal_reason(top_goal, rule_record)
        if not text:
            continue
        clause_entries.append(
            {
                "text": text,
                "facts": [item["fact"] for item in rule_record.get("matched_conditions", [])],
                "rules": [rule_id],
                "kind": "fit",
            }
        )

    for alternative in selected_goal_trace.get("alternatives_evaluated", [])[:1]:
        blocking_conditions = alternative.get("blocking_conditions", [])
        if not blocking_conditions:
            continue
        text = _build_alternative_reason(top_goal, alternative)
        if not text:
            continue
        clause_entries.append(
            {
                "text": text,
                "facts": [item["fact"] for item in blocking_conditions],
                "rules": [],
                "kind": "alternative",
            }
        )

    return _merge_why_entries(top_goal, selected_goal_trace, clause_entries)


def _build_score_evidence_line(top_goal: dict[str, Any]) -> dict[str, Any] | None:
    contributions = top_goal.get("contributions", [])
    if not contributions:
        return None
    ordered = sorted(contributions, key=lambda item: item.get("contribution", 0), reverse=True)
    strongest = ordered[:3]
    if not strongest:
        return None
    evidence = _join_text(_top_signal_fragments(strongest), conjunction="and")
    return {
        "text": f"This recommendation is supported by {evidence}.",
        "facts": [item["fact"] for item in strongest],
        "rules": [],
    }


def _build_strength_entries(
    top_goal: dict[str, Any] | None,
    normalized_facts: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    for contribution in (top_goal or {}).get("contributions", []):
        fact_key = contribution["fact"]
        entry = _strength_entry_from_fact(fact_key, contribution["value"], top_goal)
        if entry and fact_key not in seen:
            seen.add(fact_key)
            candidates.append(entry)

    for fact_key, value in normalized_facts.items():
        if fact_key in seen:
            continue
        entry = _strength_entry_from_fact(fact_key, value, top_goal)
        if entry:
            seen.add(fact_key)
            candidates.append(entry)

    candidates.sort(key=lambda item: (item["priority"], item["fact"]))
    return candidates[:5]


def _strength_entry_from_fact(
    fact_key: str,
    value: Any,
    top_goal: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    fact_type = _ALL_FACT_TYPES.get(fact_key, "")
    if not _is_positive_signal(fact_key, value, fact_type):
        return None

    text = _build_strength_text(fact_key, value, fact_type, top_goal)
    if not text:
        return None
    return {
        "text": text,
        "fact": fact_key,
        "facts": [fact_key],
        "priority": _strength_priority(fact_key),
    }


def _is_positive_signal(fact_key: str, value: Any, fact_type: str) -> bool:
    if fact_key == "hours_per_week":
        numeric = _number(value)
        return numeric is not None and numeric >= 6
    if fact_key == "pretrack_readiness":
        numeric = _number(value)
        return numeric is not None and numeric >= 2
    if fact_key == "target_outcome":
        return value in {"job", "internship", "freelance", "research"}
    if fact_key == "english_level":
        return value in {"intermediate", "advanced"}
    if fact_key == "current_level":
        return value in {"intermediate", "advanced"}
    if fact_type.startswith("scale"):
        numeric = _number(value)
        return numeric is not None and numeric >= 3
    if fact_type == "boolean":
        return value is True
    return False


def _strength_priority(fact_key: str) -> int:
    if fact_key.startswith("prefers_"):
        return 0
    if fact_key == "target_outcome":
        return 1
    if fact_key == "hours_per_week":
        return 2
    if fact_key in {"pretrack_readiness", "current_level", "english_level"}:
        return 3
    return 4


def _build_support_reason(top_goal: dict[str, Any], rule_record: dict[str, Any]) -> str | None:
    fit_conditions = [
        condition
        for condition in rule_record.get("matched_conditions", [])
        if _is_fit_condition(condition)
    ]
    reasons = [
        _condition_reason_text(condition, blocked=False)
        for condition in fit_conditions
    ]
    reasons = [reason for reason in reasons if reason]
    if not reasons:
        return None

    asserted_keys = [
        action.get("key", "")
        for action in rule_record.get("actions", [])
        if action.get("type") == "assert_fact"
    ]
    if any(key.endswith("_foundation_candidate") for key in asserted_keys):
        ending = "so a foundations-first start makes more sense right now."
    else:
        ending = "which reinforces this recommendation."
    return f"{_sentence_case(_join_text(reasons[:2], conjunction='and'))}, {ending}"


def _build_goal_reason(top_goal: dict[str, Any], rule_record: dict[str, Any]) -> str | None:
    focus = _goal_focus_phrase(top_goal)
    hours_condition = next(
        (condition for condition in rule_record.get("matched_conditions", []) if condition.get("fact") == "hours_per_week"),
        None,
    )
    time_reason = None
    if hours_condition is not None:
        hours = hours_condition.get("actual")
        if hours is not None:
            time_reason = f"you have about {_format_number(hours)} hours a week available for study"

    if "Foundations" in top_goal.get("goal_name", ""):
        return f"This foundations track gives you a realistic starting point for {focus}."

    if time_reason:
        return f"This track is a realistic next step toward {focus} with your current weekly study time."
    return f"This track is a realistic next step toward {focus}."


def _build_alternative_reason(top_goal: dict[str, Any], alternative: dict[str, Any]) -> str | None:
    reasons = [
        _condition_reason_text(condition, blocked=True)
        for condition in alternative.get("blocking_conditions", [])
    ]
    reasons = [reason for reason in reasons if reason]
    if not reasons:
        return None

    if alternative.get("status") == "blocked":
        if top_goal.get("goal_id") == "SE_GOAL_07":
            specialization = "backend specialization" if "Backend" in alternative.get("goal_name", "") else "specialization"
            return f"{alternative['goal_name']} was not chosen yet because core programming readiness still needs more practice before {specialization}."
        return f"{alternative['goal_name']} was not chosen because {_join_text(reasons[:2], conjunction='and')}."
    return f"{top_goal['goal_name']} stayed ahead of {alternative['goal_name']} because {_join_text(reasons[:2], conjunction='and')}."


def _merge_why_entries(
    top_goal: dict[str, Any],
    selected_goal_trace: dict[str, Any],
    clause_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    clauses = _take_unique_entries(clause_entries, limit=4)
    if not clauses:
        return []

    merged_text = _build_concise_why_text(top_goal, selected_goal_trace)
    merged_facts = _take_unique_strings(
        [fact for clause in clauses for fact in clause.get("facts", [])],
        limit=12,
    )
    merged_rules = _take_unique_strings(
        [rule for clause in clauses for rule in clause.get("rules", [])],
        limit=6,
    )
    return [
        {
            "text": merged_text,
            "facts": merged_facts,
            "rules": merged_rules,
        }
    ]


def _build_concise_why_text(top_goal: dict[str, Any], selected_goal_trace: dict[str, Any]) -> str:
    fit_sentence = _fit_sentence(top_goal, selected_goal_trace)
    alternative_sentence = _alternative_sentence(top_goal, selected_goal_trace)
    return f"{_strip_trailing_period(fit_sentence)}. {_strip_trailing_period(alternative_sentence)}."


def _fit_sentence(top_goal: dict[str, Any], selected_goal_trace: dict[str, Any]) -> str:
    goal_id = str(top_goal.get("goal_id", ""))
    direction = _selected_direction(top_goal, selected_goal_trace)
    if goal_id == "SE_GOAL_06":
        return "This track fits your backend direction while keeping the start realistic for your current level."
    if goal_id == "SE_GOAL_08":
        return "This track fits your frontend direction while keeping the start realistic for your current level."
    if goal_id == "SE_GOAL_07":
        if direction and direction != "software engineering":
            return f"This track fits your {direction} direction while building software engineering foundations first."
        return "This track fits your current level and gives you a realistic start in software engineering."
    if goal_id == "AIE_GOAL_06":
        return "This track fits your AI direction while matching your current study time and preparation level."
    if goal_id == "CNE_GOAL_06":
        return "This track fits your networking direction while building the fundamentals first."
    if direction:
        return f"This track fits your {direction} direction and current readiness."
    return "This track fits your current readiness better than the alternatives."


def _alternative_sentence(top_goal: dict[str, Any], selected_goal_trace: dict[str, Any]) -> str:
    goal_id = str(top_goal.get("goal_id", ""))
    if goal_id == "SE_GOAL_06":
        return "Full backend specialization was not selected yet because your Python and API foundations still need more practice."
    if goal_id == "SE_GOAL_08":
        return "Full frontend specialization was not selected yet because your web and JavaScript foundations still need more practice."
    if goal_id == "SE_GOAL_07":
        return "A specialization track was not selected yet because your core programming foundations still need more practice."
    if goal_id == "AIE_GOAL_06":
        return "A specialized AI track was not selected yet because your Python, math, or lab readiness still needs strengthening."
    if goal_id == "CNE_GOAL_06":
        return "A specialized networking track was not selected yet because your networking basics or lab readiness still need more practice."

    alternative = next(iter(selected_goal_trace.get("alternatives_evaluated", []) or []), {})
    alternative_name = str(alternative.get("goal_name") or "An alternative track").removesuffix(" Track")
    readiness = _readiness_reason_from_conditions(alternative.get("blocking_conditions", []))
    return f"{alternative_name} was not selected because {readiness}."


def _selected_direction(top_goal: dict[str, Any], selected_goal_trace: dict[str, Any]) -> str:
    goal_name = str(top_goal.get("goal_name", "")).casefold()
    if "backend" in goal_name:
        return "backend"
    if "frontend" in goal_name:
        return "frontend"
    if "network" in goal_name or "ccna" in goal_name:
        return "networking"
    if any(token in goal_name for token in ("ai", "machine learning", "computer vision", "language processing")):
        return "AI"

    direction_by_fact = {
        "prefers_backend": "backend",
        "prefers_frontend": "frontend",
        "prefers_security": "security",
        "prefers_ml": "AI",
        "prefers_cv": "computer vision",
        "prefers_nlp": "natural language processing",
        "prefers_data_eng": "AI data engineering",
        "prefers_netsec": "network security",
        "prefers_wireless": "wireless networking",
        "prefers_cloud_net": "cloud networking",
    }
    for condition in selected_goal_trace.get("matched_conditions", []):
        if condition.get("actual") is True and condition.get("fact") in direction_by_fact:
            return direction_by_fact[condition["fact"]]
    return _goal_focus_phrase(top_goal)


def _readiness_reason_from_conditions(conditions: list[dict[str, Any]]) -> str:
    facts = {condition.get("fact") for condition in conditions}
    if "python_skill" in facts and "api_concepts" in facts:
        return "your Python and API readiness still needs strengthening"
    if "python_skill" in facts:
        return "your Python readiness still needs strengthening"
    if "api_concepts" in facts:
        return "your API foundations still need more practice"
    if "math_skill" in facts:
        return "your math foundations still need strengthening"
    if "lab_access" in facts:
        return "your lab readiness still needs strengthening"
    if facts & {"networking_basic", "networking_theory", "osi_layers_basic", "ip_subnetting_basic"}:
        return "your networking fundamentals still need more practice"
    if "weak_device" in facts:
        return "device limitations would make that option harder right now"
    if "hours_per_week" in facts:
        return "your weekly study time is better suited to the selected track"
    return "the selected track is the stronger current fit"


def _is_fit_condition(condition: dict[str, Any]) -> bool:
    fact_key = condition.get("fact", "")
    actual = condition.get("actual")
    if fact_key.endswith("_foundation_candidate"):
        return False
    if condition.get("op") == "score_advantage":
        return True
    if fact_key.startswith("prefers_"):
        return actual is True
    if fact_key in {"target_outcome", "hours_per_week", "pretrack_readiness", "current_level", "english_level"}:
        return actual is not None
    return actual is True


def _build_strength_text(
    fact_key: str,
    value: Any,
    fact_type: str,
    top_goal: dict[str, Any] | None = None,
) -> str | None:
    if (top_goal or {}).get("goal_id") == "SE_GOAL_07":
        if fact_key == "prefers_backend":
            return "Backend-oriented software work appears to be your clearest longer-term direction after strengthening the foundations."
        if fact_key == "prefers_frontend":
            return "Frontend-oriented software work appears to be your clearest longer-term direction after strengthening the foundations."
        if fact_key == "prefers_security":
            return "Security-focused software work appears to be your clearest longer-term direction after strengthening the foundations."

    if fact_key == "prefers_backend":
        return "Backend work is the clearest direction in your answers."
    if fact_key == "prefers_frontend":
        return "Frontend work is the clearest direction in your answers."
    if fact_key == "prefers_devops":
        return "DevOps and cloud work are the clearest direction in your answers."
    if fact_key == "prefers_security":
        return "Security-focused work is the clearest direction in your answers."
    if fact_key == "prefers_ml":
        return "Machine learning is the clearest direction in your answers."
    if fact_key == "prefers_cv":
        return "Computer vision is the clearest direction in your answers."
    if fact_key == "prefers_nlp":
        return "Natural language processing is the clearest direction in your answers."
    if fact_key == "prefers_data_eng":
        return "AI data engineering is the clearest direction in your answers."
    if fact_key == "prefers_netsec":
        return "Network security is the clearest direction in your answers."
    if fact_key == "prefers_wireless":
        return "Wireless networking is the clearest direction in your answers."
    if fact_key == "prefers_cloud_net":
        return "Cloud networking is the clearest direction in your answers."
    if fact_key == "prefers_projects":
        return "Hands-on practice is your selected learning style."
    if fact_key == "prefers_building_apps":
        return "Building applications directly is part of your selected direction."
    if fact_key == "target_outcome":
        outcome_map = {
            "job": "Your goal is clearly job-focused.",
            "internship": "Your goal is clearly internship-focused.",
            "freelance": "Your goal is clearly freelance-focused.",
            "research": "Your goal is clearly research-focused.",
        }
        return outcome_map.get(value, None)
    if fact_key == "hours_per_week":
        return f"You currently have about {_format_number(value)} hours a week available for study."
    if fact_key == "english_level":
        return "English learning resources are still usable for your current path."
    if fact_key == "pretrack_readiness":
        return f"Your readiness to begin is around {_natural_scale(value)}."
    if fact_type.startswith("scale"):
        return f"Your {_fact_label(fact_key)} is around {_natural_scale(value)}."
    if fact_type == "boolean":
        return f"You already have a starting base in {_fact_label(fact_key)}."
    return None


def _condition_reason_text(condition: dict[str, Any], *, blocked: bool) -> str:
    fact_key = condition.get("fact", "")
    actual = condition.get("actual")

    if fact_key.endswith("_foundation_candidate"):
        return ""
    if fact_key == "prefers_backend":
        return "your answers clearly lean toward backend work" if not blocked else "your answers lean more toward backend work than that alternative"
    if fact_key == "prefers_frontend":
        return "your answers clearly lean toward frontend work" if not blocked else "your answers lean more toward frontend work than that alternative"
    if fact_key == "prefers_ml":
        return "your answers clearly lean toward machine learning" if not blocked else "your answers lean more toward machine learning than that alternative"
    if fact_key == "prefers_cv":
        return "your answers clearly lean toward computer vision" if not blocked else "your answers lean more toward computer vision than that alternative"
    if fact_key == "prefers_nlp":
        return "your answers clearly lean toward natural language processing" if not blocked else "your answers lean more toward natural language processing than that alternative"
    if fact_key == "prefers_data_eng":
        return "your answers clearly lean toward AI data engineering" if not blocked else "your answers lean more toward AI data engineering than that alternative"
    if fact_key == "prefers_netsec":
        return "your answers clearly lean toward network security" if not blocked else "your answers lean more toward network security than that alternative"
    if fact_key == "prefers_wireless":
        return "your answers clearly lean toward wireless networking" if not blocked else "your answers lean more toward wireless networking than that alternative"
    if fact_key == "prefers_cloud_net":
        return "your answers clearly lean toward cloud networking" if not blocked else "your answers lean more toward cloud networking than that alternative"
    if fact_key == "api_concepts" and actual is False:
        return "you still need API basics"
    if fact_key == "programming_basic" and actual is False:
        return "you still need basic coding practice"
    if fact_key == "basics_control_flow" and actual is False:
        return "you still need more confidence with conditions and loops"
    if fact_key == "web_basics":
        return "your web basics still need reinforcement"
    if fact_key == "dom_events" and actual is False:
        return "you still need more practice with interactive page behavior"
    if fact_key == "http_client_basics" and actual is False:
        return "you still need practice with browser requests and API responses"
    if fact_key == "python_skill_basic" and actual is False:
        return "you still need the basic building blocks of Python"
    if fact_key == "any_programming_experience" and actual is False:
        return "you still need more real coding practice"
    if fact_key == "python_skill":
        return "your current Python level is still below the starting level for that option"
    if fact_key == "js_skill":
        return "your current JavaScript level is still below the starting level for that option"
    if fact_key == "math_skill":
        return "your math foundation is still below the starting level for that option"
    if fact_key == "networking_theory":
        return "you still need a stronger networking theory base"
    if fact_key == "linux_cli_net_tools_skill":
        return "your Linux networking-tool practice is still early"
    if fact_key == "lab_access":
        return "that option expects access to a lab or simulator"
    if fact_key == "hours_per_week":
        if blocked:
            return "that option needs more weekly study time than you currently have"
        return "you have enough weekly time to move forward steadily"
    if fact_key == "weak_device" and actual is True:
        return "that option expects a stronger device setup"
    if fact_key == "weak_internet" and actual is True:
        return "that option depends more heavily on stable internet access"
    if fact_key == "english_level":
        return "that option expects more comfort with English learning resources"
    if fact_key == "pretrack_readiness":
        return "your current readiness is enough to start learning"
    if condition.get("op") == "score_advantage":
        return _signal_fragment(fact_key, actual)
    return f"your {_fact_label(fact_key)} still needs to be stronger for that option"


def _top_signal_fragments(contributions: list[dict[str, Any]]) -> list[str]:
    fragments: list[str] = []
    for item in contributions:
        fragment = _signal_fragment(item["fact"], item["value"])
        if fragment:
            fragments.append(fragment)
    return fragments


def _signal_fragment(fact_key: str, value: Any) -> str:
    if fact_key == "prefers_backend":
        return "your backend interest"
    if fact_key == "prefers_frontend":
        return "your frontend interest"
    if fact_key == "prefers_projects":
        return "your preference for hands-on learning"
    if fact_key == "prefers_building_apps":
        return "your interest in building applications"
    if fact_key == "prefers_ml":
        return "your interest in machine learning"
    if fact_key == "target_outcome":
        return {
            "job": "your job-focused goal",
            "internship": "your internship goal",
            "freelance": "your freelance goal",
            "research": "your research goal",
        }.get(value, "your end goal")
    if fact_key == "hours_per_week":
        return "your available study time"
    if fact_key == "pretrack_readiness":
        return "your readiness to start"
    if fact_key == "english_level":
        return "your ability to use English learning resources"
    if fact_key == "linux_cli_net_tools_skill":
        return "your Linux networking-tool practice"
    return f"your {_fact_label(fact_key)}"


def _goal_focus_phrase(top_goal: dict[str, Any]) -> str:
    goal_name = str(top_goal.get("goal_name", "")).replace(" Track", "").replace(" Foundations", "").strip()
    focus_map = {
        "backend development": "backend development",
        "frontend development": "frontend development",
        "software engineering": "software engineering",
        "machine learning engineering": "machine learning engineering",
        "computer vision": "computer vision",
        "natural language processing": "natural language processing",
        "ai": "AI",
        "networking": "networking",
        "ccna network operations": "CCNA-level network operations",
    }
    return focus_map.get(goal_name.lower(), goal_name.lower())


def _prioritize_qualifying_rules(
    rule_ids: list[str],
    firing_map: dict[str, dict[str, Any]],
) -> list[str]:
    def sort_key(rule_id: str) -> tuple[int, int, int]:
        rule_record = firing_map.get(rule_id, {})
        tier = str(rule_record.get("tier") or "")
        priority = int(rule_record.get("priority") or 0)
        tier_rank = 0 if tier == "goal" else 1
        fallback_rank = 1 if "SANITY_006" in rule_id else 0
        return (tier_rank, fallback_rank, -priority)

    return sorted(rule_ids, key=sort_key)
