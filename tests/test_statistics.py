from __future__ import annotations

import pandas as pd

from continuity_break_detector.statistics.breaks import detect_break_candidates
from continuity_break_detector.statistics.features import add_statistical_features, growth_rate


def test_growth_rate_calculation() -> None:
    result = growth_rate(pd.Series([100.0, 110.0, 121.0]))

    assert result.round(6).tolist()[1:] == [0.1, 0.1]


def test_rolling_z_score_calculation() -> None:
    df = _series([10.0, 12.0, 14.0, 20.0])

    result = add_statistical_features(df, window=3)

    assert pd.isna(result.loc[2, "rolling_z_score"])
    assert round(float(result.loc[3, "rolling_z_score"]), 6) == 4.898979


def test_structural_break_candidate_detection() -> None:
    df = _series([1.0] * 10 + [10.0] * 10)

    result = detect_break_candidates(df, window=5)

    assert not result.empty
    assert result["break_score"].max() > 1.0


def _series(values: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "source_id": "test",
            "metric": "metric",
            "year": list(range(2000, 2000 + len(values))),
            "value": values,
            "unit": None,
            "entity": None,
        }
    )
