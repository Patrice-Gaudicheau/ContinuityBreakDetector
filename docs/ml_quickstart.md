# ML Quickstart

ContinuityBreakDetector keeps the deterministic detector usable without ML
packages. TimesFM and Chronos are optional forecasting backends that run in
isolated Docker worker containers.

The first model run may download weights at runtime into the shared Hugging Face
cache volume. Model weights are not downloaded during Docker image builds and
are not stored in the repository.

## Worker Overview

Docker Compose defines three services:

- `core`: the lightweight project image based on `python:3.12-slim`.
- `timesfm-worker`: a separate `python:3.11-slim` image for TimesFM.
- `chronos-worker`: a separate `python:3.11-slim` image for Chronos.

Build all images:

```bash
docker compose build
```

Run the core tests and default worker readiness checks:

```bash
docker compose up
```

The ML workers are optional. Normal deterministic commands and tests do not
require Docker, TimesFM, Chronos, Torch, or model weights.

## Hugging Face Cache

Both ML worker containers mount the named Docker volume `hf_cache` at:

```text
/root/.cache/huggingface
```

The first full smoke or prediction run may download model weights into that
volume. Later runs reuse the cached files. To clear the cache intentionally:

```bash
docker compose down -v
```

No host-specific cache path is required.

## Smoke Tests

Import-level worker smoke tests:

```bash
docker compose run --rm timesfm-worker python smoke_test.py
docker compose run --rm chronos-worker python smoke_test.py
```

The core CLI can run the same lightweight checks through Docker:

```bash
python -m continuity_break_detector.main ml-smoke
python -m continuity_break_detector.main ml-smoke --worker timesfm
python -m continuity_break_detector.main ml-smoke --worker chronos
```

Full model smoke tests are opt-in and may download weights:

```bash
CBD_RUN_ML_MODEL_SMOKE=1 docker compose run --rm timesfm-worker python smoke_test.py
CBD_RUN_ML_MODEL_SMOKE=1 docker compose run --rm chronos-worker python smoke_test.py
```

or through the core CLI:

```bash
python -m continuity_break_detector.main ml-smoke --full
```

## Prediction Protocol

Worker prediction commands read one JSON object from stdin and write exactly one
JSON object to stdout. Logs, warnings, and download progress go to stderr.

Example request:

```json
{
  "series": [1.0, 2.0, 3.0, 4.0],
  "horizon": 1
}
```

Direct worker calls:

```bash
echo '{"series":[1,2,3,4],"horizon":1}' | docker compose run --rm -T timesfm-worker python predict.py
echo '{"series":[1,2,3,4],"horizon":1}' | docker compose run --rm -T chronos-worker python predict.py
```

The same contract is available through the core CLI:

```bash
python -m continuity_break_detector.main ml-predict --worker timesfm --series "1,2,3,4" --horizon 1
python -m continuity_break_detector.main ml-predict --worker chronos --series "1,2,3,4" --horizon 1
```

## One-Shot vs Daemon Mode

One-shot mode starts a worker container for each prediction. It is simple and is
the default for single-series pipeline commands.

Daemon mode starts `daemon.py` in a worker container and sends newline-delimited
JSON requests over stdin/stdout. It keeps the model loaded for repeated
predictions inside one command. It does not start an HTTP server.

Experimental daemon prediction:

```bash
python -m continuity_break_detector.main ml-daemon-predict --worker timesfm --series "1,2,3,4" --horizon 3 --repeat 3
python -m continuity_break_detector.main ml-daemon-predict --worker chronos --series "1,2,3,4" --horizon 3 --repeat 3
```

Internally, both modes go through `ForecastClient`:

- `DockerForecastClient`: one-shot Docker Compose prediction.
- `DockerWarmForecastClient`: daemon-backed Docker Compose prediction.

The JSON contract is centralized in
`continuity_break_detector.prediction_schema`.

## Pipeline Commands

`predict-series` reads a JSON file with a required `series` list and optional
`metadata` object:

```json
{
  "series": [1.0, 2.0, 3.0, 4.0],
  "metadata": {
    "name": "demo_series"
  }
}
```

Examples:

```bash
python -m continuity_break_detector.main predict-series --worker timesfm --input examples/series.json --horizon 3 --mode one-shot
python -m continuity_break_detector.main predict-series --worker chronos --input examples/series.json --horizon 3 --mode daemon
```

`analyze-series` appends the forecast to the historical input and runs the
existing break-analysis adapter over the combined series:

```bash
python -m continuity_break_detector.main analyze-series --worker timesfm --input examples/series.json --horizon 3 --mode one-shot
python -m continuity_break_detector.main analyze-series --worker chronos --input examples/series.json --horizon 3 --mode daemon
```

`batch-predict` reads multiple named series and defaults to daemon mode so one
warm worker session can serve the full batch:

```json
{
  "series": [
    {"name": "stable_demo", "values": [1.0, 1.1, 1.2, 1.3]},
    {"name": "break_demo", "values": [1.0, 1.1, 1.2, 4.8]}
  ],
  "metadata": {
    "source": "examples"
  }
}
```

```bash
python -m continuity_break_detector.main batch-predict --worker timesfm --input examples/batch_series.json --horizon 3 --mode daemon
python -m continuity_break_detector.main batch-predict --worker chronos --input examples/batch_series.json --horizon 3 --mode daemon
```

`--mode one-shot` is available for fallback or comparison. Resource and
concurrency controls for larger batches are still future work.

## Command Dependency Summary

Commands that do not require Docker or ML packages:

- `make demo-study`
- `pytest -q`
- deterministic pipeline commands such as `ingest`, `normalize`,
  `compute_statistics`, `rank_breaks`, `audit_candidates`, and
  `detect_artifacts`

Commands that require Docker with the current ML backend:

- `ml-smoke`
- `ml-predict`
- `ml-daemon-predict`
- `predict-series`
- `batch-predict`
- `analyze-series`
- direct `docker compose run ... predict.py` worker calls

See also:

- [ML architecture](ml_architecture.md)
- [Worker contract](worker_contract.md)
- [Roadmap](roadmap.md)
