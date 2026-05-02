from __future__ import annotations

import numpy as np
import pandas as pd

MODEL_NAMES = ("naive_last_value", "linear_trend", "exponential_trend")


def naive_last_value(train: pd.DataFrame, target_years: list[int]) -> dict[int, float]:
    if train.empty:
        return {}
    last_value = float(train.sort_values("year")["value"].iloc[-1])
    return {year: last_value for year in target_years}


def linear_trend(train: pd.DataFrame, target_years: list[int]) -> dict[int, float]:
    if len(train) < 2:
        return {}
    ordered = train.sort_values("year")
    years = ordered["year"].to_numpy(dtype=float)
    values = ordered["value"].to_numpy(dtype=float)
    slope, intercept = np.polyfit(years, values, deg=1)
    return {year: float(slope * year + intercept) for year in target_years}


def exponential_trend(train: pd.DataFrame, target_years: list[int]) -> dict[int, float]:
    if len(train) < 2 or (train["value"] <= 0).any():
        return {}
    ordered = train.sort_values("year")
    years = ordered["year"].to_numpy(dtype=float)
    log_values = np.log(ordered["value"].to_numpy(dtype=float))
    slope, intercept = np.polyfit(years, log_values, deg=1)
    return {year: float(np.exp(slope * year + intercept)) for year in target_years}
