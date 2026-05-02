from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from continuity_break_detector.forecast_client import (
    ForecastClient,
    ForecastResult,
    default_forecast_client,
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
    client: ForecastClient | None = None,
) -> ForecastResult:
    if horizon <= 0:
        raise SeriesPredictionError("validation_error", "horizon must be a positive integer")
    forecast_client = client or default_forecast_client()
    try:
        return forecast_client.predict(worker, series, horizon, timeout_seconds=timeout_seconds)
    except ValueError as exc:
        raise SeriesPredictionError("validation_error", str(exc)) from exc


def build_success_response(
    *,
    worker: str,
    series_input: SeriesInput,
    prediction: ForecastResult,
    horizon: int,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "worker": worker,
        "input": {
            "points": len(series_input.series),
            "metadata": series_input.metadata,
        },
        "prediction": {
            "model_id": prediction.model_id,
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
