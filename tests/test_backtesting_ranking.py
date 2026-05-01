from __future__ import annotations

import pandas as pd

from continuity_break_detector.backtesting.ranking import (
    build_ranked_candidates,
    explanation_hint,
    mark_representatives,
    min_max_normalize,
    persistence_score,
    rank_scores,
)


def test_min_max_normalization() -> None:
    result = min_max_normalize(pd.Series([10.0, 20.0, 30.0]))

    assert result.tolist() == [0.0, 0.5, 1.0]


def test_min_max_normalization_flat_series() -> None:
    result = min_max_normalize(pd.Series([5.0, 5.0]))

    assert result.tolist() == [0.0, 0.0]


def test_persistence_score_calculation() -> None:
    result = persistence_score(2000, {1998, 2000, 2002, 2005})

    assert result == 0.6


def test_rank_score_calculation() -> None:
    candidates = pd.DataFrame(
        {
            "mean_z_score": [2.0, 4.0],
            "affected_domain_count": [1, 3],
            "anomaly_count": [1, 9],
            "persistence_score": [0.2, 1.0],
        }
    )

    result = rank_scores(candidates)

    assert result.round(6).tolist() == [0.04, 1.0]


def test_explanation_hint_lookup() -> None:
    assert explanation_hint(2008) == "Global financial crisis"
    assert explanation_hint(2009) is None


def test_representative_year_selection_within_three_year_window() -> None:
    candidates = pd.DataFrame(
        {
            "target_year": [2000, 2001, 2005],
            "rank_score": [0.8, 0.9, 0.7],
        }
    )

    result = mark_representatives(candidates, window_years=3).sort_values("target_year")

    assert result["is_representative"].tolist() == [False, True, True]
    assert result["representative_year"].tolist() == [2001, 2001, 2005]


def test_build_ranked_candidates() -> None:
    anomalies = pd.DataFrame(
        [
            _anomaly(2008, "world_bank_wdi", "NY.GDP.MKTP.CD", "linear_trend", 3.0),
            _anomaly(2008, "openalex", "works_count", "linear_trend", 4.0),
            _anomaly(2009, "openalex", "works_count", "naive_last_value", 5.0),
        ]
    )
    cross_domain_breaks = pd.DataFrame(
        [
            {
                "target_year": 2008,
                "affected_domains": ["economics", "science"],
                "affected_domain_count": 2,
                "anomaly_count": 2,
                "aggregate_score": 3.5,
                "items": [],
            }
        ]
    )

    ranked = build_ranked_candidates(anomalies, cross_domain_breaks)

    assert set(ranked["target_year"]) == {2008, 2009}
    assert ranked.loc[ranked["target_year"] == 2008, "ordinary_explanation_hint"].iloc[0] == (
        "Global financial crisis"
    )


def _anomaly(year: int, source_id: str, metric: str, model: str, z_score: float) -> dict[str, object]:
    return {
        "source_id": source_id,
        "metric": metric,
        "entity": None,
        "model": model,
        "target_year": year,
        "z_score": z_score,
        "absolute_error": 1.0,
        "relative_error": 0.1,
        "severity": "medium",
    }

