from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol

from continuity_break_detector.prediction_schema import (
    PredictionRequest,
    PredictionSchemaError,
    parse_prediction_error,
    parse_prediction_success,
    prediction_request_to_json_dict,
)

DEFAULT_FORECAST_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class ForecastResult:
    worker: str
    model_id: str
    horizon: int
    forecast: list[float]
    raw_stdout: str
    raw_stderr: str
    returncode: int
    succeeded: bool
    error: str | None = None
    response: dict[str, Any] | None = None


class ForecastClient(Protocol):
    def predict(
        self,
        worker: str,
        series: list[float],
        horizon: int,
        timeout_seconds: float = DEFAULT_FORECAST_TIMEOUT_SECONDS,
    ) -> ForecastResult:
        pass


class DockerForecastClient:
    def predict(
        self,
        worker: str,
        series: list[float],
        horizon: int,
        timeout_seconds: float = DEFAULT_FORECAST_TIMEOUT_SECONDS,
    ) -> ForecastResult:
        service_name = worker_service_name(worker)
        command = ["docker", "compose", "run", "--rm", "-T", service_name, "python", "predict.py"]
        request = PredictionRequest(series=[float(value) for value in series], horizon=int(horizon))
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(prediction_request_to_json_dict(request)),
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
                env=os.environ.copy(),
            )
        except subprocess.TimeoutExpired as exc:
            stdout = text_or_empty(exc.stdout)
            stderr = text_or_empty(exc.stderr)
            message = f"{worker} worker prediction timed out after {timeout_seconds:g} seconds"
            stderr = f"{stderr}\n{message}".strip()
            return ForecastResult(
                worker=worker,
                model_id="",
                horizon=int(horizon),
                forecast=[],
                raw_stdout=stdout,
                raw_stderr=stderr,
                returncode=124,
                succeeded=False,
                error=message,
            )
        except OSError as exc:
            message = f"{worker} worker prediction could not start Docker Compose: {exc}"
            return ForecastResult(
                worker=worker,
                model_id="",
                horizon=int(horizon),
                forecast=[],
                raw_stdout="",
                raw_stderr=message,
                returncode=127,
                succeeded=False,
                error=message,
            )

        return forecast_result_from_completed(worker, int(horizon), completed)


def worker_service_name(worker: str) -> str:
    if worker == "timesfm":
        return "timesfm-worker"
    if worker == "chronos":
        return "chronos-worker"
    raise ValueError("worker must be one of: timesfm, chronos")


def forecast_result_from_completed(
    worker: str,
    horizon: int,
    completed: subprocess.CompletedProcess[str],
) -> ForecastResult:
    response, parse_error = parse_worker_json(completed.stdout)
    if parse_error is not None:
        return ForecastResult(
            worker=worker,
            model_id="",
            horizon=horizon,
            forecast=[],
            raw_stdout=completed.stdout,
            raw_stderr=completed.stderr,
            returncode=completed.returncode,
            succeeded=False,
            error=parse_error,
        )

    response_error = parse_prediction_error(response)
    if response_error is not None:
        return ForecastResult(
            worker=worker,
            model_id="",
            horizon=horizon,
            forecast=[],
            raw_stdout=completed.stdout,
            raw_stderr=completed.stderr,
            returncode=completed.returncode,
            succeeded=False,
            error=response_error.message,
            response=response,
        )

    try:
        success = parse_prediction_success(response)
    except PredictionSchemaError as exc:
        return ForecastResult(
            worker=worker,
            model_id="",
            horizon=horizon,
            forecast=[],
            raw_stdout=completed.stdout,
            raw_stderr=completed.stderr,
            returncode=completed.returncode,
            succeeded=False,
            error=str(exc) if completed.returncode == 0 else "worker failed",
            response=response,
        )

    succeeded = completed.returncode == 0
    return ForecastResult(
        worker=success.worker,
        model_id=success.model_id,
        horizon=success.horizon,
        forecast=success.forecast,
        raw_stdout=completed.stdout,
        raw_stderr=completed.stderr,
        returncode=completed.returncode,
        succeeded=succeeded,
        error=None if succeeded else "worker failed",
        response=response,
    )


def parse_worker_json(stdout: str) -> tuple[dict[str, Any], str | None]:
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {}, f"worker returned invalid JSON stdout: {exc.msg}"
    if not isinstance(parsed, dict):
        return {}, "worker returned non-object JSON stdout"
    return parsed, None


def text_or_empty(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def default_forecast_client() -> ForecastClient:
    return DockerForecastClient()
