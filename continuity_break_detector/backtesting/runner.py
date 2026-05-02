from __future__ import annotations

import argparse
from pathlib import Path

from continuity_break_detector.backtesting.study import (
    NORMALIZED_DIR,
    STUDIES_DIR,
    BacktestParameters,
    run_backtest_study,
)
from continuity_break_detector.config import (
    ANOMALY_WINDOW,
    ANOMALY_Z_THRESHOLD,
    FORECAST_HORIZON,
    MIN_SERIES_LENGTH,
    TRAIN_WINDOW_YEARS,
)
from continuity_break_detector.utils.logging import get_logger

LOGGER = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic historical backtests.")
    parser.add_argument("--input-dir", type=Path, default=NORMALIZED_DIR)
    parser.add_argument("--studies-dir", type=Path, default=STUDIES_DIR)
    parser.add_argument("--train-window-years", type=int, default=TRAIN_WINDOW_YEARS)
    parser.add_argument("--forecast-horizon-years", type=int, default=FORECAST_HORIZON)
    parser.add_argument("--minimum-series-length", type=int, default=MIN_SERIES_LENGTH)
    parser.add_argument("--anomaly-window", type=int, default=ANOMALY_WINDOW)
    parser.add_argument("--anomaly-threshold", type=float, default=ANOMALY_Z_THRESHOLD)
    args = parser.parse_args()

    result = run_backtest_study(
        input_dir=args.input_dir,
        studies_dir=args.studies_dir,
        parameters=BacktestParameters(
            train_window_years=args.train_window_years,
            forecast_horizon_years=args.forecast_horizon_years,
            minimum_series_length=args.minimum_series_length,
            anomaly_window=args.anomaly_window,
            anomaly_threshold=args.anomaly_threshold,
        ),
    )
    LOGGER.info("study_path,%s", result.output_dir)
    LOGGER.info("metrics_processed,%s", result.metrics_processed)
    LOGGER.info("forecast_error_rows,%s", result.forecast_error_rows)
    LOGGER.info("anomalies,%s", result.anomaly_rows)
    LOGGER.info("cross_domain_breaks,%s", result.cross_domain_break_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
