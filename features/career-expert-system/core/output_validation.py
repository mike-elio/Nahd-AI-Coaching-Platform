"""Validation and trace-collection helpers for GPES output formatting."""

from __future__ import annotations

from typing import Any

from core.output_specs import GENERIC_PHRASES


def _take_unique_entries(entries: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for entry in entries:
        text = entry["text"].strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(entry)
        if len(result) >= limit:
            break
    return result


def _validate_output(
    why_entries: list[dict[str, Any]],
    strength_entries: list[dict[str, Any]],
    gap_resolution_plan: list[dict[str, str]],
    selected_goal_trace: dict[str, Any],
) -> dict[str, Any]:
    issues: list[str] = []
    if why_entries and not _collect_trace_rules(why_entries):
        issues.append("WHY THIS TRACK must reference at least one triggered rule.")
    if why_entries and not _collect_trace_facts(why_entries):
        issues.append("WHY THIS TRACK must reference at least one fact.")
    for entry in strength_entries:
        if not entry.get("facts"):
            issues.append(f"Strength line lacks a fact trace: {entry['text']}")
    if not gap_resolution_plan and selected_goal_trace.get("goal_id"):
        issues.append("Gap resolution plan is empty.")
    if not selected_goal_trace.get("failed_conditions") and selected_goal_trace.get("goal_id"):
        issues.append("Selected goal trace is missing failed alternative conditions.")

    for text in [
        *(entry["text"] for entry in why_entries),
        *(entry["text"] for entry in strength_entries),
        *(item["action"] for item in gap_resolution_plan),
    ]:
        lowered = text.casefold()
        for phrase in GENERIC_PHRASES:
            if phrase in lowered:
                issues.append(f"Generic phrase detected: {phrase}")
                break

    return {
        "passed": not issues,
        "issues": issues,
    }


def _collect_trace_facts(*entry_groups: list[dict[str, Any]]) -> list[str]:
    facts: list[str] = []
    seen: set[str] = set()
    for group in entry_groups:
        for entry in group:
            for fact_key in entry.get("facts", []):
                if fact_key not in seen:
                    seen.add(fact_key)
                    facts.append(fact_key)
    return facts


def _collect_trace_rules(*entry_groups: list[dict[str, Any]]) -> list[str]:
    rules: list[str] = []
    seen: set[str] = set()
    for group in entry_groups:
        for entry in group:
            for rule_id in entry.get("rules", []):
                if rule_id not in seen:
                    seen.add(rule_id)
                    rules.append(rule_id)
    return rules
