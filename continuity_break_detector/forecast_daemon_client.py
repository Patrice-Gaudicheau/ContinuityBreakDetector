from __future__ import annotations

import json
import os
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from typing import IO

from continuity_break_detector.forecast_client import (
    DEFAULT_FORECAST_TIMEOUT_SECONDS,
    ForecastClient,
    ForecastResult,
    forecast_result_from_completed,
    text_or_empty,
    worker_service_name,
)
from continuity_break_detector.prediction_schema import (
    PredictionRequest,
    prediction_request_to_json_dict,
)


class DockerWarmForecastClient(ForecastClient):
    def __init__(self) -> None:
        self._processes: dict[str, subprocess.Popen[str]] = {}
        self._stderr_buffers: dict[str, list[str]] = {}
        self._stderr_threads: list[threading.Thread] = []
        self._read_executor = ThreadPoolExecutor(max_workers=4)
        self._closed = False

    def predict(
        self,
        worker: str,
        series: list[float],
        horizon: int,
        timeout_seconds: float = DEFAULT_FORECAST_TIMEOUT_SECONDS,
    ) -> ForecastResult:
        request = PredictionRequest(series=[float(value) for value in series], horizon=int(horizon))
        try:
            process = self._process_for(worker)
        except OSError as exc:
            message = f"{worker} daemon prediction could not start Docker Compose: {exc}"
            return self._error_result(worker, int(horizon), 127, message, self._stderr_for(worker))

        try:
            stdin = process.stdin
            stdout = process.stdout
            if stdin is None or stdout is None:
                raise BrokenPipeError("daemon stdin/stdout is not available")
            stdin.write(json.dumps(prediction_request_to_json_dict(request)) + "\n")
            stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._kill_worker(worker)
            message = f"{worker} daemon prediction failed to write request: {exc}"
            return self._error_result(worker, int(horizon), 127, message, self._stderr_for(worker))

        try:
            line = self._readline(stdout, timeout_seconds)
        except TimeoutError:
            self._kill_worker(worker)
            message = f"{worker} daemon prediction timed out after {timeout_seconds:g} seconds"
            stderr = f"{self._stderr_for(worker)}\n{message}".strip()
            return self._error_result(worker, int(horizon), 124, message, stderr)

        if line == "":
            returncode = process.poll()
            message = f"{worker} daemon exited before returning a prediction"
            return self._error_result(
                worker,
                int(horizon),
                returncode if returncode is not None else 1,
                message,
                self._stderr_for(worker),
            )

        completed = subprocess.CompletedProcess(
            args=self._command(worker),
            returncode=0,
            stdout=line.strip(),
            stderr=self._stderr_for(worker),
        )
        return forecast_result_from_completed(worker, int(horizon), completed)

    def shutdown(self, worker: str, timeout_seconds: float = 10.0) -> None:
        process = self._processes.get(worker)
        if process is None:
            return
        try:
            if process.stdin is not None:
                process.stdin.write('{"command":"shutdown"}\n')
                process.stdin.flush()
            if process.stdout is not None:
                self._readline(process.stdout, timeout_seconds)
            process.wait(timeout=timeout_seconds)
        except (BrokenPipeError, OSError, TimeoutError, subprocess.TimeoutExpired):
            self._kill_worker(worker)
        finally:
            self._processes.pop(worker, None)

    def close(self) -> None:
        if self._closed:
            return
        for worker in list(self._processes):
            self.shutdown(worker)
        self._read_executor.shutdown(wait=False, cancel_futures=True)
        self._closed = True

    def __enter__(self) -> DockerWarmForecastClient:
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()

    def _process_for(self, worker: str) -> subprocess.Popen[str]:
        existing = self._processes.get(worker)
        if existing is not None and existing.poll() is None:
            return existing

        command = self._command(worker)
        self._stderr_buffers[worker] = []
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env=os.environ.copy(),
        )
        self._processes[worker] = process
        if process.stderr is not None:
            self._start_stderr_reader(worker, process.stderr)
        return process

    def _start_stderr_reader(self, worker: str, stderr: IO[str]) -> None:
        def read_stderr() -> None:
            for line in stderr:
                self._stderr_buffers.setdefault(worker, []).append(line)

        thread = threading.Thread(target=read_stderr, daemon=True)
        thread.start()
        self._stderr_threads.append(thread)

    def _readline(self, stdout: IO[str], timeout_seconds: float) -> str:
        future = self._read_executor.submit(stdout.readline)
        return future.result(timeout=timeout_seconds)

    def _stderr_for(self, worker: str) -> str:
        return "".join(self._stderr_buffers.get(worker, [])).strip()

    def _kill_worker(self, worker: str) -> None:
        process = self._processes.pop(worker, None)
        if process is None:
            return
        process.kill()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass

    def _error_result(
        self,
        worker: str,
        horizon: int,
        returncode: int,
        message: str,
        stderr: str,
    ) -> ForecastResult:
        return ForecastResult(
            worker=worker,
            model_id="",
            horizon=horizon,
            forecast=[],
            raw_stdout="",
            raw_stderr=text_or_empty(stderr),
            returncode=returncode,
            succeeded=False,
            error=message,
        )

    def _command(self, worker: str) -> list[str]:
        service_name = worker_service_name(worker)
        return ["docker", "compose", "run", "--rm", "-T", service_name, "python", "daemon.py"]
