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
  - `predict-series`
  - `analyze-series`
- `ForecastClient` abstraction for ML prediction access.
- Shared prediction schema module for request and response validation.
- Pipeline-level forecast and forecast-plus-break-analysis commands.

## Current Limitations

- The Docker backend starts an ephemeral container for each prediction command.
- Models are loaded per container run.
- Batch and backtest workloads would repeat startup and model-load cost.
- Worker logs include upstream library warnings and download progress on stderr.
- Only the prediction contract is centralized; model-specific loading remains in
  each worker script.

## Next Step: Warm Worker Daemon

The next planned step is a warm-worker-daemon backend behind `ForecastClient`.
The daemon should keep a worker process and model instance alive across multiple
prediction requests.

Daemon mode is needed for batch and backtest workloads because those workloads
may call forecasting many times. Reusing a loaded model should reduce repeated:

- Docker container startup
- Python interpreter startup
- model import time
- Hugging Face model loading

The daemon should preserve the current JSON request and response contract. It
should be an additional backend, not a replacement for the Docker one until the
behavior is validated.

## Risks To Avoid

- Duplicating request or response schemas outside
  `continuity_break_detector.prediction_schema`.
- Making TimesFM, Chronos, or Torch mandatory core dependencies.
- Hiding model downloads during image build or unrelated deterministic commands.
- Changing CLI stdout from structured JSON to human-readable text.
- Adding daemon lifecycle complexity before the current Docker contract remains
  stable under tests.
- Mixing worker-specific model code into pipeline orchestration modules.
