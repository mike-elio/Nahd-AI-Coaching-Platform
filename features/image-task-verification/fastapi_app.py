from __future__ import annotations

import logging
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from analysis import (
    build_feedback,
    describe_image_with_gemma,
    load_model,
    predict_match,
)


logger = logging.getLogger(__name__)


app = FastAPI(
    title="Image Task Verification API",
    description="API wrapper around the local image verification pipeline.",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@lru_cache(maxsize=1)
def get_classifier() -> tuple[Any, Any]:
    return load_model()


def verify_task_image_cached(task_text: str, image_path: str) -> dict[str, Any]:
    image_description = describe_image_with_gemma(image_path)
    tokenizer, model = get_classifier()

    prediction = predict_match(
        task_text=task_text,
        image_description=image_description,
        tokenizer=tokenizer,
        model=model,
    )

    return {
        "success": True,
        "task_text": task_text,
        "image_path": image_path,
        "image_description": image_description,
        "prediction": prediction,
        "feedback": build_feedback(prediction["label"]),
    }


def run_verification(task_text: str, image_path: str) -> dict[str, Any]:
    if not task_text.strip():
        raise HTTPException(status_code=400, detail="task_text is required.")

    path = Path(image_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Image not found: {image_path}")

    try:
        return verify_task_image_cached(task_text, str(path))
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Image verification failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/verify")
async def verify_uploaded_image(
    task_text: str = Form(...),
    image: UploadFile = File(...),
) -> dict[str, Any]:
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image.")

    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Uploaded image is empty.")

    suffix = Path(image.filename or "upload.jpg").suffix or ".jpg"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(image_bytes)

    try:
        return await run_in_threadpool(run_verification, task_text, str(temp_path))
    finally:
        temp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("fastapi_app:app", host="127.0.0.1", port=8000, reload=True)
