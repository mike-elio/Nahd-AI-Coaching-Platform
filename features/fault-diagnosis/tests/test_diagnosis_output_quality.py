from dataclasses import dataclass
from typing import Iterable
import re

import pytest

from app.schemas.requests import DiagnoseRequest
from app.services import pipeline
from app.services.tag_prediction import validate_and_fix_output


GENERIC_FALLBACK_PHRASES = (
    "runtime configuration issue",
    "primary diagnostic path",
    "validate the dominant failure path",
    "general troubleshooting",
    "check the environment",
)

READ_ONLY_START_TERMS = (
    "compare",
    "confirm",
    "inspect",
    "replay",
    "resolve",
    "review",
    "trace",
    "validate",
    "verify",
)


@dataclass(frozen=True)
class OutputQualityCase:
    name: str
    problem_text: str
    predicted_domain: str
    ranked_tags: tuple[tuple[str, float], ...]
    expected_signals: tuple[str, ...]
    first_step_keywords: tuple[str, ...]
    forbidden_phrases: tuple[str, ...]


QUALITY_BENCHMARK_CASES = (
    OutputQualityCase(
        name="react_api_base_url_drift",
        problem_text=(
            "React production build calls http://localhost:8000/api after deploy because "
            "API_BASE_URL env var is missing. Browser shows net::ERR_CONNECTION_REFUSED "
            "and the backend is actually at https://api.example.com."
        ),
        predicted_domain="sw",
        ranked_tags=(("reactjs", 0.9), ("javascript", 0.75), ("debugging", 0.5)),
        expected_signals=("api base url", "localhost", "browser request target"),
        first_step_keywords=("api", "base", "url", "browser"),
        forbidden_phrases=("service selectors", "network policy", "database dsn", "postgresql"),
    ),
    OutputQualityCase(
        name="fastapi_missing_runtime_env",
        problem_text=(
            "FastAPI service crashes during startup with KeyError: OPENAI_API_KEY after deployment. "
            "The environment variable is missing from the runtime secrets and the app cannot initialize "
            "the model client."
        ),
        predicted_domain="sw",
        ranked_tags=(("fastapi", 0.88), ("python", 0.8), ("debugging", 0.65)),
        expected_signals=("environment variable", "secret", "startup"),
        first_step_keywords=("environment", "variable", "secret"),
        forbidden_phrases=("database dsn", "postgresql", "mysql", "schema migration"),
    ),
    OutputQualityCase(
        name="model_serving_base_url_unavailable",
        problem_text=(
            "Model-serving endpoint returns 503 after deploy. The app is configured with the wrong "
            "MODEL_BASE_URL and calls a disabled inference endpoint; logs show service unavailable "
            "before inference starts."
        ),
        predicted_domain="ai",
        ranked_tags=(("model-serving", 0.9), ("inference", 0.78), ("mlops", 0.65)),
        expected_signals=("model-serving", "endpoint", "base url"),
        first_step_keywords=("model", "endpoint", "health"),
        forbidden_phrases=("gpu memory", "cuda", "retrieval", "vector-store"),
    ),
    OutputQualityCase(
        name="proxy_authorization_header_stripped",
        problem_text=(
            "Requests through nginx return 401 because the Authorization header is missing at upstream. "
            "Direct backend call works with the same bearer token."
        ),
        predicted_domain="cn",
        ranked_tags=(("nginx", 0.9), ("reverse-proxy", 0.8), ("http", 0.72)),
        expected_signals=("authorization header", "proxy", "forwarding"),
        first_step_keywords=("forwarding", "header", "proxy"),
        forbidden_phrases=("cors preflight", "postgresql", "cuda", "embedding"),
    ),
)


def _stage_1_for(case: OutputQualityCase) -> dict:
    return {
        "predicted_domain": case.predicted_domain,
        "top_tags": [tag for tag, _confidence in case.ranked_tags],
        "tag_confidences": {tag: confidence for tag, confidence in case.ranked_tags},
        "ranked_tags": [
            {"tag": tag, "confidence": confidence}
            for tag, confidence in case.ranked_tags
        ],
    }


def _as_dict(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    if hasattr(value, "dict"):
        return value.dict()
    return dict(value)


def _contains_all(text: str, needles: Iterable[str]) -> bool:
    lowered = text.lower()
    return all(needle.lower() in lowered for needle in needles)


def _contains_any(text: str, needles: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(needle.lower() in lowered for needle in needles)


def _field_text(result_data: dict) -> str:
    parts = [
        result_data.get("primary_path", ""),
        " ".join(result_data.get("alternative_paths", [])),
        " ".join(result_data.get("possible_causes", [])),
    ]
    for step in result_data.get("diagnostic_checklist", []):
        parts.extend(
            [
                step.get("title", ""),
                step.get("action", ""),
                step.get("expected", ""),
                step.get("if_this_fails", ""),
            ]
        )
    return " ".join(parts).lower()


def _signature(value: str) -> set[str]:
    stopwords = {
        "the",
        "and",
        "with",
        "from",
        "that",
        "this",
        "runtime",
        "failing",
        "path",
        "request",
        "service",
        "verify",
        "confirm",
        "check",
        "inspect",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) >= 3 and token not in stopwords
    }


def _assert_no_near_duplicates(items: list[str]) -> None:
    signatures = []
    for item in items:
        current = _signature(item)
        for previous in signatures:
            if not current or not previous:
                continue
            overlap = len(current & previous)
            assert overlap / max(1, min(len(current), len(previous))) < 0.78, items
        signatures.append(current)


@pytest.mark.parametrize("case", QUALITY_BENCHMARK_CASES, ids=[case.name for case in QUALITY_BENCHMARK_CASES])
def test_specialized_output_beats_generic_fallback(monkeypatch, case):
    monkeypatch.setattr(pipeline, "predict_top_3_tags", lambda _problem_text: _stage_1_for(case))

    output = pipeline.run_existing_pipeline(
        DiagnoseRequest(problem_text=case.problem_text, display_level="expert")
    )
    from app.services.presentation import adapt_result_for_display
    display_result = adapt_result_for_display(output["result"], output, display_level="expert", debug_mode=False)
    result_data = _as_dict(output["result"])
    result_data["display_result"] = display_result
    checklist = result_data["diagnostic_checklist"]
    combined_text = _field_text(result_data)

    assert _contains_all(combined_text, case.expected_signals)
    assert not _contains_any(result_data["primary_path"], GENERIC_FALLBACK_PHRASES)
    assert not _contains_any(combined_text, case.forbidden_phrases)

    first_step_text = " ".join(
        [
            checklist[0]["title"],
            checklist[0]["action"],
            checklist[0]["expected"],
            checklist[0]["if_this_fails"],
        ]
    ).lower()
    assert _contains_all(first_step_text, case.first_step_keywords)
    assert first_step_text.startswith(READ_ONLY_START_TERMS) or _contains_any(first_step_text, READ_ONLY_START_TERMS)

    assert 4 <= len(result_data["possible_causes"]) <= 6
    assert 4 <= len(checklist) <= 6
    assert 2 <= len(result_data["alternative_paths"]) <= 4
    assert 1 <= len(result_data["references_summary"]) <= 5

    _assert_no_near_duplicates(result_data["possible_causes"])
    _assert_no_near_duplicates(result_data["alternative_paths"])
    _assert_no_near_duplicates([step["title"] for step in checklist])

    for key in ("primary_path", "alternative_paths", "possible_causes", "diagnostic_checklist", "references_summary", "display_result"):
        assert key in result_data


def test_tag_prediction_fallback_does_not_duplicate_top_tags():
    fixed = validate_and_fix_output(
        {
            "predicted_domain": "sw",
            "top_tags": [
                {"tag": "debugging", "confidence": 0.8},
                {"tag": "debugging", "confidence": 0.7},
            ],
        }
    )

    assert len(fixed["top_tags"]) == 3
    assert len(set(fixed["top_tags"])) == 3
    assert set(fixed["tag_confidences"]) == set(fixed["top_tags"])
