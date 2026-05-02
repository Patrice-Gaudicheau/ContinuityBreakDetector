from __future__ import annotations

import contextlib
import json
import math
import os
import sys
from numbers import Real
from pathlib import Path
from typing import Any

DEFAULT_MODEL_ID = "google/timesfm-1.0-200m-pytorch"
WORKER_NAME = "timesfm"


class ValidationError(ValueError):
    pass


def validate_payload(payload: Any) -> tuple[list[float], int]:
    if not isinstance(payload, dict):
        raise ValidationError("payload must be a JSON object")
    if "series" not in payload:
        raise ValidationError("missing required field: series")
    if "horizon" not in payload:
        raise ValidationError("missing required field: horizon")

    raw_series = payload["series"]
    if not isinstance(raw_series, list) or not raw_series:
        raise ValidationError("series must be a non-empty list of numbers")
    series: list[float] = []
    for index, value in enumerate(raw_series):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise ValidationError(f"series[{index}] must be a finite number")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise ValidationError(f"series[{index}] must be a finite number")
        series.append(numeric)

    horizon = payload["horizon"]
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon <= 0:
        raise ValidationError("horizon must be a positive integer")
    return series, horizon


def predict(series: list[float], horizon: int) -> dict[str, Any]:
    with contextlib.redirect_stdout(sys.stderr):
        import numpy as np
        import timesfm

        model_id = os.environ.get("CBD_TIMESFM_MODEL_ID", DEFAULT_MODEL_ID)
        cache_preexisting = is_model_cached(model_id)
        log_cache_status(model_id, cache_preexisting)
        model = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                context_len=512,
                horizon_len=horizon,
                input_patch_len=32,
                output_patch_len=128,
                backend="cpu",
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                version="torch",
                huggingface_repo_id=model_id,
            ),
        )
        point, _ = model.forecast(
            inputs=[np.asarray(series, dtype=float)],
            freq=[0],
            normalize=True,
        )
        if not cache_preexisting and is_model_cached(model_id):
            print(f"{WORKER_NAME} model cache populated: {model_id}", file=sys.stderr)
    forecast = [float(value) for value in point[0, :horizon].tolist()]
    return {
        "worker": WORKER_NAME,
        "model_id": model_id,
        "horizon": horizon,
        "forecast": forecast,
    }


def is_model_cached(model_id: str) -> bool:
    cache_root = Path(os.environ.get("HF_HOME", "/root/.cache/huggingface"))
    model_dir = cache_root / "hub" / f"models--{model_id.replace('/', '--')}"
    return model_dir.exists() and any(model_dir.iterdir())


def log_cache_status(model_id: str, cached: bool) -> None:
    status = "hit" if cached else "miss"
    print(f"{WORKER_NAME} Hugging Face cache {status}: {model_id}", file=sys.stderr)


def error_response(error_type: str, message: str) -> dict[str, Any]:
    return {
        "worker": WORKER_NAME,
        "error": {
            "type": error_type,
            "message": message,
        },
    }


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        series, horizon = validate_payload(payload)
        response = predict(series, horizon)
    except json.JSONDecodeError as exc:
        response = error_response("validation_error", f"invalid JSON: {exc.msg}")
        print(json.dumps(response, separators=(",", ":")))
        return 2
    except ValidationError as exc:
        response = error_response("validation_error", str(exc))
        print(json.dumps(response, separators=(",", ":")))
        return 2
    except Exception as exc:
        print(f"{WORKER_NAME} inference failed: {exc}", file=sys.stderr)
        response = error_response("inference_error", str(exc))
        print(json.dumps(response, separators=(",", ":")))
        return 1

    print(json.dumps(response, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
