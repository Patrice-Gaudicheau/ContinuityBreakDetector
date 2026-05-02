from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from continuity_break_detector.ml_break_analysis import analyze_prediction_result
from continuity_break_detector.series_prediction import (
    SeriesPredictionError,
    build_error_response,
    load_series_input,
    predict_series_with_worker,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run ML worker prediction and continuity-break analysis for a JSON series."
    )
    parser.add_argument("--worker", choices=["timesfm", "chronos"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    try:
        series_input = load_series_input(args.input)
        prediction = predict_series_with_worker(
            args.worker,
            series_input.series,
            args.horizon,
            timeout_seconds=args.timeout,
        )
        result = analyze_prediction_result(
            worker=args.worker,
            series_input=series_input,
            prediction=prediction,
        )
    except SeriesPredictionError as exc:
        print(json.dumps(build_error_response(exc.error_type, exc.message), separators=(",", ":")))
        return 2 if exc.error_type == "validation_error" else 1

    if result.prediction.stderr.strip():
        print(result.prediction.stderr.strip(), file=sys.stderr)

    model_id = None
    if result.prediction.response is not None:
        raw_model_id = result.prediction.response.get("model_id")
        if isinstance(raw_model_id, str):
            model_id = raw_model_id
    response = {
        "status": "ok",
        "worker": result.worker,
        "input": {
            "points": len(result.series_input.series),
            "metadata": result.series_input.metadata,
        },
        "prediction": {
            "model_id": model_id,
            "horizon": args.horizon,
            "forecast": result.prediction.forecast,
        },
        "analysis": result.analysis,
    }
    print(json.dumps(response, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
