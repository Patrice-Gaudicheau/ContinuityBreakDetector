from __future__ import annotations

import argparse
from pathlib import Path

from continuity_break_detector.backtesting.artifacts import (
    ArtifactParameters,
    detect_study_artifacts,
)
from continuity_break_detector.backtesting.study_discovery import resolve_study_path
from continuity_break_detector.backtesting.study import STUDIES_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect likely data artifacts in break candidates.")
    parser.add_argument("--studies-dir", type=Path, default=STUDIES_DIR)
    parser.add_argument("--study-path", type=Path)
    args = parser.parse_args()
    selected_study = resolve_study_path(study_path=args.study_path, studies_dir=args.studies_dir)
    result = detect_study_artifacts(
        selected_study,
        parameters=ArtifactParameters(),
    )
    print(f"study_path,{result.study_path}")
    print(f"candidate_count,{result.candidate_count}")
    print(f"likely_artifacts,{result.likely_count}")
    print(f"possible_artifacts,{result.possible_count}")
    print(f"low_artifact_risk,{result.low_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
