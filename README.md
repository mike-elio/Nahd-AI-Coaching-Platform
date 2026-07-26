# Nahd AI Coaching Platform

Nahd AI Coaching Platform brings together four AI-powered coaching and support features. Each feature remains an independent Python application so it can be developed and deployed separately.

## Features

| Feature | What it does | Directory |
| --- | --- | --- |
| Voice Coach | A conversational voice assistant for coaching sessions. | [features/voice-coach](features/voice-coach) |
| Image Task Verification | Checks whether an uploaded image is evidence that a described task was completed. | [features/image-task-verification](features/image-task-verification) |
| Career Expert System | Recommends a technical career path through a rule-based questionnaire. | [features/career-expert-system](features/career-expert-system) |
| Fault Diagnosis | Turns a technical issue description into an evidence-backed troubleshooting plan. | [features/fault-diagnosis](features/fault-diagnosis) |

Read the [feature guide](docs/features.md) for entry points and requirements.

## Repository structure

```text
features/
  voice-coach/
  image-task-verification/
  career-expert-system/
  fault-diagnosis/
docs/
experiments/
  task-verification/
  multilabel-classification/
```

## Experiments

- [Task verification](experiments/task-verification) documents the experiment entry point for the image-verification feature.
- [Multi-label classification](experiments/multilabel-classification) contains the available Jupyter notebooks and text reports from the training experiments. Datasets, virtual environments, and model artifacts are intentionally excluded.

## Requirements

- Python 3.10 or later for the Python features.
- [Ollama](https://ollama.com/) and the locally available model configured in `.env` for image verification and fault diagnosis.
- LiveKit credentials for the voice coach. Copy the feature's `.env.example` to `.env.local` and add your own credentials.

## Important: image verification model

`features/image-task-verification` requires a separately supplied local file named `model.safetensors`. It is intentionally excluded from this repository because it is large (about 504 MB). Place it beside `fastapi_app.py` only on a machine that needs to run this feature; do not commit it to Git.

## GitHub publishing

This repository is prepared for GitHub. Before your first push, create a local repository, review `git status`, then connect it to:

```text
https://github.com/mike-elio/Nahd-AI-Coaching-Platform
```

The root `.gitignore` excludes model weights, credentials, virtual environments, caches, and logs.
