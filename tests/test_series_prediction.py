from __future__ import annotations

import json
from pathlib import Path

import pytest

from continuity_break_detector import series_prediction_runner
from continuity_break_detector.ml_workers import WorkerPredictionResult
from continuity_break_detector.series_prediction import (
    SeriesInput,
    SeriesPredictionError,
    build_error_response,
    build_success_response,
    load_series_input,
    predict_series_with_worker,
)


def write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_valid_series_input(tmp_path: Path) -> None:
    path = write_json(
        tmp_path / "series.json",
        {"series": [1, 2.5, 3], "metadata": {"name": "demo"}},
    )

    result = load_series_input(path)

    assert result.series == [1.0, 2.5, 3.0]
    assert result.metadata == {"name": "demo"}


def test_reject_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SeriesPredictionError, match="does not exist"):
        load_series_input(tmp_path / "missing.json")


def test_reject_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(SeriesPredictionError, match="invalid JSON"):
        load_series_input(path)


def test_reject_missing_series(tmp_path: Path) -> None:
    path = write_json(tmp_path / "series.json", {"metadata": {}})

    with pytest.raises(SeriesPredictionError, match="missing required field: series"):
        load_series_input(path)


def test_reject_non_numeric_series_value(tmp_path: Path) -> None:
    path = write_json(tmp_path / "series.json", {"series": [1, "bad"]})

    with pytest.raises(SeriesPredictionError, match=r"series\[1\] must be a finite number"):
        load_series_input(path)


def test_reject_invalid_horizon() -> None:
    with pytest.raises(SeriesPredictionError, match="horizon must be a positive integer"):
        predict_series_with_worker("timesfm", [1.0], 0)


def test_predict_series_dispatches_to_worker(monkeypatch) -> None:
    calls = []

    def fake_predict(series, horizon, timeout_seconds=120.0):
        calls.append((series, horizon, timeout_seconds))
        return WorkerPredictionResult(
            worker_name="timesfm",
            command=[],
            returncode=0,
            stdout="",
            stderr="",
            succeeded=True,
            response={"worker": "timesfm", "model_id": "model", "horizon": horizon, "forecast": [5.0]},
            forecast=[5.0],
            error=None,
        )

    monkeypatch.setattr("continuity_break_detector.series_prediction.predict_timesfm", fake_predict)

    result = predict_series_with_worker("timesfm", [1.0, 2.0], 1, timeout_seconds=9)

    assert result.forecast == [5.0]
    assert calls == [([1.0, 2.0], 1, 9)]


def test_build_success_response_shape() -> None:
    response = build_success_response(
        worker="chronos",
        series_input=SeriesInput(series=[1.0, 2.0], metadata={"name": "demo"}),
        prediction=WorkerPredictionResult(
            worker_name="chronos",
            command=[],
            returncode=0,
            stdout="",
            stderr="",
            succeeded=True,
            response={
                "worker": "chronos",
                "model_id": "amazon/chronos-bolt-small",
                "horizon": 2,
                "forecast": [2.0, 3.0],
            },
            forecast=[2.0, 3.0],
            error=None,
        ),
        horizon=2,
    )

    assert response == {
        "status": "ok",
        "worker": "chronos",
        "input": {"points": 2, "metadata": {"name": "demo"}},
        "prediction": {
            "model_id": "amazon/chronos-bolt-small",
            "horizon": 2,
            "forecast": [2.0, 3.0],
        },
    }


def test_build_error_response_shape() -> None:
    assert build_error_response("validation_error", "bad") == {
        "status": "error",
        "error": {"type": "validation_error", "message": "bad"},
    }


def test_predict_series_cli_success(monkeypatch, tmp_path: Path, capsys) -> None:
    path = write_json(tmp_path / "series.json", {"series": [1, 2], "metadata": {"name": "demo"}})

    def fake_predict(worker, series, horizon, timeout_seconds=120.0):
        return WorkerPredictionResult(
            worker_name=worker,
            command=[],
            returncode=0,
            stdout="",
            stderr="worker log",
            succeeded=True,
            response={"worker": worker, "model_id": "model", "horizon": horizon, "forecast": [3.0]},
            forecast=[3.0],
            error=None,
        )

    monkeypatch.setattr(series_prediction_runner, "predict_series_with_worker", fake_predict)
    monkeypatch.setattr(
        "sys.argv",
        [
            "cbd",
            "--worker",
            "timesfm",
            "--input",
            str(path),
            "--horizon",
            "1",
        ],
    )

    assert series_prediction_runner.main() == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["status"] == "ok"
    assert output["prediction"]["forecast"] == [3.0]
    assert "worker log" in captured.err


def test_predict_series_cli_error(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["cbd", "--worker", "chronos", "--input", str(tmp_path / "missing.json"), "--horizon", "1"],
    )

    assert series_prediction_runner.main() == 2
    output = json.loads(capsys.readouterr().out)

    assert output["status"] == "error"
    assert output["error"]["type"] == "validation_error"
