# Reproducibility

ContinuityBreakDetector is designed to make each local run inspectable. The
repository contains source code, tests, documentation, and small synthetic
examples. Real raw data, processed data, model caches, SQLite databases, and
study outputs are generated locally and ignored by Git.

## Environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[test]'
```

Optional local forecasters require separate TimesFM and Chronos environments:

```bash
export CBD_TIMESFM_PYTHON="$HOME/projects/timesfm/.venv/bin/python"
export CBD_CHRONOS_PYTHON="$HOME/projects/chronos-forecasting/.venv/bin/python"
```

Optional local LLM analysis requires a Lemonade-compatible endpoint:

```bash
export CBD_LEMONADE_BASE_URL="http://<LEMONADE_HOST>:<PORT>/v1"
```

## Rebuild Sequence

```bash
python main.py ingest
python main.py normalize
python main.py compute_statistics
python main.py backtest_advanced
python main.py rank_breaks
python main.py audit_candidates
python main.py detect_artifacts
```

Use explicit study paths when needed:

```bash
python main.py rank_breaks --study-path studies/backtests/<study_id>
python main.py audit_candidates --study-path studies/backtests/<study_id>
python main.py detect_artifacts --study-path studies/backtests/<study_id>
```

## Validation

```bash
python -m py_compile $(find . -name "*.py")
pytest -q
```

## Excluded From Git

- `data/raw/`
- `data/processed/`
- `studies/backtests/`
- `publication/paper/`
- local SQLite databases
- model caches and checkpoints
- virtual environments
- local environment files

