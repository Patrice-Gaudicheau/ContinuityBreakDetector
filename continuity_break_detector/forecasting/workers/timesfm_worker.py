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
    import numpy as np
    import timesfm
    import torch

    series = [float(value) for value in payload["series"]]
    horizon = int(payload["horizon"])
    params = payload.get("params", {})
    if horizon <= 0:
        raise ValueError("horizon must be positive")
    if not series:
        raise ValueError("series must not be empty")

    torch.set_float32_matmul_precision("high")
    model_id = str(params.get("model_id", "google/timesfm-2.5-200m-pytorch"))
    model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
        model_id,
        local_files_only=bool(params.get("local_files_only", True)),
        torch_compile=bool(params.get("torch_compile", False)),
    )
    model.compile(
        timesfm.ForecastConfig(
            max_context=int(params.get("max_context", 1024)),
            max_horizon=max(horizon, int(params.get("max_horizon", horizon))),
            normalize_inputs=bool(params.get("normalize_inputs", True)),
            use_continuous_quantile_head=bool(params.get("use_continuous_quantile_head", True)),
            force_flip_invariance=bool(params.get("force_flip_invariance", True)),
            infer_is_positive=bool(params.get("infer_is_positive", True)),
            fix_quantile_crossing=bool(params.get("fix_quantile_crossing", True)),
        )
    )
    point, quantiles = model.forecast(
        horizon=horizon,
        inputs=[np.asarray(series, dtype=float)],
    )
    forecast = [float(value) for value in point[0, :horizon].tolist()]
    return {
        "ok": True,
        "forecast": forecast,
        "model": "timesfm",
        "metadata": {
            "model_id": model_id,
            "backend": "torch",
            "frequency": "yearly",
            "point_shape": list(point.shape),
            "quantiles_shape": list(quantiles.shape),
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
