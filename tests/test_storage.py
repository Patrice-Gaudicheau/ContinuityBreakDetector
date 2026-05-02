from __future__ import annotations

import json

from continuity_break_detector.sources.base import RawFetch, RawStorage


def test_metadata_writer_creates_expected_json(tmp_path) -> None:  # type: ignore[no-untyped-def]
    fetch = RawFetch(
        source_id="example",
        source_name="Example Source",
        dataset_or_query="demo query",
        extension="json",
        payload={"ok": True},
        url="https://example.org/data",
        params={"a": "b"},
        status_code=200,
        content_type="application/json",
        documentation_url="https://example.org/docs",
    )

    stored = RawStorage(raw_dir=tmp_path).write(fetch, timestamp="20200101_000000")
    metadata = json.loads(stored.metadata_file.read_text(encoding="utf-8"))

    assert stored.raw_file.exists()
    assert metadata["source_id"] == "example"
    assert metadata["source_name"] == "Example Source"
    assert metadata["url"] == "https://example.org/data"
    assert metadata["method"] == "GET"
    assert metadata["params"] == {"a": "b"}
    assert metadata["status_code"] == 200
    assert metadata["content_type"] == "application/json"
    assert metadata["documentation_url"] == "https://example.org/docs"
    assert metadata["raw_file"] == str(stored.raw_file)
