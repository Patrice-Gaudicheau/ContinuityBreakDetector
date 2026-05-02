from __future__ import annotations

import json

from continuity_break_detector import ml_predict_runner
from continuity_break_detector.ml_workers import WorkerPredictionResult


def test_ml_predict_cli_prints_worker_json(monkeypatch, capsys) -> None:
    def fake_predict(series, horizon, timeout_seconds=120.0):
        return WorkerPredictionResult(
            worker_name="timesfm",
            command=[],
            returncode=0,
            stdout='{"worker":"timesfm","forecast":[4.0]}',
            stderr="",
            succeeded=True,
            response={
                "worker": "timesfm",
                "model_id": "model",
                "horizon": horizon,
                "forecast": [series[-1]],
            },
            forecast=[series[-1]],
            error=None,
        )

    monkeypatch.setattr(ml_predict_runner, "predict_timesfm", fake_predict)
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
