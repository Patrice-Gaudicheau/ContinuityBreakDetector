from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from continuity_break_detector.forecasting.availability import (
    DEFAULT_CHRONOS_LOCAL_PATH,
    ImportAttempt,
    import_with_local_fallback,
)
from continuity_break_detector.forecasting.base import (
    ForecasterAvailability,
    ForecastingError,
    ensure_forecast_length,
)


@dataclass
class ChronosAdapter:
    model: Any | None = None

    forecaster_id: str = "chronos"
    display_name: str = "Chronos"

    def availability(self) -> ForecasterAvailability:
        attempt = load_chronos_module()
        available = attempt.available
        reason = attempt.reason
        if attempt.available and attempt.module is not None:
            api_available = hasattr(attempt.module, "forecast") or hasattr(attempt.module, "predict")
            available = api_available
            if api_available:
                reason = f"{attempt.reason}; supported forecast API detected"
            else:
                reason = f"{attempt.reason}; no supported forecast API exposed"
        return ForecasterAvailability(
            self.forecaster_id,
            self.display_name,
            available,
            reason,
            attempt.source_path,
        )

    def forecast(self, series: pd.Series, horizon: int) -> list[float]:
        values = series.astype(float).to_numpy(copy=True)
        if len(values) == 0:
            raise ForecastingError("chronos received an empty series")
        model = self.model or _load_forecast_object()
        forecast_method = getattr(model, "forecast", None) or getattr(model, "predict", None)
        if forecast_method is None:
            raise ForecastingError("Chronos object does not expose forecast(...) or predict(...)")
        try:
            raw = forecast_method(values, horizon=horizon)
        except TypeError:
            raw = forecast_method(values, prediction_length=horizon)
        predictions = _coerce_chronos_output(raw, horizon)
        return ensure_forecast_length(predictions, horizon=horizon, forecaster_id=self.forecaster_id)


def load_chronos_module() -> ImportAttempt:
    return import_with_local_fallback(
        "chronos",
        env_var="CBD_CHRONOS_LOCAL_PATH",
        default_root=DEFAULT_CHRONOS_LOCAL_PATH,
        candidate_relative_paths=["src", "."],
    )


def _load_forecast_object() -> Any:
    attempt = load_chronos_module()
    if not attempt.available or attempt.module is None:
        raise ForecastingError(f"Chronos unavailable: {attempt.reason}")
    if hasattr(attempt.module, "forecast") or hasattr(attempt.module, "predict"):
        return attempt.module
    raise ForecastingError("Chronos module imported but no supported minimal forecast API was found")


def _coerce_chronos_output(raw: Any, horizon: int) -> list[float]:
    if isinstance(raw, tuple):
        raw = raw[0]
    array = np.asarray(raw, dtype=float)
    if array.ndim == 0:
        raise ForecastingError("Chronos returned a scalar forecast")
    if array.ndim == 1:
        values = array[:horizon]
    else:
        values = array.reshape(-1, array.shape[-1])[0, :horizon]
    return [float(value) for value in values.tolist()]
