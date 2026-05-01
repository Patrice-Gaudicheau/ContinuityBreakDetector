from __future__ import annotations

import logging
from collections.abc import Sequence

import numpy as np
import pandas as pd

from continuity_break_detector.forecasting.base import ForecasterAdapter, ForecastingError
from continuity_break_detector.forecasting.registry import deterministic_forecaster_ids


logger = logging.getLogger(__name__)

FORECAST_ERROR_COLUMNS = [
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


def backtest_metric(
    df: pd.DataFrame,
    *,
    train_window_years: int = 20,
    forecast_horizon_years: int = 5,
    minimum_series_length: int = 30,
    forecasters: Sequence[ForecasterAdapter] | None = None,
    disabled_forecasters: set[str] | None = None,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if df.empty:
        return pd.DataFrame(columns=FORECAST_ERROR_COLUMNS)

    disabled = disabled_forecasters if disabled_forecasters is not None else set()
    group_columns = ["source_id", "metric", "entity"]
    for (_source_id, _metric, _entity), group in df.groupby(group_columns, dropna=False):
        series = (
            group[["source_id", "metric", "entity", "year", "value"]]
            .dropna(subset=["year", "value"])
            .sort_values("year")
            .drop_duplicates(subset=["year"], keep="last")
        )
        if len(series) < minimum_series_length:
            continue
        min_year = int(series["year"].min())
        max_year = int(series["year"].max())
        source_id = str(series["source_id"].iloc[0])
        metric = str(series["metric"].iloc[0])
        entity = series["entity"].iloc[0]
        values_by_year = {
            int(row["year"]): float(row["value"])
            for row in series[["year", "value"]].to_dict("records")
        }
        for cutoff_year in range(
            min_year + train_window_years - 1,
            max_year - forecast_horizon_years + 1,
        ):
            train_years = list(range(cutoff_year - train_window_years + 1, cutoff_year + 1))
            if any(year not in values_by_year for year in train_years):
                continue
            target_years = [
                year
                for year in range(cutoff_year + 1, cutoff_year + forecast_horizon_years + 1)
                if year in values_by_year
            ]
            if not target_years:
                continue
            train_values = np.array([values_by_year[year] for year in train_years], dtype=float)
            if forecasters is None:
                predictions_by_model = _predict_all_models(train_years, train_values, target_years)
            else:
                train_series = pd.Series(train_values, index=train_years, dtype=float)
                predictions_by_model = _predict_forecasters(
                    forecasters,
                    train_series,
                    target_years,
                    forecast_horizon_years,
                    disabled,
                )
            for model_name, predictions in predictions_by_model.items():
                for target_year in target_years:
                    if target_year not in predictions:
                        continue
                    actual = values_by_year[target_year]
                    predicted = predictions[target_year]
                    rows.append(
                        forecast_error_row(
                            source_id=source_id,
                            metric=metric,
                            entity=entity,
                            model=model_name,
                            cutoff_year=cutoff_year,
                            target_year=target_year,
                            actual=actual,
                            predicted=predicted,
                        )
                    )
    return pd.DataFrame(rows, columns=FORECAST_ERROR_COLUMNS)


def _predict_forecasters(
    forecasters: Sequence[ForecasterAdapter],
    train_series: pd.Series,
    target_years: list[int],
    horizon: int,
    disabled_forecasters: set[str],
) -> dict[str, dict[int, float]]:
    predictions: dict[str, dict[int, float]] = {}
    forecast_years = list(range(int(train_series.index[-1]) + 1, int(train_series.index[-1]) + horizon + 1))
    for forecaster in forecasters:
        if forecaster.forecaster_id in disabled_forecasters:
            continue
        try:
            values = forecaster.forecast(train_series, horizon)
        except ForecastingError as exc:
            if forecaster.forecaster_id in deterministic_forecaster_ids():
                continue
            logger.warning(
                "Disabling forecaster %s after forecast failure: %s",
                forecaster.forecaster_id,
                exc,
            )
            disabled_forecasters.add(forecaster.forecaster_id)
            continue
        predictions[forecaster.forecaster_id] = {
            year: float(value)
            for year, value in zip(forecast_years, values, strict=False)
            if year in target_years
        }
    return predictions


def _predict_all_models(
    train_years: list[int],
    train_values: np.ndarray,
    target_years: list[int],
) -> dict[str, dict[int, float]]:
    target_array = np.array(target_years, dtype=float)
    predictions: dict[str, dict[int, float]] = {
        "naive_last_value": {year: float(train_values[-1]) for year in target_years}
    }

    slope, intercept = np.polyfit(np.array(train_years, dtype=float), train_values, deg=1)
    linear_values = slope * target_array + intercept
    predictions["linear_trend"] = {
        year: float(value) for year, value in zip(target_years, linear_values, strict=False)
    }

    if np.all(train_values > 0):
        exp_slope, exp_intercept = np.polyfit(
            np.array(train_years, dtype=float),
            np.log(train_values),
            deg=1,
        )
        exp_values = np.exp(exp_slope * target_array + exp_intercept)
        predictions["exponential_trend"] = {
            year: float(value) for year, value in zip(target_years, exp_values, strict=False)
        }
    return predictions


def forecast_error_row(
    *,
    source_id: str,
    metric: str,
    entity: object,
    model: str,
    cutoff_year: int,
    target_year: int,
    actual: float,
    predicted: float,
) -> dict[str, object]:
    absolute_error = abs(actual - predicted)
    relative_error = None if actual == 0 else absolute_error / abs(actual)
    return {
        "source_id": source_id,
        "metric": metric,
        "entity": None if pd.isna(entity) else entity,
        "model": model,
        "cutoff_year": int(cutoff_year),
        "target_year": int(target_year),
        "horizon": int(target_year - cutoff_year),
        "actual": float(actual),
        "predicted": float(predicted),
        "absolute_error": float(absolute_error),
        "relative_error": None if relative_error is None else float(relative_error),
        "squared_error": float(np.square(actual - predicted)),
    }
