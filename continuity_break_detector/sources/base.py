from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol, TypeAlias

from continuity_break_detector.utils.paths import RAW_DATA_DIR, ensure_directory


RawPayload: TypeAlias = list[dict[str, Any]] | dict[str, Any] | str


@dataclass(frozen=True)
class RawFetch:
    source_id: str
    source_name: str
    dataset_or_query: str
    extension: str
    payload: RawPayload
    url: str
    params: dict[str, Any]
    status_code: int
    content_type: str
    documentation_url: str
    method: str = "GET"


@dataclass(frozen=True)
class StoredRawFetch:
    raw_file: Path
    metadata_file: Path


class SourceConnector(Protocol):
    name: str
    source_id: str
    base_url: str
    documentation_url: str
    rate_limit_policy: str
    output_format: str

    def fetch(self) -> RawPayload:
        ...

    def iter_fetches(self) -> list[RawFetch]:
        ...


def utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%d_%H%M%S")


def retrieved_at_iso() -> str:
    return datetime.now(UTC).isoformat()


def safe_name(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return normalized.strip("._") or "dataset"


class RawStorage:
    def __init__(self, raw_dir: Path = RAW_DATA_DIR) -> None:
        self.raw_dir = raw_dir

    def write(self, fetch: RawFetch, *, timestamp: str | None = None) -> StoredRawFetch:
        ts = timestamp or utc_timestamp()
        source_dir = ensure_directory(self.raw_dir / fetch.source_id)
        stem = f"{ts}_{safe_name(fetch.dataset_or_query)}"
        raw_file = source_dir / f"{stem}.{fetch.extension.lstrip('.')}"
        metadata_file = source_dir / f"{stem}.metadata.json"

        if fetch.extension == "json":
            raw_file.write_text(
                json.dumps(fetch.payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        else:
            raw_file.write_text(str(fetch.payload), encoding="utf-8")

        metadata = {
            "source_id": fetch.source_id,
            "source_name": fetch.source_name,
            "retrieved_at": retrieved_at_iso(),
            "url": fetch.url,
            "method": fetch.method,
            "params": fetch.params,
            "status_code": fetch.status_code,
            "content_type": fetch.content_type,
            "documentation_url": fetch.documentation_url,
            "raw_file": str(raw_file),
        }
        metadata_file.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return StoredRawFetch(raw_file=raw_file, metadata_file=metadata_file)

