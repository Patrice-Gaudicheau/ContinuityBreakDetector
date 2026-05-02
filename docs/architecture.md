# Architecture

ContinuityBreakDetector is organized as a file-based, deterministic-first
pipeline. Each phase reads the previous phase's outputs and writes auditable
artifacts with compact metadata.

## Data Flow

```text
source APIs
  -> data/raw/{source_id}/
  -> data/processed/normalized/{source_id}/
  -> data/processed/statistics/{source_id}/
  -> studies/backtests/{study_id}/
  -> optional reports and paper drafts
```

Generated data directories are intentionally ignored by Git.

## Packages

- `sources/`: API connectors and raw retrieval metadata.
- `ingestion/`: source registry execution.
- `normalization/`: source-specific conversion into yearly time series.
- `statistics/`: deterministic feature and break calculations.
- `backtesting/`: rolling forecast-error studies, ranking, candidate audit, and
  data-artifact filtering.
- `forecasting/`: deterministic adapters plus optional TimesFM and Chronos
  subprocess workers.
- `agents/`: optional local Lemonade-compatible interpretation reports.
- `publication/`: factual extraction, tables, and optional paper drafting.
- `storage/`: small file storage helpers.

## Study Folders

A valid backtest study contains at least:

- `forecast_errors.parquet`
- `anomalies.parquet`
- `cross_domain_breaks.parquet`
- `summary.json`
- `provenance.json`

Post-backtest commands can discover the latest valid study or accept an explicit
`--study-path`.

## Deterministic Boundaries

The scientific pipeline is deterministic through artifact filtering. Optional
LLM reports and paper drafting read the deterministic outputs but do not compute
statistics or alter source data.

