from __future__ import annotations

import numpy as np
import pandas as pd

ANOMALY_COLUMNS = [
    "source_id",
    "metric",
    "entity",
    "model",
    "target_year",
    "z_score",
    "absolute_error",
    "relative_error",
    "severity",
]


def build_anomalies(
    forecast_errors: pd.DataFrame,
    *,
    window: int = 10,
    threshold: float = 2.5,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if forecast_errors.empty:
        return pd.DataFrame(columns=ANOMALY_COLUMNS)

    group_columns = ["source_id", "metric", "model"]
    ordered_errors = forecast_errors.sort_values(
        ["source_id", "metric", "model", "target_year", "cutoff_year", "entity"],
        na_position="last",
    )
    for (_source_id, _metric, _model), group in ordered_errors.groupby(group_columns, dropna=False):
        errors = group["absolute_error"].astype(float)
        prior_mean = errors.shift(1).rolling(window=window, min_periods=window).mean()
        prior_std = errors.shift(1).rolling(window=window, min_periods=window).std(ddof=0)
        z_scores = (errors - prior_mean) / prior_std.replace(0, np.nan)
        for (_, row), z_score in zip(group.iterrows(), z_scores, strict=False):
            if pd.isna(z_score) or float(z_score) < threshold:
                continue
            rows.append(
                {
                    "source_id": row["source_id"],
                    "metric": row["metric"],
                    "entity": None if pd.isna(row["entity"]) else row["entity"],
                    "model": row["model"],
                    "target_year": int(row["target_year"]),
                    "z_score": float(z_score),
                    "absolute_error": float(row["absolute_error"]),
                    "relative_error": (
                        None if pd.isna(row["relative_error"]) else float(row["relative_error"])
                    ),
                    "severity": classify_severity(float(z_score)),
                }
            )
    return pd.DataFrame(rows, columns=ANOMALY_COLUMNS)


def classify_severity(z_score: float) -> str:
    if z_score >= 5.0:
        return "extreme"
    if z_score >= 3.5:
        return "high"
    return "medium"
