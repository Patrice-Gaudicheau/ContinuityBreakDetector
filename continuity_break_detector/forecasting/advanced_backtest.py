from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from continuity_break_detector.backtesting.anomalies import build_anomalies
from continuity_break_detector.backtesting.domains import build_cross_domain_breaks
from continuity_break_detector.backtesting.engine import FORECAST_ERROR_COLUMNS, backtest_metric
from continuity_break_detector.backtesting.study import (
    BacktestParameters,
    NORMALIZED_DIR,
    STUDIES_DIR,
    build_provenance,
    normalized_metric_paths,
    top_cross_domain_breaks,
)
from continuity_break_detector.forecasting.base import ForecasterAvailability
from continuity_break_detector.forecasting.registry import build_forecaster_registry
from continuity_break_detector.storage.parquet import read_parquet, write_parquet
from continuity_break_detector.utils.paths import ensure_directory


MODEL_COMPARISON_COLUMNS = [
    "model",
    "metric",
    "mae",
    "rmse",
    "median_absolute_error",
    "anomaly_count",
    "extreme_anomaly_count",
]


@dataclass(frozen=True)
class AdvancedStudyResult:
    study_id: str
    output_dir: Path
    metrics_processed: int
    forecast_error_rows: int
    anomaly_rows: int
    cross_domain_break_rows: int
    models_run: list[str]


def run_advanced_backtest_study(
    *,
    input_dir: Path = NORMALIZED_DIR,
    studies_dir: Path = STUDIES_DIR,
    parameters: BacktestParameters | None = None,
) -> AdvancedStudyResult:
    params = parameters or BacktestParameters()
    registry = build_forecaster_registry()
    availability = registry.availability()
    forecasters = registry.runnable_forecasters()
    created_at = datetime.now(UTC)
    study_id = f"{created_at.strftime('%Y%m%d_%H%M%S')}_rapid_influx_advanced_v1"
    output_dir = ensure_directory(studies_dir / study_id)

    metric_frames: list[pd.DataFrame] = []
    metrics_processed = 0
    disabled_forecasters: set[str] = set()
    for path in normalized_metric_paths(input_dir):
        normalized = read_parquet(path)
        errors = backtest_metric(
            normalized,
            train_window_years=params.train_window_years,
            forecast_horizon_years=params.forecast_horizon_years,
            minimum_series_length=params.minimum_series_length,
            forecasters=forecasters,
            disabled_forecasters=disabled_forecasters,
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
        window=params.anomaly_window,
        threshold=params.anomaly_threshold,
    )
    cross_domain_breaks = build_cross_domain_breaks(anomalies)
    model_comparison = build_model_comparison(forecast_errors, anomalies)

    write_parquet(forecast_errors, output_dir / "forecast_errors.parquet")
    write_parquet(anomalies, output_dir / "anomalies.parquet")
    write_parquet(cross_domain_breaks, output_dir / "cross_domain_breaks.parquet")
    write_parquet(model_comparison, output_dir / "model_comparison.parquet")

    top_breaks = top_cross_domain_breaks(cross_domain_breaks)
    models_run = sorted(forecast_errors["model"].dropna().astype(str).unique().tolist())
    summary = build_advanced_summary(
        study_id=study_id,
        created_at=created_at,
        input_dir=input_dir,
        parameters=params,
        metrics_processed=metrics_processed,
        forecast_error_rows=len(forecast_errors),
        anomaly_rows=len(anomalies),
        cross_domain_break_rows=len(cross_domain_breaks),
        model_comparison_rows=len(model_comparison),
        top_breaks=top_breaks,
        availability=availability,
        models_run=models_run,
    )
    write_json(output_dir / "summary.json", summary)
    provenance = build_provenance(
        created_at=created_at,
        input_dir=input_dir,
        output_dir=output_dir,
        parameters=params,
    )
    provenance["forecaster_availability"] = [availability_record(item) for item in availability]
    provenance["forecaster_execution"] = forecaster_execution(availability)
    provenance["models_run"] = models_run
    write_json(output_dir / "provenance.json", provenance)
    (output_dir / "study.md").write_text(
        build_advanced_markdown_report(summary, top_breaks),
        encoding="utf-8",
    )

    return AdvancedStudyResult(
        study_id=study_id,
        output_dir=output_dir,
        metrics_processed=metrics_processed,
        forecast_error_rows=len(forecast_errors),
        anomaly_rows=len(anomalies),
        cross_domain_break_rows=len(cross_domain_breaks),
        models_run=models_run,
    )


def build_model_comparison(
    forecast_errors: pd.DataFrame,
    anomalies: pd.DataFrame,
) -> pd.DataFrame:
    if forecast_errors.empty:
        return pd.DataFrame(columns=MODEL_COMPARISON_COLUMNS)
    rows: list[dict[str, object]] = []
    anomaly_counts = (
        anomalies.groupby(["model", "metric"], dropna=False).size().to_dict()
        if not anomalies.empty
        else {}
    )
    extreme_counts = (
        anomalies[anomalies["severity"] == "extreme"]
        .groupby(["model", "metric"], dropna=False)
        .size()
        .to_dict()
        if not anomalies.empty
        else {}
    )
    for (model, metric), group in forecast_errors.groupby(["model", "metric"], dropna=False):
        squared = group["squared_error"].astype(float)
        absolute = group["absolute_error"].astype(float)
        key = (model, metric)
        rows.append({
            "model": model,
            "metric": metric,
            "mae": float(absolute.mean()),
            "rmse": float(np.sqrt(squared.mean())),
            "median_absolute_error": float(absolute.median()),
            "anomaly_count": int(anomaly_counts.get(key, 0)),
            "extreme_anomaly_count": int(extreme_counts.get(key, 0)),
        })
    return pd.DataFrame(rows, columns=MODEL_COMPARISON_COLUMNS)


def build_advanced_summary(
    *,
    study_id: str,
    created_at: datetime,
    input_dir: Path,
    parameters: BacktestParameters,
    metrics_processed: int,
    forecast_error_rows: int,
    anomaly_rows: int,
    cross_domain_break_rows: int,
    model_comparison_rows: int,
    top_breaks: list[dict[str, Any]],
    availability: list[ForecasterAvailability],
    models_run: list[str],
) -> dict[str, Any]:
    return {
        "study_id": study_id,
        "created_at": created_at.isoformat(),
        "input_path": str(input_dir),
        "models": models_run,
        "forecaster_availability": [availability_record(item) for item in availability],
        "forecaster_execution": forecaster_execution(availability),
        "parameters": parameters.to_dict(),
        "metrics_processed": metrics_processed,
        "forecast_error_rows": forecast_error_rows,
        "anomaly_rows": anomaly_rows,
        "cross_domain_break_rows": cross_domain_break_rows,
        "model_comparison_rows": model_comparison_rows,
        "top_cross_domain_breaks": top_breaks,
    }


def build_advanced_markdown_report(
    summary: dict[str, Any],
    top_breaks: list[dict[str, Any]],
) -> str:
    parameters = summary["parameters"]
    model_lines = [f"- {model}" for model in summary["models"]]
    if not model_lines:
        model_lines = ["- No models produced forecast errors."]
    availability_lines = [
        (
            f"- {item['forecaster_id']}: "
            f"{'available' if item['available'] else 'unavailable'}"
            f" ({item['reason']})"
        )
        for item in summary["forecaster_availability"]
    ]
    top_lines = [
        (
            f"- {item['target_year']}: domains={item['affected_domains']}, "
            f"anomalies={item['anomaly_count']}, aggregate_score={item['aggregate_score']:.3f}"
        )
        for item in top_breaks[:10]
    ] or ["- No cross-domain break candidates met the anomaly threshold."]

    return "\n".join([
        "# Advanced Continuity Break Backtest Study",
        "",
        "## Objective",
        "Compare deterministic baselines with optional local advanced forecasters on normalized yearly time series.",
        "",
        "## Method",
        "The study reuses the rolling historical backtest pipeline and plugs available forecaster adapters into the same forecast-error evaluation.",
        "",
        "## Models Run",
        *model_lines,
        "",
        "## Forecaster Availability",
        *availability_lines,
        "",
        "## Parameters",
        f"- train_window_years: {parameters['train_window_years']}",
        f"- forecast_horizon_years: {parameters['forecast_horizon_years']}",
        f"- minimum_series_length: {parameters['minimum_series_length']}",
        f"- anomaly_window: {parameters['anomaly_window']}",
        f"- anomaly_threshold: {parameters['anomaly_threshold']}",
        "",
        "## Outputs",
        f"- metrics_processed: {summary['metrics_processed']}",
        f"- forecast_error_rows: {summary['forecast_error_rows']}",
        f"- anomaly_rows: {summary['anomaly_rows']}",
        f"- cross_domain_break_rows: {summary['cross_domain_break_rows']}",
        f"- model_comparison_rows: {summary['model_comparison_rows']}",
        "",
        "## Top Cross-Domain Break Candidates",
        *top_lines,
        "",
        "## Limitations",
        "TimesFM and Chronos are optional local integrations. If an adapter imports but cannot produce a forecast with the available local checkout, the run continues with remaining models.",
        "",
        "## Conclusion",
        "This study reports forecast-error behavior only. It does not add interpretation, simulation claims, or causal conclusions.",
        "",
    ])


def availability_record(availability: ForecasterAvailability) -> dict[str, Any]:
    return {
        "forecaster_id": availability.forecaster_id,
        "display_name": availability.display_name,
        "available": availability.available,
        "reason": availability.reason,
        "source_path": availability.source_path,
    }


def forecaster_execution(availability: list[ForecasterAvailability]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for status in availability:
        if status.forecaster_id not in {"timesfm", "chronos"}:
            continue
        records[status.forecaster_id] = {
            "mode": "subprocess",
            "python": status.source_path,
            "available": status.available,
            "reason": status.reason,
        }
    return records


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, ensure_ascii=False), encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value
