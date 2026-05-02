from __future__ import annotations

from pathlib import Path

import pandas as pd

from continuity_break_detector.utils.logging import get_logger

LOGGER = get_logger(__name__)
SOURCE_ID = "owid"
IDENTIFIER_COLUMNS = {"Entity", "Code", "Year"}


def normalize(raw_dir: Path, *, interpolate: bool = False) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in sorted((raw_dir / SOURCE_ID).glob("*_csv.csv")):
        slug = _slug_from_csv_path(path)
        frames.append(normalize_csv(path, slug=slug))
    if not frames:
        return pd.DataFrame(columns=["source_id", "metric", "year", "value", "unit", "entity"])
    return pd.concat(frames, ignore_index=True)


def normalize_csv(path: Path, *, slug: str) -> pd.DataFrame:
    source = pd.read_csv(path)
    if "Year" not in source.columns:
        return pd.DataFrame(columns=["source_id", "metric", "year", "value", "unit", "entity"])
    value_columns = [
        column
        for column in source.columns
        if column not in IDENTIFIER_COLUMNS and pd.api.types.is_numeric_dtype(source[column])
    ]
    rows: list[dict[str, object]] = []
    for column in value_columns:
        subset = source[
            ["Year", column, *[c for c in ["Code", "Entity"] if c in source.columns]]
        ].dropna(subset=[column])
        for row in subset.to_dict("records"):
            code = row.get("Code")
            entity_name = row.get("Entity")
            entity = code if code is not None and not pd.isna(code) else entity_name
            rows.append(
                {
                    "source_id": SOURCE_ID,
                    "metric": f"{slug}:{column}",
                    "year": int(row["Year"]),
                    "value": float(row[column]),
                    "unit": None,
                    "entity": entity,
                }
            )
    return pd.DataFrame(rows, columns=["source_id", "metric", "year", "value", "unit", "entity"])


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


def _slug_from_csv_path(path: Path) -> str:
    name = path.name
    marker = "_csv.csv"
    without_marker = name[: -len(marker)] if name.endswith(marker) else path.stem
    parts = without_marker.split("_", 2)
    return (
        parts[2]
        if len(parts) == 3 and parts[0].isdigit() and parts[1].isdigit()
        else without_marker
    )
