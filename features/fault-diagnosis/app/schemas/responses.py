from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ReferenceModel(BaseModel):
    title: str
    url: str
    source_type: str


class ChecklistStepModel(BaseModel):
    step_number: int
    title: str
    action: str
    expected: str
    reference: ReferenceModel
    if_this_fails: str


class DiagnosticResultModel(BaseModel):
    engine_title: str
    primary_path: str
    alternative_paths: List[str]
    possible_causes: List[str]
    diagnostic_checklist: List[ChecklistStepModel]
    references_summary: List[ReferenceModel]
    expert_analysis: Optional[Dict[str, Any]] = None
    diagnostic_trace: Optional[Dict[str, Any]] = None
    evidence_plan: Optional[List[Dict[str, Any]]] = None
    command_plan: Optional[List[Dict[str, Any]]] = None
    hypothesis_details: Optional[List[Dict[str, Any]]] = None

class DiagnoseResponseModel(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]]
    errors: List[str]
    processing_time_ms: int


class HealthResponseModel(BaseModel):
    success: bool
    service: str
    version: str
    status: str


class SimpleListResponseModel(BaseModel):
    success: bool
    items: List[Dict[str, Any]]


__all__ = [
    "ReferenceModel",
    "ChecklistStepModel",
    "DiagnosticResultModel",
    "DiagnoseResponseModel",
    "HealthResponseModel",
    "SimpleListResponseModel",
]
