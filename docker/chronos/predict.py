from __future__ import annotations

import contextlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from continuity_break_detector.prediction_schema import (
    PredictionError,
    PredictionSuccess,
    parse_prediction_request,
    prediction_error_to_json_dict,
    prediction_success_to_json_dict,
)
from continuity_break_detector.prediction_schema import (
    PredictionSchemaError as ValidationError,
)

DEFAULT_MODEL_ID = "amazon/chronos-bolt-small"
WORKER_NAME = "chronos"


def validate_payload(payload: Any) -> tuple[list[float], int]:
    request = parse_prediction_request(payload)
    return request.series, request.horizon


class ModelPredictor:
    def __init__(self) -> None:
        self.model_id = os.environ.get("CBD_CHRONOS_MODEL_ID", DEFAULT_MODEL_ID)
        self._pipeline: Any | None = None

    def predict(self, series: list[float], horizon: int) -> dict[str, Any]:
        pipeline = self._load_pipeline()
        with contextlib.redirect_stdout(sys.stderr):
            import torch

            raw = pipeline.predict(torch.tensor(series, dtype=torch.float32), prediction_length=horizon)
        return success_response_from_raw(raw, self.model_id, horizon)

    def _load_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline

        with contextlib.redirect_stdout(sys.stderr):
            from chronos import BaseChronosPipeline

            cache_preexisting = is_model_cached(self.model_id)
            log_cache_status(self.model_id, cache_preexisting)
            self._pipeline = BaseChronosPipeline.from_pretrained(
                self.model_id,
                device_map="cpu",
                local_files_only=False,
            )
            if not cache_preexisting and is_model_cached(self.model_id):
                print(f"{WORKER_NAME} model cache populated: {self.model_id}", file=sys.stderr)
        return self._pipeline


def success_response_from_raw(raw: Any, model_id: str, horizon: int) -> dict[str, Any]:
    if raw.ndim == 3:
        if raw.shape[1] > 1:
            point = raw[0, raw.shape[1] // 2, :horizon]
        else:
            point = raw[0, 0, :horizon]
    else:
        point = raw.reshape(-1)[:horizon]
    forecast = [float(value) for value in point.tolist()]
    return prediction_success_to_json_dict(
        PredictionSuccess(
            worker=WORKER_NAME,
            model_id=model_id,
            horizon=horizon,
            forecast=forecast,
        )
    )


def predict(series: list[float], horizon: int) -> dict[str, Any]:
    return ModelPredictor().predict(series, horizon)


def is_model_cached(model_id: str) -> bool:
    cache_root = Path(os.environ.get("HF_HOME", "/root/.cache/huggingface"))
    model_dir = cache_root / "hub" / f"models--{model_id.replace('/', '--')}"
    return model_dir.exists() and any(model_dir.iterdir())


def log_cache_status(model_id: str, cached: bool) -> None:
    status = "hit" if cached else "miss"
    print(f"{WORKER_NAME} Hugging Face cache {status}: {model_id}", file=sys.stderr)


def error_response(error_type: str, message: str) -> dict[str, Any]:
    return prediction_error_to_json_dict(
        PredictionError(worker=WORKER_NAME, error_type=error_type, message=message)
    )


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
