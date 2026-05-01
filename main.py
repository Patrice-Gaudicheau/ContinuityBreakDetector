from __future__ import annotations

import sys

from continuity_break_detector.agents.runner import main as agents_main
from continuity_break_detector.agents.lemonade_debug_runner import main as lemonade_debug_main
from continuity_break_detector.backtesting.artifact_runner import main as artifact_main
from continuity_break_detector.backtesting.audit_runner import main as audit_main
from continuity_break_detector.backtesting.runner import main as backtesting_main
from continuity_break_detector.backtesting.ranking_runner import main as ranking_main
from continuity_break_detector.forecasting.runner import (
    backtest_advanced_main,
    list_forecasters_main,
)
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
    if len(sys.argv) >= 2 and sys.argv[1] == "rank_breaks":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return ranking_main()
    if len(sys.argv) >= 2 and sys.argv[1] == "audit_candidates":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return audit_main()
    if len(sys.argv) >= 2 and sys.argv[1] == "analyze_agents":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return agents_main()
    if len(sys.argv) >= 2 and sys.argv[1] == "lemonade_debug":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return lemonade_debug_main()
    if len(sys.argv) >= 2 and sys.argv[1] == "detect_artifacts":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return artifact_main()
    if len(sys.argv) >= 2 and sys.argv[1] == "list_forecasters":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return list_forecasters_main()
    if len(sys.argv) >= 2 and sys.argv[1] == "backtest_advanced":
        sys.argv = [sys.argv[0], *sys.argv[2:]]
        return backtest_advanced_main()
    print("Usage: python main.py {ingest,normalize,compute_statistics,backtest,rank_breaks,audit_candidates,analyze_agents,lemonade_debug,detect_artifacts,list_forecasters,backtest_advanced}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
