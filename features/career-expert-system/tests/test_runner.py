"""
Tests for the Interview Runner.

Covers: session creation, question loading, answer submission,
branching (true/false paths), session completion (END),
at least one full path per domain (SE), and FastAPI endpoint integration.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.expert import (
    DEFAULT_MAX_QUESTIONS,
    InterviewManager,
    QuestionLoader,
    SessionState,
    create_session,
)
from app.expert import ExpertSystemService, SessionEntry


# ---------------------------------------------------------------------------
# Sample KB fixture (same as data/sample_questions.json)
# ---------------------------------------------------------------------------

SAMPLE_KB = [
    {
        "id": "N_TEST_001",
        "domain": "SE",
        "level_filter": ["beginner", "intermediate", "advanced"],
        "type": "boolean",
        "fact_key": "programming_basic",
        "weight": 3,
        "next_if_true": "N_TEST_002",
        "next_if_false": "N_TEST_003",
        "source_citation": "SWEBOK v3",
        "pool_pair": [
            {"id": "N_TEST_001a", "text_ar": "هل سبق لك كتابة كود؟", "text_en": "Have you written code?"},
            {"id": "N_TEST_001b", "text_ar": "عندك خبرة برمجة؟", "text_en": "Programming experience?"},
        ],
    },
    {
        "id": "N_TEST_002",
        "domain": "SE",
        "level_filter": ["beginner", "intermediate", "advanced"],
        "type": "scale",
        "fact_key": "python_skill",
        "weight": 2,
        "next_if_true": "N_TEST_004",
        "next_if_false": "N_TEST_003",
        "source_citation": "ACM CS 2023",
        "pool_pair": [
            {"id": "N_TEST_002a", "text_ar": "Python (0-5)", "text_en": "Python (0-5)"},
            {"id": "N_TEST_002b", "text_ar": "مستواك Python؟", "text_en": "Your Python level?"},
        ],
        "scale_min": 0,
        "scale_max": 5,
    },
    {
        "id": "N_TEST_003",
        "domain": "SE",
        "level_filter": ["beginner"],
        "type": "choice",
        "fact_key": "target_outcome",
        "weight": 1,
        "next_if_true": "N_TEST_005",
        "next_if_false": "N_TEST_005",
        "source_citation": "SWEBOK v3",
        "pool_pair": [
            {"id": "N_TEST_003a", "text_ar": "هدفك؟", "text_en": "Your goal?"},
            {"id": "N_TEST_003b", "text_ar": "النتيجة؟", "text_en": "Outcome?"},
        ],
        "choices_ar": ["تدريب", "وظيفة", "عمل حر", "بحث"],
        "choices_en": ["internship", "job", "freelance", "research"],
    },
    {
        "id": "N_TEST_004",
        "domain": "SE",
        "level_filter": ["intermediate", "advanced"],
        "type": "boolean",
        "fact_key": "prefers_backend",
        "weight": 2,
        "next_if_true": "END",
        "next_if_false": "N_TEST_005",
        "source_citation": "SWEBOK v3",
        "pool_pair": [
            {"id": "N_TEST_004a", "text_ar": "Backend؟", "text_en": "Backend?"},
            {"id": "N_TEST_004b", "text_ar": "Server-side؟", "text_en": "Server-side?"},
        ],
    },
    {
        "id": "N_TEST_005",
        "domain": "SE",
        "level_filter": ["beginner", "intermediate", "advanced"],
        "type": "numeric",
        "fact_key": "hours_per_week",
        "weight": 1,
        "next_if_true": "END",
        "next_if_false": "END",
        "source_citation": "SWEBOK v3",
        "pool_pair": [
            {"id": "N_TEST_005a", "text_ar": "ساعات؟", "text_en": "Hours?"},
            {"id": "N_TEST_005b", "text_ar": "وقتك؟", "text_en": "Time?"},
        ],
        "truthy_rule": ">= 8",
    },
]


def _build_linear_kb(total_nodes: int, domain: str = "SE") -> list[dict]:
    nodes: list[dict] = []
    for index in range(1, total_nodes + 1):
        node_id = f"N_LINEAR_{index:03d}"
        next_node = f"N_LINEAR_{index + 1:03d}" if index < total_nodes else "END"
        nodes.append(
            {
                "id": node_id,
                "domain": domain,
                "level_filter": ["beginner", "intermediate", "advanced"],
                "type": "boolean",
                "fact_key": f"fact_{index:03d}",
                "weight": 1,
                "next_if_true": next_node,
                "next_if_false": next_node,
                "source_citation": "Synthetic test KB",
                "pool_pair": [
                    {"id": f"{node_id}a", "text_ar": f"سؤال {index}", "text_en": f"Question {index}?"},
                    {"id": f"{node_id}b", "text_ar": f"بديل {index}", "text_en": f"Alternate question {index}?"},
                ],
            }
        )
    return nodes


@pytest.fixture
def kb_path():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "sample.json"
        path.write_text(json.dumps(SAMPLE_KB, ensure_ascii=False), encoding="utf-8")
        yield path


@pytest.fixture
def long_kb_path():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "long_sample.json"
        path.write_text(json.dumps(_build_linear_kb(25), ensure_ascii=False), encoding="utf-8")
        yield path


# ---------------------------------------------------------------------------
# QuestionLoader tests
# ---------------------------------------------------------------------------

class TestQuestionLoader:
    def test_load_all_nodes(self, kb_path):
        loader = QuestionLoader(kb_path)
        assert len(loader.nodes) == 5

    def test_load_filtered_by_domain(self, kb_path):
        loader = QuestionLoader(kb_path, domain="SE")
        assert len(loader.nodes) == 5  # all are SE

    def test_get_start_node(self, kb_path):
        loader = QuestionLoader(kb_path, domain="SE")
        start = loader.get_start_node("SE")
        assert start is not None
        assert start.id == "N_TEST_001"

    def test_pick_variant_returns_valid(self, kb_path):
        loader = QuestionLoader(kb_path)
        node = loader.nodes["N_TEST_001"]
        variant = QuestionLoader.pick_variant(node)
        assert variant["node_id"] == "N_TEST_001"
        assert variant["variant_id"] in ("N_TEST_001a", "N_TEST_001b")
        assert variant["type"] == "boolean"

    def test_pick_variant_scale_has_metadata(self, kb_path):
        loader = QuestionLoader(kb_path)
        node = loader.nodes["N_TEST_002"]
        variant = QuestionLoader.pick_variant(node)
        assert "scale_min" in variant
        assert "scale_max" in variant

    def test_pick_variant_choice_has_choices(self, kb_path):
        loader = QuestionLoader(kb_path)
        node = loader.nodes["N_TEST_003"]
        variant = QuestionLoader.pick_variant(node)
        assert "choices_en" in variant
        assert len(variant["choices_en"]) == 4


# ---------------------------------------------------------------------------
# SessionState tests
# ---------------------------------------------------------------------------

class TestSessionState:
    def test_session_creation(self):
        s = SessionState("s1", "SE", "N_TEST_001")
        assert s.session_id == "s1"
        assert s.domain == "SE"
        assert s.current_node_id == "N_TEST_001"
        assert s.max_questions == DEFAULT_MAX_QUESTIONS
        assert not s.is_finished

    def test_to_dict(self):
        s = SessionState("s1", "SE", "N_TEST_001")
        d = s.to_dict()
        assert d["session_id"] == "s1"
        assert d["max_questions"] == DEFAULT_MAX_QUESTIONS
        assert d["answers"] == {}
        assert d["facts"] == {}


# ---------------------------------------------------------------------------
# InterviewManager tests
# ---------------------------------------------------------------------------

class TestInterviewManager:
    def test_get_current_question(self, kb_path):
        manager, session = create_session(kb_path, "SE")
        q = manager.get_current_question()
        assert q is not None
        assert q["node_id"] == "N_TEST_001"

    def test_submit_boolean_true_follows_true_path(self, kb_path):
        manager, session = create_session(kb_path, "SE")
        result = manager.submit_answer(True)
        assert result["recorded"]
        assert result["fact_key"] == "programming_basic"
        assert result["fact_value"] is True
        assert result["next_node"] == "N_TEST_002"
        assert session.current_node_id == "N_TEST_002"

    def test_submit_boolean_false_follows_false_path(self, kb_path):
        manager, session = create_session(kb_path, "SE")
        result = manager.submit_answer(False)
        assert result["recorded"]
        assert result["next_node"] == "N_TEST_003"
        assert session.current_node_id == "N_TEST_003"

    def test_full_path_true_true_true(self, kb_path):
        """Path: 001(T) → 002(high=T) → 004(T) → END"""
        manager, session = create_session(kb_path, "SE")

        # Q1: boolean True → go to 002
        r1 = manager.submit_answer(True)
        assert r1["next_node"] == "N_TEST_002"

        # Q2: scale 4 (≥ 2.5 midpoint) → truthy → go to 004
        r2 = manager.submit_answer(4)
        assert r2["next_node"] == "N_TEST_004"

        # Q3: boolean True → go to END
        r3 = manager.submit_answer(True)
        assert r3["next_node"] == "END"
        assert session.is_finished

    def test_full_path_false_choice_numeric(self, kb_path):
        """Path: 001(F) → 003(choice, always T) → 005(numeric) → END"""
        manager, session = create_session(kb_path, "SE")

        # Q1: boolean False → go to 003
        r1 = manager.submit_answer(False)
        assert r1["next_node"] == "N_TEST_003"

        # Q2: choice "internship" → always truthy → go to 005
        r2 = manager.submit_answer("internship")
        assert r2["next_node"] == "N_TEST_005"
        assert session.facts["target_outcome"] == "internship"

        # Q3: numeric 10 (≥ 8) → truthy → END
        r3 = manager.submit_answer(10)
        assert r3["next_node"] == "END"
        assert session.is_finished
        assert session.facts["hours_per_week"] == 10

    def test_numeric_falsy_path(self, kb_path):
        """Path: 001(F) → 003(choice) → 005(numeric < 8, falsy) → END"""
        manager, session = create_session(kb_path, "SE")
        manager.submit_answer(False)   # → 003
        manager.submit_answer("job")   # → 005
        r = manager.submit_answer(3)   # < 8 → falsy → END (both paths END)
        assert r["next_node"] == "END"
        assert r["fact_value"] == 3

    def test_scale_falsy_goes_false_path(self, kb_path):
        """Path: 001(T) → 002(scale=1, falsy) → 003"""
        manager, session = create_session(kb_path, "SE")
        manager.submit_answer(True)              # → 002
        r = manager.submit_answer(1)             # < 2.5 midpoint → false → 003
        assert r["next_node"] == "N_TEST_003"

    def test_finished_session_returns_none(self, kb_path):
        manager, session = create_session(kb_path, "SE")
        # Quick path to END
        manager.submit_answer(True)   # → 002
        manager.submit_answer(4)      # → 004
        manager.submit_answer(True)   # → END
        assert session.is_finished
        q = manager.get_current_question()
        assert q is None

    def test_facts_stored_correctly(self, kb_path):
        manager, session = create_session(kb_path, "SE")
        manager.submit_answer(True)    # programming_basic = True
        manager.submit_answer(4)       # python_skill = 4
        assert session.facts["programming_basic"] is True
        assert session.facts["python_skill"] == 4

    def test_history_tracked(self, kb_path):
        manager, session = create_session(kb_path, "SE")
        manager.submit_answer(True)
        manager.submit_answer(4)
        manager.submit_answer(True)
        assert session.history == ["N_TEST_001", "N_TEST_002", "N_TEST_004"]

    def test_question_limit_finishes_interview_after_twenty_answers(self, long_kb_path):
        manager, session = create_session(long_kb_path, "SE")

        for _ in range(DEFAULT_MAX_QUESTIONS - 1):
            result = manager.submit_answer(True)
            assert result["is_finished"] is False

        final_result = manager.submit_answer(True)
        assert final_result["is_finished"] is True
        assert final_result["next_node"] == "END"
        assert session.is_finished is True
        assert len(session.history) == DEFAULT_MAX_QUESTIONS
        assert manager.get_current_question() is None


class TestProgressCapping:
    def test_progress_estimated_total_is_capped_by_question_limit(self, long_kb_path):
        manager, session = create_session(long_kb_path, "SE")
        entry = SessionEntry(manager=manager, session=session)

        progress = ExpertSystemService._build_progress(entry)

        assert progress["estimated_total"] == DEFAULT_MAX_QUESTIONS
        assert progress["question_number"] == 1


# ---------------------------------------------------------------------------
# FastAPI integration tests
# ---------------------------------------------------------------------------

class TestFastAPIEndpoints:
    @pytest.fixture(autouse=True)
    def setup_client(self, kb_path):
        """Provide a fresh TestClient and clear sessions each run."""
        from app.main import app, _sessions
        _sessions.clear()
        self.client = TestClient(app)
        self.kb_path = str(kb_path)

    def test_start_session(self):
        resp = self.client.post("/api/expert/sessions", json={
            "domain": "SE",
            "kb_path": self.kb_path,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["domain"] == "SE"

    def test_full_flow(self):
        # Start
        resp = self.client.post("/api/expert/sessions", json={
            "domain": "SE",
            "kb_path": self.kb_path,
        })
        sid = resp.json()["session_id"]

        # Get first question
        resp = self.client.get(f"/api/expert/sessions/{sid}/question")
        assert resp.status_code == 200
        data = resp.json()
        assert data["finished"] is False
        assert data["question"]["node_id"] == "N_TEST_001"

        # Submit True
        resp = self.client.post(f"/api/expert/sessions/{sid}/answer", json={"answer": True})
        assert resp.json()["next_node"] == "N_TEST_002"

        # Submit scale 4
        resp = self.client.post(f"/api/expert/sessions/{sid}/answer", json={"answer": 4})
        assert resp.json()["next_node"] == "N_TEST_004"

        # Submit True → END
        resp = self.client.post(f"/api/expert/sessions/{sid}/answer", json={"answer": True})
        assert resp.json()["is_finished"] is True

        # Get state
        resp = self.client.get(f"/api/expert/sessions/{sid}/state")
        state = resp.json()
        assert state["is_finished"] is True
        assert state["facts"]["programming_basic"] is True
        assert state["facts"]["python_skill"] == 4
        assert state["facts"]["prefers_backend"] is True

    def test_session_not_found(self):
        resp = self.client.get("/api/expert/sessions/nonexistent/question")
        assert resp.status_code == 404

    def test_invalid_kb_path(self):
        resp = self.client.post("/api/expert/sessions", json={
            "domain": "SE",
            "kb_path": "/nonexistent/path.json",
        })
        assert resp.status_code == 404

    def test_api_router_back_returns_previous_question(self):
        resp = self.client.post("/api/expert/sessions", json={
            "domain": "SE",
            "kb_path": self.kb_path,
        })
        sid = resp.json()["session_id"]

        self.client.post(f"/api/expert/sessions/{sid}/answer", json={"answer": True})
        self.client.post(f"/api/expert/sessions/{sid}/answer", json={"answer": 4})

        resp = self.client.post(f"/api/expert/sessions/{sid}/back")
        assert resp.status_code == 200

        data = resp.json()
        assert data["finished"] is False
        assert data["question"]["node_id"] == "N_TEST_002"
        assert data["previous_answer"] == 4
        assert data["progress"]["answered_count"] == 1

    def test_api_router_result_endpoint(self):
        resp = self.client.post("/api/expert/sessions", json={
            "domain": "SE",
            "kb_path": self.kb_path,
        })
        sid = resp.json()["session_id"]

        self.client.post(f"/api/expert/sessions/{sid}/answer", json={"answer": True})
        self.client.post(f"/api/expert/sessions/{sid}/answer", json={"answer": 4})
        self.client.post(f"/api/expert/sessions/{sid}/answer", json={"answer": True})

        state_resp = self.client.get(f"/api/expert/sessions/{sid}/state")
        assert state_resp.status_code == 200
        assert state_resp.json()["final_output"] is not None

        result_resp = self.client.get(f"/api/expert/sessions/{sid}/result")
        assert result_resp.status_code == 200
        result = result_resp.json()
        assert result["session_id"] == sid
        assert "selected_goal" in result
        assert "why_selected" in result
        assert "strengths" in result
        assert "fit_score" in result
        assert "gap_resolution_plan" in result
        assert isinstance(result["gap_resolution_plan"], list)
        assert "next_steps" in result
        # gaps must always be present (may be empty list when no gaps exist)
        assert "gaps" in result
        assert isinstance(result["gaps"], list)


# ---------------------------------------------------------------------------
# Gap entries unit tests
# ---------------------------------------------------------------------------

class TestGapEntries:
    """Verify _build_gap_entries returns gaps for known gap-triggering facts."""

    def test_low_python_skill_produces_gap(self):
        from core.output_gaps import _build_gap_entries

        top_goal = {
            "goal_id": "SE_GOAL_01",
            "goal_name": "Backend Engineer",
            "relevant_facts": ["python_skill"],
            "penalties": [],
        }
        normalized_facts = {
            "python_skill": 1,   # below threshold of 3 → gap
        }
        fc_result = {}

        gaps = _build_gap_entries(top_goal, normalized_facts, fc_result)
        assert len(gaps) >= 1
        gap = gaps[0]
        assert "text" in gap
        assert "fact" in gap
        assert "step_text" in gap

    def test_weak_device_produces_gap(self):
        from core.output_gaps import _build_gap_entries

        top_goal = {
            "goal_id": "SE_GOAL_01",
            "goal_name": "Backend Engineer",
            "relevant_facts": [],
            "penalties": [],
        }
        normalized_facts = {"weak_device": True}
        fc_result = {}

        gaps = _build_gap_entries(top_goal, normalized_facts, fc_result)
        assert any(g["fact"] == "weak_device" for g in gaps)

    def test_high_pressure_load_produces_gap(self):
        from core.output_gaps import _build_gap_entries

        top_goal = {
            "goal_id": "SE_GOAL_01",
            "goal_name": "Backend Engineer",
            "relevant_facts": [],
            "penalties": [],
        }
        normalized_facts = {"pressure_load": "high"}
        fc_result = {}

        gaps = _build_gap_entries(top_goal, normalized_facts, fc_result)
        assert any(g["fact"] == "pressure_load" for g in gaps)

    def test_low_hours_per_week_produces_gap(self):
        from core.output_gaps import _build_gap_entries

        top_goal = {
            "goal_id": "SE_GOAL_01",
            "goal_name": "Backend Engineer",
            "relevant_facts": [],
            "penalties": [],
        }
        normalized_facts = {"hours_per_week": 4}   # below threshold of 8
        fc_result = {}

        gaps = _build_gap_entries(top_goal, normalized_facts, fc_result)
        assert any(g["fact"] == "hours_per_week" for g in gaps)

    def test_no_gaps_when_facts_are_strong(self):
        from core.output_gaps import _build_gap_entries

        top_goal = {
            "goal_id": "SE_GOAL_01",
            "goal_name": "Backend Engineer",
            "relevant_facts": ["python_skill"],
            "penalties": [],
        }
        # All facts at or above thresholds
        normalized_facts = {
            "python_skill": 4,
            "weak_device": False,
            "weak_internet": False,
            "pressure_load": "low",
            "hours_per_week": 15,
        }
        fc_result = {}

        gaps = _build_gap_entries(top_goal, normalized_facts, fc_result)
        # python_skill=4 is above threshold 3 → no gap for it; constraint facts are fine
        python_gaps = [g for g in gaps if g["fact"] == "python_skill"]
        assert len(python_gaps) == 0


class TestGapResolutionPlan:
    """Verify gap entries select concise, action-bank-backed resolution items."""

    def test_known_gap_facts_map_to_short_actions_and_deduplicate(self):
        from core.output_gap_resolution import build_gap_resolution_plan

        gaps = [
            {"fact": "hours_per_week", "text": "Only 4 hours are available."},
            {"fact": "weak_device", "text": "Device may limit lab work."},
            {"fact": "math_skill", "text": "Math foundations are below target."},
            {"fact": "python_skill", "text": "Python basics are below target."},
            {"fact": "weak_device", "text": "Duplicate device gap."},
            {"fact": "ml_exposure", "text": "AI exposure is still limited."},
            {"fact": "data_handling", "text": "Data handling is still limited."},
        ]

        plan = build_gap_resolution_plan(
            gaps,
            {"goal_name": "AI Foundations Track", "domain": "AIE"},
            {"hours_per_week": 4, "weak_device": True, "target_outcome": "internship"},
        )

        assert 2 <= len(plan) <= 4
        assert all(set(item) == {"title", "action"} for item in plan)
        assert any("Colab" in item["action"] or "Kaggle" in item["action"] for item in plan)
        assert len({item["action"] for item in plan}) == len(plan)
        assert len({item["title"] for item in plan}) == len(plan)
        assert all("because" not in item["action"].casefold() for item in plan)

    def test_bank_actions_when_no_gaps_are_detected(self):
        from core.output_gap_resolution import build_gap_resolution_plan

        plan = build_gap_resolution_plan([], {"goal_name": "AI Foundations Track"}, {})

        assert plan == [
            {
                "title": "Python basics",
                "action": "Write Python functions to clean missing values in a pandas DataFrame.",
            },
            {
                "title": "Math foundations",
                "action": "Calculate accuracy, precision, recall, and F1-score in a Colab notebook.",
            },
        ]

    def test_software_engineering_plan_uses_real_build_tasks(self):
        from core.output_gap_resolution import build_gap_resolution_plan

        gaps = [
            {"fact": "programming_basic"},
            {"fact": "web_basics"},
            {"fact": "js_skill"},
            {"fact": "version_control_git"},
            {"fact": "api_concepts"},
        ]

        plan = build_gap_resolution_plan(
            gaps,
            {"goal_name": "Software Engineering Foundations Track", "domain": "SE"},
            {"current_level": "beginner", "hours_per_week": 10},
        )

        actions = " ".join(item["action"] for item in plan).casefold()
        assert 2 <= len(plan) <= 4
        assert "python calculator" in actions or "cli task manager" in actions
        assert "git" in actions

    def test_ai_plan_uses_dataset_and_notebook_tasks(self):
        from core.output_gap_resolution import build_gap_resolution_plan

        gaps = [
            {"fact": "python_skill"},
            {"fact": "math_skill"},
            {"fact": "ml_exposure"},
            {"fact": "data_handling"},
            {"fact": "weak_device"},
        ]

        plan = build_gap_resolution_plan(
            gaps,
            {"goal_name": "AI Foundations Track", "domain": "AIE"},
            {"current_level": "beginner", "hours_per_week": 6, "weak_device": True},
        )

        actions = " ".join(item["action"] for item in plan).casefold()
        assert 2 <= len(plan) <= 4
        assert "colab" in actions or "kaggle" in actions
        assert "pandas" in actions or "notebook" in actions

    def test_cne_plan_uses_lab_and_troubleshooting_tasks(self):
        from core.output_gap_resolution import build_gap_resolution_plan

        gaps = [
            {"fact": "networking_theory"},
            {"fact": "lab_access"},
            {"fact": "cisco_tools"},
            {"fact": "linux_cli_net_tools_skill"},
            {"fact": "scripting_skill"},
        ]

        plan = build_gap_resolution_plan(
            gaps,
            {"goal_name": "Networking Foundations Track", "domain": "CNE"},
            {"current_level": "beginner", "hours_per_week": 10},
        )

        actions = " ".join(item["action"] for item in plan).casefold()
        assert 2 <= len(plan) <= 4
        assert "packet tracer" in actions
        assert "terminal" in actions or "ping" in actions

    def test_backend_development_uses_bank_for_weak_backend_readiness(self):
        from core.output_gap_resolution import select_gap_resolution_actions

        plan = select_gap_resolution_actions(
            "Backend Development",
            ["weak_backend_readiness"],
            {"current_level": "beginner", "hours_per_week": 12, "weak_device": False},
        )

        assert plan[0] == {
            "action": "Build a FastAPI CRUD API with SQLite for tasks.",
            "reason": "This connects backend routes, persistence, and basic application structure.",
        }

    def test_target_outcomes_prefer_matching_bank_actions(self):
        from core.output_gap_resolution import select_gap_resolution_actions

        internship = select_gap_resolution_actions(
            "AI Foundations",
            ["internship_goal"],
            {"target_outcome": "internship", "current_level": "beginner", "hours_per_week": 12},
        )
        freelance = select_gap_resolution_actions(
            "Frontend Development",
            ["freelance_goal"],
            {"target_outcome": "freelance", "current_level": "beginner", "hours_per_week": 12},
        )

        assert "GitHub README" in internship[0]["action"]
        assert "client-style" in freelance[0]["action"]

    def test_limited_hours_and_weak_device_are_preferred(self):
        from core.output_gap_resolution import select_gap_resolution_actions

        limited = select_gap_resolution_actions(
            "Backend Development",
            ["limited_hours"],
            {"hours_per_week": 4, "current_level": "beginner"},
        )
        weak_device = select_gap_resolution_actions(
            "AI Foundations",
            ["weak_device"],
            {"weak_device": True, "current_level": "beginner", "hours_per_week": 12},
        )

        assert "30 minutes" in limited[0]["action"] or "25-minute" in limited[0]["action"]
        assert "Kaggle Notebook" in weak_device[0]["action"] or "Google Colab" in weak_device[0]["action"]


# ---------------------------------------------------------------------------
# Multi-domain test (AIE, CNE minimal nodes)
# ---------------------------------------------------------------------------

MULTI_DOMAIN_KB = [
    {
        "id": "N_AI_001",
        "domain": "AIE",
        "level_filter": ["beginner"],
        "type": "boolean",
        "fact_key": "programming_basic",
        "weight": 1,
        "next_if_true": "END",
        "next_if_false": "END",
        "source_citation": "ACM CS 2023",
        "pool_pair": [
            {"id": "N_AI_001a", "text_ar": "كود؟", "text_en": "Code?"},
            {"id": "N_AI_001b", "text_ar": "برمجة؟", "text_en": "Programming?"},
        ],
    },
    {
        "id": "N_CN_001",
        "domain": "CNE",
        "level_filter": ["beginner"],
        "type": "boolean",
        "fact_key": "programming_basic",
        "weight": 1,
        "next_if_true": "END",
        "next_if_false": "END",
        "source_citation": "Cisco CCNA Guide",
        "pool_pair": [
            {"id": "N_CN_001a", "text_ar": "شبكات؟", "text_en": "Networks?"},
            {"id": "N_CN_001b", "text_ar": "شبكة؟", "text_en": "Network?"},
        ],
    },
]


class TestMultiDomain:
    @pytest.fixture
    def multi_kb_path(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "multi.json"
            path.write_text(json.dumps(MULTI_DOMAIN_KB, ensure_ascii=False), encoding="utf-8")
            yield path

    def test_aie_session(self, multi_kb_path):
        manager, session = create_session(multi_kb_path, "AIE")
        assert session.domain == "AIE"
        q = manager.get_current_question()
        assert q["node_id"] == "N_AI_001"
        r = manager.submit_answer(True)
        assert r["is_finished"]

    def test_cne_session(self, multi_kb_path):
        manager, session = create_session(multi_kb_path, "CNE")
        assert session.domain == "CNE"
        q = manager.get_current_question()
        assert q["node_id"] == "N_CN_001"
        r = manager.submit_answer(False)
        assert r["is_finished"]
