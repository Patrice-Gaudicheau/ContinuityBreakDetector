from __future__ import annotations

import numpy as np
import pandas as pd


def add_break_scores(df: pd.DataFrame, *, window: int = 10) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    frames: list[pd.DataFrame] = []
    group_columns = ["source_id", "metric", "entity"]
    for _keys, group in df.sort_values(group_columns + ["year"]).groupby(group_columns, dropna=False):
        enriched = group.copy()
        values = enriched["value"].astype(float).reset_index(drop=True)
        scores = [np.nan] * len(values)
        for index in range(window, len(values) - window + 1):
            before = values.iloc[index - window:index]
            after = values.iloc[index:index + window]
            before_mean = before.mean()
            after_mean = after.mean()
            pooled_std = pd.concat([before, after]).std(ddof=0)
            denominator = pooled_std if pooled_std and not np.isnan(pooled_std) else 1.0
            scores[index] = abs(after_mean - before_mean) / denominator
        enriched["break_score"] = scores
        frames.append(enriched)
    return pd.concat(frames, ignore_index=True)


def detect_break_candidates(df: pd.DataFrame, *, window: int = 10) -> pd.DataFrame:
    scored = add_break_scores(df, window=window)
    return scored[scored["break_score"].notna()].copy()

