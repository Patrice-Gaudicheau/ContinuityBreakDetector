from __future__ import annotations

from continuity_break_detector.sources.world_bank import world_bank_total_pages


def test_world_bank_pagination_reads_pages_from_metadata() -> None:
    payload = [
        {"page": 1, "pages": 4, "per_page": 1000, "total": 3200},
        [{"date": "2020", "value": 1}],
    ]

    assert world_bank_total_pages(payload) == 4


def test_world_bank_pagination_defaults_to_one_for_bad_payload() -> None:
    assert world_bank_total_pages({}) == 1
    assert world_bank_total_pages([{"pages": None}]) == 1
