from __future__ import annotations

import argparse
import re
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from continuity_break_detector.normalization import arxiv, crossref, openalex, owid, world_bank
from continuity_break_detector.normalization.models import NormalizationResult
from continuity_break_detector.storage.parquet import write_parquet
from continuity_break_detector.utils.logging import get_logger
from continuity_break_detector.utils.paths import PROJECT_ROOT, RAW_DATA_DIR

LOGGER = get_logger(__name__)
NORMALIZED_DIR = PROJECT_ROOT / "data" / "processed" / "normalized"
Normalizer = Callable[..., pd.DataFrame]
WarningCounter = Callable[[pd.DataFrame], int]


NORMALIZERS: dict[str, tuple[Normalizer, WarningCounter]] = {
    world_bank.SOURCE_ID: (world_bank.normalize, world_bank.log_missing_years),
    openalex.SOURCE_ID: (openalex.normalize, openalex.log_missing_years),
    arxiv.SOURCE_ID: (arxiv.normalize, arxiv.log_missing_years),
    crossref.SOURCE_ID: (crossref.normalize, crossref.log_missing_years),
    owid.SOURCE_ID: (owid.normalize, owid.log_missing_years),
}


def run_normalization(
    *,
    raw_dir: Path = RAW_DATA_DIR,
    output_dir: Path = NORMALIZED_DIR,
    interpolate: bool = False,
) -> list[NormalizationResult]:
    results: list[NormalizationResult] = []
    for source_id, (normalizer, warning_counter) in NORMALIZERS.items():
        df = normalizer(raw_dir, interpolate=interpolate)
        if df.empty:
            LOGGER.warning("No normalized rows for %s", source_id)
            continue
        for metric, metric_df in df.groupby("metric", dropna=False):
            warnings_count = warning_counter(metric_df)
            output_path = output_dir / source_id / f"{safe_metric_filename(str(metric))}.parquet"
            write_parquet(metric_df.sort_values(["metric", "entity", "year"]), output_path)
            results.append(
                NormalizationResult(
                    source_id=source_id,
                    metric=str(metric),
                    rows_written=len(metric_df),
                    warnings_count=warnings_count,
                    path=output_path,
                )
            )
    return results


def print_summary(results: list[NormalizationResult]) -> None:
    LOGGER.info("source_id,metric,rows_written,warnings_count")
    for result in results:
        LOGGER.info(
            "%s,%s,%s,%s",
            result.source_id,
            result.metric,
            result.rows_written,
            result.warnings_count,
        )


def safe_metric_filename(metric: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", metric).strip("._") or "metric"


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize raw source payloads.")
    parser.add_argument("--raw-dir", type=Path, default=RAW_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=NORMALIZED_DIR)
    parser.add_argument("--interpolate", action="store_true")
    args = parser.parse_args()
    results = run_normalization(
        raw_dir=args.raw_dir,
        output_dir=args.output_dir,
        interpolate=args.interpolate,
    )
    print_summary(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
