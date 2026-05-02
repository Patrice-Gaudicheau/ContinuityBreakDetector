from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from continuity_break_detector.backtesting.anomalies import build_anomalies
from continuity_break_detector.backtesting.artifacts import detect_study_artifacts
from continuity_break_detector.backtesting.audit import audit_study
from continuity_break_detector.backtesting.domains import build_cross_domain_breaks
from continuity_break_detector.backtesting.engine import FORECAST_ERROR_COLUMNS, backtest_metric
from continuity_break_detector.backtesting.ranking import rank_study
from continuity_break_detector.backtesting.study import (
    BacktestParameters,
    build_markdown_report,
    build_provenance,
    build_summary,
    normalized_metric_paths,
    top_cross_domain_breaks,
    write_json,
)
from continuity_break_detector.statistics.runner import run_statistics
from continuity_break_detector.storage.parquet import read_parquet, write_parquet
from continuity_break_detector.utils.logging import get_logger
from continuity_break_detector.utils.paths import PROJECT_ROOT, ensure_directory

LOGGER = get_logger(__name__)

DEMO_RAW_DIR = PROJECT_ROOT / "examples" / "demo_raw"
DEMO_SOURCE_FILE = DEMO_RAW_DIR / "demo_indicators.csv"
DEMO_STUDY_DIR = PROJECT_ROOT / "studies" / "demo_study"

DEMO_METRICS = {
    "population": {
        "source_id": "world_bank_wdi",
        "metric": "SP.POP.TOTL",
        "unit": "people",
        "entity": "DEMO",
    },
    "gdp": {
        "source_id": "world_bank_wdi",
        "metric": "NY.GDP.MKTP.CD",
        "unit": "current US dollars",
        "entity": "DEMO",
    },
    "life_expectancy": {
        "source_id": "owid",
        "metric": "life-expectancy:Life expectancy",
        "unit": "years",
        "entity": "DEMO",
    },
}


@dataclass(frozen=True)
class DemoStudyResult:
    study_path: Path
    normalized_files: int
    statistics_files: int
    forecast_error_rows: int
    ranked_candidates: int
    audited_candidates: int
    artifact_candidates: int


def run_demo_study() -> DemoStudyResult:
    if not DEMO_SOURCE_FILE.exists():
        raise FileNotFoundError(f"Demo fixture is missing: {DEMO_SOURCE_FILE}")

    if DEMO_STUDY_DIR.exists():
        shutil.rmtree(DEMO_STUDY_DIR)
    ensure_directory(DEMO_STUDY_DIR)

    raw_path = ingest_demo_fixture()
    normalized_files = normalize_demo_fixture(raw_path)
    statistics = run_statistics(
        normalized_dir=DEMO_STUDY_DIR / "normalized",
        output_dir=DEMO_STUDY_DIR / "statistics",
        window=5,
    )
    forecast_error_rows = run_demo_backtest()
    ranking = rank_study(DEMO_STUDY_DIR)
    audit = audit_study(DEMO_STUDY_DIR)
    artifacts = detect_study_artifacts(DEMO_STUDY_DIR)

    LOGGER.info("demo study path: %s", DEMO_STUDY_DIR)
    LOGGER.info("normalized files: %s", normalized_files)
    LOGGER.info("statistics files: %s", len(statistics))
    LOGGER.info("forecast error rows: %s", forecast_error_rows)
    LOGGER.info("ranked candidates: %s", ranking.all_candidates)
    LOGGER.info("audited candidates: %s", audit.candidate_count)
    LOGGER.info("artifact candidates: %s", artifacts.candidate_count)

    return DemoStudyResult(
        study_path=DEMO_STUDY_DIR,
        normalized_files=normalized_files,
        statistics_files=len(statistics),
        forecast_error_rows=forecast_error_rows,
        ranked_candidates=ranking.all_candidates,
        audited_candidates=audit.candidate_count,
        artifact_candidates=artifacts.candidate_count,
    )


def ingest_demo_fixture() -> Path:
    raw_dir = ensure_directory(DEMO_STUDY_DIR / "raw")
    output_path = raw_dir / DEMO_SOURCE_FILE.name
    shutil.copyfile(DEMO_SOURCE_FILE, output_path)
    metadata = {
        "source": "embedded demo fixture",
        "retrieved_at": datetime.now(UTC).isoformat(),
        "network_used": False,
        "raw_file": str(output_path),
    }
    write_json(raw_dir / "demo_ingestion_metadata.json", metadata)
    return output_path


def normalize_demo_fixture(raw_path: Path) -> int:
    source = pd.read_csv(raw_path)
    files_written = 0
    for column, spec in DEMO_METRICS.items():
        rows = [
            {
                "source_id": spec["source_id"],
                "metric": spec["metric"],
                "year": int(row["year"]),
                "value": float(row[column]),
                "unit": spec["unit"],
                "entity": spec["entity"],
            }
            for row in source[["year", column]].to_dict("records")
        ]
        normalized = pd.DataFrame(
            rows,
            columns=["source_id", "metric", "year", "value", "unit", "entity"],
        )
        output_path = (
            DEMO_STUDY_DIR
            / "normalized"
            / str(spec["source_id"])
            / f"{_safe_metric_name(str(spec['metric']))}.parquet"
        )
        write_parquet(normalized, output_path)
        files_written += 1
    return files_written


def run_demo_backtest() -> int:
    parameters = BacktestParameters(
        train_window_years=12,
        forecast_horizon_years=3,
        minimum_series_length=30,
        anomaly_window=5,
        anomaly_threshold=1.8,
    )
    created_at = datetime.now(UTC)
    metric_frames: list[pd.DataFrame] = []
    metrics_processed = 0
    input_dir = DEMO_STUDY_DIR / "normalized"
    for path in normalized_metric_paths(input_dir):
        normalized = read_parquet(path)
        errors = backtest_metric(
            normalized,
            train_window_years=parameters.train_window_years,
            forecast_horizon_years=parameters.forecast_horizon_years,
            minimum_series_length=parameters.minimum_series_length,
        )
        if not errors.empty:
            metric_frames.append(errors)
            metrics_processed += 1

    forecast_errors = (
        pd.concat(metric_frames, ignore_index=True)
        if metric_frames
        else pd.DataFrame(columns=FORECAST_ERROR_COLUMNS)
    )
    anomalies = build_anomalies(
        forecast_errors,
        window=parameters.anomaly_window,
        threshold=parameters.anomaly_threshold,
    )
    cross_domain_breaks = build_cross_domain_breaks(anomalies)

    write_parquet(forecast_errors, DEMO_STUDY_DIR / "forecast_errors.parquet")
    write_parquet(anomalies, DEMO_STUDY_DIR / "anomalies.parquet")
    write_parquet(cross_domain_breaks, DEMO_STUDY_DIR / "cross_domain_breaks.parquet")

    top_breaks = top_cross_domain_breaks(cross_domain_breaks)
    summary = build_summary(
        study_id="demo_study",
        created_at=created_at,
        input_dir=input_dir,
        parameters=parameters,
        metrics_processed=metrics_processed,
        forecast_error_rows=len(forecast_errors),
        anomaly_rows=len(anomalies),
        cross_domain_break_rows=len(cross_domain_breaks),
        top_breaks=top_breaks,
    )
    summary["demo"] = True
    summary["network_used"] = False
    write_json(DEMO_STUDY_DIR / "summary.json", summary)
    provenance = build_provenance(
        created_at=created_at,
        input_dir=input_dir,
        output_dir=DEMO_STUDY_DIR,
        parameters=parameters,
    )
    provenance["demo"] = True
    provenance["input_files"] = [str(DEMO_SOURCE_FILE)]
    write_json(DEMO_STUDY_DIR / "provenance.json", provenance)
    (DEMO_STUDY_DIR / "study.md").write_text(
        build_markdown_report(summary, top_breaks),
        encoding="utf-8",
    )
    write_json(DEMO_STUDY_DIR / "demo_manifest.json", build_demo_manifest(summary))
    return len(forecast_errors)


def build_demo_manifest(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "study_path": str(DEMO_STUDY_DIR),
        "fixture_path": str(DEMO_SOURCE_FILE),
        "network_used": False,
        "external_models_used": False,
        "outputs": [
            "normalized/",
            "statistics/",
            "forecast_errors.parquet",
            "ranked_break_candidates.json",
            "candidate_audit.json",
            "data_artifact_audit.json",
        ],
        "summary": summary,
    }


def _safe_metric_name(metric: str) -> str:
    return (
        metric.replace(":", "_")
        .replace("/", "_")
        .replace(" ", "_")
        .replace(".", "_")
        .replace("-", "_")
    )


def main() -> int:
    run_demo_study()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
