from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

SOURCE_ID = "crossref"


def normalize(raw_dir: Path, *, interpolate: bool = False) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in sorted((raw_dir / SOURCE_ID).glob("*.json")):
        if path.name.endswith(".metadata.json"):
            continue
        year = _year_from_name(path.name)
        if year is None:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(normalize_payload(payload, year).to_dict("records"))
    return pd.DataFrame(rows, columns=["source_id", "metric", "year", "value", "unit", "entity"])


def normalize_payload(payload: dict[str, object], year: int) -> pd.DataFrame:
    message = payload.get("message")
    count = None
    if isinstance(message, dict):
        count = message.get("total-results")
        if count is None and isinstance(message.get("items"), list):
            count = len(message["items"])
    return pd.DataFrame(
        [
            {
                "source_id": SOURCE_ID,
                "metric": "works_count",
                "year": year,
                "value": float(count or 0),
                "unit": "works",
                "entity": None,
            }
        ]
    )


def log_missing_years(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    years = sorted(int(year) for year in df["year"].unique())
    return 1 if set(range(years[0], years[-1] + 1)) - set(years) else 0


def _year_from_name(name: str) -> int | None:
    match = re.search(r"created_(\d{4})", name)
    return int(match.group(1)) if match else None
