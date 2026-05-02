from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_daemon(name: str, worker_dir: Path) -> ModuleType:
    sys.modules.pop("predict", None)
    sys.path.insert(0, str(worker_dir))
    try:
        spec = importlib.util.spec_from_file_location(name, worker_dir / "daemon.py")
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(worker_dir))
        sys.modules.pop("predict", None)


@pytest.mark.parametrize(
    ("name", "worker_dir", "worker"),
    [
        ("timesfm_daemon", PROJECT_ROOT / "docker" / "timesfm", "timesfm"),
        ("chronos_daemon", PROJECT_ROOT / "docker" / "chronos", "chronos"),
    ],
)
def test_daemon_handle_line_predicts_without_loading_model(
    name: str, worker_dir: Path, worker: str
) -> None:
    module = load_daemon(name, worker_dir)

    line, should_shutdown = module.handle_line(
        '{"series":[1,2,3],"horizon":2}',
        lambda series, horizon: {
            "worker": worker,
            "model_id": "fake",
            "horizon": horizon,
            "forecast": [series[-1], series[-1]],
        },
    )

    assert should_shutdown is False
    assert json.loads(line) == {
        "worker": worker,
        "model_id": "fake",
        "horizon": 2,
        "forecast": [3.0, 3.0],
    }


def test_daemon_invalid_request_returns_json_error() -> None:
    module = load_daemon("timesfm_daemon_bad", PROJECT_ROOT / "docker" / "timesfm")

    line, should_shutdown = module.handle_line('{"series":[],"horizon":1}', lambda _s, _h: {})
    payload = json.loads(line)

    assert should_shutdown is False
    assert payload["worker"] == "timesfm"
    assert payload["error"]["type"] == "validation_error"
    assert "series must be a non-empty list" in payload["error"]["message"]


def test_daemon_shutdown_request_returns_status() -> None:
    module = load_daemon("chronos_daemon_shutdown", PROJECT_ROOT / "docker" / "chronos")

    line, should_shutdown = module.handle_line('{"command":"shutdown"}', lambda _s, _h: {})

    assert should_shutdown is True
    assert json.loads(line) == {"worker": "chronos", "status": "shutdown"}
