from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict


class DiagnoseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_text: str = Field(..., min_length=10, max_length=5000)
    display_level: Optional[str] = Field(default=None, max_length=20)

    @field_validator("problem_text")
    @classmethod
    def strip_problem_text(cls, value):
        cleaned = value.strip()
        if len(cleaned) < 10:
            raise ValueError("problem_text must contain at least 10 non-space characters.")
        return cleaned

    @field_validator("display_level")
    @classmethod
    def strip_display_level(cls, value):
        if value is None:
            return None
        cleaned = value.strip().lower()
        return cleaned or None


__all__ = ["DiagnoseRequest"]
