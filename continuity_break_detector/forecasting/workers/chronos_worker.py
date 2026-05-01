from __future__ import annotations

import json
import sys
from typing import Any


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        forecast = run_forecast(payload)
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1
    print(json.dumps(forecast))
    return 0


def run_forecast(payload: dict[str, Any]) -> dict[str, Any]:
    import torch
    from chronos import BaseChronosPipeline

    series = [float(value) for value in payload["series"]]
    horizon = int(payload["horizon"])
    params = payload.get("params", {})
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if not series:
        raise ValueError("series must not be empty")

    model_id = str(params.get("model_id", "amazon/chronos-bolt-small"))
    device_map = str(params.get("device_map", "cpu"))
    pipeline = BaseChronosPipeline.from_pretrained(
        model_id,
        device_map=device_map,
        local_files_only=bool(params.get("local_files_only", True)),
    )
    context = torch.tensor(series, dtype=torch.float32)
    raw = pipeline.predict(context, prediction_length=horizon)
    if raw.ndim == 3:
        if raw.shape[1] > 1:
            point = raw[0, raw.shape[1] // 2, :horizon]
        else:
            point = raw[0, 0, :horizon]
    else:
        point = raw.reshape(-1)[:horizon]
    forecast = [float(value) for value in point.tolist()]
    return {
        "ok": True,
        "forecast": forecast,
        "model": "chronos",
        "metadata": {
            "model_id": model_id,
            "pipeline_type": type(pipeline).__name__,
            "device_map": device_map,
            "frequency": "yearly",
            "forecast_shape": list(raw.shape),
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
