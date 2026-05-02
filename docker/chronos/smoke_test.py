from __future__ import annotations

import importlib.metadata
import os
import sys


def main() -> int:
    try:
        import torch
        from chronos import BaseChronosPipeline

        version = importlib.metadata.version("chronos-forecasting")
        tensor = torch.tensor([1.0, 2.0, 3.0], dtype=torch.float32)
        if float(tensor.mean()) != 2.0:
            raise RuntimeError("unexpected torch tensor validation result")

        print(f"Chronos import smoke passed: chronos-forecasting {version}")
        print(f"Chronos tensor smoke passed: torch {torch.__version__}, device=cpu")

        if os.environ.get("CBD_RUN_ML_MODEL_SMOKE") != "1":
            print("Chronos model smoke skipped: set CBD_RUN_ML_MODEL_SMOKE=1 to enable runtime model loading")
            return 0

        model_id = os.environ.get("CBD_CHRONOS_MODEL_ID", "amazon/chronos-bolt-small")
        print(f"Chronos model smoke starting: model_id={model_id}")
        pipeline = BaseChronosPipeline.from_pretrained(
            model_id,
            device_map="cpu",
            local_files_only=False,
        )
        forecast = pipeline.predict(tensor, prediction_length=1)
        if forecast.numel() < 1:
            raise RuntimeError(f"unexpected Chronos forecast shape: {tuple(forecast.shape)}")
        print("Chronos model smoke passed")
        return 0
    except Exception as exc:
        print(f"Chronos smoke failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
