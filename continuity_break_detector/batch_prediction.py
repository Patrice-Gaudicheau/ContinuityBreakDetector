from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from continuity_break_detector.forecast_client import ForecastClient
from continuity_break_detector.prediction_schema import (
    PredictionSchemaError,
    validate_horizon,
    validate_numeric_series,
)
from continuity_break_detector.series_prediction import (
    SeriesPredictionError,
    close_forecast_client,
    forecast_client_for_mode,
    validate_prediction_mode,
)

DEFAULT_BATCH_PREDICTION_MODE = "daemon"


@dataclass(frozen=True)
class BatchSeriesItem:
    name: str
    values: list[float]


@dataclass(frozen=True)
class BatchInput:
    series: list[BatchSeriesItem]
    metadata: dict[str, Any]


def load_batch_input(path: Path) -> BatchInput:
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
    return BatchInput(series=validate_batch_series(payload["series"]), metadata=metadata)


def validate_batch_series(raw_series: object) -> list[BatchSeriesItem]:
    if not isinstance(raw_series, list) or not raw_series:
        raise SeriesPredictionError("validation_error", "series must be a non-empty list")

    seen_names: set[str] = set()
    series: list[BatchSeriesItem] = []
    for index, item in enumerate(raw_series):
        if not isinstance(item, dict):
            raise SeriesPredictionError("validation_error", f"series[{index}] must be an object")
        raw_name = item.get("name")
        if not isinstance(raw_name, str) or raw_name.strip() == "":
            raise SeriesPredictionError(
                "validation_error",
                f"series[{index}].name must be a non-empty string",
            )
        name = raw_name.strip()
        if name in seen_names:
            raise SeriesPredictionError("validation_error", f"duplicate series name: {name}")
        if "values" not in item:
            raise SeriesPredictionError(
                "validation_error",
                f"series[{index}] missing required field: values",
            )
        try:
            values = validate_numeric_series(item["values"])
        except PredictionSchemaError as exc:
            raise SeriesPredictionError("validation_error", f"series[{index}].values: {exc}") from exc
        seen_names.add(name)
        series.append(BatchSeriesItem(name=name, values=values))
    return series


def run_batch_prediction(
    *,
    worker: str,
    batch_input: BatchInput,
    horizon: int,
    mode: str = DEFAULT_BATCH_PREDICTION_MODE,
    timeout_seconds: float = 120.0,
    client: ForecastClient | None = None,
) -> dict[str, Any]:
    try:
        validated_horizon = validate_horizon(horizon)
    except PredictionSchemaError as exc:
        raise SeriesPredictionError("validation_error", str(exc)) from exc
    validated_mode = validate_prediction_mode(mode)

    forecast_client = client or forecast_client_for_mode(validated_mode)
    should_close_client = client is None
    try:
        results = []
        for item in batch_input.series:
            result = predict_batch_item(
                worker=worker,
                item=item,
                horizon=validated_horizon,
                client=forecast_client,
                timeout_seconds=timeout_seconds,
            )
            if validated_mode == "daemon" and is_fatal_daemon_error(result):
                error = result["error"]
                raise SeriesPredictionError("worker_error", str(error["message"]))
            results.append(result)
    finally:
        if should_close_client:
            close_forecast_client(forecast_client)

    ok_count = sum(1 for result in results if result["status"] == "ok")
    failed_count = len(results) - ok_count
    return {
        "status": "ok" if failed_count == 0 else "partial",
        "worker": worker,
        "mode": validated_mode,
        "horizon": validated_horizon,
        "input": {
            "series_count": len(batch_input.series),
            "metadata": batch_input.metadata,
        },
        "results": results,
        "summary": {
            "ok": ok_count,
            "failed": failed_count,
        },
    }


def predict_batch_item(
    *,
    worker: str,
    item: BatchSeriesItem,
    horizon: int,
    client: ForecastClient,
    timeout_seconds: float,
) -> dict[str, Any]:
    try:
        prediction = client.predict(
            worker,
            item.values,
            horizon,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        return batch_item_error(item.name, "worker_error", str(exc))

    if prediction.succeeded:
        return {
            "name": item.name,
            "status": "ok",
            "prediction": {
                "model_id": prediction.model_id,
                "forecast": prediction.forecast,
            },
        }
    return batch_item_error(item.name, "worker_error", prediction.error or "worker prediction failed")


def batch_item_error(name: str, error_type: str, message: str) -> dict[str, Any]:
    return {
        "name": name,
        "status": "error",
        "error": {
            "type": error_type,
            "message": message,
        },
    }


def is_fatal_daemon_error(result: dict[str, Any]) -> bool:
    if result.get("status") != "error":
        return False
    error = result.get("error")
    if not isinstance(error, dict):
        return False
    message = error.get("message")
    if not isinstance(message, str):
        return False
    fatal_fragments = (
        "daemon prediction could not start Docker Compose",
        "daemon prediction failed to write request",
        "daemon prediction timed out",
        "daemon exited before returning a prediction",
    )
    return any(fragment in message for fragment in fatal_fragments)
