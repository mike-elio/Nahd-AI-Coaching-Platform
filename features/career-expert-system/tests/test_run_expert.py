from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.output_formatter import render_console_summary
from tools.run_expert import (
    _match_choice,
    _normalize_domain,
    _parse_boolean_input,
    _parse_multi_choice_input,
    _parse_numeric_input,
)


class TestDomainHelpers:
    def test_normalize_domain_uppercases(self):
        assert _normalize_domain("se") == "SE"


class TestInputParsing:
    def test_parse_boolean_truthy(self):
        assert _parse_boolean_input("yes") is True

    def test_parse_boolean_falsy(self):
        assert _parse_boolean_input("0") is False

    def test_parse_numeric_int(self):
        assert _parse_numeric_input("4", as_int=True) == 4

    def test_parse_numeric_float(self):
        assert _parse_numeric_input("4.5", as_int=False) == 4.5

    def test_match_choice_by_index(self):
        assert _match_choice("2", ["internship", "job"]) == "job"

    def test_match_choice_by_text(self):
        assert _match_choice("Research", ["internship", "research"]) == "research"

    def test_parse_multi_choice(self):
        result = _parse_multi_choice_input("1, research", ["internship", "job", "research"])
        assert result == ["internship", "research"]


class TestConsoleSummary:
    def test_render_console_summary_keeps_dynamic_sections(self):
        final_output = {
            "top_goal": {
                "goal_id": "g1",
                "goal_name": "Backend Engineer",
                "fit_score_percent": 87,
            },
            "why_selected": [
                "Backend work is the clearest direction in your answers. You currently have about 12 hours a week available for study. Frontend Engineer was not chosen because your answers lean more toward backend work than that alternative.",
            ],
            "strengths": ["Backend work is the clearest direction in your answers.", "Your goal is clearly job-focused."],
            "gaps": ["Your Python level is still below the starting level this track expects."],
            "gap_resolution_plan": [
                {"title": "Programming basics", "action": "Build your core coding base first with tiny scripts and short logic exercises."}
            ],
        }

        summary = render_console_summary(final_output)

        assert "GOAL:" in summary
        assert "Backend Engineer" in summary
        assert "FIT SCORE:" in summary
        assert "87%" in summary
        assert "WHY THIS TRACK:" in summary
        assert "Backend work is the clearest direction" in summary
        assert "CORE STRENGTHS:" in summary
        assert "job-focused" in summary
        assert "GAP RESOLUTION PLAN:" in summary
        assert "Programming basics: Build your core coding base first" in summary
