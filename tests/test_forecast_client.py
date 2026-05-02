from __future__ import annotations

import subprocess

import pytest

from continuity_break_detector.forecast_client import (
    DockerForecastClient,
    forecast_result_from_completed,
    worker_service_name,
)


def test_docker_forecast_client_builds_compose_command(monkeypatch) -> None:
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout='{"worker":"timesfm","model_id":"model","horizon":1,"forecast":[2.0]}',
            stderr="cache hit",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = DockerForecastClient().predict("timesfm", [1.0, 2.0], 1, timeout_seconds=9)

    assert result.succeeded is True
    assert result.forecast == [2.0]
    assert result.model_id == "model"
    args, kwargs = calls[0]
    assert args[0] == [
        "docker",
        "compose",
        "run",
        "--rm",
        "-T",
        "timesfm-worker",
        "python",
        "predict.py",
    ]
    assert kwargs["input"] == '{"series": [1.0, 2.0], "horizon": 1}'
    assert kwargs["timeout"] == 9


def test_docker_forecast_client_handles_timeout(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=3, output="partial", stderr="slow")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = DockerForecastClient().predict("chronos", [1.0], 1, timeout_seconds=3)

    assert result.succeeded is False
    assert result.returncode == 124
    assert result.raw_stdout == "partial"
    assert "timed out after 3 seconds" in result.raw_stderr


def test_docker_forecast_client_handles_missing_docker(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = DockerForecastClient().predict("timesfm", [1.0], 1)

    assert result.succeeded is False
    assert result.returncode == 127
    assert "could not start Docker Compose" in (result.error or "")


def test_forecast_result_handles_invalid_json() -> None:
    result = forecast_result_from_completed(
        "timesfm",
        1,
        subprocess.CompletedProcess(args=[], returncode=0, stdout="not-json", stderr=""),
    )

    assert result.succeeded is False
    assert "invalid JSON" in (result.error or "")


def test_forecast_result_handles_nonzero_worker_error() -> None:
    result = forecast_result_from_completed(
        "chronos",
        1,
        subprocess.CompletedProcess(
            args=[],
            returncode=2,
            stdout='{"worker":"chronos","error":{"type":"validation_error","message":"bad input"}}',
            stderr="",
        ),
    )

    assert result.succeeded is False
    assert result.error == "bad input"


def test_worker_service_name_rejects_unknown_worker() -> None:
    with pytest.raises(ValueError, match="worker must be one of"):
        worker_service_name("other")
