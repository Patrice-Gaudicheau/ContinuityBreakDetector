from __future__ import annotations

import sys
from collections.abc import Callable

from continuity_break_detector.agents.lemonade_debug_runner import main as lemonade_debug_main
from continuity_break_detector.agents.runner import main as agents_main
from continuity_break_detector.backtesting.artifact_runner import main as artifact_main
from continuity_break_detector.backtesting.audit_runner import main as audit_main
from continuity_break_detector.backtesting.ranking_runner import main as ranking_main
from continuity_break_detector.backtesting.runner import main as backtesting_main
from continuity_break_detector.demo import main as demo_study_main
from continuity_break_detector.forecasting.runner import (
    backtest_advanced_main,
    list_forecasters_main,
)
from continuity_break_detector.ingestion.runner import main as ingestion_main
from continuity_break_detector.ml_worker_runner import main as ml_worker_main
from continuity_break_detector.normalization.runner import main as normalization_main
from continuity_break_detector.publication.runner import main as publication_main
from continuity_break_detector.statistics.runner import main as statistics_main
from continuity_break_detector.utils.logging import configure_logging, get_logger

LOGGER = get_logger(__name__)

COMMANDS: dict[str, Callable[[], int]] = {
    "ingest": ingestion_main,
    "normalize": normalization_main,
    "compute_statistics": statistics_main,
    "backtest": backtesting_main,
    "backtest_advanced": backtest_advanced_main,
    "rank_breaks": ranking_main,
    "audit_candidates": audit_main,
    "detect_artifacts": artifact_main,
    "analyze_agents": agents_main,
    "lemonade_debug": lemonade_debug_main,
    "list_forecasters": list_forecasters_main,
    "draft_paper": publication_main,
    "demo_study": demo_study_main,
    "ml-smoke": ml_worker_main,
}


def main() -> int:
    configure_logging()
    if len(sys.argv) >= 2 and sys.argv[1] in COMMANDS:
        command = sys.argv[1]
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return COMMANDS[command]()
    LOGGER.error("Usage: cbd {%s}", ",".join(COMMANDS))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
