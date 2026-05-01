from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

from continuity_break_detector.forecasting.adapters import chronos_adapter, timesfm_adapter
from continuity_break_detector.forecasting.adapters.chronos_adapter import ChronosAdapter
from continuity_break_detector.forecasting.adapters.deterministic_adapter import DeterministicAdapter
from continuity_break_detector.forecasting.adapters.timesfm_adapter import TimesFMAdapter
from continuity_break_detector.forecasting.availability import ImportAttempt
from continuity_break_detector.forecasting.advanced_backtest import run_advanced_backtest_study
from continuity_break_detector.forecasting.registry import build_forecaster_registry
from continuity_break_detector.storage.parquet import write_parquet


def test_timesfm_adapter_import_fallback(tmp_path: Path, monkeypatch) -> None:
    sys.modules.pop("timesfm", None)
    local_root = tmp_path / "timesfm"
    source_dir = local_root / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "timesfm.py").write_text(
        "def forecast(input_series, freq=2):\n"
        "    return [[1.0, 2.0, 3.0]]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CBD_TIMESFM_LOCAL_PATH", str(local_root))

    status = TimesFMAdapter().availability()

    assert status.available is True
    assert status.source_path == str(source_dir)
    sys.modules.pop("timesfm", None)


def test_chronos_adapter_import_fallback(tmp_path: Path, monkeypatch) -> None:
    sys.modules.pop("chronos", None)
    local_root = tmp_path / "chronos-forecasting"
    source_dir = local_root / "src"
    source_dir.mkdir(parents=True)
    (source_dir / "chronos.py").write_text(
        "def forecast(values, horizon):\n"
        "    return [float(values[-1])] * horizon\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("CBD_CHRONOS_LOCAL_PATH", str(local_root))

    status = ChronosAdapter().availability()

    assert status.available is True
    assert status.source_path == str(source_dir)
    sys.modules.pop("chronos", None)


def test_forecast_output_length() -> None:
    series = pd.Series([1.0, 2.0, 3.0], index=[2020, 2021, 2022])
    adapter = DeterministicAdapter("naive_last_value", "naive_last_value")

    assert adapter.forecast(series, 3) == [3.0, 3.0, 3.0]


def test_model_availability_detection(monkeypatch) -> None:
    monkeypatch.setenv("CBD_TIMESFM_LOCAL_PATH", "/path/that/does/not/exist")
    monkeypatch.setenv("CBD_CHRONOS_LOCAL_PATH", "/path/that/does/not/exist")
    monkeypatch.setattr(timesfm_adapter, "DEFAULT_TIMESFM_LOCAL_PATH", Path("/missing/timesfm"))
    monkeypatch.setattr(chronos_adapter, "DEFAULT_CHRONOS_LOCAL_PATH", Path("/missing/chronos"))
    monkeypatch.setattr(
        timesfm_adapter,
        "load_timesfm_module",
        lambda: ImportAttempt(None, False, "missing timesfm", None),
    )
    monkeypatch.setattr(
        chronos_adapter,
        "load_chronos_module",
        lambda: ImportAttempt(None, False, "missing chronos", None),
    )

    statuses = {item.forecaster_id: item for item in build_forecaster_registry().availability()}

    assert statuses["naive_last_value"].available is True
    assert statuses["linear_trend"].available is True
    assert statuses["exponential_trend"].available is True
    assert statuses["timesfm"].available is False
    assert statuses["chronos"].available is False


def test_advanced_backtest_falls_back_to_deterministic(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("CBD_TIMESFM_LOCAL_PATH", "/path/that/does/not/exist")
    monkeypatch.setenv("CBD_CHRONOS_LOCAL_PATH", "/path/that/does/not/exist")
    monkeypatch.setattr(timesfm_adapter, "DEFAULT_TIMESFM_LOCAL_PATH", Path("/missing/timesfm"))
    monkeypatch.setattr(chronos_adapter, "DEFAULT_CHRONOS_LOCAL_PATH", Path("/missing/chronos"))
    monkeypatch.setattr(
        timesfm_adapter,
        "load_timesfm_module",
        lambda: ImportAttempt(None, False, "missing timesfm", None),
    )
    monkeypatch.setattr(
        chronos_adapter,
        "load_chronos_module",
        lambda: ImportAttempt(None, False, "missing chronos", None),
    )
    input_dir = tmp_path / "normalized"
    source_dir = input_dir / "fixture"
    source_dir.mkdir(parents=True)
    values = pd.DataFrame(
        {
            "source_id": ["fixture"] * 35,
            "metric": ["metric"] * 35,
            "year": list(range(1990, 2025)),
            "value": [float(value) for value in range(1, 36)],
            "unit": [None] * 35,
            "entity": [None] * 35,
        }
    )
    write_parquet(values, source_dir / "metric.parquet")

    result = run_advanced_backtest_study(
        input_dir=input_dir,
        studies_dir=tmp_path / "studies",
    )
    errors = pd.read_parquet(result.output_dir / "forecast_errors.parquet")

    assert result.forecast_error_rows > 0
    assert "naive_last_value" in set(errors["model"])
    assert "linear_trend" in set(errors["model"])
    assert "timesfm" not in set(errors["model"])
    assert "chronos" not in set(errors["model"])
    assert (result.output_dir / "model_comparison.parquet").exists()
