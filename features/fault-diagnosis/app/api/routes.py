import logging
import time

from fastapi import APIRouter

from app.config import APP_NAME, APP_VERSION, CANONICAL_DOMAINS
from app.repositories.tags import ALL_SUPPORTED_TAGS
from app.schemas.requests import DiagnoseRequest
from app.schemas.responses import (
    DiagnoseResponseModel,
    HealthResponseModel,
    SimpleListResponseModel,
)
from app.services.pipeline import run_existing_pipeline
from app.services.presentation import adapt_result_for_display


logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/v1/health", response_model=HealthResponseModel)
def health_check() -> HealthResponseModel:
    return HealthResponseModel(
        success=True,
        service=APP_NAME,
        version=APP_VERSION,
        status="ok",
    )


@router.get("/api/v1/tags", response_model=SimpleListResponseModel)
def get_tags() -> SimpleListResponseModel:
    return SimpleListResponseModel(
        success=True,
        items=[{"tag": tag} for tag in sorted(ALL_SUPPORTED_TAGS)],
    )


@router.get("/api/v1/domains", response_model=SimpleListResponseModel)
def get_domains() -> SimpleListResponseModel:
    return SimpleListResponseModel(
        success=True,
        items=[{"domain": domain} for domain in sorted(CANONICAL_DOMAINS)],
    )


@router.post("/api/v1/diagnose", response_model=DiagnoseResponseModel)
def diagnose(payload: DiagnoseRequest) -> DiagnoseResponseModel:
    started = time.perf_counter()
    pipeline_output = run_existing_pipeline(payload)
    processing_time_ms = int((time.perf_counter() - started) * 1000)

    context = {
        "stage_1": pipeline_output.get("stage_1"),
        "stage_1_interpretation": pipeline_output.get("stage_1_interpretation"),
        "stage_2": pipeline_output.get("stage_2"),
        "stage_3": pipeline_output.get("stage_3"),
        "stage_4": pipeline_output.get("stage_4"),
    }

    final_result = adapt_result_for_display(
        result=pipeline_output["result"],
        context=context,
        display_level=payload.display_level,
        debug_mode=False,
    )

    logger.info(
        "Diagnosis complete | domain=%s | tags=%s | primary=%s",
        pipeline_output["stage_1_interpretation"]["active_domain"],
        pipeline_output["stage_1"]["top_tags"],
        pipeline_output["result"].primary_path,
    )

    return DiagnoseResponseModel(
        success=True,
        result=final_result,
        errors=[],
        processing_time_ms=processing_time_ms,
    )


__all__ = [
    "router",
    "health_check",
    "get_tags",
    "get_domains",
    "diagnose",
]
