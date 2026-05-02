from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from continuity_break_detector.backtesting.ranking import latest_study_folder, min_max_normalize
from continuity_break_detector.backtesting.study import STUDIES_DIR
from continuity_break_detector.storage.parquet import read_parquet, write_parquet


@dataclass(frozen=True)
class AuditParameters:
    pre_post_window_years: int = 10
    top_list_limit: int = 20

    def to_dict(self) -> dict[str, int | dict[str, float]]:
        return {
            "pre_post_window_years": self.pre_post_window_years,
            "top_list_limit": self.top_list_limit,
            "robustness_weights": {
                "model_agreement_score": 0.30,
                "domain_agreement_score": 0.30,
                "normalized_log1p_anomaly_count": 0.20,
                "persistence_score": 0.20,
            },
            "penalties": {
                "sparsity_high": 0.20,
                "sparsity_medium": 0.10,
                "historical_high": 0.15,
                "historical_medium": 0.08,
                "known_explanation_high": 0.10,
            },
        }


@dataclass(frozen=True)
class AuditResult:
    study_path: Path
    candidate_count: int
    strong_count: int
    moderate_count: int
    weak_count: int


def audit_latest_study(
    *,
    studies_dir: Path = STUDIES_DIR,
    parameters: AuditParameters | None = None,
) -> AuditResult:
    return audit_study(latest_study_folder(studies_dir), parameters=parameters)


def audit_study(
    study_path: Path,
    *,
    parameters: AuditParameters | None = None,
) -> AuditResult:
    params = parameters or AuditParameters()
    ranked = read_parquet(study_path / "ranked_break_candidates.parquet")
    forecast_errors = read_parquet(study_path / "forecast_errors.parquet")
    anomalies = read_parquet(study_path / "anomalies.parquet")
    audit = build_candidate_audit(
        ranked,
        forecast_errors,
        anomalies,
        parameters=params,
    )

    write_parquet(audit, study_path / "candidate_audit.parquet")
    payload = build_audit_json(study_path, audit, params)
    write_json(study_path / "candidate_audit.json", payload)
    (study_path / "candidate_audit.md").write_text(build_markdown(payload), encoding="utf-8")

    verdict_counts = payload["verdict_counts"]
    return AuditResult(
        study_path=study_path,
        candidate_count=int(payload["candidate_count"]),
        strong_count=int(verdict_counts.get("strong_candidate", 0)),
        moderate_count=int(verdict_counts.get("moderate_candidate", 0)),
        weak_count=int(verdict_counts.get("weak_candidate", 0)),
    )


def build_candidate_audit(
    ranked: pd.DataFrame,
    forecast_errors: pd.DataFrame,
    anomalies: pd.DataFrame,
    *,
    parameters: AuditParameters | None = None,
) -> pd.DataFrame:
    params = parameters or AuditParameters()
    representatives = ranked[ranked["is_representative"]].copy()
    if representatives.empty:
        return _empty_audit_frame()

    max_domain_count = int(max(1, ranked["affected_domain_count"].max()))
    total_model_counts = _available_model_counts(forecast_errors)
    anomaly_norm = min_max_normalize(np.log1p(representatives["anomaly_count"].astype(float)))

    rows: list[dict[str, Any]] = []
    for position, candidate in enumerate(representatives.to_dict("records")):
        target_year = int(candidate["target_year"])
        year_anomalies = anomalies[anomalies["target_year"] == target_year]
        affected_domains = _as_list(candidate["affected_domains"])
        anomalous_model_count = (
            int(year_anomalies["model"].nunique()) if not year_anomalies.empty else 0
        )
        total_models = int(total_model_counts.get(target_year, 0))
        model_agreement_score = anomalous_model_count / total_models if total_models > 0 else 0.0
        domain_agreement_score = len(affected_domains) / max_domain_count
        pre_count = _window_count(
            forecast_errors,
            start_year=target_year - params.pre_post_window_years,
            end_year=target_year - 1,
        )
        post_count = _window_count(
            forecast_errors,
            start_year=target_year + 1,
            end_year=target_year + params.pre_post_window_years,
        )
        sparsity = sparsity_risk(pre_count, post_count)
        historical = historical_data_risk(target_year)
        hint = _clean_hint(candidate.get("ordinary_explanation_hint"))
        known = known_explanation_risk(hint)
        score = robustness_score(
            model_agreement_score=model_agreement_score,
            domain_agreement_score=domain_agreement_score,
            normalized_anomaly_count=float(anomaly_norm.iloc[position]),
            persistence_score=float(candidate["persistence_score"]),
            sparsity_risk_value=sparsity,
            historical_data_risk_value=historical,
            known_explanation_risk_value=known,
        )
        rows.append(
            {
                "target_year": target_year,
                "rank_score": float(candidate["rank_score"]),
                "robustness_score": score,
                "audit_verdict": audit_verdict(score),
                "affected_domains": affected_domains,
                "source_count": int(year_anomalies["source_id"].nunique()),
                "metric_count": int(year_anomalies["metric"].nunique()),
                "domain_count": len(affected_domains),
                "model_count": anomalous_model_count,
                "anomaly_count": int(candidate["anomaly_count"]),
                "pre_window_data_count": pre_count,
                "post_window_data_count": post_count,
                "model_agreement_score": float(model_agreement_score),
                "domain_agreement_score": float(domain_agreement_score),
                "persistence_score": float(candidate["persistence_score"]),
                "sparsity_risk": sparsity,
                "historical_data_risk": historical,
                "known_explanation_risk": known,
                "ordinary_explanation_hint": hint,
                "audit_notes": audit_notes(sparsity, historical, known, pre_count, post_count),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(
            ["robustness_score", "rank_score"],
            ascending=[False, False],
        )
        .reset_index(drop=True)
    )


def historical_data_risk(year: int) -> str:
    if year < 1900:
        return "high"
    if year < 1950:
        return "medium"
    return "low"


def sparsity_risk(pre_window_data_count: int, post_window_data_count: int) -> str:
    if pre_window_data_count < 10 or post_window_data_count < 10:
        return "high"
    if pre_window_data_count < 25 or post_window_data_count < 25:
        return "medium"
    return "low"


def known_explanation_risk(hint: str | None) -> str:
    return "high" if hint else "low"


def robustness_score(
    *,
    model_agreement_score: float,
    domain_agreement_score: float,
    normalized_anomaly_count: float,
    persistence_score: float,
    sparsity_risk_value: str,
    historical_data_risk_value: str,
    known_explanation_risk_value: str,
) -> float:
    score = (
        0.30 * model_agreement_score
        + 0.30 * domain_agreement_score
        + 0.20 * normalized_anomaly_count
        + 0.20 * persistence_score
    )
    if sparsity_risk_value == "high":
        score -= 0.20
    elif sparsity_risk_value == "medium":
        score -= 0.10
    if historical_data_risk_value == "high":
        score -= 0.15
    elif historical_data_risk_value == "medium":
        score -= 0.08
    if known_explanation_risk_value == "high":
        score -= 0.10
    return float(min(1.0, max(0.0, score)))


def audit_verdict(score: float) -> str:
    if score >= 0.70:
        return "strong_candidate"
    if score >= 0.45:
        return "moderate_candidate"
    return "weak_candidate"


def audit_notes(
    sparsity: str,
    historical: str,
    known: str,
    pre_count: int,
    post_count: int,
) -> list[str]:
    notes: list[str] = []
    if sparsity != "low":
        notes.append(f"{sparsity} sparsity risk: pre={pre_count}, post={post_count}")
    if historical != "low":
        notes.append(f"{historical} historical data risk")
    if known == "high":
        notes.append("known ordinary historical explanation hint exists")
    return notes


def build_audit_json(
    study_path: Path,
    audit: pd.DataFrame,
    parameters: AuditParameters,
) -> dict[str, Any]:
    summary_path = study_path / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    verdict_counts = (
        {
            str(key): int(value)
            for key, value in audit["audit_verdict"].value_counts().to_dict().items()
        }
        if not audit.empty
        else {}
    )
    return {
        "study_id": summary.get("study_id", study_path.name),
        "created_at": datetime.now(UTC).isoformat(),
        "source_study_path": str(study_path),
        "audit_parameters": parameters.to_dict(),
        "candidate_count": int(len(audit)),
        "verdict_counts": verdict_counts,
        "top_strong_candidates": _top_by_verdict(
            audit, "strong_candidate", parameters.top_list_limit
        ),
        "top_moderate_candidates": _top_by_verdict(
            audit, "moderate_candidate", parameters.top_list_limit
        ),
        "top_weak_candidates": _top_by_verdict(audit, "weak_candidate", parameters.top_list_limit),
    }


def build_markdown(payload: dict[str, Any]) -> str:
    verdict_counts = payload["verdict_counts"]
    lines = [
        "# Candidate Audit Report",
        "",
        "## Objective",
        "Evaluate ranked representative break candidates for statistical robustness and data reliability risks.",
        "",
        "## Audit Method",
        "The audit scores model agreement, domain agreement, anomaly volume, and persistence, then applies deterministic penalties for sparse data, older historical years, and exact-year ordinary explanation hints.",
        "",
        "## Verdict Summary",
        f"- strong_candidate: {verdict_counts.get('strong_candidate', 0)}",
        f"- moderate_candidate: {verdict_counts.get('moderate_candidate', 0)}",
        f"- weak_candidate: {verdict_counts.get('weak_candidate', 0)}",
        "",
        "## Strong Candidates",
        *_candidate_lines(payload["top_strong_candidates"]),
        "",
        "## Moderate Candidates",
        *_candidate_lines(payload["top_moderate_candidates"]),
        "",
        "## Weak Candidates",
        *_candidate_lines(payload["top_weak_candidates"]),
        "",
        "## Data Quality Risks",
        "Sparsity and historical-data penalties reduce scores where coverage around the candidate year is thin or where the candidate falls in older historical periods.",
        "",
        "## Known Explanation Risks",
        "Exact-year ordinary explanation hints reduce scores because well-known shocks may explain forecast errors without requiring a novel continuity-break interpretation.",
        "",
        "## Limitations",
        "The audit is deterministic and depends on the Phase 3 backtest outputs. It does not validate source truth, causal mechanisms, or narrative explanations.",
        "",
        "## Conclusion",
        "This audit only evaluates statistical robustness and data reliability. It does not claim simulation results or proof of rapid influx.",
        "",
    ]
    return "\n".join(lines)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _available_model_counts(forecast_errors: pd.DataFrame) -> dict[int, int]:
    if forecast_errors.empty:
        return {}
    return {
        int(year): int(count)
        for year, count in forecast_errors.groupby("target_year")["model"]
        .nunique()
        .to_dict()
        .items()
    }


def _window_count(df: pd.DataFrame, *, start_year: int, end_year: int) -> int:
    if df.empty:
        return 0
    return int(df[(df["target_year"] >= start_year) & (df["target_year"] <= end_year)].shape[0])


def _top_by_verdict(audit: pd.DataFrame, verdict: str, limit: int) -> list[dict[str, Any]]:
    if audit.empty:
        return []
    top = (
        audit[audit["audit_verdict"] == verdict]
        .sort_values(
            ["robustness_score", "rank_score"],
            ascending=[False, False],
        )
        .head(limit)
    )
    return [_json_safe(record) for record in top.to_dict("records")]


def _candidate_lines(candidates: list[dict[str, Any]]) -> list[str]:
    if not candidates:
        return ["- None"]
    lines: list[str] = []
    for item in candidates:
        hint = item.get("ordinary_explanation_hint") or "none"
        lines.append(
            f"- {item['target_year']}: verdict={item['audit_verdict']}, "
            f"robustness={float(item['robustness_score']):.4f}, "
            f"rank={float(item['rank_score']):.4f}, domains={item['affected_domains']}, "
            f"anomalies={item['anomaly_count']}, hint={hint}"
        )
    return lines


def _clean_hint(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def _as_list(value: Any) -> list[str]:
    if value is None or (not isinstance(value, (list, tuple, np.ndarray)) and pd.isna(value)):
        return []
    if isinstance(value, np.ndarray):
        return [str(item) for item in value.tolist()]
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value]
    return [str(value)]


def _json_safe(record: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, np.generic):
            safe[key] = value.item()
        elif isinstance(value, np.ndarray):
            safe[key] = value.tolist()
        elif isinstance(value, list):
            safe[key] = value
        elif pd.isna(value):
            safe[key] = None
        else:
            safe[key] = value
    return safe


def _empty_audit_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "target_year",
            "rank_score",
            "robustness_score",
            "audit_verdict",
            "affected_domains",
            "source_count",
            "metric_count",
            "domain_count",
            "model_count",
            "anomaly_count",
            "pre_window_data_count",
            "post_window_data_count",
            "model_agreement_score",
            "domain_agreement_score",
            "persistence_score",
            "sparsity_risk",
            "historical_data_risk",
            "known_explanation_risk",
            "ordinary_explanation_hint",
            "audit_notes",
        ]
    )
