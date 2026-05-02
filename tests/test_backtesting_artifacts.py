from __future__ import annotations

import pandas as pd

from continuity_break_detector.backtesting.artifacts import (
    artifact_score,
    artifact_verdict,
    dominant_source_share,
    extreme_z_score_risk,
    model_echo_neighbor_years,
    revision_artifact_hint,
    source_dominance,
)


def test_single_source_dominance() -> None:
    anomalies = pd.DataFrame({"source_id": ["owid", "owid", "world_bank_wdi"]})

    result = source_dominance(anomalies, source_count=1)

    assert result["single_source_dominance"] is True
    assert result["dominant_source_id"] == "owid"


def test_dominant_source_share_calculation() -> None:
    counts = pd.Series({"owid": 8, "world_bank_wdi": 2})

    assert dominant_source_share(counts) == 0.8


def test_extreme_z_score_risk() -> None:
    assert extreme_z_score_risk(max_z_score=100.0, mean_z_score=1.0) is True
    assert extreme_z_score_risk(max_z_score=1.0, mean_z_score=50.0) is True
    assert extreme_z_score_risk(max_z_score=99.0, mean_z_score=49.0) is False


def test_revision_hint_lookup() -> None:
    assert revision_artifact_hint(2012) == "possible global data revision or methodology artifact"
    assert revision_artifact_hint(2016) == "possible global data revision or methodology artifact"
    assert revision_artifact_hint(2017) is None


def test_model_echo_risk_detection() -> None:
    ranked_by_year = {
        2012: {"affected_metrics": ["a", "b"]},
        2016: {"affected_metrics": ["b", "a"]},
        2022: {"affected_metrics": ["a", "b"]},
    }

    result = model_echo_neighbor_years(
        target_year=2012,
        ranked_by_year=ranked_by_year,
        model_agreement_score=1.0,
        window_years=5,
    )

    assert result == [2016]


def test_artifact_score_calculation() -> None:
    result = artifact_score(
        single_source_dominance=True,
        extreme_z_score_risk=True,
        historical_coverage_risk=True,
        has_revision_artifact_hint=True,
        model_echo_risk=True,
        known_real_world_event=True,
    )

    assert round(result, 6) == 0.85


def test_artifact_verdict_classification() -> None:
    assert artifact_verdict(0.60) == "likely_data_artifact"
    assert artifact_verdict(0.35) == "possible_data_artifact"
    assert artifact_verdict(0.34) == "low_artifact_risk"
