from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.inference_engine import InferenceEngine
from core.output_formatter import build_final_output
from core.rules_loader import load_rules


class TestFallbackCoverage:
    def test_se_backend_beginner_gets_foundation_goal(self):
        facts = {
            "current_level": "beginner",
            "hours_per_week": 20,
            "target_outcome": "job",
            "prefers_hands_on": True,
            "prefers_product_over_devops_security": True,
            "prefers_backend_over_frontend": True,
            "has_written_code": False,
            "understands_basic_programming": False,
            "readiness_to_learn": 3,
            "knows_http_methods": False,
            "knows_status_codes": False,
            "knows_openapi": False,
            "erd_skill": 1,
            "input_validation_practice": False,
            "endpoint_testing_experience": False,
            "cacheability_knowledge": False,
            "same_build_config_idea": False,
            "weak_device": False,
        }

        result = InferenceEngine.run("SE", facts, load_rules("SE"))
        final_output = build_final_output("SE", facts, result)

        assert final_output["top_goal"] is not None
        assert final_output["top_goal"]["goal_id"] == "SE_GOAL_06"
        assert len(final_output["why_selected"]) == 1
        assert "backend" in final_output["why_selected"][0].casefold()
        assert "foundations" in final_output["why_selected"][0].casefold()
        assert all("alignment" not in item.casefold() for item in final_output["why_selected"])
        assert any("hands-on" in item.casefold() for item in final_output["strengths"])
        assert any("job-focused" in item.casefold() for item in final_output["strengths"])
        assert all("you show" not in item.casefold() for item in final_output["strengths"])
        assert len(final_output["gap_resolution_plan"]) >= 2
        assert all(isinstance(item["action"], str) for item in final_output["gap_resolution_plan"])
        assert all(
            "=" not in item and "True" not in item and "False" not in item
            for item in final_output["why_selected"] + final_output["strengths"] + [x["action"] for x in final_output["gap_resolution_plan"]]
        )
        assert "SE_GOAL_Q_006" in final_output["debug_trace"]["rules_used"]
        assert final_output["debug_trace"]["validation"]["passed"] is True

    def test_se_frontend_beginner_prefers_specific_foundation(self):
        facts = {
            "current_level": "beginner",
            "hours_per_week": 14,
            "target_outcome": "job",
            "prefers_projects": True,
            "prefers_building_apps": True,
            "prefers_backend": False,
            "web_basics": 1,
            "programming_basic": True,
            "basics_control_flow": True,
        }

        result = InferenceEngine.run("SE", facts, load_rules("SE"))
        final_output = build_final_output("SE", facts, result)

        assert final_output["top_goal"] is not None
        assert final_output["top_goal"]["goal_id"] == "SE_GOAL_08"
        assert len(final_output["why_selected"]) == 1
        assert "frontend" in final_output["why_selected"][0].casefold()
        assert any("html" in item["action"].casefold() or "javascript" in item["action"].casefold() for item in final_output["gap_resolution_plan"])
        assert len(final_output["gap_resolution_plan"]) >= 2
        assert "SE_GOAL_Q_008" in final_output["debug_trace"]["rules_used"]

    def test_aie_beginner_gets_foundation_goal(self):
        facts = {
            "hours_per_week": 8,
            "target_outcome": "job",
            "weak_device": False,
            "research_interest": False,
            "prefers_cv": False,
            "prefers_nlp": False,
            "prefers_data_eng": False,
            "python_skill_basic": False,
            "any_programming_experience": False,
            "pretrack_readiness": 3,
            "english_level": "intermediate",
        }

        result = InferenceEngine.run("AIE", facts, load_rules("AIE"))
        final_output = build_final_output("AIE", facts, result)

        assert final_output["top_goal"] is not None
        assert final_output["top_goal"]["goal_id"] == "AIE_GOAL_06"
        assert len(final_output["why_selected"]) == 1
        assert "machine learning" in final_output["why_selected"][0].casefold() or "ai" in final_output["why_selected"][0].casefold()
        assert any("python" in item["action"].casefold() for item in final_output["gap_resolution_plan"])
        assert len(final_output["gap_resolution_plan"]) >= 2
        assert "AIE_GOAL_Q_006" in final_output["debug_trace"]["rules_used"]

    def test_cne_beginner_gets_foundation_goal(self):
        facts = {
            "hours_per_week": 10,
            "target_outcome": "job",
            "weak_internet": False,
            "networking_basic": False,
            "osi_layers_basic": False,
            "ip_subnetting_basic": False,
            "linux_cli_net_tools_skill": 1,
            "cne_focus_area": "not_sure",
        }

        result = InferenceEngine.run("CNE", facts, load_rules("CNE"))
        final_output = build_final_output("CNE", facts, result)

        assert final_output["top_goal"] is not None
        assert final_output["top_goal"]["goal_id"] == "CNE_GOAL_06"
        assert len(final_output["why_selected"]) == 1
        assert "networking" in final_output["why_selected"][0].casefold()
        assert any("packet tracer" in item["action"].casefold() or "ping" in item["action"].casefold() for item in final_output["gap_resolution_plan"])
        assert len(final_output["gap_resolution_plan"]) >= 2
        assert "CNE_GOAL_Q_006" in final_output["debug_trace"]["rules_used"]

    def test_se_foundations_frontend_leaning_generates_five_steps(self):
        """SE_GOAL_07 (general SE Foundations) with frontend-relevant gaps
        and limited weekly hours must produce 5 concrete, actionable steps.
        prefers_frontend is NOT set so the engine picks SE_GOAL_07 (general)
        rather than SE_GOAL_08 (frontend-specific foundations).
        """
        facts = {
            "current_level": "beginner",
            "hours_per_week": 5,
            "target_outcome": "job",
            "prefers_projects": True,
            "prefers_building_apps": True,
            "programming_basic": False,
            "basics_control_flow": False,
            "problem_solving": 1,
            "web_basics": 1,
            "js_skill": 1,
            "dom_events": False,
            "http_client_basics": False,
            "version_control_git": False,
            "weak_device": False,
        }

        result = InferenceEngine.run("SE", facts, load_rules("SE"))
        final_output = build_final_output("SE", facts, result)

        assert final_output["top_goal"] is not None
        goal_id = final_output["top_goal"]["goal_id"]
        assert goal_id == "SE_GOAL_07"

        plan = final_output["gap_resolution_plan"]

        # Must produce between 2 and 4 items
        assert 2 <= len(plan) <= 4, f"Expected 2 to 4 plan items, got {len(plan)}: {plan}"

        # No action should contain "because"
        assert all("because" not in item["action"].casefold() for item in plan), (
            f"Some actions contain 'because': {[s['action'] for s in plan if 'because' in s['action']]}"
        )

        # At least one item references frontend-related content
        assert any(
            "html" in item["action"].casefold()
            or "javascript" in item["action"].casefold()
            or "css" in item["action"].casefold()
            or "frontend" in item["action"].casefold()
            or "web" in item["action"].casefold()
            for item in plan
        ), f"No frontend-related action found in: {plan}"

        # No vague generic phrases
        for item in plan:
            assert "give the remaining weak spots" not in item["action"].casefold(), (
                f"Vague fallback text found: {item['action']}"
            )

        # No raw fact values or Python literals leaked into output
        for item in plan:
            assert "=" not in item["action"] and "True" not in item["action"] and "False" not in item["action"], (
                f"Leaked literal in action: {item['action']}"
            )

    def test_se_foundations_security_leaning_uses_concrete_minimum_steps(self):
        facts = {
            "current_level": "beginner",
            "pretrack_readiness": 3,
            "hours_per_week": 22,
            "target_outcome": "freelance",
            "prefers_security": True,
            "weak_device": False,
        }

        result = InferenceEngine.run("SE", facts, load_rules("SE"))
        final_output = build_final_output("SE", facts, result)

        assert final_output["top_goal"] is not None
        assert final_output["top_goal"]["goal_id"] == "SE_GOAL_07"

        plan = final_output["gap_resolution_plan"]
        assert 2 <= len(plan) <= 4
        assert all("because" not in item["action"].casefold() for item in plan)

        forbidden = (
            "Review the recommended fundamentals",
            "Build one small project to validate your interest",
            "Retake the interview after gaining more exposure",
        )
        for item in plan:
            assert all(phrase not in item["action"] for phrase in forbidden)

        assert any(
            "python calculator" in item["action"].casefold()
            or "functions" in item["action"].casefold()
            or "input validation" in item["action"].casefold()
            for item in plan
        )
        assert any(
            "api" in item["action"].casefold()
            or "crud" in item["action"].casefold()
            for item in plan
        )
        assert all("strong alignment" not in item.casefold() for item in final_output["why_selected"])
        frontend_app = (PROJECT_ROOT / "frontend" / "static" / "app.js").read_text(encoding="utf-8")
        assert "You show strong alignment" not in frontend_app
        assert all(
            "directly in that specialization" not in item.casefold()
            and "security-focused work is the clearest direction" not in item.casefold()
            and "backend work is the clearest direction" not in item.casefold()
            and "frontend work is the clearest direction" not in item.casefold()
            for item in final_output["strengths"]
        )
        assert any(
            "Security-focused software work appears to be your clearest longer-term direction after strengthening the foundations."
            in item
            for item in final_output["strengths"]
        )
        assert any(
            "A specialization track was not selected yet because your core programming foundations still need more practice."
            in item
            for item in final_output["why_selected"]
        )


