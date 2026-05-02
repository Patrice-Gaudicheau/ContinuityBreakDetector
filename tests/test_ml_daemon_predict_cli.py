from __future__ import annotations

import json

from continuity_break_detector import ml_daemon_predict_runner
from continuity_break_detector.forecast_client import ForecastResult


def test_ml_daemon_predict_cli_prints_json(monkeypatch, capsys) -> None:
    class FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            pass

        def predict(self, worker, series, horizon, timeout_seconds=120.0):
            return ForecastResult(
                worker=worker,
                model_id="model",
                horizon=horizon,
                forecast=[series[-1]],
                raw_stdout="",
                raw_stderr="",
                returncode=0,
                succeeded=True,
                response={
                    "worker": worker,
                    "model_id": "model",
                    "horizon": horizon,
                    "forecast": [series[-1]],
                },
            )

    monkeypatch.setattr(ml_daemon_predict_runner, "DockerWarmForecastClient", FakeClient)
    monkeypatch.setattr(
        "sys.argv",
        [
            "cbd",
            "--worker",
            "timesfm",
            "--series",
            "1,2,4",
            "--horizon",
            "1",
            "--repeat",
            "2",
        ],
    )

    assert ml_daemon_predict_runner.main() == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert captured.err == ""
    assert output["status"] == "ok"
    assert output["mode"] == "daemon"
    assert output["repeat"] == 2
    assert output["completed"] == 2
    assert output["predictions"] == [
        {"model_id": "model", "horizon": 1, "forecast": [4.0]},
        {"model_id": "model", "horizon": 1, "forecast": [4.0]},
    ]


def test_ml_daemon_predict_cli_rejects_invalid_repeat(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        [
            "cbd",
            "--worker",
            "chronos",
            "--series",
            "1,2",
            "--horizon",
            "1",
            "--repeat",
            "0",
        ],
    )

    assert ml_daemon_predict_runner.main() == 2
    output = json.loads(capsys.readouterr().out)

    assert output["worker"] == "chronos"
    assert output["error"]["type"] == "validation_error"
