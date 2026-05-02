from __future__ import annotations

import importlib.metadata
import json
import platform
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from continuity_break_detector.backtesting.anomalies import build_anomalies
from continuity_break_detector.backtesting.domains import build_cross_domain_breaks
from continuity_break_detector.backtesting.engine import backtest_metric
from continuity_break_detector.backtesting.models import MODEL_NAMES
from continuity_break_detector.storage.parquet import read_parquet, write_parquet
from continuity_break_detector.utils.paths import PROJECT_ROOT, ensure_directory

NORMALIZED_DIR = PROJECT_ROOT / "data" / "processed" / "normalized"
STUDIES_DIR = PROJECT_ROOT / "studies" / "backtests"


@dataclass(frozen=True)
class BacktestParameters:
    train_window_years: int = 20
    forecast_horizon_years: int = 5
    minimum_series_length: int = 30
    anomaly_window: int = 10
    anomaly_threshold: float = 2.5

    def to_dict(self) -> dict[str, int | float]:
        return {
            "train_window_years": self.train_window_years,
            "forecast_horizon_years": self.forecast_horizon_years,
            "minimum_series_length": self.minimum_series_length,
            "anomaly_window": self.anomaly_window,
            "anomaly_threshold": self.anomaly_threshold,
        }


@dataclass(frozen=True)
class StudyResult:
    study_id: str
    output_dir: Path
    metrics_processed: int
    forecast_error_rows: int
    anomaly_rows: int
    cross_domain_break_rows: int


def run_backtest_study(
    *,
    input_dir: Path = NORMALIZED_DIR,
    studies_dir: Path = STUDIES_DIR,
    parameters: BacktestParameters | None = None,
) -> StudyResult:
    params = parameters or BacktestParameters()
    created_at = datetime.now(UTC)
    study_id = f"{created_at.strftime('%Y%m%d_%H%M%S')}_rapid_influx_v1"
    output_dir = ensure_directory(studies_dir / study_id)

    metric_frames: list[pd.DataFrame] = []
    metrics_processed = 0
    for path in normalized_metric_paths(input_dir):
        normalized = read_parquet(path)
        errors = backtest_metric(
            normalized,
            train_window_years=params.train_window_years,
            forecast_horizon_years=params.forecast_horizon_years,
            minimum_series_length=params.minimum_series_length,
        )
        if not errors.empty:
            metric_frames.append(errors)
            metrics_processed += 1

    forecast_errors = (
        pd.concat(metric_frames, ignore_index=True)
        if metric_frames
        else pd.DataFrame(
            columns=[
                "source_id",
                "metric",
                "entity",
                "model",
                "cutoff_year",
                "target_year",
                "horizon",
                "actual",
                "predicted",
                "absolute_error",
                "relative_error",
                "squared_error",
            ]
        )
    )
    anomalies = build_anomalies(
        forecast_errors,
        window=params.anomaly_window,
        threshold=params.anomaly_threshold,
    )
    cross_domain_breaks = build_cross_domain_breaks(anomalies)

    write_parquet(forecast_errors, output_dir / "forecast_errors.parquet")
    write_parquet(anomalies, output_dir / "anomalies.parquet")
    write_parquet(cross_domain_breaks, output_dir / "cross_domain_breaks.parquet")

    top_breaks = top_cross_domain_breaks(cross_domain_breaks)
    summary = build_summary(
        study_id=study_id,
        created_at=created_at,
        input_dir=input_dir,
        parameters=params,
        metrics_processed=metrics_processed,
        forecast_error_rows=len(forecast_errors),
        anomaly_rows=len(anomalies),
        cross_domain_break_rows=len(cross_domain_breaks),
        top_breaks=top_breaks,
    )
    write_json(output_dir / "summary.json", summary)
    write_json(
        output_dir / "provenance.json",
        build_provenance(
            created_at=created_at,
            input_dir=input_dir,
            output_dir=output_dir,
            parameters=params,
        ),
    )
    (output_dir / "study.md").write_text(
        build_markdown_report(summary, top_breaks),
        encoding="utf-8",
    )

    return StudyResult(
        study_id=study_id,
        output_dir=output_dir,
        metrics_processed=metrics_processed,
        forecast_error_rows=len(forecast_errors),
        anomaly_rows=len(anomalies),
        cross_domain_break_rows=len(cross_domain_breaks),
    )


def normalized_metric_paths(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        return []
    return sorted(input_dir.glob("*/*.parquet"))


def top_cross_domain_breaks(df: pd.DataFrame, *, limit: int = 10) -> list[dict[str, Any]]:
    if df.empty:
        return []
    ordered = df.sort_values(
        ["affected_domain_count", "aggregate_score", "anomaly_count"],
        ascending=[False, False, False],
    ).head(limit)
    return [_json_safe_record(record) for record in ordered.to_dict("records")]


def build_summary(
    *,
    study_id: str,
    created_at: datetime,
    input_dir: Path,
    parameters: BacktestParameters,
    metrics_processed: int,
    forecast_error_rows: int,
    anomaly_rows: int,
    cross_domain_break_rows: int,
    top_breaks: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "study_id": study_id,
        "created_at": created_at.isoformat(),
        "input_path": str(input_dir),
        "models": list(MODEL_NAMES),
        "parameters": parameters.to_dict(),
        "metrics_processed": metrics_processed,
        "forecast_error_rows": forecast_error_rows,
        "anomaly_rows": anomaly_rows,
        "cross_domain_break_rows": cross_domain_break_rows,
        "top_cross_domain_breaks": top_breaks,
    }


def build_provenance(
    *,
    created_at: datetime,
    input_dir: Path,
    output_dir: Path,
    parameters: BacktestParameters,
) -> dict[str, Any]:
    return {
        "created_at": created_at.isoformat(),
        "git_commit": git_commit_hash(),
        "input_directories": [str(input_dir)],
        "output_directory": str(output_dir),
        "parameters": parameters.to_dict(),
        "python_version": platform.python_version(),
        "package_versions": package_versions(["numpy", "pandas", "pyarrow"]),
    }


def build_markdown_report(summary: dict[str, Any], top_breaks: list[dict[str, Any]]) -> str:
    parameters = summary["parameters"]
    top_lines = [
        (
            f"- {item['target_year']}: domains={item['affected_domains']}, "
            f"anomalies={item['anomaly_count']}, aggregate_score={item['aggregate_score']:.3f}"
        )
        for item in top_breaks[:10]
    ]
    if not top_lines:
        top_lines = ["- No cross-domain break candidates met the anomaly threshold."]

    return "\n".join(
        [
            "# Continuity Break Backtest Study",
            "",
            "## Objective",
            "Identify historical periods where future yearly values became difficult to predict from prior observations using deterministic baseline models.",
            "",
            "## Method",
            "The study uses rolling historical windows over normalized yearly time series. For each cutoff year, models are trained on prior data and evaluated against observed future values.",
            "",
            "## Models",
            "- naive_last_value",
            "- linear_trend",
            "- exponential_trend",
            "",
            "## Parameters",
            f"- train_window_years: {parameters['train_window_years']}",
            f"- forecast_horizon_years: {parameters['forecast_horizon_years']}",
            f"- minimum_series_length: {parameters['minimum_series_length']}",
            f"- anomaly_window: {parameters['anomaly_window']}",
            f"- anomaly_threshold: {parameters['anomaly_threshold']}",
            "",
            "## Data Sources Processed",
            f"- metrics_processed: {summary['metrics_processed']}",
            f"- forecast_error_rows: {summary['forecast_error_rows']}",
            f"- anomaly_rows: {summary['anomaly_rows']}",
            f"- cross_domain_break_rows: {summary['cross_domain_break_rows']}",
            "",
            "## Main Findings",
            "Forecast-error anomalies identify years where simple deterministic historical baselines had unusually large errors compared with nearby prior errors.",
            "",
            "## Top Cross-Domain Break Candidates",
            *top_lines,
            "",
            "## Limitations",
            "These baselines are intentionally simple. Sparse series, reporting revisions, metric definitions, and source-specific coverage can affect forecast errors.",
            "",
            "## Conclusion",
            "This study reports statistical discontinuity candidates only. It does not claim simulation results, proof of rapid influx, or causal interpretation.",
            "",
        ]
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def git_commit_hash() -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def package_versions(names: list[str]) -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for name in names:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return versions


def _json_safe_record(record: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, np_generic_types()):
            safe[key] = value.item()
        else:
            safe[key] = value
    return safe


def np_generic_types() -> tuple[type[Any], ...]:
    import numpy as np

    return (np.generic,)
