from __future__ import annotations

import argparse
import json
import math
import sys

from continuity_break_detector.ml_workers import (
    WorkerPredictionResult,
    predict_chronos,
    predict_timesfm,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run optional Docker ML worker prediction.")
    parser.add_argument("--worker", choices=["timesfm", "chronos"], required=True)
    parser.add_argument("--series", required=True, help="Comma-separated numeric time series.")
    parser.add_argument("--horizon", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()

    try:
        series = _parse_series(args.series)
    except ValueError as exc:
        _print_error(args.worker, "validation_error", str(exc))
        return 2
    if args.horizon <= 0:
        _print_error(args.worker, "validation_error", "horizon must be a positive integer")
        return 2

    if args.worker == "timesfm":
        result = predict_timesfm(series, args.horizon, timeout_seconds=args.timeout)
    else:
        result = predict_chronos(series, args.horizon, timeout_seconds=args.timeout)
    return _print_result(result)


def _parse_series(value: str) -> list[float]:
    items = [item.strip() for item in value.split(",")]
    if not items or any(item == "" for item in items):
        raise ValueError("series must be a comma-separated list of numbers")
    try:
        series = [float(item) for item in items]
    except ValueError as exc:
        raise ValueError("series must be a comma-separated list of numbers") from exc
    if not all(math.isfinite(item) for item in series):
        raise ValueError("series must contain only finite numbers")
    return series


def _print_result(result: WorkerPredictionResult) -> int:
    if result.stderr.strip():
        print(result.stderr.strip(), file=sys.stderr)
    if result.response is not None:
        print(json.dumps(result.response, separators=(",", ":")))
    else:
        _print_error(result.worker_name, "worker_error", result.error or "worker prediction failed")
    return 0 if result.succeeded else 1


def _print_error(worker: str, error_type: str, message: str) -> None:
    print(
        json.dumps(
            {
                "worker": worker,
                "error": {
                    "type": error_type,
                    "message": message,
                },
            },
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
