from __future__ import annotations

import argparse
from pathlib import Path

from continuity_break_detector.backtesting.artifacts import (
    ArtifactParameters,
    detect_study_artifacts,
)
from continuity_break_detector.backtesting.study import STUDIES_DIR
from continuity_break_detector.backtesting.study_discovery import resolve_study_path
from continuity_break_detector.utils.logging import get_logger

LOGGER = get_logger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Detect likely data artifacts in break candidates."
    )
    parser.add_argument("--studies-dir", type=Path, default=STUDIES_DIR)
    parser.add_argument("--study-path", type=Path)
    args = parser.parse_args()
    selected_study = resolve_study_path(study_path=args.study_path, studies_dir=args.studies_dir)
    result = detect_study_artifacts(
        selected_study,
        parameters=ArtifactParameters(),
    )
    LOGGER.info("study_path,%s", result.study_path)
    LOGGER.info("candidate_count,%s", result.candidate_count)
    LOGGER.info("likely_artifacts,%s", result.likely_count)
    LOGGER.info("possible_artifacts,%s", result.possible_count)
    LOGGER.info("low_artifact_risk,%s", result.low_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
