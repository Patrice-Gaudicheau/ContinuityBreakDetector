from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from continuity_break_detector.forecast_client import (
    ForecastClient,
    ForecastResult,
    default_forecast_client,
)
from continuity_break_detector.forecast_daemon_client import DockerWarmForecastClient
from continuity_break_detector.prediction_schema import (
    PredictionSchemaError,
    validate_horizon,
    validate_numeric_series,
)

DEFAULT_PREDICTION_MODE = "one-shot"
PREDICTION_MODES = frozenset({DEFAULT_PREDICTION_MODE, "daemon"})


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
    try:
        validated_horizon = validate_horizon(horizon)
    except PredictionSchemaError as exc:
        raise SeriesPredictionError("validation_error", str(exc)) from exc
    forecast_client = client or default_forecast_client()
    try:
        return forecast_client.predict(worker, series, validated_horizon, timeout_seconds=timeout_seconds)
    except ValueError as exc:
        raise SeriesPredictionError("validation_error", str(exc)) from exc


def validate_prediction_mode(mode: str) -> str:
    if mode not in PREDICTION_MODES:
        raise SeriesPredictionError(
            "validation_error",
            "mode must be one of: one-shot, daemon",
        )
    return mode


def forecast_client_for_mode(mode: str) -> ForecastClient:
    validated_mode = validate_prediction_mode(mode)
    if validated_mode == "daemon":
        return DockerWarmForecastClient()
    return default_forecast_client()


def close_forecast_client(client: ForecastClient) -> None:
    close = getattr(client, "close", None)
    if callable(close):
        close()


def build_success_response(
    *,
    worker: str,
    mode: str = DEFAULT_PREDICTION_MODE,
    series_input: SeriesInput,
    prediction: ForecastResult,
    horizon: int,
) -> dict[str, Any]:
    return {
        "status": "ok",
        "worker": worker,
        "mode": mode,
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
    try:
        return validate_numeric_series(raw_series)
    except PredictionSchemaError as exc:
        raise SeriesPredictionError("validation_error", str(exc)) from exc
