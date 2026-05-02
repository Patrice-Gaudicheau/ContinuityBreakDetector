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

        model_id = os.environ.get("CBD_TIMESFM_MODEL_ID", "google/timesfm-1.0-200m-pytorch")
        print(f"TimesFM model smoke starting: model_id={model_id}")
        model = timesfm.TimesFm(
            hparams=timesfm.TimesFmHparams(
                context_len=512,
                horizon_len=1,
                input_patch_len=32,
                output_patch_len=128,
                backend="cpu",
            ),
            checkpoint=timesfm.TimesFmCheckpoint(
                version="torch",
                huggingface_repo_id=model_id,
            ),
        )
        point, _ = model.forecast(inputs=[array], freq=[0], normalize=True)
        if point.shape[-1] < 1:
            raise RuntimeError(f"unexpected TimesFM forecast shape: {point.shape}")
        print(f"TimesFM model smoke passed: forecast={float(point[0, 0]):.6g}")
        return 0
    except Exception as exc:
        print(f"TimesFM smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
