from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from continuity_break_detector.normalization.models import NormalizedRecord


LOGGER = logging.getLogger(__name__)
SOURCE_ID = "world_bank_wdi"
INDICATORS = {"SP.POP.TOTL", "NY.GDP.MKTP.CD", "NY.GDP.PCAP.CD"}


def normalize(raw_dir: Path, *, interpolate: bool = False) -> pd.DataFrame:
    records: list[NormalizedRecord] = []
    source_dir = raw_dir / SOURCE_ID
    for path in sorted(source_dir.glob("*_combined.json")):
        indicator = _indicator_from_combined_path(path)
        if indicator not in INDICATORS:
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for page in payload.get("pages", []):
            rows = _page_rows(page)
            for row in rows:
                value = row.get("value")
                if value is None:
                    continue
                year = _parse_year(row.get("date"))
                if year is None:
                    continue
                country = row.get("country") or {}
                entity = row.get("countryiso3code") or country.get("id") or country.get("value")
                records.append(
                    NormalizedRecord(
                        source_id=SOURCE_ID,
                        metric=indicator,
                        year=year,
                        value=float(value),
                        unit=row.get("unit") or None,
                        entity=entity,
                    )
                )
    df = _to_frame(records)
    return interpolate_missing(df) if interpolate else df


def normalize_payload(payload: dict[str, Any], indicator: str) -> pd.DataFrame:
    records: list[NormalizedRecord] = []
    for page in payload.get("pages", []):
        for row in _page_rows(page):
            value = row.get("value")
            year = _parse_year(row.get("date"))
            if value is None or year is None:
                continue
            country = row.get("country") or {}
            records.append(
                NormalizedRecord(
                    source_id=SOURCE_ID,
                    metric=indicator,
                    year=year,
                    value=float(value),
                    unit=row.get("unit") or None,
                    entity=row.get("countryiso3code") or country.get("id") or country.get("value"),
                )
            )
    return _to_frame(records)


def log_missing_years(df: pd.DataFrame) -> int:
    warnings = 0
    if df.empty:
        return warnings
    for metric, metric_df in df.groupby("metric", dropna=False):
        missing_series = 0
        for _entity, group in metric_df.groupby("entity", dropna=False):
            years = sorted(int(year) for year in group["year"].dropna().unique())
            if years and set(range(years[0], years[-1] + 1)) - set(years):
                missing_series += 1
        if missing_series:
            warnings += missing_series
            LOGGER.warning("%s series have missing years for %s", missing_series, metric)
    return warnings


def interpolate_missing(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    frames: list[pd.DataFrame] = []
    for (_metric, _entity), group in df.groupby(["metric", "entity"], dropna=False):
        indexed = group.sort_values("year").set_index("year")
        full_index = range(int(indexed.index.min()), int(indexed.index.max()) + 1)
        expanded = indexed.reindex(full_index)
        expanded["value"] = expanded["value"].interpolate()
        for column in ["source_id", "metric", "unit", "entity"]:
            expanded[column] = expanded[column].ffill().bfill()
        expanded["year"] = expanded.index.astype(int)
        frames.append(expanded.reset_index(drop=True))
    return pd.concat(frames, ignore_index=True)


def _page_rows(page: Any) -> list[dict[str, Any]]:
    if isinstance(page, list) and len(page) >= 2 and isinstance(page[1], list):
        return [row for row in page[1] if isinstance(row, dict)]
    return []


def _parse_year(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _indicator_from_combined_path(path: Path) -> str:
    name = path.name
    marker = "_combined.json"
    stem = name[: -len(marker)] if name.endswith(marker) else path.stem
    parts = stem.split("_", 2)
    return parts[2] if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit() else stem


def _to_frame(records: list[NormalizedRecord]) -> pd.DataFrame:
    return pd.DataFrame([record.__dict__ for record in records], columns=[
        "source_id",
        "metric",
        "year",
        "value",
        "unit",
        "entity",
    ])
