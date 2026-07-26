"""
GPES Forward Chaining Engine — Inference Engine.

Orchestrates the full inference loop:
  1. Compute applicable rules (conditions all true, not yet fired)
  2. Resolve conflicts → pick one rule
  3. Execute its actions
  4. Mark as fired
  5. Repeat until no applicable rules or max_steps reached

Usage:
  from core.inference_engine import InferenceEngine
  result = InferenceEngine.run("SE", facts_dict, rules_list)
"""

from __future__ import annotations

from typing import Any, Dict, List

from core.working_memory import WorkingMemory
from core.condition_evaluator import evaluate_all, evaluate_condition
from core.actions import apply_actions, make_context
from core.conflict_resolver import choose_next_rule
from core.goal_score import GoalScorer


class InferenceEngine:
    """
    Stateless forward-chaining engine.

    Call ``InferenceEngine.run(...)`` — everything is encapsulated
    inside the single class method.
    """

    @staticmethod
    def run(
        domain: str,
        facts: Dict[str, Any],
        rules: List[dict],
        max_steps: int = 500,
    ) -> Dict[str, Any]:
        """
        Execute forward chaining and return the inference result.

        Parameters
        ----------
        domain : str
            SE | AIE | CNE (used only for metadata in the result).
        facts : dict
            Initial facts from the interview session.
        rules : list[dict]
            Rule dicts (from rules_loader or directly from RULES).
        max_steps : int
            Safety limit to prevent infinite loops.

        Returns
        -------
        dict
            Keys:
              qualified_goals  : dict[goal_id] -> [reasons]
              excluded_goals   : dict[goal_id] -> [reasons]
              final_qualified  : list[goal_id]  (qualified minus excluded)
              inferred_facts   : dict  (full WM snapshot)
              why              : list[str]
              strengths        : list[str]
              weaknesses       : list[str]
              constraints      : list[str]
              fired_rules      : list[str]  (ordered by firing sequence)
              steps            : int
        """
        # --- Initialise ---
        normalized_facts = _normalize_input_facts(domain, facts)
        wm = WorkingMemory(normalized_facts)
        ctx = make_context()
        fired: set[str] = set()
        fired_order: list[str] = []
        rule_firings: list[dict[str, Any]] = []

        # --- Main loop ---
        for step in range(1, max_steps + 1):

            # 1) Find applicable rules
            applicable: List[dict] = []
            for rule in rules:
                rid = rule["rule_id"]
                if rid in fired:
                    continue
                if evaluate_all(rule.get("conditions", []), wm):
                    applicable.append(rule)

            if not applicable:
                break  # quiescence — no more rules can fire

            # 2) Conflict resolution → single winner
            winner = choose_next_rule(applicable, wm)
            if winner is None:
                break  # should not happen, but defensive

            # 3) Fire: execute actions
            rid = winner["rule_id"]
            rule_firings.append(
                _snapshot_rule_firing(winner, wm)
            )
            apply_actions(
                winner.get("actions", []),
                wm,
                ctx,
                source_rule_id=rid,
            )

            # 4) Mark as fired
            fired.add(rid)
            fired_order.append(rid)

        # --- Build result ---

        # final_qualified = qualified minus excluded
        excluded_ids = set(ctx["excluded_goals"].keys())
        final_qualified = [
            gid for gid in ctx["qualified_goals"]
            if gid not in excluded_ids
        ]

        # --- Goal Scoring & Ranking ---
        ranked_goals: list = []
        top_goal: dict | None = None

        if final_qualified:
            from app.expert import load_goals

            all_domain_goals = load_goals(domain)
            qualified_goals_list = [
                g for g in all_domain_goals
                if g["goal_id"] in final_qualified
            ]
            current_facts = wm.export_facts()
            ranked_goals = GoalScorer.rank_goals(qualified_goals_list, current_facts)
            if ranked_goals:
                top_goal = ranked_goals[0]

        return {
            "domain": domain,
            "qualified_goals": ctx["qualified_goals"],
            "excluded_goals": ctx["excluded_goals"],
            "final_qualified": sorted(final_qualified),
            "input_facts": dict(facts),
            "normalized_facts": normalized_facts,
            "inferred_facts": wm.export_facts(),
            "fact_sources": wm.export_sources(),
            "why": ctx["reasons_why"],
            "strengths": ctx["strengths"],
            "weaknesses": ctx["weaknesses"],
            "constraints": ctx["constraints"],
            "fired_rules": fired_order,
            "rule_firings": rule_firings,
            "steps": len(fired_order),
            "ranked_goals": ranked_goals,
            "top_goal": top_goal,
        }


def _snapshot_rule_firing(rule: dict[str, Any], wm: WorkingMemory) -> dict[str, Any]:
    """Capture the matched conditions and actions for a fired rule."""
    conditions: list[dict[str, Any]] = []
    for cond in rule.get("conditions", []):
        fact_key = cond["fact"]
        conditions.append(
            {
                "fact": fact_key,
                "op": cond["op"],
                "expected": cond["value"],
                "actual": wm.get(fact_key) if wm.has(fact_key) else None,
                "matched": evaluate_condition(cond, wm),
                "source_rule_id": wm.export_sources().get(fact_key),
            }
        )

    actions: list[dict[str, Any]] = []
    for action in rule.get("actions", []):
        action_snapshot = {"type": action.get("type")}
        for field in ("goal_id", "reason", "category", "text", "key", "value"):
            if field in action:
                action_snapshot[field] = action[field]
        actions.append(action_snapshot)

    return {
        "rule_id": rule.get("rule_id", ""),
        "tier": rule.get("tier"),
        "priority": rule.get("priority"),
        "matched_conditions": conditions,
        "actions": actions,
    }


def _normalize_input_facts(domain: str, facts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize incoming interview / facts-file keys into the rule engine's
    canonical fact names and derive a few stable direction hints.
    """
    normalized = dict(facts)
    domain = domain.upper()

    alias_map: dict[str, dict[str, str]] = {
        "SE": {
            "has_written_code": "programming_basic",
            "understands_basic_programming": "basics_control_flow",
            "readiness_to_learn": "pretrack_readiness",
            "prefers_hands_on": "prefers_projects",
            "prefers_product_over_devops_security": "prefers_building_apps",
            "prefers_backend_over_frontend": "prefers_backend",
            "knows_http_methods": "api_concepts",
            "knows_status_codes": "status_codes_basic",
            "knows_openapi": "api_documentation_openapi",
            "erd_skill": "db_modeling_skill",
            "input_validation_practice": "input_validation",
            "endpoint_testing_experience": "backend_testing",
            "cacheability_knowledge": "http_caching",
            "same_build_config_idea": "config_12factor",
        },
        "AIE": {
            "readiness_to_learn": "pretrack_readiness",
        },
    }

    for source_key, target_key in alias_map.get(domain, {}).items():
        if source_key in normalized and target_key not in normalized:
            normalized[target_key] = normalized[source_key]

    if domain == "SE":
        if (
            normalized.get("prefers_building_apps") is True
            and normalized.get("prefers_backend") is False
            and "prefers_frontend" not in normalized
        ):
            normalized["prefers_frontend"] = True

    if domain == "AIE":
        if (
            normalized.get("research_interest") is False
            and normalized.get("prefers_cv") is False
            and normalized.get("prefers_nlp") is False
            and normalized.get("prefers_data_eng") is False
            and "prefers_ml" not in normalized
        ):
            normalized["prefers_ml"] = True

    if domain == "CNE":
        focus_area = normalized.get("cne_focus_area")
        focus_to_pref = {
            "network_security": "prefers_netsec",
            "wireless_wifi": "prefers_wireless",
            "cloud_datacenter": "prefers_cloud_net",
        }
        derived_pref = focus_to_pref.get(focus_area)
        if derived_pref and derived_pref not in normalized:
            normalized[derived_pref] = True

    return normalized


# Demo (run:  python -m core.inference_engine)

if __name__ == "__main__":
    from core.output_formatter import build_final_output, render_console_summary
    from core.rules_loader import load_rules

    DOMAIN = "SE"

    sample_facts: Dict[str, Any] = {
        # Universal
        "user_type": "graduate",
        "current_level": "intermediate",
        "hours_per_week": 12,
        "target_outcome": "job",
        "time_horizon": "medium",
        "weak_device": False,
        "weak_internet": False,
        "pressure_load": "medium",
        "prefers_projects": True,
        "english_level": "intermediate",
        # SE domain
        "python_skill": 3,
        "js_skill": 1,
        "sql_skill": 2,
        "problem_solving": 3,
        "prefers_backend": True,
        "prefers_frontend": False,
        "prefers_devops": False,
        "prefers_security": False,
        "linux_skill": 2,
        "math_tolerance": True,
    }

    rules = load_rules(DOMAIN)
    fc_result = InferenceEngine.run(DOMAIN, sample_facts, rules)

    final_output = build_final_output(DOMAIN, sample_facts, fc_result)
    print(render_console_summary(final_output))
