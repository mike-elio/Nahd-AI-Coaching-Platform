import logging
import time

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import router
from app.config import (
    APP_NAME,
    APP_VERSION,
    CORS_ALLOW_CREDENTIALS,
    CORS_ALLOW_ORIGINS,
)
from app.schemas.responses import DiagnoseResponseModel


logger = logging.getLogger(__name__)


app = FastAPI(title=APP_NAME, version=APP_VERSION)


app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    duration_ms = int((time.perf_counter() - started) * 1000)
    logger.info("%s %s -> %s in %sms", request.method, request.url.path, response.status_code, duration_ms)
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = [f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in exc.errors()]
    logger.warning("Validation error on %s: %s", request.url.path, errors)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=DiagnoseResponseModel(
            success=False,
            result=None,
            errors=errors,
            processing_time_ms=0,
        ).dict(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=DiagnoseResponseModel(
            success=False,
            result=None,
            errors=["internal_server_error"],
            processing_time_ms=0,
        ).dict(),
    )

app.include_router(router)


__all__ = ["app"]
