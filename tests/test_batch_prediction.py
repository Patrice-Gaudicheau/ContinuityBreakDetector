from __future__ import annotations

import json
from pathlib import Path

import pytest

from continuity_break_detector import batch_prediction_runner
from continuity_break_detector.batch_prediction import (
    BatchInput,
    BatchSeriesItem,
    load_batch_input,
    run_batch_prediction,
)
from continuity_break_detector.forecast_client import ForecastResult
from continuity_break_detector.series_prediction import SeriesPredictionError


def write_json(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def valid_payload() -> dict[str, object]:
    return {
        "series": [
            {"name": "stable", "values": [1, 1.1, 1.2]},
            {"name": "break", "values": [1, 1.1, 4.2]},
        ],
        "metadata": {"source": "test"},
    }


def test_load_valid_batch_input(tmp_path: Path) -> None:
    path = write_json(tmp_path / "batch.json", valid_payload())

    result = load_batch_input(path)

    assert [item.name for item in result.series] == ["stable", "break"]
    assert result.series[0].values == [1.0, 1.1, 1.2]
    assert result.metadata == {"source": "test"}


def test_reject_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SeriesPredictionError, match="does not exist"):
        load_batch_input(tmp_path / "missing.json")


def test_reject_invalid_json(tmp_path: Path) -> None:
    path = tmp_path / "bad.json"
    path.write_text("{", encoding="utf-8")

    with pytest.raises(SeriesPredictionError, match="invalid JSON"):
        load_batch_input(path)


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "missing required field: series"),
        ({"series": []}, "series must be a non-empty list"),
        ({"series": [{"name": "", "values": [1]}]}, "name must be a non-empty string"),
        ({"series": [{"name": "x", "values": [1, "bad"]}]}, r"values: series\[1\]"),
        (
            {"series": [{"name": "x", "values": [1]}, {"name": "x", "values": [2]}]},
            "duplicate series name: x",
        ),
    ],
)
def test_reject_invalid_batch_payloads(tmp_path: Path, payload: object, message: str) -> None:
    path = write_json(tmp_path / "batch.json", payload)

    with pytest.raises(SeriesPredictionError, match=message):
        load_batch_input(path)


def test_run_batch_prediction_uses_one_client_for_multiple_series() -> None:
    calls = []

    class FakeClient:
        def predict(self, worker, series, horizon, timeout_seconds=120.0):
            calls.append((worker, series, horizon, timeout_seconds))
            return ForecastResult(
                worker=worker,
                model_id="model",
                horizon=horizon,
                forecast=[series[-1] + 1],
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                succeeded=True,
            )

    response = run_batch_prediction(
        worker="timesfm",
        batch_input=BatchInput(
            series=[
                BatchSeriesItem(name="a", values=[1.0]),
                BatchSeriesItem(name="b", values=[2.0]),
            ],
            metadata={"source": "test"},
        ),
        horizon=1,
        mode="daemon",
        timeout_seconds=9,
        client=FakeClient(),
    )

    assert response["status"] == "ok"
    assert response["mode"] == "daemon"
    assert response["summary"] == {"ok": 2, "failed": 0}
    assert calls == [
        ("timesfm", [1.0], 1, 9),
        ("timesfm", [2.0], 1, 9),
    ]


def test_run_batch_prediction_keeps_per_series_failure() -> None:
    class FakeClient:
        def predict(self, worker, series, horizon, timeout_seconds=120.0):
            succeeded = series[0] != 2.0
            return ForecastResult(
                worker=worker,
                model_id="model" if succeeded else "",
                horizon=horizon,
                forecast=[3.0] if succeeded else [],
                raw_stdout="",
                raw_stderr="",
                returncode=0 if succeeded else 1,
                succeeded=succeeded,
                error=None if succeeded else "failed",
            )

    response = run_batch_prediction(
        worker="chronos",
        batch_input=BatchInput(
            series=[
                BatchSeriesItem(name="ok", values=[1.0]),
                BatchSeriesItem(name="bad", values=[2.0]),
            ],
            metadata={},
        ),
        horizon=1,
        client=FakeClient(),
    )

    assert response["status"] == "partial"
    assert response["summary"] == {"ok": 1, "failed": 1}
    assert response["results"][1]["name"] == "bad"
    assert response["results"][1]["error"]["message"] == "failed"


def test_run_batch_prediction_top_level_client_start_failure(monkeypatch) -> None:
    def fake_factory(mode: str):
        raise SeriesPredictionError("worker_error", "daemon unavailable")

    monkeypatch.setattr("continuity_break_detector.batch_prediction.forecast_client_for_mode", fake_factory)

    with pytest.raises(SeriesPredictionError, match="daemon unavailable"):
        run_batch_prediction(
            worker="timesfm",
            batch_input=BatchInput(series=[BatchSeriesItem(name="x", values=[1.0])], metadata={}),
            horizon=1,
            mode="daemon",
        )


def test_run_batch_prediction_treats_daemon_start_failure_as_top_level_error() -> None:
    class FakeClient:
        def predict(self, worker, series, horizon, timeout_seconds=120.0):
            return ForecastResult(
                worker=worker,
                model_id="",
                horizon=horizon,
                forecast=[],
                raw_stdout="",
                raw_stderr="",
                returncode=127,
                succeeded=False,
                error=f"{worker} daemon prediction could not start Docker Compose: missing docker",
            )

    with pytest.raises(SeriesPredictionError, match="could not start Docker Compose"):
        run_batch_prediction(
            worker="timesfm",
            batch_input=BatchInput(series=[BatchSeriesItem(name="x", values=[1.0])], metadata={}),
            horizon=1,
            mode="daemon",
            client=FakeClient(),
        )


def test_batch_predict_cli_success(monkeypatch, tmp_path: Path, capsys) -> None:
    path = write_json(tmp_path / "batch.json", valid_payload())

    def fake_run(**kwargs):
        return {
            "status": "ok",
            "worker": kwargs["worker"],
            "mode": kwargs["mode"],
            "horizon": kwargs["horizon"],
            "input": {"series_count": 2, "metadata": {"source": "test"}},
            "results": [
                {"name": "stable", "status": "ok", "prediction": {"model_id": "m", "forecast": [1.0]}},
                {"name": "break", "status": "ok", "prediction": {"model_id": "m", "forecast": [2.0]}},
            ],
            "summary": {"ok": 2, "failed": 0},
        }

    monkeypatch.setattr(batch_prediction_runner, "run_batch_prediction", fake_run)
    monkeypatch.setattr(
        "sys.argv",
        [
            "cbd",
            "--worker",
            "timesfm",
            "--input",
            str(path),
            "--horizon",
            "3",
            "--mode",
            "daemon",
        ],
    )

    assert batch_prediction_runner.main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["status"] == "ok"
    assert output["mode"] == "daemon"
    assert output["summary"] == {"ok": 2, "failed": 0}


def test_batch_predict_cli_invalid_input_returns_json(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "cbd",
            "--worker",
            "timesfm",
            "--input",
            str(tmp_path / "missing.json"),
            "--horizon",
            "3",
        ],
    )

    assert batch_prediction_runner.main() == 2
    output = json.loads(capsys.readouterr().out)

    assert output["status"] == "error"
    assert output["error"]["type"] == "validation_error"
