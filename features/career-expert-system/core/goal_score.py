"""
GPES Expert System — Goal Scoring Layer.

Scores qualified goals based on the user's facts and each goal's
relevant_facts, base_score, and a small set of penalty rules.

Public API
----------
GoalScorer.score_goal(goal, facts) -> dict
GoalScorer.rank_goals(goals, facts) -> list[dict]
"""

from __future__ import annotations

from typing import Any, Dict, List

from app.models import (
    UNIVERSAL_FACTS,
    SE_FACTS,
    AIE_FACTS,
    CNE_FACTS,
)


# ---------------------------------------------------------------------------
# Merge all fact schemas for type look-up
# ---------------------------------------------------------------------------

_ALL_FACT_TYPES: Dict[str, str] = {}
_ALL_FACT_TYPES.update(UNIVERSAL_FACTS)
_ALL_FACT_TYPES.update(SE_FACTS)
_ALL_FACT_TYPES.update(AIE_FACTS)
_ALL_FACT_TYPES.update(CNE_FACTS)


# ---------------------------------------------------------------------------
# Enum preference mapping  (goal field → preferred value)
#
# For each enum fact that appears in relevant_facts, this mapping tells us
# what value is considered a "positive match" when computing a contribution.
# If the fact is missing from this map, we treat any non-None value as +0.
# ---------------------------------------------------------------------------

_ENUM_PREFERENCES: Dict[str, List[str]] = {
    # target_outcome: all practical outcomes are positive
    "target_outcome": ["job", "internship", "freelance", "research"],
    # current_level
    "current_level": ["intermediate", "advanced"],
    # english_level
    "english_level": ["intermediate", "advanced"],
    # pressure_load: low/medium are positive
    "pressure_load": ["low", "medium"],
}


# ---------------------------------------------------------------------------
# GoalScorer
# ---------------------------------------------------------------------------

class GoalScorer:
    """
    Stateless scorer — all methods are static / class-level.

    Scoring recipe
    ~~~~~~~~~~~~~~
    1. Start with ``goal["base_score"]``.
    2. Walk ``goal["relevant_facts"]`` and compute a *contribution* for each
       fact that actually exists in *facts*:
       - **scale 0..5** → ``(value / 5) * 10``   (max +10 per fact)
       - **boolean**    → ``+5`` if True, ``0`` if False
       - **enum**       → ``+5`` if matches a preferred value, else ``0``
    3. Apply global penalties:
       - ``weak_device == True``     → ``-10``
       - ``hours_per_week < 6``      → ``-8``
       - ``pressure_load == "high"`` → ``-5``
    4. ``fit_score_percent = clamp(raw_score, 0, 100)``
    """

    # ------------------------------------------------------------------ #
    # score_goal
    # ------------------------------------------------------------------ #

    @staticmethod
    def score_goal(goal: dict, facts: Dict[str, Any]) -> dict:
        """
        Compute a score dict for a single *goal* given the user's *facts*.

        Returns
        -------
        dict  with keys:
            goal_id, goal_name, raw_score, penalties, contributions,
            fit_score_percent
        """
        goal_id:   str = goal.get("goal_id", "UNKNOWN")
        goal_name: str = goal.get("goal_name", "")
        base_score: int = goal.get("base_score", 50)
        selection_priority: float = float(goal.get("selection_priority", 0))

        raw_score: float = base_score
        contributions: List[dict] = []
        penalties:     List[dict] = []

        # ----- Contributions from relevant_facts -------------------------
        for fact_key in goal.get("relevant_facts", []):
            if fact_key not in facts:
                continue  # fact not collected — skip silently

            value = facts[fact_key]
            fact_type = _ALL_FACT_TYPES.get(fact_key, "")

            contribution = _compute_contribution(fact_key, value, fact_type)

            if contribution != 0:
                raw_score += contribution
                contributions.append({
                    "fact": fact_key,
                    "value": value,
                    "contribution": contribution,
                })

        # ----- Penalties --------------------------------------------------
        penalty_list = _compute_penalties(facts)
        for p in penalty_list:
            raw_score += p["penalty"]  # penalty is negative
            penalties.append(p)

        # ----- Fit score (clamped) ----------------------------------------
        fit_score_percent = min(max(raw_score, 0), 100)

        fit_score_percent = round(fit_score_percent, 2)

        return {
            "goal_id": goal_id,
            "goal_name": goal_name,
            "raw_score": round(raw_score, 2),
            "contributions": contributions,
            "penalties": penalties,
            "fit_score_percent": fit_score_percent,
            "selection_priority": selection_priority,
            "ranking_score": round(fit_score_percent + selection_priority, 2),
        }

    # rank_goals

    @staticmethod
    def rank_goals(
        goals: List[dict],
        facts: Dict[str, Any],
    ) -> List[dict]:
        """
        Score every goal in *goals* and return them sorted descending
        by ``fit_score_percent``.
        """
        scored = [GoalScorer.score_goal(g, facts) for g in goals]
        scored.sort(
            key=lambda s: (
                s.get("ranking_score", 0),
                s["fit_score_percent"],
                s.get("selection_priority", 0),
                s["raw_score"],
            ),
            reverse=True,
        )
        return scored


# Internal helpers

def _compute_contribution(
    fact_key: str,
    value: Any,
    fact_type: str,
) -> float:
    """
    Return the numeric contribution of a single fact.

    Rules:
      - scale 0..5  → normalized * 10
      - boolean      → +5 / 0
      - enum         → +5 if preferred, else 0
    """
    # --- scale 0..5 ---
    if fact_type.startswith("scale"):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        normalized = numeric / 5.0
        return normalized * 10.0

    # --- boolean ---
    if fact_type == "boolean":
        return 5.0 if value is True else 0.0

    # --- enum ---
    if fact_type.startswith("enum"):
        prefs = _ENUM_PREFERENCES.get(fact_key)
        if prefs is not None:
            return 5.0 if value in prefs else 0.0
        # No preference list defined → neutral
        return 0.0

    # --- integer (e.g. hours_per_week) ---
    if fact_type.startswith("integer"):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return 0.0
        # Generic: cap at 40 for safety
        normalized = min(numeric / 40.0, 1.0)
        return normalized * 10.0

    return 0.0


def _compute_penalties(facts: Dict[str, Any]) -> List[dict]:
    """
    Return a list of penalty dicts that apply based on the user's facts.

    Each penalty dict: {"fact": ..., "reason": ..., "penalty": <negative int>}
    """
    result: List[dict] = []

    # weak_device == True → -10
    if facts.get("weak_device") is True:
        result.append({
            "fact": "weak_device",
            "reason": "Weak device limits heavy-tooling goals",
            "penalty": -10,
        })

    # hours_per_week < 6 → -8
    hours = facts.get("hours_per_week")
    if hours is not None:
        try:
            if float(hours) < 6:
                result.append({
                    "fact": "hours_per_week",
                    "reason": "Less than 6 hours/week available",
                    "penalty": -8,
                })
        except (TypeError, ValueError):
            pass

    # pressure_load == "high" → -5
    if facts.get("pressure_load") == "high":
        result.append({
            "fact": "pressure_load",
            "reason": "High pressure load reduces capacity",
            "penalty": -5,
        })

    return result
