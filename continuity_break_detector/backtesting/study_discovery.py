from __future__ import annotations

from pathlib import Path

from continuity_break_detector.backtesting.study import STUDIES_DIR

VALID_STUDY_FILES = [
    "forecast_errors.parquet",
    "anomalies.parquet",
    "cross_domain_breaks.parquet",
    "summary.json",
    "provenance.json",
]


def validate_study_path(study_path: Path) -> Path:
    path = study_path.expanduser()
    if not path.is_absolute():
        path = path.resolve()
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"Study folder does not exist: {path}")
    missing = [filename for filename in VALID_STUDY_FILES if not (path / filename).exists()]
    if missing:
        raise FileNotFoundError(
            f"Invalid study folder {path}; missing required files: {', '.join(missing)}"
        )
    return path


def latest_valid_study_folder(studies_dir: Path = STUDIES_DIR) -> Path:
    root = studies_dir.expanduser()
    if not root.exists():
        raise FileNotFoundError(f"Studies directory does not exist: {root}")
    candidates = [path for path in root.iterdir() if path.is_dir() and _is_valid_study(path)]
    if not candidates:
        raise FileNotFoundError(f"No valid backtest study folders found under {root}")
    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))


def resolve_study_path(
    *,
    study_path: Path | None = None,
    studies_dir: Path = STUDIES_DIR,
) -> Path:
    if study_path is not None:
        return validate_study_path(study_path)
    return latest_valid_study_folder(studies_dir)


def _is_valid_study(path: Path) -> bool:
    return all((path / filename).exists() for filename in VALID_STUDY_FILES)
