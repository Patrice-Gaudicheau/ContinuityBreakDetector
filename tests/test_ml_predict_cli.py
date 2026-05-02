from __future__ import annotations

import json

from continuity_break_detector import ml_predict_runner
from continuity_break_detector.forecast_client import ForecastResult


def test_ml_predict_cli_prints_worker_json(monkeypatch, capsys) -> None:
    class FakeClient:
        def predict(self, worker, series, horizon, timeout_seconds=120.0):
            return ForecastResult(
                worker=worker,
                model_id="model",
                horizon=horizon,
                forecast=[series[-1]],
                raw_stdout='{"worker":"timesfm","model_id":"model","horizon":1,"forecast":[4.0]}',
                raw_stderr="",
                returncode=0,
                succeeded=True,
                response={
                    "worker": "timesfm",
                    "model_id": "model",
                    "horizon": horizon,
                    "forecast": [series[-1]],
                },
            )

    monkeypatch.setattr(ml_predict_runner, "default_forecast_client", lambda: FakeClient())
    monkeypatch.setattr(
        "sys.argv",
        ["cbd", "--worker", "timesfm", "--series", "1,2,4", "--horizon", "1"],
    )

    assert ml_predict_runner.main() == 0
    output = json.loads(capsys.readouterr().out)

    assert output["worker"] == "timesfm"
    assert output["forecast"] == [4.0]


def test_ml_predict_cli_rejects_bad_series(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["cbd", "--worker", "chronos", "--series", "1,nope", "--horizon", "1"],
    )

    assert ml_predict_runner.main() == 2
    output = json.loads(capsys.readouterr().out)

    assert output["worker"] == "chronos"
    assert output["error"]["type"] == "validation_error"
