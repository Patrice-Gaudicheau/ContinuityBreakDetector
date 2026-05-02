from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Protocol

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
        payload = {"series": [float(value) for value in series], "horizon": int(horizon)}
        try:
            completed = subprocess.run(
                command,
                input=json.dumps(payload),
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

    forecast = forecast_from_response(response)
    response_error = error_from_response(response)
    model_id = model_id_from_response(response)
    succeeded = completed.returncode == 0 and forecast is not None and response_error is None
    return ForecastResult(
        worker=worker,
        model_id=model_id,
        horizon=horizon,
        forecast=forecast or [],
        raw_stdout=completed.stdout,
        raw_stderr=completed.stderr,
        returncode=completed.returncode,
        succeeded=succeeded,
        error=response_error if response_error is not None else None if succeeded else "worker failed",
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


def forecast_from_response(response: dict[str, Any]) -> list[float] | None:
    forecast = response.get("forecast")
    if not isinstance(forecast, list):
        return None
    try:
        return [float(value) for value in forecast]
    except (TypeError, ValueError):
        return None


def error_from_response(response: dict[str, Any]) -> str | None:
    error = response.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
        return str(error)
    return None


def model_id_from_response(response: dict[str, Any]) -> str:
    model_id = response.get("model_id")
    return model_id if isinstance(model_id, str) else ""


def text_or_empty(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value


def default_forecast_client() -> ForecastClient:
    return DockerForecastClient()
