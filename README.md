# ContinuityBreakDetector

ContinuityBreakDetector is a deterministic-first research pipeline for finding
candidate continuity breaks in long-term public time-series data. It retrieves
raw source data, normalizes it into yearly time series, computes transparent
statistical signals, runs historical forecasting backtests, filters likely data
artifacts, and can optionally produce local interpretation reports and research
drafts.

The project is designed as an auditable portfolio system: every stage writes
files, metadata, and reproducible outputs. It does not claim proof of simulation,
proof of unexplained influx, or causal certainty. Current study outputs indicate
that the pipeline detects known real-world shocks and data artifacts, but does
not currently identify an unexplained synchronized cross-domain continuity
break.

## Problem

Long-run development datasets can contain abrupt changes caused by real shocks,
methodology revisions, sparse early data, source coverage changes, or model
failure. A raw anomaly score alone is not enough to decide whether a year is
substantively meaningful. ContinuityBreakDetector separates the workflow into
retrieval, normalization, deterministic statistics, backtesting, ranking, audit,
artifact filtering, and optional interpretation so each claim can be inspected.

## Architecture

```text
public APIs -> data/raw/ -> normalization -> data/processed/normalized/
           -> deterministic statistics -> data/processed/statistics/
           -> backtesting studies -> studies/backtests/
           -> ranking, audit, artifact filtering
           -> optional local reports and paper drafts
```

Core design choices:

- raw source responses are stored separately from processed outputs
- normalized data uses a simple yearly schema
- statistics and break candidates are deterministic
- LLM-based interpretation is optional and never part of the statistical method
- TimesFM and Chronos integrations are optional subprocess workers
- generated data and study outputs are intentionally excluded from Git

## Pipeline Phases

1. **Source retrieval**: API-first connectors write raw responses and metadata.
2. **Normalization**: raw files become yearly time series with `source_id`,
   `metric`, `year`, `value`, `unit`, and `entity`.
3. **Statistics**: growth, log growth, acceleration, rolling z-scores, rolling
   deviations, and simple break candidates are computed deterministically.
4. **Backtesting**: rolling historical windows evaluate forecast failure using
   baseline models.
5. **Ranking and audit**: cross-domain candidates are ranked, checked for
   robustness, and filtered for artifact risk.
6. **Optional interpretation**: local Lemonade-compatible LLM reports can read
   deterministic outputs. These reports are not treated as scientific evidence.
7. **Optional paper drafting**: compact study summaries and tables can be passed
   to a local or CLI model to draft research prose.

## Supported Data Sources

Implemented connectors:

- World Bank WDI
- OpenAlex
- arXiv
- Crossref
- Our World in Data grapher CSV and metadata endpoints

Documented but not implemented yet:

- OECD
- Eurostat
- IEA
- BP / Energy Institute
- Maddison
- GitHub public activity
- Dimensions
- UN World Population Prospects

See [docs/data_sources.md](docs/data_sources.md) and
[docs/sources_connection_detail.md](docs/sources_connection_detail.md).

## Optional Advanced Forecasters

The deterministic baselines always run:

- `naive_last_value`
- `linear_trend`
- `exponential_trend`

Optional local forecasters can be enabled without installing their dependencies
into this repository:

- TimesFM through `CBD_TIMESFM_PYTHON`
- Chronos through `CBD_CHRONOS_PYTHON`

Example:

```bash
export CBD_TIMESFM_PYTHON="$HOME/projects/timesfm/.venv/bin/python"
export CBD_CHRONOS_PYTHON="$HOME/projects/chronos-forecasting/.venv/bin/python"
python main.py list_forecasters
python main.py backtest_advanced
```

The subprocess workers read JSON from stdin and write JSON to stdout. If either
optional model is unavailable, the advanced backtest continues with available
models and deterministic baselines.

## Optional Local LLM Analysis

Agent-style reports can run against a local Lemonade OpenAI-compatible endpoint.
This is optional and separate from deterministic analysis.

```bash
export CBD_LEMONADE_BASE_URL="http://<LEMONADE_HOST>:<PORT>/v1"
export CBD_ROUTER_MODEL="Qwen3-0.6B-GGUF"
export CBD_EXECUTOR_MODEL="Qwen3.5-35B-A3B-GGUF"
python main.py analyze_agents --study-path studies/backtests/<study_id>
```

The prompts instruct the model to prefer ordinary explanations, distinguish data
artifacts from real-world shocks, and avoid proof claims.

## Installation

Python 3.11 or later is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

## Basic Usage

```bash
python main.py ingest
python main.py normalize
python main.py compute_statistics
python main.py backtest
python main.py rank_breaks
python main.py audit_candidates
python main.py detect_artifacts
```

Advanced forecasting:

```bash
python main.py list_forecasters
python main.py backtest_advanced
```

Paper drafting from an existing study:

```bash
python main.py draft_paper --study-path studies/backtests/<study_id>
```

## Commands

- `python main.py ingest`
- `python main.py normalize`
- `python main.py compute_statistics`
- `python main.py backtest`
- `python main.py backtest_advanced`
- `python main.py list_forecasters`
- `python main.py rank_breaks [--study-path <path>]`
- `python main.py audit_candidates [--study-path <path>]`
- `python main.py detect_artifacts [--study-path <path>]`
- `python main.py analyze_agents [--study-path <path>]`
- `python main.py lemonade_debug`
- `python main.py draft_paper --study-path <path>`

## Expected Outputs

Generated outputs are local artifacts and are ignored by Git:

- `data/raw/`
- `data/processed/`
- `studies/backtests/`
- `publication/paper/`

Safe synthetic examples are committed under [examples/](examples/).

## Development

```bash
make test
make lint-basic
make typecheck-basic
make clean-generated
make run-demo
```

`typecheck-basic` runs only if `mypy` is installed.

## Limitations

- The pipeline detects statistical candidates, not causes.
- Artifact filtering identifies risk indicators, not definitive proof that a
  candidate is invalid.
- Optional TimesFM and Chronos runs depend on local model checkouts and cached
  model weights.
- Optional LLM reports are interpretive aids and are not part of the
  deterministic scientific method.
- Public API schemas, rate limits, and availability can change.

## Research Conclusion

The current workflow detects known real-world shocks and likely data artifacts.
It does not currently identify an unexplained synchronized cross-domain
continuity break. Any stronger claim would require additional source-level
validation, broader data coverage, and independent replication.

## Public Release Notes

Real raw data, processed data, study outputs, SQLite files, model caches, and
draft paper outputs are excluded from Git. The repository is intended to publish
the reproducible pipeline, not large generated artifacts.

