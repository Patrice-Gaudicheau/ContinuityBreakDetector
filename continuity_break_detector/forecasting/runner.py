from __future__ import annotations

import argparse

from continuity_break_detector.forecasting.advanced_backtest import run_advanced_backtest_study
from continuity_break_detector.forecasting.registry import build_forecaster_registry
from continuity_break_detector.utils.logging import get_logger

LOGGER = get_logger(__name__)


def list_forecasters_main() -> int:
    registry = build_forecaster_registry()
    for status in registry.availability():
        label = "available" if status.available else "unavailable"
        details = status.reason
        if status.source_path:
            details = f"{details}; source_path={status.source_path}"
        LOGGER.info("%s: %s - %s", status.forecaster_id, label, details)
    return 0


def backtest_advanced_main() -> int:
    parser = argparse.ArgumentParser(description="Run advanced forecasting backtests.")
    parser.parse_args()
    result = run_advanced_backtest_study()
    LOGGER.info("study_path: %s", result.output_dir)
    LOGGER.info("metrics_processed: %s", result.metrics_processed)
    LOGGER.info("forecast_error_rows: %s", result.forecast_error_rows)
    LOGGER.info("anomalies: %s", result.anomaly_rows)
    LOGGER.info("cross_domain_breaks: %s", result.cross_domain_break_rows)
    LOGGER.info("models_run: %s", ", ".join(result.models_run) if result.models_run else "none")
    return 0
