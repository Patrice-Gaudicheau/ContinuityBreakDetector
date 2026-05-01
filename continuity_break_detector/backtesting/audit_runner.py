from __future__ import annotations

import argparse
from pathlib import Path

from continuity_break_detector.backtesting.audit import AuditParameters, audit_latest_study
from continuity_break_detector.backtesting.study import STUDIES_DIR


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ranked break candidates.")
    parser.add_argument("--studies-dir", type=Path, default=STUDIES_DIR)
    parser.add_argument("--pre-post-window-years", type=int, default=10)
    parser.add_argument("--top-list-limit", type=int, default=20)
    args = parser.parse_args()

    result = audit_latest_study(
        studies_dir=args.studies_dir,
        parameters=AuditParameters(
            pre_post_window_years=args.pre_post_window_years,
            top_list_limit=args.top_list_limit,
        ),
    )
    print(f"study_path,{result.study_path}")
    print(f"candidate_count,{result.candidate_count}")
    print(f"strong_count,{result.strong_count}")
    print(f"moderate_count,{result.moderate_count}")
    print(f"weak_count,{result.weak_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

