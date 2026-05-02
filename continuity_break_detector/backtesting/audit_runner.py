from __future__ import annotations

import argparse
from pathlib import Path

from continuity_break_detector.backtesting.audit import AuditParameters, audit_study
from continuity_break_detector.backtesting.study import STUDIES_DIR
from continuity_break_detector.backtesting.study_discovery import resolve_study_path
from continuity_break_detector.utils.logging import get_logger

LOGGER = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ranked break candidates.")
    parser.add_argument("--studies-dir", type=Path, default=STUDIES_DIR)
    parser.add_argument("--study-path", type=Path)
    parser.add_argument("--pre-post-window-years", type=int, default=10)
    parser.add_argument("--top-list-limit", type=int, default=20)
    args = parser.parse_args()

    selected_study = resolve_study_path(study_path=args.study_path, studies_dir=args.studies_dir)
    result = audit_study(
        selected_study,
        parameters=AuditParameters(
            pre_post_window_years=args.pre_post_window_years,
            top_list_limit=args.top_list_limit,
        ),
    )
    LOGGER.info("study_path,%s", result.study_path)
    LOGGER.info("candidate_count,%s", result.candidate_count)
    LOGGER.info("strong_count,%s", result.strong_count)
    LOGGER.info("moderate_count,%s", result.moderate_count)
    LOGGER.info("weak_count,%s", result.weak_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
