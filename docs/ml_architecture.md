# ML Architecture

ContinuityBreakDetector keeps the statistical detector independent from ML
runtime dependencies. The core package can ingest data, normalize series,
compute statistics, run backtests, rank candidates, audit artifacts, and produce
reports without importing TimesFM, Chronos, Torch, or model-specific packages.

## Current Shape

```text
core CLI / pipeline
  -> continuity_break_detector.forecast_client.ForecastClient
  -> DockerForecastClient
  -> docker compose run --rm -T timesfm-worker|chronos-worker python predict.py
  -> JSON response on stdout
```

Experimental warm mode adds a second backend:

```text
core CLI
  -> DockerWarmForecastClient
  -> docker compose run --rm -T timesfm-worker|chronos-worker python daemon.py
  -> newline-delimited JSON requests and responses over stdin/stdout
```

The workers are separate Docker images:

- `timesfm-worker`: Python 3.11 image with TimesFM and CPU Torch.
- `chronos-worker`: Python 3.11 image with Chronos and CPU Torch.
- `core`: Python 3.12 slim image for the deterministic project and tests.

The worker images copy only their worker scripts and the lightweight
`continuity_break_detector.prediction_schema` module. They do not install the
full core project and do not bake model weights into the image.

## Boundaries

The core remains ML-free:

- no TimesFM dependency in `pyproject.toml`
- no Chronos dependency in `pyproject.toml`
- no Torch dependency in the core image
- no model downloads during Docker build
- no ML worker startup required for deterministic commands

The ML layer is optional:

- `ml-smoke` checks worker availability.
- `ml-predict` calls a worker with inline series input.
- `ml-daemon-predict` starts an experimental warm worker session and can repeat
  predictions without restarting the container for each request.
- `predict-series` reads a JSON series file and returns a forecast.
- `analyze-series` appends a forecast and runs the existing break detector over
  the historical-plus-forecast series.

## Protocol

Workers use JSON over stdin/stdout:

- stdin: one prediction request object
- stdout: exactly one JSON response object
- stderr: logs, cache messages, warnings, and model download progress
- exit code: `0` for success, non-zero for validation or inference failure

The shared schema module is the source of truth for request and response
validation. See [worker_contract.md](worker_contract.md).

Daemon mode uses the same request and response objects but frames them as one
JSON object per line. It also accepts `{"command":"shutdown"}` to end a session
cleanly.

## Why Docker First

TimesFM and Chronos have different dependency and Python-version constraints
from the core project. Docker workers keep those dependencies isolated while
still giving the core a stable call boundary.

This avoids dependency contamination:

- the core can stay on Python 3.12
- workers can use Python 3.11
- ML packages can update independently
- CI and local deterministic tests remain lightweight
- model downloads happen only at runtime, into the Hugging Face cache volume

## Warm Worker Daemon

`DockerWarmForecastClient` is a first daemon backend. It keeps a Docker worker
process alive for repeated predictions within one client session. The worker
loads the model lazily on the first request and reuses it for later requests in
that session.

One-shot `DockerForecastClient` remains the default. Daemon mode is experimental
and currently exposed through `ml-daemon-predict`; it is not used by regular
pipeline commands yet.
