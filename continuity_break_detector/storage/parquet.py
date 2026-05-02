from __future__ import annotations

from pathlib import Path

import pandas as pd

from continuity_break_detector.utils.paths import ensure_directory


def write_parquet(df: pd.DataFrame, path: Path) -> None:
    ensure_directory(path.parent)
    df.to_parquet(path, index=False)


def read_parquet(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)
