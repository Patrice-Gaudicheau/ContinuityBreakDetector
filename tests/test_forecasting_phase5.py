from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

from continuity_break_detector.forecasting.adapters.deterministic_adapter import DeterministicAdapter
from continuity_break_detector.forecasting.adapters.timesfm_adapter import TimesFMAdapter
from continuity_break_detector.forecasting.advanced_backtest import run_advanced_backtest_study
from continuity_break_detector.forecasting.base import ForecastingError
from continuity_break_detector.forecasting.registry import build_forecaster_registry
from continuity_break_detector.forecasting.runner import list_forecasters_main
from continuity_break_detector.forecasting.subprocess_client import run_worker_forecast
from continuity_break_detector.storage.parquet import write_parquet


def test_subprocess_client_success_using_fake_worker(tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json, sys\n"
        "payload = json.loads(sys.stdin.read())\n"
        "print(json.dumps({'ok': True, 'forecast': [1.0] * payload['horizon'], 'model': 'fake', 'metadata': {'x': 1}}))\n",
        encoding="utf-8",
    )

    result = run_worker_forecast(
        python_executable=Path(sys.executable),
        worker_path=worker,
        model="fake",
        series=[1.0, 2.0],
        horizon=3,
        timeout=5,
    )

    assert result.forecast == [1.0, 1.0, 1.0]
    assert result.metadata == {"x": 1}


def test_subprocess_client_failure_json(tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json\n"
        "print(json.dumps({'ok': False, 'error': 'boom'}))\n",
        encoding="utf-8",
    )

    with pytest.raises(ForecastingError, match="boom"):
        run_worker_forecast(
            python_executable=Path(sys.executable),
            worker_path=worker,
            model="fake",
            series=[1.0],
            horizon=1,
            timeout=5,
        )


def test_subprocess_timeout_handling(tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text("import time\ntime.sleep(5)\n", encoding="utf-8")

    with pytest.raises(ForecastingError, match="timed out"):
        run_worker_forecast(
            python_executable=Path(sys.executable),
            worker_path=worker,
            model="fake",
            series=[1.0],
            horizon=1,
            timeout=0.1,
        )


def test_invalid_forecast_length(tmp_path: Path) -> None:
    worker = tmp_path / "worker.py"
    worker.write_text(
        "import json\n"
        "print(json.dumps({'ok': True, 'forecast': [1.0], 'model': 'fake', 'metadata': {}}))\n",
        encoding="utf-8",
    )

    with pytest.raises(ForecastingError, match="returned 1 values"):
        run_worker_forecast(
            python_executable=Path(sys.executable),
            worker_path=worker,
            model="fake",
            series=[1.0],
            horizon=2,
            timeout=5,
        )


def test_adapter_unavailable_when_python_executable_missing(monkeypatch) -> None:
    monkeypatch.setenv("CBD_TIMESFM_PYTHON", "/path/that/does/not/exist")

    status = TimesFMAdapter().availability()

    assert status.available is False
    assert "does not exist" in status.reason


def test_list_forecasters_handles_unavailable_workers(monkeypatch, capsys) -> None:
    monkeypatch.setenv("CBD_TIMESFM_PYTHON", "/path/that/does/not/exist")
    monkeypatch.setenv("CBD_CHRONOS_PYTHON", "/path/that/also/does/not/exist")

    assert list_forecasters_main() == 0
    output = capsys.readouterr().out

    assert "naive_last_value: available" in output
    assert "timesfm: unavailable" in output
    assert "chronos: unavailable" in output


def test_forecast_output_length() -> None:
    series = pd.Series([1.0, 2.0, 3.0], index=[2020, 2021, 2022])
    adapter = DeterministicAdapter("naive_last_value", "naive_last_value")

    assert adapter.forecast(series, 3) == [3.0, 3.0, 3.0]


def test_model_availability_detection(monkeypatch) -> None:
    monkeypatch.setenv("CBD_TIMESFM_PYTHON", "/path/that/does/not/exist")
    monkeypatch.setenv("CBD_CHRONOS_PYTHON", "/path/that/does/not/exist")

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
    monkeypatch.setenv("CBD_TIMESFM_PYTHON", "/path/that/does/not/exist")
    monkeypatch.setenv("CBD_CHRONOS_PYTHON", "/path/that/does/not/exist")
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

