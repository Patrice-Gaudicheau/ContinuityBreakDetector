from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from continuity_break_detector.ml_workers import (
    WorkerPredictionResult,
    predict_chronos,
    predict_timesfm,
)


class SeriesPredictionError(ValueError):
    def __init__(self, error_type: str, message: str) -> None:
        super().__init__(message)
        self.error_type = error_type
        self.message = message


@dataclass(frozen=True)
class SeriesInput:
    series: list[float]
    metadata: dict[str, Any]


def load_series_input(path: Path) -> SeriesInput:
    if not path.exists():
        raise SeriesPredictionError("validation_error", f"input file does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SeriesPredictionError("validation_error", f"invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise SeriesPredictionError("validation_error", "input JSON must be an object")
    if "series" not in payload:
        raise SeriesPredictionError("validation_error", "missing required field: series")

    metadata = payload.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise SeriesPredictionError("validation_error", "metadata must be an object when provided")
    return SeriesInput(series=_validate_series(payload["series"]), metadata=metadata)


def predict_series_with_worker(
    worker: str,
    series: list[float],
    horizon: int,
    timeout_seconds: float = 120.0,
) -> WorkerPredictionResult:
    if horizon <= 0:
        raise SeriesPredictionError("validation_error", "horizon must be a positive integer")
    if worker == "timesfm":
        return predict_timesfm(series, horizon, timeout_seconds=timeout_seconds)
    if worker == "chronos":
        return predict_chronos(series, horizon, timeout_seconds=timeout_seconds)
    raise SeriesPredictionError("validation_error", "worker must be one of: timesfm, chronos")


def build_success_response(
    *,
    worker: str,
    series_input: SeriesInput,
    prediction: WorkerPredictionResult,
    horizon: int,
) -> dict[str, Any]:
    model_id = None
    if prediction.response is not None:
        raw_model_id = prediction.response.get("model_id")
        if isinstance(raw_model_id, str):
            model_id = raw_model_id
    return {
        "status": "ok",
        "worker": worker,
        "input": {
            "points": len(series_input.series),
            "metadata": series_input.metadata,
        },
        "prediction": {
            "model_id": model_id,
            "horizon": horizon,
            "forecast": prediction.forecast,
        },
    }


def build_error_response(error_type: str, message: str) -> dict[str, Any]:
    return {
        "status": "error",
        "error": {
            "type": error_type,
            "message": message,
        },
    }


def _validate_series(raw_series: Any) -> list[float]:
    if not isinstance(raw_series, list) or not raw_series:
        raise SeriesPredictionError(
            "validation_error",
            "series must be a non-empty list of finite numbers",
        )
    series: list[float] = []
    for index, value in enumerate(raw_series):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise SeriesPredictionError(
                "validation_error",
                f"series[{index}] must be a finite number",
            )
        numeric = float(value)
        if not math.isfinite(numeric):
            raise SeriesPredictionError(
                "validation_error",
                f"series[{index}] must be a finite number",
            )
        series.append(numeric)
    return series
