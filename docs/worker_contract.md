# Worker Contract

TimesFM and Chronos worker prediction entrypoints implement the same JSON
contract. The current entrypoints are:

- `docker/timesfm/predict.py`
- `docker/chronos/predict.py`
- `docker/timesfm/daemon.py`
- `docker/chronos/daemon.py`

The contract is shared with the core through
`continuity_break_detector.prediction_schema`.

## Request

Workers read exactly one JSON object from stdin.

```json
{
  "series": [1.0, 2.0, 3.0, 4.0],
  "horizon": 1
}
```

One-shot `predict.py` reads one JSON object and exits. Daemon `daemon.py` reads
one JSON object per line and keeps running until stdin closes or it receives a
shutdown command.

Validation rules:

- `series` is required.
- `series` must be a non-empty list of finite numbers.
- Boolean values are rejected even though Python treats `bool` as a subclass of
  `int`.
- `horizon` is required.
- `horizon` must be a positive integer.

## Success Response

Workers write exactly one JSON object to stdout on success.

```json
{
  "worker": "timesfm",
  "model_id": "google/timesfm-1.0-200m-pytorch",
  "horizon": 1,
  "forecast": [4.7215]
}
```

For Chronos:

```json
{
  "worker": "chronos",
  "model_id": "amazon/chronos-bolt-small",
  "horizon": 1,
  "forecast": [4.1647]
}
```

Validation rules:

- `worker` must be a string.
- `model_id` must be a string.
- `horizon` must be a positive integer.
- `forecast` must be a non-empty list of finite numbers.

## Error Response

Workers write a JSON error object to stdout and return a non-zero exit code for
validation or inference failures.

```json
{
  "worker": "timesfm",
  "error": {
    "type": "validation_error",
    "message": "horizon must be a positive integer"
  }
}
```

Known error types:

- `validation_error`: invalid JSON or invalid request shape.
- `inference_error`: model loading or inference failed.

## stdout and stderr

stdout is machine-readable and must contain only the response JSON object.
Daemon mode writes one machine-readable JSON object per output line.

stderr is for human diagnostics:

- Docker Compose container messages
- model import warnings
- Hugging Face cache hit or miss messages
- download progress
- inference exception logs

Core CLI commands preserve this separation by printing structured JSON to stdout
and forwarding diagnostics to stderr.

## Exit Codes

- `0`: prediction succeeded and stdout contains a success response.
- `2`: request validation failed and stdout contains a validation error.
- `1`: inference failed and stdout contains an inference error.

The core `ForecastClient` does not raise for worker failures. It captures the
return code, stdout, stderr, parsed response, and success state in a structured
result.

## Daemon Control

Daemon mode supports a control request:

```json
{"command": "shutdown"}
```

The worker returns a status object and exits cleanly:

```json
{"worker": "timesfm", "status": "shutdown"}
```

Prediction requests in daemon mode use the same request, success, and error
objects documented above. Invalid requests return JSON errors and do not crash
the daemon.
