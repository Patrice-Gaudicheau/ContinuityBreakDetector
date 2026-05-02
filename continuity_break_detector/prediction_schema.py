from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real


class PredictionSchemaError(ValueError):
    pass


@dataclass(frozen=True)
class PredictionRequest:
    series: list[float]
    horizon: int


@dataclass(frozen=True)
class PredictionSuccess:
    worker: str
    model_id: str
    horizon: int
    forecast: list[float]


@dataclass(frozen=True)
class PredictionError:
    worker: str
    error_type: str
    message: str


def parse_prediction_request(data: object) -> PredictionRequest:
    if not isinstance(data, dict):
        raise PredictionSchemaError("payload must be a JSON object")
    if "series" not in data:
        raise PredictionSchemaError("missing required field: series")
    if "horizon" not in data:
        raise PredictionSchemaError("missing required field: horizon")
    return PredictionRequest(
        series=validate_numeric_series(
            data["series"],
            empty_message="series must be a non-empty list of numbers",
        ),
        horizon=validate_horizon(data["horizon"]),
    )


def prediction_request_to_json_dict(request: PredictionRequest) -> dict[str, object]:
    return {
        "series": request.series,
        "horizon": request.horizon,
    }


def prediction_success_to_json_dict(success: PredictionSuccess) -> dict[str, object]:
    return {
        "worker": success.worker,
        "model_id": success.model_id,
        "horizon": success.horizon,
        "forecast": success.forecast,
    }


def prediction_error_to_json_dict(error: PredictionError) -> dict[str, object]:
    return {
        "worker": error.worker,
        "error": {
            "type": error.error_type,
            "message": error.message,
        },
    }


def parse_prediction_success(data: object) -> PredictionSuccess:
    if not isinstance(data, dict):
        raise PredictionSchemaError("worker returned non-object JSON stdout")
    worker = data.get("worker")
    if not isinstance(worker, str) or not worker:
        raise PredictionSchemaError("worker response missing string field: worker")
    model_id = data.get("model_id")
    if not isinstance(model_id, str):
        raise PredictionSchemaError("worker response missing string field: model_id")
    if "horizon" not in data:
        raise PredictionSchemaError("worker response missing required field: horizon")
    if "forecast" not in data:
        raise PredictionSchemaError("worker response missing required field: forecast")
    return PredictionSuccess(
        worker=worker,
        model_id=model_id,
        horizon=validate_horizon(data["horizon"]),
        forecast=validate_forecast(data["forecast"]),
    )


def parse_prediction_error(data: object) -> PredictionError | None:
    if not isinstance(data, dict):
        return None
    worker = data.get("worker")
    error = data.get("error")
    if not isinstance(worker, str) or not isinstance(error, dict):
        return None
    error_type = error.get("type")
    message = error.get("message")
    if not isinstance(error_type, str) or not isinstance(message, str):
        return None
    return PredictionError(worker=worker, error_type=error_type, message=message)


def validate_numeric_series(
    series: object,
    *,
    empty_message: str = "series must be a non-empty list of finite numbers",
) -> list[float]:
    return _validate_numeric_list(series, field_name="series", empty_message=empty_message)


def validate_forecast(forecast: object) -> list[float]:
    return _validate_numeric_list(
        forecast,
        field_name="forecast",
        empty_message="forecast must be a non-empty list of finite numbers",
    )


def validate_horizon(horizon: object) -> int:
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon <= 0:
        raise PredictionSchemaError("horizon must be a positive integer")
    return horizon


def _validate_numeric_list(data: object, *, field_name: str, empty_message: str) -> list[float]:
    if not isinstance(data, list) or not data:
        raise PredictionSchemaError(empty_message)

    validated: list[float] = []
    for index, value in enumerate(data):
        if isinstance(value, bool) or not isinstance(value, Real):
            raise PredictionSchemaError(f"{field_name}[{index}] must be a finite number")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise PredictionSchemaError(f"{field_name}[{index}] must be a finite number")
        validated.append(numeric)
    return validated
