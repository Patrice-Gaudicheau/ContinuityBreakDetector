from __future__ import annotations

from dataclasses import dataclass

from continuity_break_detector.forecasting.adapters.chronos_adapter import ChronosAdapter
from continuity_break_detector.forecasting.adapters.deterministic_adapter import (
    deterministic_adapters,
)
from continuity_break_detector.forecasting.adapters.timesfm_adapter import TimesFMAdapter
from continuity_break_detector.forecasting.base import ForecasterAdapter, ForecasterAvailability


@dataclass(frozen=True)
class ForecasterRegistry:
    forecasters: list[ForecasterAdapter]

    def availability(self) -> list[ForecasterAvailability]:
        return [forecaster.availability() for forecaster in self.forecasters]

    def runnable_forecasters(self) -> list[ForecasterAdapter]:
        runnable: list[ForecasterAdapter] = []
        for forecaster in self.forecasters:
            status = forecaster.availability()
            if status.available:
                runnable.append(forecaster)
        return runnable


def build_forecaster_registry() -> ForecasterRegistry:
    forecasters: list[ForecasterAdapter] = []
    forecasters.extend(deterministic_adapters())
    forecasters.append(TimesFMAdapter())
    forecasters.append(ChronosAdapter())
    return ForecasterRegistry(forecasters)


def deterministic_forecaster_ids() -> set[str]:
    return {"naive_last_value", "linear_trend", "exponential_trend"}
