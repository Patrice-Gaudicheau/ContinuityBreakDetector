from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Any

from continuity_break_detector.forecast_client import (
    DEFAULT_FORECAST_TIMEOUT_SECONDS,
    ForecastResult,
    default_forecast_client,
    worker_service_name,
)

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
    return worker_prediction_from_forecast_result(
        default_forecast_client().predict(
            "timesfm",
            series,
            horizon,
            timeout_seconds=timeout_seconds,
        )
    )


def predict_worker(
    worker: str,
    series: list[float],
    horizon: int,
    timeout_seconds: float = DEFAULT_FORECAST_TIMEOUT_SECONDS,
) -> WorkerPredictionResult:
    return worker_prediction_from_forecast_result(
        default_forecast_client().predict(
            worker,
            series,
            horizon,
            timeout_seconds=timeout_seconds,
        )
    )


def worker_prediction_from_forecast_result(result: ForecastResult) -> WorkerPredictionResult:
    return WorkerPredictionResult(
        worker_name=result.worker,
        command=_predict_command(result.worker),
        returncode=result.returncode,
        stdout=result.raw_stdout,
        stderr=result.raw_stderr,
        succeeded=result.succeeded,
        response=result.response,
        forecast=result.forecast,
        error=result.error,
    )


def predict_chronos(
    series: list[float],
    horizon: int,
    timeout_seconds: float = DEFAULT_WORKER_TIMEOUT_SECONDS,
) -> WorkerPredictionResult:
    return worker_prediction_from_forecast_result(
        default_forecast_client().predict(
            "chronos",
            series,
            horizon,
            timeout_seconds=timeout_seconds,
        )
    )


def _predict_command(worker: str) -> list[str]:
    service_name = worker_service_name(worker)
    return ["docker", "compose", "run", "--rm", "-T", service_name, "python", "predict.py"]


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


def _text_or_empty(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
