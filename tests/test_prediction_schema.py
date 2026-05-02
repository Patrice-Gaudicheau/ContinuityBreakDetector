from __future__ import annotations

import re

import pytest

from continuity_break_detector.prediction_schema import (
    PredictionError,
    PredictionSchemaError,
    PredictionSuccess,
    parse_prediction_error,
    parse_prediction_request,
    parse_prediction_success,
    prediction_error_to_json_dict,
    prediction_request_to_json_dict,
    prediction_success_to_json_dict,
    validate_forecast,
    validate_horizon,
    validate_numeric_series,
)


def test_parse_prediction_request_accepts_common_contract() -> None:
    request = parse_prediction_request({"series": [1, 2.5, 3], "horizon": 2})

    assert request.series == [1.0, 2.5, 3.0]
    assert request.horizon == 2
    assert prediction_request_to_json_dict(request) == {
        "series": [1.0, 2.5, 3.0],
        "horizon": 2,
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "missing required field: series"),
        ({"series": [1], "horizon": False}, "horizon must be a positive integer"),
        ({"series": [1, True], "horizon": 1}, "series[1] must be a finite number"),
        ({"series": [1, float("inf")], "horizon": 1}, "series[1] must be a finite number"),
    ],
)
def test_parse_prediction_request_rejects_invalid_payloads(payload: object, message: str) -> None:
    with pytest.raises(PredictionSchemaError, match=re.escape(message)):
        parse_prediction_request(payload)


def test_prediction_success_round_trip() -> None:
    success = PredictionSuccess(
        worker="timesfm",
        model_id="model",
        horizon=1,
        forecast=[2.5],
    )

    payload = prediction_success_to_json_dict(success)
    parsed = parse_prediction_success(payload)

    assert parsed == success


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"worker": "timesfm", "model_id": "m", "horizon": 1, "forecast": []}, "forecast must"),
        (
            {"worker": "timesfm", "model_id": "m", "horizon": 1, "forecast": [True]},
            "forecast[0] must be a finite number",
        ),
        ({"worker": "timesfm", "model_id": "m", "horizon": 0, "forecast": [1]}, "horizon must"),
    ],
)
def test_parse_prediction_success_rejects_invalid_payloads(
    payload: object, message: str
) -> None:
    with pytest.raises(PredictionSchemaError, match=re.escape(message)):
        parse_prediction_success(payload)


def test_prediction_error_round_trip() -> None:
    error = PredictionError(worker="chronos", error_type="validation_error", message="bad input")

    payload = prediction_error_to_json_dict(error)

    assert parse_prediction_error(payload) == error


def test_direct_validation_helpers_reject_bool_and_empty_values() -> None:
    with pytest.raises(PredictionSchemaError, match="series must be a non-empty list"):
        validate_numeric_series([])
    with pytest.raises(PredictionSchemaError, match="horizon must be a positive integer"):
        validate_horizon(True)
    with pytest.raises(PredictionSchemaError, match="forecast must be a non-empty list"):
        validate_forecast([])
