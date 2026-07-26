"""Produce fact-driven recommendation summaries from inference results."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.output_copy import (
    _format_fact_value,
)
from core.output_gaps import (
    _build_gap_entries,
)
from core.output_gap_resolution import (
    build_gap_resolution_plan,
)
from core.output_reasons import (
    _build_strength_entries,
    _build_why_entries,
)
from core.output_validation import (
    _collect_trace_facts,
    _collect_trace_rules,
    _validate_output,
)
from core.output_trace import (
    _build_selected_goal_trace,
)
from core.output_specs import (
    SUMMARY_SECTIONS,
)


_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_GOAL_FILES = {
    "SE": _PROJECT_ROOT / "knowledge_base" / "goals" / "goals_se.json",
    "AIE": _PROJECT_ROOT / "knowledge_base" / "goals" / "goals_aie.json",
    "CNE": _PROJECT_ROOT / "knowledge_base" / "goals" / "goals_cne.json",
}


def build_final_output(domain: str, facts: dict[str, Any], fc_result: dict[str, Any]) -> dict[str, Any]:
    ranked_goals = fc_result.get("ranked_goals", []) if fc_result.get("final_qualified") else []
    top_goal = ranked_goals[0] if ranked_goals else None
    normalized_facts = dict(fc_result.get("normalized_facts", facts))
    inferred_facts = dict(fc_result.get("inferred_facts", normalized_facts))
    goal_catalog = _load_goal_catalog(domain)
    top_goal_detail = _merge_goal_metadata(top_goal, goal_catalog)
    selected_goal_trace = _build_selected_goal_trace(
        top_goal_detail,
        normalized_facts,
        inferred_facts,
        fc_result,
        goal_catalog,
    )
    why_entries = _build_why_entries(top_goal_detail, selected_goal_trace, fc_result)
    strength_entries = _build_strength_entries(top_goal_detail, normalized_facts)
    gap_entries = _build_gap_entries(top_goal_detail, normalized_facts, fc_result)
    gap_resolution_plan = build_gap_resolution_plan(gap_entries, top_goal_detail, normalized_facts)
    validation = _validate_output(why_entries, strength_entries, gap_resolution_plan, selected_goal_trace)

    final_output = {
        "domain": domain.upper(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "top_goal": top_goal_detail,
        "ranked_goals": ranked_goals,
        "qualified_goals": fc_result.get("qualified_goals", {}),
        "excluded_goals": fc_result.get("excluded_goals", {}),
        "why_selected": [entry["text"] for entry in why_entries],
        "strengths": [entry["text"] for entry in strength_entries],
        "gaps": [entry["text"] for entry in gap_entries],
        "gap_resolution_plan": gap_resolution_plan,
        "next_steps": [],
        "constraints": fc_result.get("constraints", []),
        "weaknesses": fc_result.get("weaknesses", []),
        "fired_rules": fc_result.get("fired_rules", []),
        "input_facts": dict(facts),
        "normalized_facts": normalized_facts,
        "goal_trace": selected_goal_trace,
        "debug_trace": {
            "facts_used": _collect_trace_facts(why_entries, strength_entries, gap_entries),
            "rules_used": _collect_trace_rules(why_entries),
            "gaps_identified": [
                {
                    "fact": gap["fact"],
                    "actual": gap["actual"],
                    "expected": gap.get("expected"),
                    "source": gap.get("source"),
                }
                for gap in gap_entries
            ],
            "selected_goal_trace": selected_goal_trace,
            "validation": validation,
        },
    }
    return final_output


def render_console_summary(final_output: dict[str, Any]) -> str:
    top_goal = final_output.get("top_goal")
    if not top_goal:
        return "\nNo qualified goal found.\n"

    lines = [
        "",
        "GOAL:",
        f"  {top_goal['goal_name']}",
        "",
        "FIT SCORE:",
        f"  {top_goal['fit_score_percent']}%",
    ]
    for title, key, fallback in SUMMARY_SECTIONS:
        lines.extend(["", title])
        items = final_output.get(key, []) or [fallback]
        if key == "why_selected":
            lines.extend(f"  {item}" for item in items)
            continue
        if key == "gap_resolution_plan":
            lines.extend(
                f"  •  {item['title']}: {item['action']}" if isinstance(item, dict) else f"  •  {item}"
                for item in items
            )
            continue
        lines.extend(f"  •  {item}" for item in items)
    lines.append("")
    return "\n".join(lines)


def _load_goal_catalog(domain: str) -> dict[str, dict[str, Any]]:
    path = _GOAL_FILES[domain.upper()]
    goals = json.loads(path.read_text(encoding="utf-8"))
    return {goal["goal_id"]: goal for goal in goals}


def _merge_goal_metadata(
    top_goal: dict[str, Any] | None,
    goal_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    if not top_goal:
        return None
    merged = dict(goal_catalog.get(top_goal.get("goal_id", ""), {}))
    merged.update(top_goal)
    return merged


def _format_condition_list(
    conditions: list[dict[str, Any]],
    *,
    failed: bool,
    limit: int,
) -> str:
    snippets = [
        _format_condition(condition, failed=failed)
        for condition in conditions[:limit]
    ]
    return "; ".join(snippets)


def _format_condition(condition: dict[str, Any], *, failed: bool) -> str:
    fact_key = condition["fact"]
    actual = condition.get("actual")
    op = condition.get("op")
    expected = condition.get("expected")
    actual_present = actual is not None or isinstance(actual, bool)
    actual_display = _format_fact_value(fact_key, actual)
    expected_display = _format_fact_value(fact_key, expected)

    if op == "score_advantage":
        return f"{fact_key} = {actual_display} contributed more strongly here"
    if not actual_present:
        return f"{fact_key} is missing, so {fact_key} {op} {expected_display} was not satisfied"
    if failed:
        if condition.get("matched"):
            return f"{fact_key} = {actual_display} triggered {fact_key} {op} {expected_display}"
        return f"{fact_key} = {actual_display} failed {fact_key} {op} {expected_display}"
    if op == "==":
        return f"{fact_key} = {actual_display}"
    if op == "in":
        expected_values = ", ".join(str(item) for item in expected)
        return f"{fact_key} = {actual_display} is in [{expected_values}]"
    return f"{fact_key} = {actual_display} satisfies {fact_key} {op} {expected_display}"

