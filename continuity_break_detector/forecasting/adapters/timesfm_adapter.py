from __future__ import annotations

import os
from dataclasses import dataclass, field

import pandas as pd

from continuity_break_detector.forecasting.base import ForecasterAvailability, ForecastingError
from continuity_break_detector.forecasting.subprocess_client import (
    run_worker_forecast,
    smoke_test_worker,
    timesfm_python,
    timesfm_worker_path,
    timeout_seconds,
)


@dataclass
class TimesFMAdapter:
    forecaster_id: str = "timesfm"
    display_name: str = "TimesFM"
    _availability: ForecasterAvailability | None = field(default=None, init=False, repr=False)
    _forecast_count: int = field(default=0, init=False, repr=False)

    def availability(self) -> ForecasterAvailability:
        if self._availability is not None:
            return self._availability
        python_executable = timesfm_python()
        worker_path = timesfm_worker_path()
        if not python_executable.exists():
            self._availability = ForecasterAvailability(
                self.forecaster_id,
                self.display_name,
                False,
                f"subprocess Python executable does not exist: {python_executable}",
                str(python_executable),
            )
            return self._availability
        if not worker_path.exists():
            self._availability = ForecasterAvailability(
                self.forecaster_id,
                self.display_name,
                False,
                f"worker script does not exist: {worker_path}",
                str(python_executable),
            )
            return self._availability
        available, reason = smoke_test_worker(
            python_executable=python_executable,
            worker_path=worker_path,
            model=self.forecaster_id,
            params=_timesfm_params(2, smoke=True),
        )
        self._availability = ForecasterAvailability(
            self.forecaster_id,
            self.display_name,
            available,
            f"subprocess: {reason}",
            str(python_executable),
        )
        return self._availability

    def forecast(self, series: pd.Series, horizon: int) -> list[float]:
        _enforce_optional_forecast_limit(self.forecaster_id, self._forecast_count)
        values = series.astype(float).to_numpy(copy=True)
        if len(values) == 0:
            raise ForecastingError("timesfm received an empty series")
        result = run_worker_forecast(
            python_executable=timesfm_python(),
            worker_path=timesfm_worker_path(),
            model=self.forecaster_id,
            series=[float(value) for value in values.tolist()],
            horizon=horizon,
            params=_timesfm_params(horizon),
            timeout=timeout_seconds(),
        )
        self._forecast_count += 1
        return result.forecast


def _timesfm_params(horizon: int, *, smoke: bool = False) -> dict[str, object]:
    return {
        "model_id": "google/timesfm-2.5-200m-pytorch",
        "local_files_only": True,
        "torch_compile": False,
        "max_context": 64 if smoke else 1024,
        "max_horizon": max(2, int(horizon)),
        "normalize_inputs": True,
        "use_continuous_quantile_head": True,
        "force_flip_invariance": True,
        "infer_is_positive": True,
        "fix_quantile_crossing": True,
        "frequency": "yearly",
    }


def _enforce_optional_forecast_limit(forecaster_id: str, completed_count: int) -> None:
    raw_limit = os.environ.get("CBD_OPTIONAL_FORECAST_LIMIT")
    if not raw_limit:
        return
    limit = int(raw_limit)
    if completed_count >= limit:
        raise ForecastingError(f"{forecaster_id} optional forecast limit reached: {limit}")

