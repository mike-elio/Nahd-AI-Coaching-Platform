from app.api import routes
from app.schemas.requests import DiagnoseRequest
from app.services import pipeline


BACKEND_ONLY_PUBLIC_KEYS = {
    "stage_1",
    "stage_1_interpretation",
    "stage_2",
    "stage_3",
    "stage_4",
    "predicted_domain",
    "top_tags",
    "tag_confidences",
    "ranked_tags",
    "reasoning_trace_internal",
    "checklist_trace_internal",
    "reference_trace_internal",
    "reference_selection_metadata",
    "debug_diagnostics",
    "expert_analysis",
    "diagnostic_trace",
    "evidence_plan",
    "command_plan",
    "hypothesis_details",
    "display_result",
    "ranked_action_plan",
    "recommended_steps",
    "detected_signals",
    "processing_time_ms",
    "errors",
    "confidence",
    "level",
    "complexity",
}


def _stage_1_auth_case() -> dict:
    return {
        "predicted_domain": "sw",
        "top_tags": ["jwt", "authentication", "fastapi"],
        "tag_confidences": {"jwt": 0.95, "authentication": 0.9, "fastapi": 0.75},
        "ranked_tags": [
            {"tag": "jwt", "confidence": 0.95},
            {"tag": "authentication", "confidence": 0.9},
            {"tag": "fastapi", "confidence": 0.75},
        ],
    }


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def test_public_diagnose_response_contract_uses_display_result_only(monkeypatch):
    monkeypatch.setattr(pipeline, "predict_top_3_tags", lambda _problem_text: _stage_1_auth_case())
    monkeypatch.setattr(routes, "run_existing_pipeline", pipeline.run_existing_pipeline)

    response = routes.diagnose(
        DiagnoseRequest(
            problem_text=(
                "FastAPI API returns 401 unauthorized after deploy. Bearer JWT is present, "
                "but backend logs invalid audience and expired token for the login request."
            )
        )
    )

    response_data = response.model_dump(mode="python") if hasattr(response, "model_dump") else response.dict()
    result = response_data["result"]

    assert response_data["success"] is True
    assert result["domain"] == "software"
    assert "auth" in result["primary_path"].lower() or "token" in result["primary_path"].lower()
    assert len(result["possible_causes"]) >= 3
    assert 3 <= len(result["diagnostic_checklist"]) <= 6
    assert result["references_summary"]

    first_step_text = " ".join(str(value) for value in result["diagnostic_checklist"][0].values())
    assert "auth" in first_step_text.lower() or "token" in first_step_text.lower() or "identity" in first_step_text.lower()

    reference_text = " ".join(
        f"{reference.get('title', '')} {reference.get('url', '')} {reference.get('source_type', '')}"
        for reference in result["references_summary"]
    ).lower()
    assert any(keyword in reference_text for keyword in ("jwt", "oauth", "auth", "security", "fastapi"))

    public_keys = set(_walk_keys(result))
    assert public_keys.isdisjoint(BACKEND_ONLY_PUBLIC_KEYS)


_ACTION_PLAN_FORBIDDEN_KEYS = {
    "priority",
    "difficulty",
    "risk",
    "expected_value",
    "score",
    "path_kind",
    "source_rank",
    "semantic_key",
    "phase",
}

_ACTION_PLAN_ALLOWED_KEYS = {"rank", "title", "action", "expected", "if_this_fails", "reference"}


def test_action_plan_present_and_safe(monkeypatch):
    """action_plan must be present, contain only public-safe fields, and never
    expose internal scoring metadata."""
    monkeypatch.setattr(pipeline, "predict_top_3_tags", lambda _problem_text: _stage_1_auth_case())
    monkeypatch.setattr(routes, "run_existing_pipeline", pipeline.run_existing_pipeline)

    for level in ("basic", "standard", "expert"):
        response = routes.diagnose(
            DiagnoseRequest(
                problem_text=(
                    "FastAPI API returns 401 unauthorized after deploy. Bearer JWT is present, "
                    "but backend logs invalid audience and expired token for the login request."
                ),
                display_level=level,
            )
        )

        response_data = response.model_dump(mode="python") if hasattr(response, "model_dump") else response.dict()
        result = response_data["result"]

        # action_plan must be present and non-empty
        assert "action_plan" in result, f"action_plan missing from {level} response"
        action_plan = result["action_plan"]
        assert isinstance(action_plan, list), f"action_plan is not a list in {level} response"
        assert len(action_plan) >= 1, f"action_plan is empty in {level} response"

        for item in action_plan:
            # Only allowed keys
            item_keys = set(item.keys())
            assert item_keys <= _ACTION_PLAN_ALLOWED_KEYS, (
                f"Unexpected keys in action_plan item ({level}): {item_keys - _ACTION_PLAN_ALLOWED_KEYS}"
            )

            # No forbidden internal keys
            assert item_keys.isdisjoint(_ACTION_PLAN_FORBIDDEN_KEYS), (
                f"Internal keys leaked in action_plan item ({level}): {item_keys & _ACTION_PLAN_FORBIDDEN_KEYS}"
            )

            # Required fields
            assert item.get("title"), f"action_plan item missing title ({level})"
            assert item.get("action"), f"action_plan item missing action ({level})"

        # ranked_action_plan / recommended_steps must not appear
        all_keys = set(_walk_keys(result))
        assert "ranked_action_plan" not in all_keys
        assert "recommended_steps" not in all_keys
