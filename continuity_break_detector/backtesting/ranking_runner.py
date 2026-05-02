from __future__ import annotations

import argparse
from pathlib import Path

from continuity_break_detector.backtesting.ranking import (
    RankingParameters,
    rank_study,
)
from continuity_break_detector.backtesting.study import STUDIES_DIR
from continuity_break_detector.backtesting.study_discovery import resolve_study_path
from continuity_break_detector.utils.logging import get_logger

LOGGER = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank deterministic backtest break candidates.")
    parser.add_argument("--studies-dir", type=Path, default=STUDIES_DIR)
    parser.add_argument("--study-path", type=Path)
    parser.add_argument("--neighborhood-years", type=int, default=2)
    parser.add_argument("--representative-window-years", type=int, default=3)
    parser.add_argument("--top-representative-limit", type=int, default=50)
    args = parser.parse_args()

    selected_study = resolve_study_path(study_path=args.study_path, studies_dir=args.studies_dir)
    result = rank_study(
        selected_study,
        parameters=RankingParameters(
            neighborhood_years=args.neighborhood_years,
            representative_window_years=args.representative_window_years,
            top_representative_limit=args.top_representative_limit,
        ),
    )
    LOGGER.info("study_path,%s", result.study_path)
    LOGGER.info("all_candidates,%s", result.all_candidates)
    LOGGER.info("representative_candidates,%s", result.representative_candidates)
    LOGGER.info("top_year,%s", result.top_year)
    LOGGER.info("top_rank_score,%s", result.top_rank_score)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
