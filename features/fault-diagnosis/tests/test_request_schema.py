import pytest
from pydantic import ValidationError

from app.schemas.requests import DiagnoseRequest


def test_diagnose_request_keeps_only_public_input_fields():
    payload = DiagnoseRequest(
        problem_text="  FastAPI returns 401 after deploy with an invalid JWT audience.  ",
        display_level=" Expert ",
    )

    assert payload.problem_text == "FastAPI returns 401 after deploy with an invalid JWT audience."
    assert payload.display_level == "expert"
    assert set(DiagnoseRequest.model_fields) == {"problem_text", "display_level"}


def test_diagnose_request_rejects_old_extra_fields():
    with pytest.raises(ValidationError):
        DiagnoseRequest(
            problem_text="FastAPI returns 401 after deploy with an invalid JWT audience.",
            top_k=3,
        )
