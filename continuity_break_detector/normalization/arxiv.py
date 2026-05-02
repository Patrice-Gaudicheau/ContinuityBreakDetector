from __future__ import annotations

from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd

SOURCE_ID = "arxiv"
ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def normalize(raw_dir: Path, *, interpolate: bool = False) -> pd.DataFrame:
    counter: Counter[int] = Counter()
    for path in sorted((raw_dir / SOURCE_ID).glob("*.xml")):
        counter.update(_counts_from_xml(path.read_text(encoding="utf-8")))
    return _counter_to_frame(counter)


def log_missing_years(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    years = sorted(int(year) for year in df["year"].unique())
    return 1 if set(range(years[0], years[-1] + 1)) - set(years) else 0


def _counts_from_xml(text: str) -> Counter[int]:
    root = ElementTree.fromstring(text)
    counter: Counter[int] = Counter()
    for entry in root.findall("atom:entry", ATOM_NS):
        published = entry.findtext("atom:published", default="", namespaces=ATOM_NS)
        if len(published) >= 4 and published[:4].isdigit():
            counter[int(published[:4])] += 1
    return counter


def _counter_to_frame(counter: Counter[int]) -> pd.DataFrame:
    rows = [
        {
            "source_id": SOURCE_ID,
            "metric": "entry_count",
            "year": year,
            "value": float(count),
            "unit": "entries",
            "entity": None,
        }
        for year, count in sorted(counter.items())
    ]
    return pd.DataFrame(rows, columns=["source_id", "metric", "year", "value", "unit", "entity"])
