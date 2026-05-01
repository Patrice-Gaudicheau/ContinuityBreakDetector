from __future__ import annotations

import pandas as pd

from continuity_break_detector.backtesting.models import (
    exponential_trend,
    linear_trend,
    naive_last_value,
)


def test_naive_last_value_forecast() -> None:
    train = pd.DataFrame({"year": [2000, 2001, 2002], "value": [1.0, 2.0, 3.0]})

    assert naive_last_value(train, [2003, 2004]) == {2003: 3.0, 2004: 3.0}


def test_linear_trend_forecast() -> None:
    train = pd.DataFrame({"year": [2000, 2001, 2002], "value": [10.0, 12.0, 14.0]})

    forecast = linear_trend(train, [2003])

    assert round(forecast[2003], 6) == 16.0


def test_exponential_trend_forecast_on_positive_data() -> None:
    train = pd.DataFrame({"year": [2000, 2001, 2002], "value": [2.0, 4.0, 8.0]})

    forecast = exponential_trend(train, [2003])

    assert round(forecast[2003], 6) == 16.0

