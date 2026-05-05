from __future__ import annotations

import sys
from collections.abc import Callable

from continuity_break_detector.agents.lemonade_debug_runner import main as lemonade_debug_main
from continuity_break_detector.agents.runner import main as agents_main
from continuity_break_detector.backtesting.artifact_runner import main as artifact_main
from continuity_break_detector.backtesting.audit_runner import main as audit_main
from continuity_break_detector.backtesting.ranking_runner import main as ranking_main
from continuity_break_detector.backtesting.runner import main as backtesting_main
from continuity_break_detector.batch_prediction_runner import main as batch_prediction_main
from continuity_break_detector.demo import main as demo_study_main
from continuity_break_detector.forecasting.runner import (
    backtest_advanced_main,
    list_forecasters_main,
)
from continuity_break_detector.ingestion.runner import main as ingestion_main
from continuity_break_detector.ml_break_analysis_runner import main as ml_break_analysis_main
from continuity_break_detector.ml_daemon_predict_runner import main as ml_daemon_predict_main
from continuity_break_detector.ml_predict_runner import main as ml_predict_main
from continuity_break_detector.ml_worker_runner import main as ml_worker_main
from continuity_break_detector.normalization.runner import main as normalization_main
from continuity_break_detector.publication.runner import main as publication_main
from continuity_break_detector.series_prediction_runner import main as series_prediction_main
from continuity_break_detector.statistics.runner import main as statistics_main
from continuity_break_detector.utils.logging import configure_logging, get_logger

LOGGER = get_logger(__name__)

COMMANDS: dict[str, tuple[Callable[[], int], str]] = {
    "ingest": (ingestion_main, "Fetch public-source data from supported APIs"),
    "normalize": (normalization_main, "Convert raw source data into a common yearly Parquet schema"),
    "compute_statistics": (statistics_main, "Compute statistical features (growth, z-scores, etc.)"),
    "backtest": (backtesting_main, "Run deterministic historical backtests to find anomalies"),
    "backtest_advanced": (backtest_advanced_main, "Run backtests using advanced ML models (requires Docker)"),
    "rank_breaks": (ranking_main, "Rank candidate break years across multiple metrics"),
    "audit_candidates": (audit_main, "Audit candidates for robustness and model agreement"),
    "detect_artifacts": (artifact_main, "Identify likely data artifacts and source-revision noise"),
    "analyze_agents": (agents_main, "Run AI agents to interpret and critique the results"),
    "lemonade_debug": (lemonade_debug_main, "Test the connection to a Lemonade-compatible LLM endpoint"),
    "list_forecasters": (list_forecasters_main, "List available advanced forecasting models"),
    "draft_paper": (publication_main, "Generate a draft article or report from the study artifacts"),
    "demo_study": (demo_study_main, "Run a complete end-to-end study using embedded demo data"),
    "ml-smoke": (ml_worker_main, "Run a smoke test for the ML worker infrastructure"),
    "ml-predict": (ml_predict_main, "Run a single prediction using an ML worker"),
    "ml-daemon-predict": (ml_daemon_predict_main, "Run a prediction using a warm daemon ML worker"),
    "predict-series": (series_prediction_main, "Run a prediction for a single series (CLI helper)"),
    "batch-predict": (batch_prediction_main, "Run batch predictions for multiple series"),
    "analyze-series": (ml_break_analysis_main, "Run a break analysis for a single series"),
}


def print_usage() -> None:
    print("\nUsage: cbd <command> [options]\n")
    print("Commands:")
    for cmd, (_, desc) in COMMANDS.items():
        print(f"  {cmd:<20} {desc}")
    print("\nUse 'cbd <command> --help' for details on a specific command.\n")


def main() -> int:
    configure_logging()
    if len(sys.argv) == 2 and sys.argv[1] in {"-h", "--help"}:
        print_usage()
        return 0

    if len(sys.argv) >= 2 and sys.argv[1] in COMMANDS:
        command = sys.argv[1]
        handler, _ = COMMANDS[command]
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return handler()

    print_usage()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
