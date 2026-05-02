from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from continuity_break_detector.backtesting.ranking import latest_study_folder
from continuity_break_detector.backtesting.study import STUDIES_DIR
from continuity_break_detector.storage.parquet import read_parquet, write_parquet

REVISION_ARTIFACT_HINTS = {
    2012: "possible global data revision or methodology artifact",
    2016: "possible global data revision or methodology artifact",
}


@dataclass(frozen=True)
class ArtifactParameters:
    source_dominance_threshold: float = 0.80
    extreme_max_z_threshold: float = 100.0
    extreme_mean_z_threshold: float = 50.0
    echo_window_years: int = 5

    def to_dict(self) -> dict[str, float | int]:
        return {
            "source_dominance_threshold": self.source_dominance_threshold,
            "extreme_max_z_threshold": self.extreme_max_z_threshold,
            "extreme_mean_z_threshold": self.extreme_mean_z_threshold,
            "echo_window_years": self.echo_window_years,
        }


@dataclass(frozen=True)
class ArtifactResult:
    study_path: Path
    candidate_count: int
    likely_count: int
    possible_count: int
    low_count: int


def detect_latest_study_artifacts(
    *,
    studies_dir: Path = STUDIES_DIR,
    parameters: ArtifactParameters | None = None,
) -> ArtifactResult:
    return detect_study_artifacts(latest_study_folder(studies_dir), parameters=parameters)


def detect_study_artifacts(
    study_path: Path,
    *,
    parameters: ArtifactParameters | None = None,
) -> ArtifactResult:
    params = parameters or ArtifactParameters()
    ranked = read_parquet(study_path / "ranked_break_candidates.parquet")
    candidate_audit = read_parquet(study_path / "candidate_audit.parquet")
    anomalies = read_parquet(study_path / "anomalies.parquet")
    artifact_audit = build_data_artifact_audit(
        ranked=ranked,
        candidate_audit=candidate_audit,
        anomalies=anomalies,
        parameters=params,
    )

    write_parquet(artifact_audit, study_path / "data_artifact_audit.parquet")
    payload = build_artifact_json(study_path, artifact_audit, params)
    write_json(study_path / "data_artifact_audit.json", payload)
    (study_path / "data_artifact_audit.md").write_text(
        build_markdown(payload),
        encoding="utf-8",
    )
    counts = payload["verdict_counts"]
    return ArtifactResult(
        study_path=study_path,
        candidate_count=int(payload["candidate_count"]),
        likely_count=int(counts.get("likely_data_artifact", 0)),
        possible_count=int(counts.get("possible_data_artifact", 0)),
        low_count=int(counts.get("low_artifact_risk", 0)),
    )


def build_data_artifact_audit(
    *,
    ranked: pd.DataFrame,
    candidate_audit: pd.DataFrame,
    anomalies: pd.DataFrame,
    parameters: ArtifactParameters | None = None,
) -> pd.DataFrame:
    params = parameters or ArtifactParameters()
    representatives = ranked[ranked["is_representative"]].copy()
    if representatives.empty:
        return _empty_artifact_frame()

    audit_by_year = {int(row["target_year"]): row for row in candidate_audit.to_dict("records")}
    ranked_by_year = {int(row["target_year"]): row for row in representatives.to_dict("records")}
    rows: list[dict[str, Any]] = []
    for candidate in representatives.to_dict("records"):
        target_year = int(candidate["target_year"])
        audit_row = audit_by_year.get(target_year, {})
        year_anomalies = anomalies[anomalies["target_year"] == target_year]
        dominance = source_dominance(
            year_anomalies,
            source_count=int(audit_row.get("source_count", 0)),
            threshold=params.source_dominance_threshold,
        )
        extreme = extreme_z_score_risk(
            max_z_score=float(candidate["max_z_score"]),
            mean_z_score=float(candidate["mean_z_score"]),
            max_threshold=params.extreme_max_z_threshold,
            mean_threshold=params.extreme_mean_z_threshold,
        )
        historical = historical_coverage_risk(
            target_year=target_year,
            historical_data_risk_value=str(audit_row.get("historical_data_risk", "low")),
        )
        hint = revision_artifact_hint(target_year)
        echo_years = model_echo_neighbor_years(
            target_year=target_year,
            ranked_by_year=ranked_by_year,
            model_agreement_score=float(audit_row.get("model_agreement_score", 0.0)),
            window_years=params.echo_window_years,
        )
        known_hint = _clean_hint(candidate.get("ordinary_explanation_hint"))
        known_event = known_hint is not None
        score = artifact_score(
            single_source_dominance=dominance["single_source_dominance"],
            extreme_z_score_risk=extreme,
            historical_coverage_risk=historical,
            has_revision_artifact_hint=hint is not None,
            model_echo_risk=bool(echo_years),
            known_real_world_event=known_event,
        )
        rows.append(
            {
                "target_year": target_year,
                "rank_score": float(candidate["rank_score"]),
                "robustness_score": float(audit_row.get("robustness_score", np.nan)),
                "artifact_score": score,
                "artifact_verdict": artifact_verdict(score),
                "single_source_dominance": dominance["single_source_dominance"],
                "dominant_source_id": dominance["dominant_source_id"],
                "dominant_source_share": dominance["dominant_source_share"],
                "extreme_z_score_risk": extreme,
                "historical_coverage_risk": historical,
                "revision_artifact_hint": hint,
                "model_echo_risk": bool(echo_years),
                "echo_neighbor_years": echo_years,
                "known_real_world_event": known_event,
                "ordinary_explanation_hint": known_hint,
                "notes": artifact_notes(
                    dominance=dominance,
                    extreme=extreme,
                    historical=historical,
                    revision_hint=hint,
                    echo_years=echo_years,
                    known_event=known_event,
                ),
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(
            ["artifact_score", "rank_score"],
            ascending=[False, False],
        )
        .reset_index(drop=True)
    )


def source_dominance(
    anomalies: pd.DataFrame,
    *,
    source_count: int,
    threshold: float = 0.80,
) -> dict[str, Any]:
    if anomalies.empty:
        return {
            "single_source_dominance": source_count <= 1,
            "dominant_source_id": None,
            "dominant_source_share": 0.0,
        }
    source_counts = anomalies["source_id"].value_counts()
    dominant_source_id = str(source_counts.index[0])
    dominant_share = dominant_source_share(source_counts)
    return {
        "single_source_dominance": source_count <= 1 or dominant_share >= threshold,
        "dominant_source_id": dominant_source_id,
        "dominant_source_share": dominant_share,
    }


def dominant_source_share(source_counts: pd.Series) -> float:
    total = int(source_counts.sum())
    if total <= 0:
        return 0.0
    return float(source_counts.max() / total)


def extreme_z_score_risk(
    *,
    max_z_score: float,
    mean_z_score: float,
    max_threshold: float = 100.0,
    mean_threshold: float = 50.0,
) -> bool:
    return max_z_score >= max_threshold or mean_z_score >= mean_threshold


def historical_coverage_risk(*, target_year: int, historical_data_risk_value: str) -> bool:
    return target_year < 1900 or historical_data_risk_value == "high"


def revision_artifact_hint(target_year: int) -> str | None:
    return REVISION_ARTIFACT_HINTS.get(int(target_year))


def model_echo_neighbor_years(
    *,
    target_year: int,
    ranked_by_year: dict[int, dict[str, Any]],
    model_agreement_score: float,
    window_years: int = 5,
) -> list[int]:
    if model_agreement_score != 1.0:
        return []
    current = ranked_by_year.get(target_year)
    if current is None:
        return []
    current_metrics = set(_as_list(current.get("affected_metrics")))
    if not current_metrics:
        return []
    neighbors: list[int] = []
    for year, candidate in ranked_by_year.items():
        if year == target_year or abs(year - target_year) > window_years:
            continue
        if set(_as_list(candidate.get("affected_metrics"))) == current_metrics:
            neighbors.append(int(year))
    return sorted(neighbors)


def artifact_score(
    *,
    single_source_dominance: bool,
    extreme_z_score_risk: bool,
    historical_coverage_risk: bool,
    has_revision_artifact_hint: bool,
    model_echo_risk: bool,
    known_real_world_event: bool,
) -> float:
    score = (
        0.25 * float(single_source_dominance)
        + 0.25 * float(extreme_z_score_risk)
        + 0.20 * float(historical_coverage_risk)
        + 0.15 * float(has_revision_artifact_hint)
        + 0.15 * float(model_echo_risk)
    )
    if known_real_world_event:
        score -= 0.15
    return float(min(1.0, max(0.0, score)))


def artifact_verdict(score: float) -> str:
    if score >= 0.60:
        return "likely_data_artifact"
    if score >= 0.35:
        return "possible_data_artifact"
    return "low_artifact_risk"


def artifact_notes(
    *,
    dominance: dict[str, Any],
    extreme: bool,
    historical: bool,
    revision_hint: str | None,
    echo_years: list[int],
    known_event: bool,
) -> list[str]:
    notes: list[str] = []
    if dominance["single_source_dominance"]:
        notes.append(
            f"source dominance: {dominance['dominant_source_id']} share={dominance['dominant_source_share']:.3f}"
        )
    if extreme:
        notes.append("extreme z-score risk")
    if historical:
        notes.append("historical coverage risk")
    if revision_hint:
        notes.append(revision_hint)
    if echo_years:
        notes.append(f"model echo neighbors: {echo_years}")
    if known_event:
        notes.append("known ordinary real-world event hint lowers artifact score")
    return notes


def build_artifact_json(
    study_path: Path,
    artifact_audit: pd.DataFrame,
    parameters: ArtifactParameters,
) -> dict[str, Any]:
    summary_path = study_path / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    verdict_counts = (
        {
            str(key): int(value)
            for key, value in artifact_audit["artifact_verdict"].value_counts().to_dict().items()
        }
        if not artifact_audit.empty
        else {}
    )
    return {
        "study_id": summary.get("study_id", study_path.name),
        "created_at": datetime.now(UTC).isoformat(),
        "source_study_path": str(study_path),
        "artifact_parameters": parameters.to_dict(),
        "candidate_count": int(len(artifact_audit)),
        "verdict_counts": verdict_counts,
        "likely_data_artifacts": _top_by_verdict(artifact_audit, "likely_data_artifact"),
        "possible_data_artifacts": _top_by_verdict(artifact_audit, "possible_data_artifact"),
        "low_artifact_risk_candidates": _top_by_verdict(artifact_audit, "low_artifact_risk"),
    }


def build_markdown(payload: dict[str, Any]) -> str:
    counts = payload["verdict_counts"]
    lines = [
        "# Data Artifact Audit",
        "",
        "## Objective",
        "Identify ranked continuity break candidates with deterministic indicators of data-artifact risk.",
        "",
        "## Method",
        "The audit checks single-source dominance, extreme z-scores, historical coverage risk, revision hints, model echo risk, and known real-world event hints.",
        "",
        "## Verdict Summary",
        f"- likely_data_artifact: {counts.get('likely_data_artifact', 0)}",
        f"- possible_data_artifact: {counts.get('possible_data_artifact', 0)}",
        f"- low_artifact_risk: {counts.get('low_artifact_risk', 0)}",
        "",
        "## Likely Data Artifacts",
        *_candidate_lines(payload["likely_data_artifacts"]),
        "",
        "## Possible Data Artifacts",
        *_candidate_lines(payload["possible_data_artifacts"]),
        "",
        "## Low Artifact Risk Candidates",
        *_candidate_lines(payload["low_artifact_risk_candidates"]),
        "",
        "## Notes on 1848",
        _notes_for_year(payload, 1848),
        "",
        "## Notes on 2012 and 2016",
        _notes_for_year(payload, 2012),
        _notes_for_year(payload, 2016),
        "",
        "## Limitations",
        "This module uses deterministic indicators only. It does not inspect source files manually, verify source methodology, or prove that a candidate is an artifact.",
        "",
        "## Conclusion",
        "The audit detects data-artifact risk indicators, not certainty that a candidate is fake. Candidates require source-level validation before interpretation.",
        "",
    ]
    return "\n".join(lines)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _top_by_verdict(df: pd.DataFrame, verdict: str, limit: int = 20) -> list[dict[str, Any]]:
    if df.empty:
        return []
    top = (
        df[df["artifact_verdict"] == verdict]
        .sort_values(
            ["artifact_score", "rank_score"],
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
        lines.append(
            f"- {item['target_year']}: verdict={item['artifact_verdict']}, "
            f"artifact_score={float(item['artifact_score']):.3f}, "
            f"rank_score={float(item['rank_score']):.3f}, "
            f"dominant_source={item['dominant_source_id']}, "
            f"dominant_share={float(item['dominant_source_share']):.3f}, "
            f"notes={item['notes']}"
        )
    return lines


def _notes_for_year(payload: dict[str, Any], year: int) -> str:
    for key in [
        "likely_data_artifacts",
        "possible_data_artifacts",
        "low_artifact_risk_candidates",
    ]:
        for item in payload[key]:
            if int(item["target_year"]) == year:
                return (
                    f"- {year}: {item['artifact_verdict']} with score "
                    f"{float(item['artifact_score']):.3f}; notes={item['notes']}"
                )
    return f"- {year}: not present in top artifact output lists."


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


def _empty_artifact_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "target_year",
            "rank_score",
            "robustness_score",
            "artifact_score",
            "artifact_verdict",
            "single_source_dominance",
            "dominant_source_id",
            "dominant_source_share",
            "extreme_z_score_risk",
            "historical_coverage_risk",
            "revision_artifact_hint",
            "model_echo_risk",
            "echo_neighbor_years",
            "known_real_world_event",
            "ordinary_explanation_hint",
            "notes",
        ]
    )
