# Feature Guide

## Voice Coach

- **Directory:** `features/voice-coach`
- **Purpose:** Runs a LiveKit voice AI assistant for coaching conversations.
- **Entry point:** `src/agent.py`
- **Requirements:** Python dependencies managed through `pyproject.toml`, plus `LIVEKIT_URL`, `LIVEKIT_API_KEY`, and `LIVEKIT_API_SECRET` in a local `.env.local` file.

Follow the feature's own [README](../features/voice-coach/README.md) for development and deployment commands.

## Image Task Verification

- **Directory:** `features/image-task-verification`
- **Purpose:** Compares a task description to a submitted image and returns a completion assessment.
- **Entry point:** `fastapi_app.py`
- **Run command:** `uvicorn fastapi_app:app --reload` from this feature directory.
- **Requirements:** FastAPI, Pillow, Transformers, PyTorch, an Ollama-compatible image-description model, and a local `model.safetensors` file next to `fastapi_app.py`.

The model file is deliberately absent from Git and must be supplied locally.

Experiment guidance is available at [experiments/task-verification](../experiments/task-verification).

## Career Expert System

- **Directory:** `features/career-expert-system`
- **Purpose:** Interviews the user and recommends suitable technical career paths through a question bank and rules engine.
- **Entry point:** `app/main.py`
- **Run command:** `uvicorn app.main:app --reload` from this feature directory after `pip install -r requirements.txt`.
- **Requirements:** Python, FastAPI, Uvicorn, Pydantic, and the bundled knowledge-base JSON files.

## Fault Diagnosis

- **Directory:** `features/fault-diagnosis`
- **Purpose:** Generates a troubleshooting workflow, likely causes, checklist steps, and supporting references from a technical problem description.
- **Entry point:** `app/main.py`
- **Run command:** `uvicorn app.main:app --reload` from this feature directory after its Python dependencies are installed.
- **Requirements:** Python, FastAPI-compatible dependencies, the bundled CSV reference data, and an Ollama service for tag prediction.

Set `OLLAMA_URL` and `OLLAMA_MODEL` in a local `.env` file if the local defaults do not match your Ollama installation.

## Multi-label Classification Experiments

- **Directory:** `experiments/multilabel-classification`
- **Contents:** Jupyter notebooks and text reports from the first through fifth experiments, including DistilBERT, RoBERTa, LinearSVC, and ModernBERT variants.
- **Excluded material:** training datasets, model weights, virtual environments, and generated caches.
