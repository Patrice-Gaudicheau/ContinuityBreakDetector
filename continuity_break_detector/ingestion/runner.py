from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

from continuity_break_detector.sources.base import RawStorage
from continuity_break_detector.sources.registry import build_registry

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class IngestionSummary:
    source_id: str
    status: str
    files_written: int
    error: str | None = None


def run_ingestion(*, raw_dir: Path | None = None) -> list[IngestionSummary]:
    registry = build_registry()
    storage = RawStorage(raw_dir=raw_dir) if raw_dir is not None else RawStorage()
    summaries: list[IngestionSummary] = []

    for source_id, connector in registry.implemented.items():
        try:
            written_count = 0
            for raw_fetch in connector.iter_fetches():
                stored = storage.write(raw_fetch)
                written_count += 2
                LOGGER.info("Wrote %s and %s", stored.raw_file, stored.metadata_file)
            summaries.append(
                IngestionSummary(
                    source_id=source_id,
                    status="ok",
                    files_written=written_count,
                )
            )
        except Exception as exc:
            LOGGER.exception("Ingestion failed for %s", source_id)
            summaries.append(
                IngestionSummary(
                    source_id=source_id,
                    status="error",
                    files_written=0,
                    error=str(exc),
                )
            )
    return summaries


def print_summary(summaries: list[IngestionSummary]) -> None:
    print("source_id,status,files_written")
    for summary in summaries:
        suffix = f",{summary.error}" if summary.error else ""
        print(f"{summary.source_id},{summary.status},{summary.files_written}{suffix}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run raw source ingestion.")
    parser.add_argument("--raw-dir", type=Path, default=None)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(levelname)s %(name)s: %(message)s",
    )
    summaries = run_ingestion(raw_dir=args.raw_dir)
    print_summary(summaries)
    return 1 if any(summary.status != "ok" for summary in summaries) else 0


if __name__ == "__main__":
    raise SystemExit(main())
