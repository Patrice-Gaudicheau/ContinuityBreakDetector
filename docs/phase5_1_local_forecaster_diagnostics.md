# Phase 5.1 Local Forecaster Diagnostics

Created: 2026-05-01

Scope: inspect the local TimesFM and Chronos checkouts only. No external
repositories were modified, and no ContinuityBreakDetector source code was
changed for this diagnostic.

## Summary

Both local forecaster repositories have their own working Python virtual
environment and can run a minimal CPU forecast when invoked through that
environment.

ContinuityBreakDetector's current Python environment does not include either
model stack. Direct in-process imports from CBD are therefore not sufficient
without installing large optional dependencies into CBD's environment.

Recommended Phase 5.1 integration direction: call TimesFM and Chronos through
small subprocess workers using each repository's own `.venv/bin/python`.

## Current CBD Python Environment

Executable:

```text
/usr/bin/python
```

Version:

```text
3.12.3
```

Observed imports:

```text
timesfm      MISSING
chronos      MISSING
torch        MISSING
transformers MISSING
jax          MISSING
einshape     MISSING
pandas       FOUND
numpy        FOUND
```

Implication: CBD cannot run TimesFM or Chronos in-process today by adding only
local source paths to `sys.path`. The heavy runtime dependencies are absent from
CBD's active Python environment.

## TimesFM

Local checkout:

```text
<TIMESFM_CHECKOUT>
```

Virtual environment Python:

```text
<TIMESFM_CHECKOUT>/.venv/bin/python
```

`pyvenv.cfg`:

```text
home = /usr/bin
include-system-site-packages = false
version = 3.12.3
executable = /usr/bin/python3.12
command = /usr/bin/python3 -m venv <TIMESFM_CHECKOUT>/.venv
```

Exact import names:

```python
import timesfm
timesfm.ForecastConfig
timesfm.TimesFM_2p5_200M_torch
```

Additional import notes:

```text
timesfm.timesfm_2p5.timesfm_2p5_torch imports successfully
timesfm.timesfm_2p5.timesfm_2p5_flax fails because einshape is missing
```

Relevant package versions in the TimesFM venv:

```text
timesfm          2.0.0
torch            2.11.0
numpy            2.4.4
huggingface-hub  1.10.1
safetensors      0.7.0
jax              0.10.0
einshape         MISSING
pandas           MISSING
```

Minimal working forecast example:

```python
import numpy as np
import torch
import timesfm

torch.set_float32_matmul_precision("high")

model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
    "google/timesfm-2.5-200m-pytorch",
    local_files_only=True,
    torch_compile=False,
)
model.compile(timesfm.ForecastConfig(
    max_context=64,
    max_horizon=5,
    normalize_inputs=True,
    use_continuous_quantile_head=True,
    force_flip_invariance=True,
    infer_is_positive=True,
    fix_quantile_crossing=True,
))

point, quantiles = model.forecast(
    horizon=5,
    inputs=[np.arange(30, dtype=float)],
)
```

Observed output:

```text
point_shape (1, 5)
quantiles_shape (1, 5, 10)
point [29.977378845214844, 30.72301483154297, 31.74395179748535, 33.196311950683594, 33.83880615234375]
```

Model cache observed:

```text
<HF_CACHE>/hub/models--google--timesfm-2.5-200m-pytorch
```

Missing dependencies:

- CBD environment: `timesfm`, `torch`, `jax`, and related TimesFM runtime
  dependencies are missing.
- TimesFM venv: `einshape` is missing, so the Flax backend is not available.
  The PyTorch backend works for the tested minimal forecast.
- TimesFM venv: `pandas` is missing, but the minimal array forecast path does
  not require pandas.

## Chronos

Local checkout:

```text
<CHRONOS_CHECKOUT>
```

Virtual environment Python:

```text
<CHRONOS_CHECKOUT>/.venv/bin/python
```

`pyvenv.cfg`:

```text
home = /usr/bin
include-system-site-packages = false
version = 3.12.3
executable = /usr/bin/python3.12
command = /usr/bin/python -m venv <CHRONOS_CHECKOUT>/.venv
```

Exact import names:

```python
from chronos import BaseChronosPipeline
from chronos import ChronosBoltPipeline
from chronos import ChronosPipeline
from chronos import Chronos2Pipeline
```

Observed available modules/classes:

```text
chronos.BaseChronosPipeline
chronos.ChronosPipeline
chronos.ChronosBoltPipeline
chronos.Chronos2Pipeline
chronos.ChronosConfig
chronos.ChronosBoltConfig
chronos.Chronos2ForecastingConfig
```

Relevant package versions in the Chronos venv:

```text
chronos-forecasting 2.2.2
torch               2.11.0
transformers        4.57.6
accelerate          1.13.0
numpy               2.4.4
einops              0.8.2
scikit-learn        1.8.0
pandas              MISSING
```

Minimal working forecast example:

```python
import torch
from chronos import BaseChronosPipeline

pipeline = BaseChronosPipeline.from_pretrained(
    "amazon/chronos-bolt-small",
    device_map="cpu",
    local_files_only=True,
)

context = torch.arange(30, dtype=torch.float32)
forecast = pipeline.predict(context, prediction_length=5)

# Chronos Bolt returns quantiles with shape (batch, quantiles, horizon).
point = forecast[0, forecast.shape[1] // 2]
```

Observed output:

```text
pipeline_type ChronosBoltPipeline
forecast_shape (1, 9, 5)
point [28.90576934814453, 29.77041244506836, 30.45915412902832, 31.04821014404297, 31.631078720092773]
```

Model cache observed:

```text
<HF_CACHE>/hub/models--amazon--chronos-bolt-small
```

Missing dependencies:

- CBD environment: `chronos`, `torch`, and `transformers` are missing.
- Chronos venv: `pandas` is missing. This blocks `predict_df(...)` examples,
  but does not block tensor-based `pipeline.predict(...)`.

## Integration Options

### Option 1: In-process import from CBD

Not recommended for the current environment.

Reasons:

- CBD's Python does not have `torch`, `timesfm`, `chronos`, or `transformers`.
- Adding only local source paths to `sys.path` cannot supply the missing runtime
  dependencies.
- Installing both model stacks into CBD would make the base project environment
  heavy and less deterministic-first.

### Option 2: Shared venv for CBD, TimesFM, and Chronos

Possible, but not recommended as the default.

Reasons:

- It would require merging two large model stacks into CBD's runtime.
- It increases dependency conflict risk.
- It makes optional forecasters less isolated.
- It would make deterministic backtests depend on an environment intended for
  heavyweight model inference unless carefully separated.

### Option 3: Subprocess workers using each local repo venv

Recommended.

Reasons:

- Both local model venvs already run minimal forecasts successfully.
- CBD can remain lightweight and deterministic-first.
- Optional model failures can be isolated per subprocess.
- Each adapter can pass a JSON payload containing one univariate series and
  horizon, then read JSON forecast values from stdout.
- The adapters can continue to report clear availability diagnostics:
  missing venv Python, import failure, model cache failure, forecast failure.

Suggested worker behavior for a later implementation:

- TimesFM subprocess:
  - executable: `<TIMESFM_CHECKOUT>/.venv/bin/python`
  - imports: `timesfm`, `numpy`, `torch`
  - model: `timesfm.TimesFM_2p5_200M_torch.from_pretrained(...)`
  - forecast call: `model.forecast(horizon=horizon, inputs=[array])`
  - point output: `point[0].tolist()`

- Chronos subprocess:
  - executable: `<CHRONOS_CHECKOUT>/.venv/bin/python`
  - imports: `torch`, `chronos.BaseChronosPipeline`
  - model: `BaseChronosPipeline.from_pretrained("amazon/chronos-bolt-small", ...)`
  - forecast call: `pipeline.predict(context, prediction_length=horizon)`
  - point output: median quantile for Chronos Bolt, or median across samples for
    sample-based Chronos outputs.

## Recommended Phase 5.1 Decision

CBD should call local TimesFM and Chronos through subprocess workers, not direct
imports and not a shared venv.

The local source checkout remains useful for resolving the worker interpreter and
validating import paths, but the actual model execution should happen inside the
respective repository `.venv`.

