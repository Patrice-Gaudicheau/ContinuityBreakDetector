from __future__ import annotations

import io
import subprocess
from concurrent.futures import TimeoutError

from continuity_break_detector.forecast_daemon_client import DockerWarmForecastClient


class FakeStdin:
    def __init__(self, broken: bool = False) -> None:
        self.lines: list[str] = []
        self.broken = broken

    def write(self, value: str) -> int:
        if self.broken:
            raise BrokenPipeError("closed")
        self.lines.append(value)
        return len(value)

    def flush(self) -> None:
        if self.broken:
            raise BrokenPipeError("closed")


class FakeProcess:
    def __init__(self, stdout: str, *, broken_stdin: bool = False) -> None:
        self.stdin = FakeStdin(broken=broken_stdin)
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO("")
        self.returncode: int | None = None
        self.killed = False
        self.waited = False

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.waited = True
        self.returncode = 0
        return 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


def test_warm_client_starts_process_once_and_sends_multiple_requests(monkeypatch) -> None:
    processes: list[FakeProcess] = []

    def fake_popen(*args, **kwargs):
        process = FakeProcess(
            '{"worker":"timesfm","model_id":"m","horizon":1,"forecast":[2.0]}\n'
            '{"worker":"timesfm","model_id":"m","horizon":1,"forecast":[3.0]}\n'
            '{"worker":"timesfm","status":"shutdown"}\n'
        )
        processes.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with DockerWarmForecastClient() as client:
        first = client.predict("timesfm", [1.0], 1)
        second = client.predict("timesfm", [2.0], 1)

    assert len(processes) == 1
    assert first.forecast == [2.0]
    assert second.forecast == [3.0]
    assert processes[0].stdin.lines[:2] == [
        '{"series": [1.0], "horizon": 1}\n',
        '{"series": [2.0], "horizon": 1}\n',
    ]
    assert processes[0].stdin.lines[-1] == '{"command":"shutdown"}\n'


def test_warm_client_handles_invalid_json_response(monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: FakeProcess("not-json\n"),
    )

    with DockerWarmForecastClient() as client:
        result = client.predict("chronos", [1.0], 1)

    assert result.succeeded is False
    assert "invalid JSON" in (result.error or "")


def test_warm_client_handles_timeout(monkeypatch) -> None:
    process = FakeProcess("")
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: process)
    monkeypatch.setattr(
        DockerWarmForecastClient,
        "_readline",
        lambda self, stdout, timeout_seconds: (_ for _ in ()).throw(TimeoutError()),
    )

    client = DockerWarmForecastClient()
    result = client.predict("timesfm", [1.0], 1, timeout_seconds=0.01)
    client.close()

    assert result.succeeded is False
    assert result.returncode == 124
    assert process.killed is True


def test_warm_client_handles_broken_pipe(monkeypatch) -> None:
    process = FakeProcess("", broken_stdin=True)
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: process)

    with DockerWarmForecastClient() as client:
        result = client.predict("timesfm", [1.0], 1)

    assert result.succeeded is False
    assert result.returncode == 127
    assert "failed to write request" in (result.error or "")


def test_warm_client_handles_missing_docker(monkeypatch) -> None:
    def fake_popen(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    with DockerWarmForecastClient() as client:
        result = client.predict("timesfm", [1.0], 1)

    assert result.succeeded is False
    assert result.returncode == 127
    assert "could not start Docker Compose" in (result.error or "")
