"""FastAPI routes for the GPES expert system."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.ai.expert_models import (
    DomainOption,
    FinalResultResponse,
    QuestionEnvelopeResponse,
    SessionStateResponse,
    StartSessionRequest,
    StartSessionResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from app.expert import (
    SessionNotFoundError,
    SessionStateError,
    expert_service,
)


app = FastAPI(
    title="GPES Expert System",
    description="GoalPath Expert System with FastAPI APIs and an Alpine.js + Tailwind interface",
    version="0.2.0",
)


_sessions = expert_service.sessions
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_FRONTEND_STATIC_DIR = _PROJECT_ROOT / "frontend" / "static"


@app.get("/healthz")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/expert/domains", response_model=list[DomainOption])
async def list_domains() -> list[dict[str, str]]:
    return expert_service.list_domains()


@app.post("/api/expert/sessions", response_model=StartSessionResponse)
async def api_start_session(req: StartSessionRequest) -> dict[str, Any]:
    try:
        return expert_service.start_session(req.domain, req.kb_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/expert/sessions/{session_id}/question", response_model=QuestionEnvelopeResponse)
async def api_get_next_question(session_id: str) -> dict[str, Any]:
    try:
        return expert_service.get_current_question(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.post("/api/expert/sessions/{session_id}/answer", response_model=SubmitAnswerResponse)
async def api_submit_answer(session_id: str, req: SubmitAnswerRequest) -> dict[str, Any]:
    try:
        return expert_service.submit_answer(session_id, req.answer)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except (SessionStateError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/expert/sessions/{session_id}/back", response_model=QuestionEnvelopeResponse)
async def api_go_back(session_id: str) -> dict[str, Any]:
    try:
        return expert_service.go_back(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except SessionStateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/expert/sessions/{session_id}/state", response_model=SessionStateResponse)
async def api_get_session_state(session_id: str) -> dict[str, Any]:
    try:
        return expert_service.get_session_state(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc


@app.get("/api/expert/sessions/{session_id}/result", response_model=FinalResultResponse)
async def api_get_final_result(session_id: str) -> dict[str, Any]:
    try:
        return expert_service.get_final_result(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Session not found") from exc
    except SessionStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc



def _setup_frontend() -> None:
    if getattr(app.state, "frontend_ready", False):
        return

    app.state.frontend_ready = True
    app.mount("/static", StaticFiles(directory=_FRONTEND_STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def frontend_index() -> FileResponse:
        return FileResponse(_FRONTEND_STATIC_DIR / "index.html")


_setup_frontend()
