from __future__ import annotations

import numpy as np
import pandas as pd

from continuity_break_detector.config import ROLLING_STATISTICS_WINDOW


def add_statistical_features(
    df: pd.DataFrame, *, window: int = ROLLING_STATISTICS_WINDOW
) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    frames: list[pd.DataFrame] = []
    group_columns = ["source_id", "metric", "entity"]
    for _keys, group in df.sort_values(group_columns + ["year"]).groupby(
        group_columns, dropna=False
    ):
        enriched = group.copy()
        previous = enriched["value"].shift(1)
        enriched["growth_rate"] = growth_rate(enriched["value"])
        enriched["log_growth"] = log_growth(enriched["value"])
        enriched["acceleration"] = enriched["growth_rate"] - enriched["growth_rate"].shift(1)
        rolling_mean = previous.rolling(window=window, min_periods=window).mean()
        rolling_std = previous.rolling(window=window, min_periods=window).std(ddof=0)
        enriched["rolling_z_score"] = (enriched["value"] - rolling_mean) / rolling_std.replace(
            0, np.nan
        )
        enriched["rolling_mean_deviation"] = enriched["value"] - rolling_mean
        frames.append(enriched)
    return pd.concat(frames, ignore_index=True)


def growth_rate(values: pd.Series) -> pd.Series:
    previous = values.shift(1)
    return (values - previous) / previous.replace(0, np.nan)


def log_growth(values: pd.Series) -> pd.Series:
    positive = values.where(values > 0)
    previous = positive.shift(1)
    return np.log(positive) - np.log(previous)
