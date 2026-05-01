# Phase 5 Implementation Plan: Optional Advanced Forecasters

Phase 5 will add optional advanced forecasting adapters for TimesFM and Chronos
while preserving the deterministic baseline backtests as the always-available
fallback.

## Scope

- Add `python main.py list_forecasters`.
- Add `python main.py backtest_advanced`.
- Keep `naive_last_value`, `linear_trend`, and `exponential_trend` available and
  runnable even when TimesFM or Chronos are unavailable.
- Do not add TimesFM or Chronos as required dependencies.
- Do not vendor, copy, commit, or modify the TimesFM or Chronos repositories.

## Local Repository Support

Phase 5 must support local source checkouts:

- `CBD_TIMESFM_LOCAL_PATH`, default `~/Projets/timesfm`
- `CBD_CHRONOS_LOCAL_PATH`, default `~/Projets/chronos-forecasting`

Availability detection must check in this order:

1. Installed import from the current Python environment.
2. Local checkout path from the environment variable.
3. Default local checkout path.

If a local checkout exists, the adapter may add a candidate source path to
`sys.path` only inside the adapter availability/loading code. It must not mutate
`sys.path` globally at module import time.

TimesFM local path candidates:

- `~/Projets/timesfm/src`
- `~/Projets/timesfm/timesfm-forecasting`
- `~/Projets/timesfm`

Chronos local path candidates:

- `~/Projets/chronos-forecasting/src`
- `~/Projets/chronos-forecasting`

## Adapter Behavior

Each advanced adapter should expose:

- `forecaster_id`
- `display_name`
- `availability_status`
- `availability_reason`
- `forecast(...)`

If a local import fails, report the exact reason clearly in
`list_forecasters`. A missing or broken adapter must not fail the whole
advanced backtest.

## CLI Behavior

`python main.py list_forecasters` should print:

- deterministic baselines as available
- TimesFM status and source path, if detected
- Chronos status and source path, if detected
- failure reasons for unavailable optional models

`python main.py backtest_advanced` should:

- read normalized yearly series from `data/processed/normalized/`
- run deterministic baselines unconditionally
- run TimesFM only if available
- run Chronos only if available
- write a study folder with clear provenance indicating which forecasters ran
- continue if one optional model is unavailable

## Configuration Example

```bash
export CBD_TIMESFM_LOCAL_PATH="$HOME/Projets/timesfm"
export CBD_CHRONOS_LOCAL_PATH="$HOME/Projets/chronos-forecasting"

python main.py list_forecasters
python main.py backtest_advanced
```

## Constraints

- Keep both integrations optional.
- Do not fail the whole advanced backtest if one optional model is unavailable.
- Do not modify TimesFM or Chronos repositories.
- Do not copy external repository code into this repository.
- Do not add cloud APIs.
- Do not add LLM calls to Phase 5 forecasting.
- Preserve deterministic baseline behavior.

