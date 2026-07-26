"""
GPES Forward Chaining Engine — Action Executor.

Applies actions produced by fired rules to the Working Memory
and the inference context (qualified/excluded goals, reasons).
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.working_memory import WorkingMemory


# ---------------------------------------------------------------------------
# Inference context — mutable accumulator passed through the engine
# ---------------------------------------------------------------------------

def make_context() -> Dict[str, Any]:
    """
    Create a fresh inference context.

    Keys
    ----
    qualified_goals : dict[goal_id, list[str]]
        Goal IDs that passed eligibility, with reasons.
    excluded_goals  : dict[goal_id, list[str]]
        Goal IDs that were disqualified, with reasons.
    reasons_why     : list[str]
        General explanatory reasons (category "why" / "info").
    strengths       : list[str]
        User strengths detected.
    weaknesses      : list[str]
        User weaknesses detected.
    constraints     : list[str]
        Environmental constraints detected.
    """
    return {
        "qualified_goals": {},   # goal_id -> [reason, ...]
        "excluded_goals": {},    # goal_id -> [reason, ...]
        "reasons_why": [],
        "strengths": [],
        "weaknesses": [],
        "constraints": [],
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_action(
    action: dict,
    wm: WorkingMemory,
    context: Dict[str, Any],
    source_rule_id: str = "",
) -> None:
    """
    Execute a single action dict.

    Supported action types
    ----------------------
    assert_fact   : {type, key, value}
    qualify_goal  : {type, goal_id, reason}
    exclude_goal  : {type, goal_id, reason}
    add_reason    : {type, category, text}

    Parameters
    ----------
    action : dict
        One element from a rule's ``actions`` list.
    wm : WorkingMemory
        Current working memory (may be mutated by assert_fact).
    context : dict
        Inference context (mutated in-place).
    source_rule_id : str
        The rule that produced this action (for traceability).
    """
    atype = action.get("type", "")

    if atype == "assert_fact":
        _do_assert_fact(action, wm, source_rule_id)

    elif atype == "qualify_goal":
        _do_qualify_goal(action, context)

    elif atype == "exclude_goal":
        _do_exclude_goal(action, context)

    elif atype == "add_reason":
        _do_add_reason(action, context)

    # Unknown action types are silently ignored (forward-compatible).


def apply_actions(
    actions: List[dict],
    wm: WorkingMemory,
    context: Dict[str, Any],
    source_rule_id: str = "",
) -> None:
    """Apply every action in the list."""
    for a in actions:
        apply_action(a, wm, context, source_rule_id)


# Handlers

def _do_assert_fact(action: dict, wm: WorkingMemory, rule_id: str) -> None:
    key = action["key"]
    value = action["value"]
    wm.set(key, value, source_rule_id=rule_id)


def _do_qualify_goal(action: dict, ctx: Dict[str, Any]) -> None:
    gid = action["goal_id"]
    reason = action.get("reason", "")
    ctx["qualified_goals"].setdefault(gid, []).append(reason)


def _do_exclude_goal(action: dict, ctx: Dict[str, Any]) -> None:
    gid = action["goal_id"]
    reason = action.get("reason", "")
    ctx["excluded_goals"].setdefault(gid, []).append(reason)


def _do_add_reason(action: dict, ctx: Dict[str, Any]) -> None:
    category = action.get("category", "why")
    text = action.get("text", "")

    if category == "strength":
        ctx["strengths"].append(text)
    elif category == "weakness":
        ctx["weaknesses"].append(text)
    elif category == "constraint":
        ctx["constraints"].append(text)
    else:
        # "why", "info", or anything else → reasons_why
        ctx["reasons_why"].append(text)
