"""Trace and goal-analysis helpers for GPES output formatting."""

from __future__ import annotations

import json
from typing import Any

from core.output_specs import GOAL_COMPARISON_ORDER


def _build_selected_goal_trace(
    top_goal: dict[str, Any] | None,
    normalized_facts: dict[str, Any],
    inferred_facts: dict[str, Any],
    fc_result: dict[str, Any],
    goal_catalog: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    if not top_goal:
        return {
            "goal_id": None,
            "triggered_rules": [],
            "matched_conditions": [],
            "failed_conditions": [],
            "alternatives_evaluated": [],
        }

    goal_id = top_goal["goal_id"]
    firing_map = {record["rule_id"]: record for record in fc_result.get("rule_firings", [])}
    direct_rule_ids = [
        record["rule_id"]
        for record in fc_result.get("rule_firings", [])
        if any(
            action.get("type") == "qualify_goal" and action.get("goal_id") == goal_id
            for action in record.get("actions", [])
        )
    ]
    support_rule_ids = _collect_support_rule_ids(direct_rule_ids, firing_map)
    triggered_rule_ids = _ordered_rule_ids(
        fc_result.get("fired_rules", []),
        [*support_rule_ids, *direct_rule_ids],
    )
    matched_conditions = _dedupe_conditions(
        [
            {**condition, "rule_id": rule_id}
            for rule_id in triggered_rule_ids
            for condition in firing_map.get(rule_id, {}).get("matched_conditions", [])
        ]
    )
    alternatives = _build_alternative_analysis(top_goal, normalized_facts, fc_result, goal_catalog)
    failed_conditions = _dedupe_conditions(
        [
            condition
            for alternative in alternatives
            for condition in alternative.get("blocking_conditions", [])
        ]
    )
    return {
        "goal_id": goal_id,
        "triggered_rules": triggered_rule_ids,
        "qualifying_rules": direct_rule_ids,
        "matched_conditions": matched_conditions,
        "failed_conditions": failed_conditions,
        "alternatives_evaluated": alternatives,
        "inferred_facts_used": [
            {
                "fact": fact_key,
                "value": inferred_facts.get(fact_key),
                "source_rule_id": fc_result.get("fact_sources", {}).get(fact_key),
            }
            for fact_key in sorted(
                {
                    condition["fact"]
                    for condition in matched_conditions
                    if fc_result.get("fact_sources", {}).get(condition["fact"])
                }
            )
        ],
    }


def _build_alternative_analysis(
    top_goal: dict[str, Any],
    normalized_facts: dict[str, Any],
    fc_result: dict[str, Any],
    goal_catalog: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    goal_id = top_goal["goal_id"]
    ranked_map = {
        goal["goal_id"]: goal
        for goal in fc_result.get("ranked_goals", [])
    }
    candidate_ids: list[str] = []
    for candidate_id in GOAL_COMPARISON_ORDER.get(goal_id, []):
        candidate_ids.append(candidate_id)
    for ranked_goal in fc_result.get("ranked_goals", [])[1:3]:
        candidate_ids.append(ranked_goal["goal_id"])

    analyses: list[dict[str, Any]] = []
    seen: set[str] = set()
    for candidate_id in candidate_ids:
        if candidate_id == goal_id or candidate_id in seen or candidate_id not in goal_catalog:
            continue
        seen.add(candidate_id)
        candidate_goal = goal_catalog[candidate_id]
        candidate_result = _evaluate_goal(candidate_goal, normalized_facts)
        ranked_candidate = ranked_map.get(candidate_id)
        if candidate_result["failed_eligibility"] or candidate_result["triggered_disqualifiers"]:
            preference_disqualifiers = [
                item
                for item in candidate_result["triggered_disqualifiers"]
                if str(item.get("fact", "")).startswith("prefers_")
            ]
            blocking_conditions = (
                preference_disqualifiers
                or candidate_result["failed_eligibility"]
                or candidate_result["triggered_disqualifiers"]
            )
            analyses.append(
                {
                    "goal_id": candidate_id,
                    "goal_name": candidate_goal["goal_name"],
                    "status": "blocked",
                    "blocking_conditions": blocking_conditions,
                    "fit_score_percent": ranked_candidate.get("fit_score_percent")
                    if ranked_candidate
                    else None,
                }
            )
            continue
        if ranked_candidate:
            analyses.append(
                {
                    "goal_id": candidate_id,
                    "goal_name": candidate_goal["goal_name"],
                    "status": "lower_score",
                    "blocking_conditions": _better_score_facts(top_goal, ranked_candidate),
                    "fit_score_percent": ranked_candidate.get("fit_score_percent"),
                }
            )

    return analyses[:2]


def _evaluate_goal(goal: dict[str, Any], facts: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    matched_eligibility: list[dict[str, Any]] = []
    failed_eligibility: list[dict[str, Any]] = []
    triggered_disqualifiers: list[dict[str, Any]] = []

    for condition in goal.get("eligibility_rules", []):
        snapshot = _evaluate_condition_snapshot(condition, facts)
        if snapshot["matched"]:
            matched_eligibility.append(snapshot)
        else:
            failed_eligibility.append(snapshot)

    for condition in goal.get("disqualifiers", []):
        snapshot = _evaluate_condition_snapshot(condition, facts)
        if snapshot["matched"]:
            triggered_disqualifiers.append(snapshot)

    return {
        "matched_eligibility": matched_eligibility,
        "failed_eligibility": failed_eligibility,
        "triggered_disqualifiers": triggered_disqualifiers,
    }


def _evaluate_condition_snapshot(condition: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    fact_key = condition["fact"]
    actual = facts.get(fact_key)
    return {
        "fact": fact_key,
        "op": condition["op"],
        "expected": condition["value"],
        "actual": actual,
        "matched": _matches_condition(actual, condition["op"], condition["value"], fact_key in facts),
    }


def _matches_condition(actual: Any, op: str, expected: Any, fact_present: bool) -> bool:
    if not fact_present:
        return False
    if op == "in":
        return isinstance(expected, list) and actual in expected
    if op in {">", ">=", "<", "<="}:
        try:
            actual = float(actual)
            expected = float(expected)
        except (TypeError, ValueError):
            return False
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected
    if op == ">":
        return actual > expected
    if op == ">=":
        return actual >= expected
    if op == "<":
        return actual < expected
    if op == "<=":
        return actual <= expected
    return False


def _better_score_facts(top_goal: dict[str, Any], alternative_goal: dict[str, Any]) -> list[dict[str, Any]]:
    top_contributions = {
        item["fact"]: item
        for item in top_goal.get("contributions", [])
    }
    alternative_contributions = {
        item["fact"]: item
        for item in alternative_goal.get("contributions", [])
    }
    candidates: list[dict[str, Any]] = []
    for fact_key, contribution in top_contributions.items():
        alt_contribution = alternative_contributions.get(fact_key, {}).get("contribution", 0)
        if contribution.get("contribution", 0) > alt_contribution:
            candidates.append(
                {
                    "fact": fact_key,
                    "actual": contribution.get("value"),
                    "op": "score_advantage",
                    "expected": alt_contribution,
                    "matched": True,
                }
            )
    candidates.sort(
        key=lambda item: top_contributions[item["fact"]].get("contribution", 0),
        reverse=True,
    )
    return candidates[:2]


def _collect_support_rule_ids(
    direct_rule_ids: list[str],
    firing_map: dict[str, dict[str, Any]],
) -> list[str]:
    queue = list(direct_rule_ids)
    collected: list[str] = []
    seen = set(direct_rule_ids)
    while queue:
        rule_id = queue.pop(0)
        for condition in firing_map.get(rule_id, {}).get("matched_conditions", []):
            source_rule_id = condition.get("source_rule_id")
            if not source_rule_id or source_rule_id in seen or source_rule_id not in firing_map:
                continue
            seen.add(source_rule_id)
            collected.append(source_rule_id)
            queue.append(source_rule_id)
    return collected


def _ordered_rule_ids(fired_rules: list[str], desired_rule_ids: list[str]) -> list[str]:
    desired = set(desired_rule_ids)
    return [rule_id for rule_id in fired_rules if rule_id in desired]


def _dedupe_conditions(conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for condition in conditions:
        key = (
            condition.get("rule_id"),
            condition.get("fact"),
            condition.get("op"),
            json.dumps(condition.get("expected"), sort_keys=True, default=str),
            json.dumps(condition.get("actual"), sort_keys=True, default=str),
            condition.get("matched"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(condition)
    return result
