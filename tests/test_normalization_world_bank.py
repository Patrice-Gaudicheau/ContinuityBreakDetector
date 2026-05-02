from __future__ import annotations

from continuity_break_detector.normalization.world_bank import normalize_payload


def test_world_bank_normalization_from_fixture() -> None:
    payload = {
        "indicator": "SP.POP.TOTL",
        "pages": [
            [
                {"page": 1, "pages": 1},
                [
                    {
                        "country": {"id": "FR", "value": "France"},
                        "countryiso3code": "FRA",
                        "date": "2020",
                        "value": 67000000,
                        "unit": "",
                    }
                ],
            ]
        ],
    }

    normalized = normalize_payload(payload, "SP.POP.TOTL")

    assert normalized.to_dict("records") == [
        {
            "source_id": "world_bank_wdi",
            "metric": "SP.POP.TOTL",
            "year": 2020,
            "value": 67000000.0,
            "unit": None,
            "entity": "FRA",
        }
    ]
