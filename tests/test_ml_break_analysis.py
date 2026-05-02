from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from continuity_break_detector import ml_break_analysis_runner
from continuity_break_detector.forecast_client import ForecastResult
from continuity_break_detector.ml_break_analysis import (
    analyze_combined_series,
    analyze_prediction_result,
    combined_series_frame,
    validate_forecast,
)
from continuity_break_detector.series_prediction import SeriesInput, SeriesPredictionError


def prediction_result(
    *,
    worker: str = "timesfm",
    forecast: list[float] | None = None,
    stderr: str = "",
) -> ForecastResult:
    forecast = [5.0, 6.0] if forecast is None else forecast
    return ForecastResult(
        worker=worker,
        model_id="model",
        horizon=len(forecast),
        forecast=forecast,
        raw_stdout="",
        raw_stderr=stderr,
        returncode=0,
        succeeded=True,
        response={"worker": worker, "model_id": "model", "horizon": len(forecast), "forecast": forecast},
    )


def test_combined_series_frame_construction() -> None:
    frame = combined_series_frame([1.0, 2.0, 3.0])

    assert frame["value"].tolist() == [1.0, 2.0, 3.0]
    assert frame["year"].tolist() == [0, 1, 2]
    assert frame["source_id"].tolist() == ["ml_pipeline"] * 3


def test_detector_adapter_is_called(monkeypatch) -> None:
    calls = []

    def fake_detect(frame, *, window):
        calls.append((frame.copy(), window))
        return pd.DataFrame({"year": [3], "break_score": [1.25]})

    monkeypatch.setattr("continuity_break_detector.ml_break_analysis.detect_break_candidates", fake_detect)

    analysis = analyze_combined_series([1.0, 2.0, 3.0], [10.0, 11.0])

    assert analysis["break_detected"] is True
    assert analysis["score"] == 1.25
    assert calls[0][0]["value"].tolist() == [1.0, 2.0, 3.0, 10.0, 11.0]


def test_success_output_shape() -> None:
    result = analyze_prediction_result(
        worker="chronos",
        series_input=SeriesInput(series=[1.0, 2.0, 3.0, 4.0], metadata={"name": "demo"}),
        prediction=prediction_result(worker="chronos", forecast=[4.2, 4.3]),
    )

    assert result.worker == "chronos"
    assert result.series_input.metadata == {"name": "demo"}
    assert result.prediction.forecast == [4.2, 4.3]
    assert result.analysis["combined_points"] == 6
    assert "score" in result.analysis


def test_error_output_shape_from_cli(monkeypatch, tmp_path: Path, capsys) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["cbd", "--worker", "timesfm", "--input", str(tmp_path / "missing.json"), "--horizon", "1"],
    )

    assert ml_break_analysis_runner.main() == 2
    output = json.loads(capsys.readouterr().out)

    assert output["status"] == "error"
    assert output["error"]["type"] == "validation_error"


def test_invalid_forecast_is_rejected() -> None:
    with pytest.raises(SeriesPredictionError, match=r"forecast\[1\] must be a finite number"):
        validate_forecast([1.0, float("nan")])


def test_cli_success_prints_only_json_to_stdout(monkeypatch, tmp_path: Path, capsys) -> None:
    input_path = tmp_path / "series.json"
    input_path.write_text(
        json.dumps({"series": [1.0, 2.0, 3.0], "metadata": {"name": "demo"}}),
        encoding="utf-8",
    )

    def fake_predict(worker, series, horizon, timeout_seconds=120.0):
        return prediction_result(worker=worker, forecast=[4.0], stderr="worker diagnostic")

    monkeypatch.setattr(ml_break_analysis_runner, "predict_series_with_worker", fake_predict)
    monkeypatch.setattr(
        "sys.argv",
        [
            "cbd",
            "--worker",
            "timesfm",
            "--input",
            str(input_path),
            "--horizon",
            "1",
        ],
    )

    assert ml_break_analysis_runner.main() == 0
    captured = capsys.readouterr()
    output = json.loads(captured.out)

    assert output["status"] == "ok"
    assert output["prediction"]["forecast"] == [4.0]
    assert output["analysis"]["combined_points"] == 4
    assert "worker diagnostic" in captured.err
