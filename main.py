from __future__ import annotations

import sys

from continuity_break_detector.backtesting.runner import main as backtesting_main
from continuity_break_detector.ingestion.runner import main as ingestion_main
from continuity_break_detector.normalization.runner import main as normalization_main
from continuity_break_detector.statistics.runner import main as statistics_main


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "ingest":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return ingestion_main()
    if len(sys.argv) >= 2 and sys.argv[1] == "normalize":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return normalization_main()
    if len(sys.argv) >= 2 and sys.argv[1] == "compute_statistics":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return statistics_main()
    if len(sys.argv) >= 2 and sys.argv[1] == "backtest":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return backtesting_main()
    print("Usage: python main.py {ingest,normalize,compute_statistics,backtest}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
