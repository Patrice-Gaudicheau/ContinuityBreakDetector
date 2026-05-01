from __future__ import annotations

from continuity_break_detector.normalization.openalex import normalize_payload


def test_openalex_yearly_count_normalization_from_fixture() -> None:
    payload = {"meta": {"count": 12345}, "results": [{"id": "https://openalex.org/W1"}]}

    normalized = normalize_payload(payload, 2020)

    assert normalized.to_dict("records") == [
        {
            "source_id": "openalex",
            "metric": "works_count",
            "year": 2020,
            "value": 12345.0,
            "unit": "works",
            "entity": None,
        }
    ]

