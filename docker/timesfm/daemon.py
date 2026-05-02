from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

from predict import WORKER_NAME, ModelPredictor, validate_payload

from continuity_break_detector.prediction_schema import (
    PredictionError,
    prediction_error_to_json_dict,
)
from continuity_break_detector.prediction_schema import PredictionSchemaError as ValidationError


def handle_payload(
    payload: Any,
    predict_func: Callable[[list[float], int], dict[str, Any]],
) -> tuple[dict[str, Any], bool]:
    if isinstance(payload, dict) and payload.get("command") == "shutdown":
        return {"worker": WORKER_NAME, "status": "shutdown"}, True
    try:
        series, horizon = validate_payload(payload)
        return predict_func(series, horizon), False
    except ValidationError as exc:
        return error_response("validation_error", str(exc)), False
    except Exception as exc:
        print(f"{WORKER_NAME} daemon inference failed: {exc}", file=sys.stderr)
        return error_response("inference_error", str(exc)), False


def handle_line(
    line: str,
    predict_func: Callable[[list[float], int], dict[str, Any]],
) -> tuple[str, bool]:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        response = error_response("validation_error", f"invalid JSON: {exc.msg}")
        return json.dumps(response, separators=(",", ":")), False
    response, should_shutdown = handle_payload(payload, predict_func)
    return json.dumps(response, separators=(",", ":")), should_shutdown


def error_response(error_type: str, message: str) -> dict[str, Any]:
    return prediction_error_to_json_dict(
        PredictionError(worker=WORKER_NAME, error_type=error_type, message=message)
    )


def main() -> int:
    predictor = ModelPredictor()
    print(f"{WORKER_NAME} daemon ready", file=sys.stderr)
    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue
        response_line, should_shutdown = handle_line(line, predictor.predict)
        print(response_line, flush=True)
        if should_shutdown:
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
