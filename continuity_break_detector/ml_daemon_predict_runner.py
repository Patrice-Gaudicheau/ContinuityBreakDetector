from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from continuity_break_detector.forecast_client import ForecastResult
from continuity_break_detector.forecast_daemon_client import DockerWarmForecastClient
from continuity_break_detector.ml_predict_runner import _parse_series
from continuity_break_detector.prediction_schema import (
    PredictionError,
    PredictionSchemaError,
    prediction_error_to_json_dict,
    validate_horizon,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run experimental warm Docker ML worker prediction.")
    parser.add_argument("--worker", choices=["timesfm", "chronos"], required=True)
    parser.add_argument("--series", required=True, help="Comma-separated numeric time series.")
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    try:
        series = _parse_series(args.series)
        horizon = validate_horizon(args.horizon)
        if args.repeat <= 0:
            raise ValueError("repeat must be a positive integer")
    except (PredictionSchemaError, ValueError) as exc:
        print(json.dumps(_error_response(args.worker, "validation_error", str(exc)), separators=(",", ":")))
        return 2

    predictions: list[dict[str, Any]] = []
    timings: list[float] = []
    stderr_offset = 0
    status = "ok"
    return_code = 0
    started = time.perf_counter()

    with DockerWarmForecastClient() as client:
        for _ in range(args.repeat):
            request_started = time.perf_counter()
            result = client.predict(
                args.worker,
                series,
                horizon,
                timeout_seconds=args.timeout,
            )
            timings.append(round(time.perf_counter() - request_started, 6))
            if result.raw_stderr:
                new_stderr = result.raw_stderr[stderr_offset:]
                if new_stderr.strip():
                    print(new_stderr.strip(), file=sys.stderr)
                stderr_offset = len(result.raw_stderr)
            predictions.append(_prediction_payload(result))
            if not result.succeeded:
                status = "error"
                return_code = 1
                break

    response = {
        "status": status,
        "worker": args.worker,
        "mode": "daemon",
        "repeat": args.repeat,
        "completed": len(predictions),
        "duration_seconds": round(time.perf_counter() - started, 6),
        "request_durations_seconds": timings,
        "predictions": predictions,
    }
    print(json.dumps(response, separators=(",", ":")))
    return return_code


def _prediction_payload(result: ForecastResult) -> dict[str, Any]:
    if result.succeeded:
        return {
            "model_id": result.model_id,
            "horizon": result.horizon,
            "forecast": result.forecast,
        }
    return {
        "error": {
            "type": "worker_error",
            "message": result.error or "worker prediction failed",
        }
    }


def _error_response(worker: str, error_type: str, message: str) -> dict[str, object]:
    return prediction_error_to_json_dict(
        PredictionError(worker=worker, error_type=error_type, message=message)
    )


if __name__ == "__main__":
    raise SystemExit(main())
