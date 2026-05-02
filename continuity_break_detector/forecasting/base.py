from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import pandas as pd


class ForecastingError(RuntimeError):
    """Raised when a forecaster cannot produce a usable forecast."""


@dataclass(frozen=True)
class ForecasterAvailability:
    forecaster_id: str
    display_name: str
    available: bool
    reason: str
    source_path: str | None = None


class ForecasterAdapter(Protocol):
    @property
    def forecaster_id(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    def availability(self) -> ForecasterAvailability: ...

    def forecast(self, series: pd.Series, horizon: int) -> list[float]: ...


def ensure_forecast_length(
    values: list[float],
    *,
    horizon: int,
    forecaster_id: str,
) -> list[float]:
    if len(values) != horizon:
        raise ForecastingError(
            f"{forecaster_id} returned {len(values)} values for horizon {horizon}"
        )
    return [float(value) for value in values]
