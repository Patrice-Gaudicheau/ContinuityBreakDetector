from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from continuity_break_detector.ml_break_analysis import analyze_prediction_result
from continuity_break_detector.series_prediction import (
    DEFAULT_PREDICTION_MODE,
    SeriesPredictionError,
    build_error_response,
    close_forecast_client,
    forecast_client_for_mode,
    load_series_input,
    predict_series_with_worker,
    validate_prediction_mode,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ML worker prediction and continuity-break analysis for a JSON series."
    )
    parser.add_argument("--worker", choices=["timesfm", "chronos"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--mode", default=DEFAULT_PREDICTION_MODE)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    client = None
    try:
        mode = validate_prediction_mode(args.mode)
        series_input = load_series_input(args.input)
        client = forecast_client_for_mode(mode)
        prediction = predict_series_with_worker(
            args.worker,
            series_input.series,
            args.horizon,
            timeout_seconds=args.timeout,
            client=client,
        )
        result = analyze_prediction_result(
            worker=args.worker,
            series_input=series_input,
            prediction=prediction,
        )
    except SeriesPredictionError as exc:
        print(json.dumps(build_error_response(exc.error_type, exc.message), separators=(",", ":")))
        return 2 if exc.error_type == "validation_error" else 1
    finally:
        if client is not None:
            close_forecast_client(client)

    if result.prediction.raw_stderr.strip():
        print(result.prediction.raw_stderr.strip(), file=sys.stderr)

    response = {
        "status": "ok",
        "worker": result.worker,
        "mode": mode,
        "input": {
            "points": len(result.series_input.series),
            "metadata": result.series_input.metadata,
        },
        "prediction": {
            "model_id": result.prediction.model_id,
            "horizon": args.horizon,
            "forecast": result.prediction.forecast,
        },
        "analysis": result.analysis,
    }
    print(json.dumps(response, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
