from __future__ import annotations

import argparse
import logging

from continuity_break_detector.forecasting.advanced_backtest import run_advanced_backtest_study
from continuity_break_detector.forecasting.registry import build_forecaster_registry


def list_forecasters_main() -> int:
    registry = build_forecaster_registry()
    for status in registry.availability():
        label = "available" if status.available else "unavailable"
        details = status.reason
        if status.source_path:
            details = f"{details}; source_path={status.source_path}"
        print(f"{status.forecaster_id}: {label} - {details}")
    return 0


def backtest_advanced_main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    parser = argparse.ArgumentParser(description="Run advanced forecasting backtests.")
    parser.parse_args()
    result = run_advanced_backtest_study()
    print(f"study_path: {result.output_dir}")
    print(f"metrics_processed: {result.metrics_processed}")
    print(f"forecast_error_rows: {result.forecast_error_rows}")
    print(f"anomalies: {result.anomaly_rows}")
    print(f"cross_domain_breaks: {result.cross_domain_break_rows}")
    print(f"models_run: {', '.join(result.models_run) if result.models_run else 'none'}")
    return 0

