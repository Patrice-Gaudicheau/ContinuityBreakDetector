# Roadmap

This roadmap tracks the ML-worker architecture around the deterministic
continuity-break detector. It is not a product roadmap.

## Completed

- Lightweight core Docker image based on `python:3.12-slim`.
- Optional Docker Compose workers for TimesFM and Chronos.
- Worker smoke tests with opt-in full model checks.
- JSON `predict.py` entrypoints for both workers.
- Persistent Hugging Face cache volume shared by ML workers.
- Core CLI commands:
  - `ml-smoke`
  - `ml-predict`
  - `ml-daemon-predict`
  - `predict-series`
  - `analyze-series`
- `ForecastClient` abstraction for ML prediction access.
- Experimental `DockerWarmForecastClient` daemon backend for repeated
  predictions in one worker session.
- Shared prediction schema module for request and response validation.
- Pipeline-level forecast and forecast-plus-break-analysis commands.

## Current Limitations

- The default Docker backend still starts an ephemeral container for each
  prediction command.
- `predict-series` and `analyze-series` still use one-shot prediction.
- Daemon mode is available only through the experimental CLI/client path.
- Worker logs include upstream library warnings and download progress on stderr.
- Only the prediction contract is centralized; model-specific loading remains in
  each worker script.

## Next Step: Batch/Backtest Integration

The warm-worker daemon exists, but normal pipeline commands do not use it yet.
The next step is to integrate daemon-backed forecasting into batch and backtest
workloads where many predictions are made in one run. Reusing a loaded model
should reduce repeated:

- Docker container startup
- Python interpreter startup
- model import time
- Hugging Face model loading

The integration should preserve the current JSON request and response contract.
Daemon mode should remain an additional backend until its lifecycle and failure
behavior are validated under realistic batch workloads.

## Risks To Avoid

- Duplicating request or response schemas outside
  `continuity_break_detector.prediction_schema`.
- Making TimesFM, Chronos, or Torch mandatory core dependencies.
- Hiding model downloads during image build or unrelated deterministic commands.
- Changing CLI stdout from structured JSON to human-readable text.
- Adding daemon lifecycle complexity before the current Docker contract remains
  stable under tests.
- Mixing worker-specific model code into pipeline orchestration modules.
