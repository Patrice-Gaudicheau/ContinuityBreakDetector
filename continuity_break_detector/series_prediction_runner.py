from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from continuity_break_detector.series_prediction import (
    SeriesPredictionError,
    build_error_response,
    build_success_response,
    load_series_input,
    predict_series_with_worker,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict a JSON time series with an ML worker.")
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
    except SeriesPredictionError as exc:
        print(json.dumps(build_error_response(exc.error_type, exc.message), separators=(",", ":")))
        return 2

    if prediction.raw_stderr.strip():
        print(prediction.raw_stderr.strip(), file=sys.stderr)
    if not prediction.succeeded:
        message = prediction.error or "worker prediction failed"
        print(json.dumps(build_error_response("worker_error", message), separators=(",", ":")))
        return 1

    response = build_success_response(
        worker=args.worker,
        series_input=series_input,
        prediction=prediction,
        horizon=args.horizon,
    )
    print(json.dumps(response, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
