from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from continuity_break_detector.config import DEFAULT_FORECASTER_TIMEOUT_SECONDS
from continuity_break_detector.forecasting.base import ForecastingError, ensure_forecast_length
from continuity_break_detector.utils.logging import get_logger
from continuity_break_detector.utils.paths import PROJECT_ROOT

DEFAULT_TIMESFM_PYTHON = Path("~/projects/timesfm/.venv/bin/python")
DEFAULT_CHRONOS_PYTHON = Path("~/projects/chronos-forecasting/.venv/bin/python")

LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class WorkerResult:
    forecast: list[float]
    metadata: dict[str, Any]


def timeout_seconds() -> float:
    return float(
        os.environ.get("CBD_FORECASTER_TIMEOUT_SECONDS", DEFAULT_FORECASTER_TIMEOUT_SECONDS)
    )


def timesfm_python() -> Path:
    return Path(os.environ.get("CBD_TIMESFM_PYTHON", str(DEFAULT_TIMESFM_PYTHON))).expanduser()


def chronos_python() -> Path:
    return Path(os.environ.get("CBD_CHRONOS_PYTHON", str(DEFAULT_CHRONOS_PYTHON))).expanduser()


def timesfm_worker_path() -> Path:
    return (
        PROJECT_ROOT / "continuity_break_detector" / "forecasting" / "workers" / "timesfm_worker.py"
    )


def chronos_worker_path() -> Path:
    return (
        PROJECT_ROOT / "continuity_break_detector" / "forecasting" / "workers" / "chronos_worker.py"
    )


def run_worker_forecast(
    *,
    python_executable: Path,
    worker_path: Path,
    model: str,
    series: list[float],
    horizon: int,
    params: dict[str, Any] | None = None,
    timeout: float | None = None,
) -> WorkerResult:
    if not python_executable.exists():
        raise ForecastingError(f"{model} Python executable does not exist: {python_executable}")
    if not worker_path.exists():
        raise ForecastingError(f"{model} worker script does not exist: {worker_path}")
    payload = {
        "series": [float(value) for value in series],
        "horizon": int(horizon),
        "params": params or {},
    }
    try:
        completed = subprocess.run(
            [str(python_executable), str(worker_path)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=timeout if timeout is not None else timeout_seconds(),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ForecastingError(f"{model} worker timed out after {exc.timeout} seconds") from exc
    except OSError as exc:
        raise ForecastingError(f"{model} worker could not start: {exc}") from exc

    stdout = completed.stdout.strip()
    stderr = completed.stderr.strip()
    if stderr:
        LOGGER.warning("%s worker stderr: %s", model, stderr)
    if not stdout:
        detail = f"; stderr: {stderr}" if stderr else ""
        raise ForecastingError(f"{model} worker returned no JSON output{detail}")
    json_text = stdout.splitlines()[-1]
    try:
        response = json.loads(json_text)
    except json.JSONDecodeError as exc:
        detail = f"; stderr: {stderr}" if stderr else ""
        raise ForecastingError(f"{model} worker returned invalid JSON{detail}") from exc
    if not isinstance(response, dict):
        raise ForecastingError(f"{model} worker returned non-object JSON")
    if not response.get("ok"):
        error = response.get("error", "unknown worker error")
        detail = f"; stderr: {stderr}" if stderr else ""
        raise ForecastingError(f"{model} worker failed: {error}{detail}")
    forecast = response.get("forecast")
    if not isinstance(forecast, list):
        raise ForecastingError(f"{model} worker response did not include a forecast list")
    validated = ensure_forecast_length(
        [float(value) for value in forecast],
        horizon=int(horizon),
        forecaster_id=model,
    )
    metadata = response.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    return WorkerResult(forecast=validated, metadata=metadata)


def smoke_test_worker(
    *,
    python_executable: Path,
    worker_path: Path,
    model: str,
    params: dict[str, Any] | None = None,
) -> tuple[bool, str]:
    try:
        run_worker_forecast(
            python_executable=python_executable,
            worker_path=worker_path,
            model=model,
            series=[1.0, 2.0, 3.0, 4.0],
            horizon=2,
            params=params,
        )
    except ForecastingError as exc:
        return False, str(exc)
    return True, "subprocess smoke forecast succeeded"
