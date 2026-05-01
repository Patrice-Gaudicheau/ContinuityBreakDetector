from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

from continuity_break_detector.statistics.breaks import add_break_scores
from continuity_break_detector.statistics.features import add_statistical_features
from continuity_break_detector.storage.parquet import read_parquet, write_parquet
from continuity_break_detector.utils.paths import PROJECT_ROOT


LOGGER = logging.getLogger(__name__)
NORMALIZED_DIR = PROJECT_ROOT / "data" / "processed" / "normalized"
STATISTICS_DIR = PROJECT_ROOT / "data" / "processed" / "statistics"


@dataclass(frozen=True)
class StatisticsResult:
    source_id: str
    metric: str
    rows_written: int
    warnings_count: int
    path: Path


def run_statistics(
    *,
    normalized_dir: Path = NORMALIZED_DIR,
    output_dir: Path = STATISTICS_DIR,
    window: int = 10,
) -> list[StatisticsResult]:
    results: list[StatisticsResult] = []
    if not normalized_dir.exists():
        LOGGER.warning("Normalized directory does not exist: %s", normalized_dir)
        return results
    for source_dir in sorted(path for path in normalized_dir.iterdir() if path.is_dir()):
        source_id = source_dir.name
        for input_path in sorted(source_dir.glob("*.parquet")):
            normalized = read_parquet(input_path)
            if normalized.empty:
                continue
            metric = str(normalized["metric"].iloc[0])
            stats = add_break_scores(add_statistical_features(normalized, window=window), window=window)
            output_path = output_dir / source_id / f"{input_path.stem}_statistics.parquet"
            write_parquet(stats, output_path)
            results.append(
                StatisticsResult(
                    source_id=source_id,
                    metric=metric,
                    rows_written=len(stats),
                    warnings_count=0,
                    path=output_path,
                )
            )
    return results


def print_summary(results: list[StatisticsResult]) -> None:
    print("source_id,metric,rows_written,warnings_count")
    for result in results:
        print(f"{result.source_id},{result.metric},{result.rows_written},{result.warnings_count}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compute deterministic statistical signals.")
    parser.add_argument("--normalized-dir", type=Path, default=NORMALIZED_DIR)
    parser.add_argument("--output-dir", type=Path, default=STATISTICS_DIR)
    parser.add_argument("--window", type=int, default=10)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
    results = run_statistics(
        normalized_dir=args.normalized_dir,
        output_dir=args.output_dir,
        window=args.window,
    )
    print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
