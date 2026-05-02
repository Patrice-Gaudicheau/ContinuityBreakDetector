from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

SOURCE_ID = "openalex"


def normalize(raw_dir: Path, *, interpolate: bool = False) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in sorted((raw_dir / SOURCE_ID).glob("*.json")):
        if path.name.endswith(".metadata.json"):
            continue
        year = _year_from_name(path.name)
        if year is None:
            continue
        rows.extend(
            normalize_payload(json.loads(path.read_text(encoding="utf-8")), year).to_dict("records")
        )
    return pd.DataFrame(rows, columns=["source_id", "metric", "year", "value", "unit", "entity"])


def normalize_payload(payload: dict[str, object], year: int) -> pd.DataFrame:
    meta = payload.get("meta")
    count = meta.get("count") if isinstance(meta, dict) else None
    if count is None:
        results = payload.get("results")
        count = len(results) if isinstance(results, list) else 0
    return pd.DataFrame(
        [
            {
                "source_id": SOURCE_ID,
                "metric": "works_count",
                "year": year,
                "value": float(count),
                "unit": "works",
                "entity": None,
            }
        ]
    )


def log_missing_years(df: pd.DataFrame) -> int:
    return _count_missing_years(df)


def _year_from_name(name: str) -> int | None:
    match = re.search(r"publication_year_(\d{4})", name)
    return int(match.group(1)) if match else None


def _count_missing_years(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    years = sorted(int(year) for year in df["year"].unique())
    return 1 if set(range(years[0], years[-1] + 1)) - set(years) else 0
