from __future__ import annotations

import argparse
from pathlib import Path

from continuity_break_detector.backtesting.study import (
    NORMALIZED_DIR,
    STUDIES_DIR,
    BacktestParameters,
    run_backtest_study,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic historical backtests.")
    parser.add_argument("--input-dir", type=Path, default=NORMALIZED_DIR)
    parser.add_argument("--studies-dir", type=Path, default=STUDIES_DIR)
    parser.add_argument("--train-window-years", type=int, default=20)
    parser.add_argument("--forecast-horizon-years", type=int, default=5)
    parser.add_argument("--minimum-series-length", type=int, default=30)
    parser.add_argument("--anomaly-window", type=int, default=10)
    parser.add_argument("--anomaly-threshold", type=float, default=2.5)
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
    print(f"study_path,{result.output_dir}")
    print(f"metrics_processed,{result.metrics_processed}")
    print(f"forecast_error_rows,{result.forecast_error_rows}")
    print(f"anomalies,{result.anomaly_rows}")
    print(f"cross_domain_breaks,{result.cross_domain_break_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
