from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from continuity_break_detector.forecasting.availability import (
    DEFAULT_TIMESFM_LOCAL_PATH,
    ImportAttempt,
    import_with_local_fallback,
)
from continuity_break_detector.forecasting.base import (
    ForecasterAvailability,
    ForecastingError,
    ensure_forecast_length,
)


@dataclass
class TimesFMAdapter:
    model: Any | None = None

    forecaster_id: str = "timesfm"
    display_name: str = "TimesFM"

    def availability(self) -> ForecasterAvailability:
        attempt = load_timesfm_module()
        available = attempt.available
        reason = attempt.reason
        if attempt.available and attempt.module is not None:
            api_available, api_reason = _timesfm_api_status(attempt.module)
            available = api_available
            reason = f"{attempt.reason}; {api_reason}"
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
            raise ForecastingError("timesfm received an empty series")
        model = self.model or _load_forecast_object()
        forecast_method = getattr(model, "forecast", None)
        if forecast_method is None:
            raise ForecastingError("TimesFM object does not expose forecast(...)")
        try:
            raw = forecast_method([values], freq=2)
        except TypeError:
            raw = forecast_method(input_series=[values], freq=2)
        predictions = _coerce_timesfm_output(raw, horizon)
        return ensure_forecast_length(predictions, horizon=horizon, forecaster_id=self.forecaster_id)


def load_timesfm_module() -> ImportAttempt:
    return import_with_local_fallback(
        "timesfm",
        env_var="CBD_TIMESFM_LOCAL_PATH",
        default_root=DEFAULT_TIMESFM_LOCAL_PATH,
        candidate_relative_paths=["src", "timesfm-forecasting", "."],
    )


def _load_forecast_object() -> Any:
    attempt = load_timesfm_module()
    if not attempt.available or attempt.module is None:
        raise ForecastingError(f"TimesFM unavailable: {attempt.reason}")
    if hasattr(attempt.module, "forecast"):
        return attempt.module
    timesfm_class = (
        getattr(attempt.module, "TimesFm", None)
        or getattr(attempt.module, "TimesFM", None)
        or getattr(attempt.module, "TimesFM_2p5_200M_torch", None)
        or getattr(attempt.module, "TimesFM_2p5_200M_flax", None)
    )
    if timesfm_class is None:
        raise ForecastingError("TimesFM module imported but no supported forecast API was found")
    try:
        return timesfm_class()
    except Exception as exc:
        raise ForecastingError(f"TimesFM model could not be initialized: {exc}") from exc


def _timesfm_api_status(module: Any) -> tuple[bool, str]:
    supported_names = [
        "forecast",
        "TimesFm",
        "TimesFM",
        "TimesFM_2p5_200M_torch",
        "TimesFM_2p5_200M_flax",
    ]
    if any(hasattr(module, name) for name in supported_names):
        return True, "supported forecast API detected"
    return (
        False,
        "TimesFM imported but no supported forecast API was exposed; "
        "local optional dependencies may be missing",
    )


def _coerce_timesfm_output(raw: Any, horizon: int) -> list[float]:
    if isinstance(raw, tuple):
        raw = raw[0]
    array = np.asarray(raw, dtype=float)
    if array.ndim == 0:
        raise ForecastingError("TimesFM returned a scalar forecast")
    if array.ndim == 1:
        values = array[:horizon]
    else:
        values = array[0, :horizon]
    return [float(value) for value in values.tolist()]
