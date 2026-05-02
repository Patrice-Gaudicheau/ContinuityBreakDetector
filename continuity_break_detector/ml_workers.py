from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from typing import Any

DEFAULT_WORKER_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class WorkerResult:
    worker_name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    succeeded: bool


@dataclass(frozen=True)
class WorkerPredictionResult:
    worker_name: str
    command: list[str]
    returncode: int
    stdout: str
    stderr: str
    succeeded: bool
    response: dict[str, Any] | None
    forecast: list[float]
    error: str | None


def run_timesfm_worker_smoke(
    *,
    full: bool = False,
    timeout: float = DEFAULT_WORKER_TIMEOUT_SECONDS,
) -> WorkerResult:
    return _run_worker_smoke(
        worker_name="timesfm",
        service_name="timesfm-worker",
        full=full,
        timeout=timeout,
    )


def run_chronos_worker_smoke(
    *,
    full: bool = False,
    timeout: float = DEFAULT_WORKER_TIMEOUT_SECONDS,
) -> WorkerResult:
    return _run_worker_smoke(
        worker_name="chronos",
        service_name="chronos-worker",
        full=full,
        timeout=timeout,
    )


def predict_timesfm(
    series: list[float],
    horizon: int,
    timeout_seconds: float = DEFAULT_WORKER_TIMEOUT_SECONDS,
) -> WorkerPredictionResult:
    return _run_worker_predict(
        worker_name="timesfm",
        service_name="timesfm-worker",
        series=series,
        horizon=horizon,
        timeout=timeout_seconds,
    )


def predict_chronos(
    series: list[float],
    horizon: int,
    timeout_seconds: float = DEFAULT_WORKER_TIMEOUT_SECONDS,
) -> WorkerPredictionResult:
    return _run_worker_predict(
        worker_name="chronos",
        service_name="chronos-worker",
        series=series,
        horizon=horizon,
        timeout=timeout_seconds,
    )


def _run_worker_smoke(
    *,
    worker_name: str,
    service_name: str,
    full: bool,
    timeout: float,
) -> WorkerResult:
    command = ["docker", "compose", "run", "--rm", service_name, "python", "smoke_test.py"]
    env = os.environ.copy()
    if full:
        env["CBD_RUN_ML_MODEL_SMOKE"] = "1"
    else:
        env.pop("CBD_RUN_ML_MODEL_SMOKE", None)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _text_or_empty(exc.stdout)
        stderr = _text_or_empty(exc.stderr)
        message = f"{worker_name} worker smoke timed out after {timeout:g} seconds"
        stderr = f"{stderr}\n{message}".strip()
        return WorkerResult(
            worker_name=worker_name,
            command=command,
            returncode=124,
            stdout=stdout,
            stderr=stderr,
            succeeded=False,
        )
    except OSError as exc:
        return WorkerResult(
            worker_name=worker_name,
            command=command,
            returncode=127,
            stdout="",
            stderr=f"{worker_name} worker smoke could not start Docker Compose: {exc}",
            succeeded=False,
        )

    return WorkerResult(
        worker_name=worker_name,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        succeeded=completed.returncode == 0,
    )


def _run_worker_predict(
    *,
    worker_name: str,
    service_name: str,
    series: list[float],
    horizon: int,
    timeout: float,
) -> WorkerPredictionResult:
    command = ["docker", "compose", "run", "--rm", "-T", service_name, "python", "predict.py"]
    payload = {"series": [float(value) for value in series], "horizon": int(horizon)}
    try:
        completed = subprocess.run(
            command,
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=os.environ.copy(),
        )
    except subprocess.TimeoutExpired as exc:
        stdout = _text_or_empty(exc.stdout)
        stderr = _text_or_empty(exc.stderr)
        message = f"{worker_name} worker prediction timed out after {timeout:g} seconds"
        stderr = f"{stderr}\n{message}".strip()
        return WorkerPredictionResult(
            worker_name=worker_name,
            command=command,
            returncode=124,
            stdout=stdout,
            stderr=stderr,
            succeeded=False,
            response=None,
            forecast=[],
            error=message,
        )
    except OSError as exc:
        message = f"{worker_name} worker prediction could not start Docker Compose: {exc}"
        return WorkerPredictionResult(
            worker_name=worker_name,
            command=command,
            returncode=127,
            stdout="",
            stderr=message,
            succeeded=False,
            response=None,
            forecast=[],
            error=message,
        )

    response, parse_error = _parse_worker_json(completed.stdout)
    if parse_error is not None:
        return WorkerPredictionResult(
            worker_name=worker_name,
            command=command,
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            succeeded=False,
            response=None,
            forecast=[],
            error=parse_error,
        )

    forecast = _forecast_from_response(response)
    response_error = _error_from_response(response)
    succeeded = completed.returncode == 0 and forecast is not None and response_error is None
    return WorkerPredictionResult(
        worker_name=worker_name,
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        succeeded=succeeded,
        response=response,
        forecast=forecast or [],
        error=response_error if response_error is not None else None if succeeded else "worker failed",
    )


def _parse_worker_json(stdout: str) -> tuple[dict[str, Any], str | None]:
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as exc:
        return {}, f"worker returned invalid JSON stdout: {exc.msg}"
    if not isinstance(parsed, dict):
        return {}, "worker returned non-object JSON stdout"
    return parsed, None


def _forecast_from_response(response: dict[str, Any]) -> list[float] | None:
    forecast = response.get("forecast")
    if not isinstance(forecast, list):
        return None
    try:
        return [float(value) for value in forecast]
    except (TypeError, ValueError):
        return None


def _error_from_response(response: dict[str, Any]) -> str | None:
    error = response.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
        return str(error)
    return None


def _text_or_empty(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
