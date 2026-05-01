from __future__ import annotations

from continuity_break_detector.backtesting.audit import (
    audit_verdict,
    historical_data_risk,
    known_explanation_risk,
    robustness_score,
    sparsity_risk,
)


def test_historical_data_risk_classification() -> None:
    assert historical_data_risk(1899) == "high"
    assert historical_data_risk(1900) == "medium"
    assert historical_data_risk(1949) == "medium"
    assert historical_data_risk(1950) == "low"


def test_sparsity_risk_classification() -> None:
    assert sparsity_risk(9, 100) == "high"
    assert sparsity_risk(100, 9) == "high"
    assert sparsity_risk(24, 100) == "medium"
    assert sparsity_risk(25, 25) == "low"


def test_known_explanation_risk_classification() -> None:
    assert known_explanation_risk("Global financial crisis") == "high"
    assert known_explanation_risk(None) == "low"


def test_robustness_score_penalty_application() -> None:
    score = robustness_score(
        model_agreement_score=1.0,
        domain_agreement_score=1.0,
        normalized_anomaly_count=1.0,
        persistence_score=1.0,
        sparsity_risk_value="high",
        historical_data_risk_value="medium",
        known_explanation_risk_value="high",
    )

    assert round(score, 6) == 0.62


def test_audit_verdict_classification() -> None:
    assert audit_verdict(0.70) == "strong_candidate"
    assert audit_verdict(0.45) == "moderate_candidate"
    assert audit_verdict(0.44) == "weak_candidate"

