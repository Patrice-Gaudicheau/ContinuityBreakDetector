from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("script_name", "script_path"),
    [
        ("timesfm_predict", PROJECT_ROOT / "docker" / "timesfm" / "predict.py"),
        ("chronos_predict", PROJECT_ROOT / "docker" / "chronos" / "predict.py"),
    ],
)
def test_worker_predict_validation_accepts_common_payload(script_name: str, script_path: Path) -> None:
    module = load_script(script_name, script_path)

    series, horizon = module.validate_payload({"series": [1, 2.5, 3], "horizon": 2})

    assert series == [1.0, 2.5, 3.0]
    assert horizon == 2


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({}, "missing required field: series"),
        ({"series": [], "horizon": 1}, "series must be a non-empty list"),
        ({"series": [1, "x"], "horizon": 1}, "series[1] must be a finite number"),
        ({"series": [1, float("nan")], "horizon": 1}, "series[1] must be a finite number"),
        ({"series": [1], "horizon": 0}, "horizon must be a positive integer"),
    ],
)
def test_worker_predict_validation_rejects_bad_payloads(payload, message: str) -> None:
    module = load_script("timesfm_predict_bad_payload", PROJECT_ROOT / "docker" / "timesfm" / "predict.py")

    with pytest.raises(module.ValidationError) as exc_info:
        module.validate_payload(payload)
    assert message in str(exc_info.value)
