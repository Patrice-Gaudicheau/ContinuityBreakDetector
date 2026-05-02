from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from continuity_break_detector.forecasting.base import (
    ForecasterAvailability,
    ForecastingError,
    ensure_forecast_length,
)


@dataclass(frozen=True)
class DeterministicAdapter:
    forecaster_id: str
    display_name: str

    def availability(self) -> ForecasterAvailability:
        return ForecasterAvailability(
            self.forecaster_id,
            self.display_name,
            True,
            "deterministic baseline",
        )

    def forecast(self, series: pd.Series, horizon: int) -> list[float]:
        values = series.astype(float).to_numpy(copy=True)
        if len(values) == 0:
            raise ForecastingError(f"{self.forecaster_id} received an empty series")
        years = np.asarray(series.index, dtype=float)
        target_years = np.arange(int(years[-1]) + 1, int(years[-1]) + horizon + 1, dtype=float)
        if self.forecaster_id == "naive_last_value":
            predictions = [float(values[-1])] * horizon
        elif self.forecaster_id == "linear_trend":
            slope, intercept = np.polyfit(years, values, deg=1)
            predictions = [float(slope * year + intercept) for year in target_years]
        elif self.forecaster_id == "exponential_trend":
            if np.any(values <= 0):
                raise ForecastingError("exponential_trend requires strictly positive values")
            slope, intercept = np.polyfit(years, np.log(values), deg=1)
            predictions = [float(np.exp(slope * year + intercept)) for year in target_years]
        else:
            raise ForecastingError(f"unknown deterministic model: {self.forecaster_id}")
        return ensure_forecast_length(
            predictions,
            horizon=horizon,
            forecaster_id=self.forecaster_id,
        )


def deterministic_adapters() -> list[DeterministicAdapter]:
    return [
        DeterministicAdapter("naive_last_value", "naive_last_value"),
        DeterministicAdapter("linear_trend", "linear_trend"),
        DeterministicAdapter("exponential_trend", "exponential_trend"),
    ]
