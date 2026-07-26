# Task Verification Experiments

The runnable task-verification implementation is in [../../features/image-task-verification](../../features/image-task-verification).

Use `fastapi_app.py` as the experiment entry point. It accepts a task description and a proof image at the `/verify` endpoint, then uses the local image-description service and classifier to produce the completion assessment.

The local `model.safetensors` file remains excluded from this repository. See the root README for the model policy and setup requirements.
