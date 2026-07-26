import json
import re

import requests

from app.config import MODEL, OLLAMA_URL


def extract_first_json_object(text: str) -> str:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON object found in model response.")
    return match.group(0)


def call_ollama_json(prompt: str, schema: dict) -> dict:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "format": schema,
    }

    response = requests.post(OLLAMA_URL, json=payload, timeout=300)
    response.raise_for_status()

    raw_text = response.json().get("response", "").strip()
    json_text = extract_first_json_object(raw_text)
    return json.loads(json_text)


__all__ = ["extract_first_json_object", "call_ollama_json"]
