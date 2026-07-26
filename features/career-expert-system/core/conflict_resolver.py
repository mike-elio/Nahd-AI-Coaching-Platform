"""
GPES Forward Chaining Engine — Conflict Resolver.

When multiple rules are applicable at the same time, this module
selects the single best rule to fire next.

Resolution order (highest precedence first):
  1. Tier order:  profile > goal > sanity
  2. Priority:    higher number fires first
  3. Specificity: more conditions = more specific = fires first
  4. Recency:     rules whose conditions reference recently-updated
                  facts are preferred (sum of recency timestamps)
"""

from __future__ import annotations

from typing import List

from core.working_memory import WorkingMemory

# ---------------------------------------------------------------------------
# Tier ordering — lower number = fires first
# ---------------------------------------------------------------------------

_TIER_ORDER = {
    "profile": 0,
    "goal": 1,
    "sanity": 2,
}

_DEFAULT_TIER = 99


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def choose_next_rule(
    applicable_rules: List[dict],
    wm: WorkingMemory,
) -> dict | None:
    """
    Select the single best rule from *applicable_rules*.

    Returns None if the list is empty.

    Sorting key (ascending, then we pick the first):
      1. tier_order  (lower = earlier)
      2. -priority   (higher priority first)
      3. -specificity (more conditions first)
      4. -recency_sum (higher recency sum first)
    """
    if not applicable_rules:
        return None

    def sort_key(rule: dict):
        tier_rank = _TIER_ORDER.get(rule.get("tier", ""), _DEFAULT_TIER)
        priority = rule.get("priority", 0)
        specificity = len(rule.get("conditions", []))
        recency_sum = _compute_recency_sum(rule, wm)

        return (
            tier_rank,        # 1) tier: lower = first
            -priority,        # 2) priority: higher = first
            -specificity,     # 3) specificity: more conditions = first
            -recency_sum,     # 4) recency: higher sum = first
        )

    applicable_rules.sort(key=sort_key)
    return applicable_rules[0]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_recency_sum(rule: dict, wm: WorkingMemory) -> int:
    """Sum of recency timestamps for all facts referenced by the rule's conditions."""
    total = 0
    for cond in rule.get("conditions", []):
        fact_key = cond.get("fact", "")
        total += wm.get_recency(fact_key)
    return total
