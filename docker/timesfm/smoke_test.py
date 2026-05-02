from __future__ import annotations

import importlib.metadata
import os
import sys


def main() -> int:
    try:
        import numpy as np
        import timesfm
        import torch

        version = importlib.metadata.version("timesfm")
        tensor = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float32)
        array = np.asarray(tensor.tolist(), dtype=float)
        if array.shape != (3,):
            raise RuntimeError(f"unexpected validation array shape: {array.shape}")

        print(f"TimesFM import smoke passed: timesfm {version}")
        print(f"TimesFM tensor smoke passed: torch {torch.__version__}, device=cpu")

        if os.environ.get("CBD_RUN_ML_MODEL_SMOKE") != "1":
            print("TimesFM model smoke skipped: set CBD_RUN_ML_MODEL_SMOKE=1 to enable runtime model loading")
            return 0

        model_id = os.environ.get("CBD_TIMESFM_MODEL_ID", "google/timesfm-2.5-200m-pytorch")
        print(f"TimesFM model smoke starting: model_id={model_id}")
        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
            model_id,
            local_files_only=False,
            torch_compile=False,
        )
        model.compile(
            timesfm.ForecastConfig(
                max_context=16,
                max_horizon=1,
                normalize_inputs=True,
            )
        )
        point, _ = model.forecast(horizon=1, inputs=[array])
        if point.shape[-1] < 1:
            raise RuntimeError(f"unexpected TimesFM forecast shape: {point.shape}")
        print("TimesFM model smoke passed")
        return 0
    except Exception as exc:
        print(f"TimesFM smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
