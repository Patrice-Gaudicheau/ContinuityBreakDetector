from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NormalizedRecord:
    source_id: str
    metric: str
    year: int
    value: float
    unit: str | None = None
    entity: str | None = None


@dataclass(frozen=True)
class NormalizationResult:
    source_id: str
    metric: str
    rows_written: int
    warnings_count: int
    path: Path

