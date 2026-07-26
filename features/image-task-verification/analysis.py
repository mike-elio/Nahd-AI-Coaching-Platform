from __future__ import annotations

import base64
import html
import json
import re
import urllib.request
from pathlib import Path
from typing import Any

import torch
from PIL import Image
from transformers import AutoModelForSequenceClassification, AutoTokenizer, PreTrainedTokenizerFast


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
GEMMA_MODEL = "gemma4:e4b"

MODEL_DIR = Path(__file__).resolve().parent
MAX_LENGTH = 184

LABELS = {
    0: "NOT_COMPLETED",
    1: "SIMILAR",
    2: "COMPLETED",
}

GEMMA_PROMPT = """
Describe the visible software evidence in this image.

Answer with one short sentence only.
Do not think step by step.
Do not explain.
Do not use markdown.
Do not return JSON.

Start directly with the main visible thing.

Example:
Django image upload page shows a file chooser, Upload button, and uploaded image preview.
"""

PRE_CODE_RE = re.compile(r"<pre><code>.*?</code></pre>", re.IGNORECASE | re.DOTALL)
INLINE_CODE_RE = re.compile(r"<code>.*?</code>", re.IGNORECASE | re.DOTALL)
PRE_RE = re.compile(r"<pre>.*?</pre>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<[^>]+>")
URL_RE = re.compile(r"http[s]?://\S+|www\.\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
ODD_CHARS_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
MULTISPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    text = "" if text is None else str(text)
    text = html.unescape(text)

    text = PRE_CODE_RE.sub(" ", text)
    text = INLINE_CODE_RE.sub(" ", text)
    text = PRE_RE.sub(" ", text)
    text = HTML_TAG_RE.sub(" ", text)
    text = URL_RE.sub(" ", text)
    text = EMAIL_RE.sub(" ", text)

    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    text = ODD_CHARS_RE.sub("", text)

    return MULTISPACE_RE.sub(" ", text.lower()).strip()


def resize_image(image_path: str, max_width: int = 1600) -> str:
    path = Path(image_path)

    img = Image.open(path).convert("RGB")

    if img.width <= max_width:
        return str(path)

    ratio = max_width / img.width
    new_size = (max_width, int(img.height * ratio))

    resized = img.resize(new_size)
    resized_path = path.with_name(f"{path.stem}_resized.jpg")
    resized.save(resized_path, "JPEG", quality=95, optimize=True)

    return str(resized_path)


def image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def describe_image_with_gemma(image_path: str) -> str:
    image_path = resize_image(image_path)

    payload = {
        "model": GEMMA_MODEL,
        "prompt": GEMMA_PROMPT,
        "images": [image_to_base64(image_path)],
        "stream": False,
        "keep_alive": "30m",
        "think": False,
        "options": {
            "num_predict": 80,
            "temperature": 0.0,
            "top_p": 0.8,
            "stop": ["\n", "\n\n"],
        },
    }

    request = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request, timeout=600) as response:
        data = json.loads(response.read().decode("utf-8"))

    description = normalize_text(data.get("response", ""))

    if not description:
        return "A software interface is visible, but Gemma returned no description."

    return description


def load_model(model_dir: Path = MODEL_DIR) -> tuple[Any, Any]:
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            local_files_only=True,
        )
    except Exception:
        tokenizer = PreTrainedTokenizerFast(
            tokenizer_file=str(model_dir / "tokenizer.json"),
            bos_token="<s>",
            eos_token="</s>",
            unk_token="<unk>",
            sep_token="</s>",
            cls_token="<s>",
            pad_token="<pad>",
            mask_token="<mask>",
            model_max_length=512,
        )

    model = AutoModelForSequenceClassification.from_pretrained(
        model_dir,
        local_files_only=True,
    )

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()

    return tokenizer, model


def predict_match(
    task_text: str,
    image_description: str,
    tokenizer: Any,
    model: Any,
) -> dict[str, Any]:
    inputs = tokenizer(
        normalize_text(task_text),
        normalize_text(image_description),
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=MAX_LENGTH,
    )

    device = next(model.parameters()).device
    inputs = {key: value.to(device) for key, value in inputs.items()}

    with torch.no_grad():
        logits = model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]

    class_id = int(torch.argmax(probs).item())
    confidence = float(probs[class_id].item())

    return {
        "class_id": class_id,
        "label": LABELS[class_id],
        "confidence": round(confidence, 4),
        "probabilities": {
            LABELS[i]: round(float(probs[i].item()), 4)
            for i in range(len(probs))
        },
    }


def build_feedback(label: str) -> str:
    if label == "COMPLETED":
        return "Proof accepted. The uploaded image matches the requested task."

    if label == "SIMILAR":
        return "Proof needs review. The uploaded image is related but does not clearly prove completion."

    return "Proof rejected. The uploaded image does not match the requested task."


def verify_task_image(task_text: str, image_path: str) -> dict[str, Any]:
    image_description = describe_image_with_gemma(image_path)

    tokenizer, model = load_model()

    prediction = predict_match(
        task_text=task_text,
        image_description=image_description,
        tokenizer=tokenizer,
        model=model,
    )

    return {
        "success": True,
        "task_text": task_text,
        "image_description": image_description,
        "prediction": prediction,
        "feedback": build_feedback(prediction["label"]),
    }


if __name__ == "__main__":
    import io
    from contextlib import redirect_stdout, redirect_stderr

    task_text = "Build a complete Django upload feature with model, form, view, template, media settings, and successful upload test."

    image_path = r"images\ff.png"
    buffer = io.StringIO()

    with redirect_stdout(buffer), redirect_stderr(buffer):
        result = verify_task_image(task_text, image_path)

    print(result["feedback"])
    #Build a complete Django upload feature with model, form, view, template, media settings, and successful upload test.
    #Implement JWT authentication with login, refresh token, and protected API endpoints.
    #Configure Celery to run asynchronous background tasks with Redis and Django ORM.
    #.\venv\Scripts\python.exe analysis.py
    #.\venv\Scripts\python.exe -m uvicorn fastapi_app:app --host 127.0.0.1 --port 8000 --reload
