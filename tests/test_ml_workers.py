from __future__ import annotations

import os
import subprocess

from continuity_break_detector.ml_workers import (
    run_chronos_worker_smoke,
    run_timesfm_worker_smoke,
)


def test_timesfm_smoke_builds_lightweight_compose_command(monkeypatch) -> None:
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("CBD_RUN_ML_MODEL_SMOKE", "1")

    result = run_timesfm_worker_smoke(full=False, timeout=7)

    assert result.succeeded is True
    assert result.worker_name == "timesfm"
    assert result.command == [
        "docker",
        "compose",
        "run",
        "--rm",
        "timesfm-worker",
        "python",
        "smoke_test.py",
    ]
    _, kwargs = calls[0]
    assert kwargs["timeout"] == 7
    assert "CBD_RUN_ML_MODEL_SMOKE" not in kwargs["env"]


def test_chronos_smoke_sets_full_model_environment(monkeypatch) -> None:
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="ok\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_chronos_worker_smoke(full=True)

    assert result.succeeded is True
    assert result.command[4] == "chronos-worker"
    _, kwargs = calls[0]
    assert kwargs["env"]["CBD_RUN_ML_MODEL_SMOKE"] == "1"


def test_worker_nonzero_exit_is_represented(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=17,
            stdout="",
            stderr="worker failed",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_timesfm_worker_smoke()

    assert result.succeeded is False
    assert result.returncode == 17
    assert result.stderr == "worker failed"


def test_worker_timeout_is_represented(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], timeout=3, output="partial", stderr="slow")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_chronos_worker_smoke(timeout=3)

    assert result.succeeded is False
    assert result.returncode == 124
    assert result.stdout == "partial"
    assert "timed out after 3 seconds" in result.stderr


def test_docker_missing_is_represented(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = run_timesfm_worker_smoke()

    assert result.succeeded is False
    assert result.returncode == 127
    assert "could not start Docker Compose" in result.stderr


def test_existing_environment_is_preserved(monkeypatch) -> None:
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setenv("CBD_CUSTOM_VALUE", "kept")

    run_timesfm_worker_smoke()

    _, kwargs = calls[0]
    assert kwargs["env"]["CBD_CUSTOM_VALUE"] == "kept"
    assert kwargs["env"] is not os.environ
