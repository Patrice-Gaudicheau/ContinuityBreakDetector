from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import pandas as pd

from continuity_break_detector.config import ROLLING_STATISTICS_WINDOW
from continuity_break_detector.forecast_client import ForecastResult
from continuity_break_detector.series_prediction import (
    SeriesInput,
    SeriesPredictionError,
    predict_series_with_worker,
)
from continuity_break_detector.statistics.breaks import detect_break_candidates


@dataclass(frozen=True)
class BreakAnalysisResult:
    worker: str
    series_input: SeriesInput
    prediction: ForecastResult
    analysis: dict[str, Any]


def analyze_series_with_forecast(
    worker: str,
    series: list[float],
    horizon: int,
    *,
    timeout_seconds: float = 120.0,
) -> BreakAnalysisResult:
    prediction = predict_series_with_worker(
        worker,
        series,
        horizon,
        timeout_seconds=timeout_seconds,
    )
    if not prediction.succeeded:
        raise SeriesPredictionError("worker_error", prediction.error or "worker prediction failed")
    forecast = validate_forecast(prediction.forecast)
    if not forecast:
        raise SeriesPredictionError("worker_error", "worker forecast must not be empty")
    series_input = SeriesInput(series=series, metadata={})
    analysis = analyze_combined_series(series, forecast)
    return BreakAnalysisResult(
        worker=worker,
        series_input=series_input,
        prediction=prediction,
        analysis=analysis,
    )


def analyze_prediction_result(
    *,
    worker: str,
    series_input: SeriesInput,
    prediction: ForecastResult,
) -> BreakAnalysisResult:
    if not prediction.succeeded:
        raise SeriesPredictionError("worker_error", prediction.error or "worker prediction failed")
    forecast = validate_forecast(prediction.forecast)
    if not forecast:
        raise SeriesPredictionError("worker_error", "worker forecast must not be empty")
    return BreakAnalysisResult(
        worker=worker,
        series_input=series_input,
        prediction=prediction,
        analysis=analyze_combined_series(series_input.series, forecast),
    )


def analyze_combined_series(series: list[float], forecast: list[float]) -> dict[str, Any]:
    combined = [*series, *forecast]
    window = analysis_window(len(combined))
    candidates = detect_break_candidates(combined_series_frame(combined), window=window)
    if candidates.empty:
        return {
            "combined_points": len(combined),
            "break_detected": False,
            "score": 0.0,
            "details": {
                "method": "statistics.breaks.detect_break_candidates",
                "series": "historical_plus_forecast",
                "window": window,
                "candidate_count": 0,
                "max_break_index": None,
            },
        }
    top = candidates.sort_values("break_score", ascending=False).iloc[0]
    score = float(top["break_score"])
    return {
        "combined_points": len(combined),
        "break_detected": score > 1.0,
        "score": score,
        "details": {
            "method": "statistics.breaks.detect_break_candidates",
            "series": "historical_plus_forecast",
            "window": window,
            "candidate_count": int(len(candidates)),
            "max_break_index": int(top["year"]),
        },
    }


def combined_series_frame(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_id": ["ml_pipeline"] * len(values),
            "metric": ["series"] * len(values),
            "year": list(range(len(values))),
            "value": values,
            "unit": [None] * len(values),
            "entity": [None] * len(values),
        }
    )


def analysis_window(point_count: int) -> int:
    if point_count < 4:
        return 2
    return max(2, min(ROLLING_STATISTICS_WINDOW, point_count // 2 - 1))


def validate_forecast(forecast: list[float]) -> list[float]:
    validated: list[float] = []
    for index, value in enumerate(forecast):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise SeriesPredictionError("worker_error", f"forecast[{index}] must be a finite number")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise SeriesPredictionError("worker_error", f"forecast[{index}] must be a finite number")
        validated.append(numeric)
    return validated
