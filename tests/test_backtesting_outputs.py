from __future__ import annotations

import pandas as pd

from continuity_break_detector.backtesting.anomalies import classify_severity
from continuity_break_detector.backtesting.domains import build_cross_domain_breaks
from continuity_break_detector.backtesting.engine import forecast_error_row


def test_forecast_error_computation() -> None:
    row = forecast_error_row(
        source_id="source",
        metric="metric",
        entity=None,
        model="naive_last_value",
        cutoff_year=2020,
        target_year=2022,
        actual=120.0,
        predicted=100.0,
    )

    assert row["horizon"] == 2
    assert row["absolute_error"] == 20.0
    assert round(float(row["relative_error"]), 6) == 0.166667
    assert row["squared_error"] == 400.0


def test_anomaly_severity_classification() -> None:
    assert classify_severity(2.5) == "medium"
    assert classify_severity(3.5) == "high"
    assert classify_severity(5.0) == "extreme"


def test_cross_domain_grouping() -> None:
    anomalies = pd.DataFrame(
        [
            {
                "source_id": "world_bank_wdi",
                "metric": "NY.GDP.MKTP.CD",
                "entity": "USA",
                "model": "linear_trend",
                "target_year": 2020,
                "z_score": 3.0,
                "absolute_error": 1.0,
                "relative_error": 0.1,
                "severity": "medium",
            },
            {
                "source_id": "openalex",
                "metric": "works_count",
                "entity": None,
                "model": "naive_last_value",
                "target_year": 2020,
                "z_score": 4.0,
                "absolute_error": 2.0,
                "relative_error": 0.2,
                "severity": "high",
            },
        ]
    )

    grouped = build_cross_domain_breaks(anomalies)
    row = grouped.iloc[0].to_dict()

    assert row["target_year"] == 2020
    assert row["affected_domains"] == ["economics", "science"]
    assert row["affected_domain_count"] == 2
    assert row["anomaly_count"] == 2
    assert row["aggregate_score"] == 3.5
