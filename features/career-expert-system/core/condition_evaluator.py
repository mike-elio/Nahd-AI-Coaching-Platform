"""
GPES Forward Chaining Engine — Condition Evaluator.

Safely evaluates a single condition dict against Working Memory.
No eval / exec — only explicit operator dispatch.
"""

from __future__ import annotations

from typing import Any

from core.working_memory import WorkingMemory

# Supported operators
_OPS = frozenset({"==", "!=", ">", ">=", "<", "<=", "in"})


def evaluate_condition(cond: dict, wm: WorkingMemory) -> bool:
    """
    Evaluate one condition ``{fact, op, value}`` against *wm*.

    Returns False if:
      - the fact is missing from WM
      - the operator is unsupported
      - a type error occurs during comparison

    Parameters
    ----------
    cond : dict
        Keys: ``fact`` (str), ``op`` (str), ``value`` (any).
    wm : WorkingMemory
        Current working memory.
    """
    fact_key: str = cond["fact"]
    op: str = cond["op"]
    expected: Any = cond["value"]

    if op not in _OPS:
        return False

    if not wm.has(fact_key):
        return False  # missing fact → condition fails

    fact_val: Any = wm.get(fact_key)

    try:
        return _compare(fact_val, op, expected)
    except (TypeError, ValueError):
        return False


def evaluate_all(conditions: list[dict], wm: WorkingMemory) -> bool:
    """Return True only if **every** condition in *conditions* passes (AND)."""
    return all(evaluate_condition(c, wm) for c in conditions)


# Internal dispatch

def _compare(fact_val: Any, op: str, expected: Any) -> bool:
    """Dispatch the comparison — never uses eval."""

    if op == "in":
        if not isinstance(expected, list):
            return False
        return fact_val in expected

    # Numeric coercion for relational operators
    if op in (">", ">=", "<", "<="):
        try:
            fact_val = float(fact_val)
            expected = float(expected)
        except (TypeError, ValueError):
            pass

    if op == "==":
        return fact_val == expected
    if op == "!=":
        return fact_val != expected
    if op == ">":
        return fact_val > expected   # type: ignore[operator]
    if op == ">=":
        return fact_val >= expected  # type: ignore[operator]
    if op == "<":
        return fact_val < expected   # type: ignore[operator]
    if op == "<=":
        return fact_val <= expected  # type: ignore[operator]

    return False
