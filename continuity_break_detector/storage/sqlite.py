from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from continuity_break_detector.utils.paths import ensure_directory


def append_dataframe(df: pd.DataFrame, database_path: Path, table_name: str) -> None:
    ensure_directory(database_path.parent)
    with sqlite3.connect(database_path) as connection:
        df.to_sql(table_name, connection, if_exists="append", index=False)

