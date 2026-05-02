from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from continuity_break_detector.batch_prediction import (
    DEFAULT_BATCH_PREDICTION_MODE,
    load_batch_input,
    run_batch_prediction,
)
from continuity_break_detector.series_prediction import SeriesPredictionError, build_error_response


def main() -> int:
    parser = argparse.ArgumentParser(description="Predict multiple JSON series with one ML worker.")
    parser.add_argument("--worker", choices=["timesfm", "chronos"], required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--mode", default=DEFAULT_BATCH_PREDICTION_MODE)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    try:
        batch_input = load_batch_input(args.input)
        response = run_batch_prediction(
            worker=args.worker,
            batch_input=batch_input,
            horizon=args.horizon,
            mode=args.mode,
            timeout_seconds=args.timeout,
        )
    except SeriesPredictionError as exc:
        print(json.dumps(build_error_response(exc.error_type, exc.message), separators=(",", ":")))
        return 2 if exc.error_type == "validation_error" else 1

    for result in response["results"]:
        if isinstance(result, dict) and result.get("status") == "error":
            error = result.get("error")
            if isinstance(error, dict) and isinstance(error.get("message"), str):
                print(f"{result.get('name')}: {error['message']}", file=sys.stderr)
    print(json.dumps(response, separators=(",", ":")))
    return 0 if response["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
