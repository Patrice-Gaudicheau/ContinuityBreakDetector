from __future__ import annotations

from continuity_break_detector.sources.owid import build_owid_urls


def test_owid_url_builder_returns_csv_and_metadata_urls() -> None:
    csv_url, metadata_url = build_owid_urls("life-expectancy")

    assert csv_url == "https://ourworldindata.org/grapher/life-expectancy.csv"
    assert metadata_url == "https://ourworldindata.org/grapher/life-expectancy.metadata.json"

