from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from continuity_break_detector.backtesting.domains import metric_domain
from continuity_break_detector.backtesting.study import STUDIES_DIR
from continuity_break_detector.storage.parquet import read_parquet, write_parquet


EXPLANATION_HINTS: dict[int, str] = {
    1914: "World War I",
    1918: "World War I aftermath and influenza pandemic",
    1929: "Great Depression onset",
    1939: "World War II onset",
    1945: "World War II end and reconstruction",
    1971: "Bretton Woods system collapse",
    1973: "First oil shock",
    1979: "Second oil shock",
    1989: "End of Cold War transition",
    1991: "Soviet Union collapse",
    2000: "Dot-com bubble peak",
    2001: "9/11 shock and recession",
    2008: "Global financial crisis",
    2011: "Eurozone sovereign debt crisis",
    2020: "COVID-19 pandemic shock",
    2022: "Energy shock and inflation surge after Russia invasion of Ukraine",
}


@dataclass(frozen=True)
class RankingParameters:
    neighborhood_years: int = 2
    representative_window_years: int = 3
    top_representative_limit: int = 50

    def to_dict(self) -> dict[str, int | dict[str, float]]:
        return {
            "neighborhood_years": self.neighborhood_years,
            "representative_window_years": self.representative_window_years,
            "top_representative_limit": self.top_representative_limit,
            "rank_score_weights": {
                "mean_z_score": 0.35,
                "affected_domain_count": 0.25,
                "log1p_anomaly_count": 0.20,
                "persistence_score": 0.20,
            },
        }


@dataclass(frozen=True)
class RankingResult:
    study_path: Path
    all_candidates: int
    representative_candidates: int
    top_year: int | None
    top_rank_score: float | None


def latest_study_folder(studies_dir: Path = STUDIES_DIR) -> Path:
    candidates = sorted(path for path in studies_dir.glob("*_rapid_influx_v1") if path.is_dir())
    if not candidates:
        raise FileNotFoundError(f"No backtest study folders found under {studies_dir}")
    return candidates[-1]


def rank_latest_study(
    *,
    studies_dir: Path = STUDIES_DIR,
    parameters: RankingParameters | None = None,
) -> RankingResult:
    return rank_study(latest_study_folder(studies_dir), parameters=parameters)


def rank_study(
    study_path: Path,
    *,
    parameters: RankingParameters | None = None,
) -> RankingResult:
    params = parameters or RankingParameters()
    anomalies = read_parquet(study_path / "anomalies.parquet")
    cross_domain_breaks = read_parquet(study_path / "cross_domain_breaks.parquet")
    ranked = build_ranked_candidates(anomalies, cross_domain_breaks, parameters=params)

    write_parquet(ranked, study_path / "ranked_break_candidates.parquet")
    json_payload = build_ranking_json(study_path, ranked, params)
    write_json(study_path / "ranked_break_candidates.json", json_payload)
    write_json(study_path / "ordinary_explanation_hints.json", EXPLANATION_HINTS)
    (study_path / "top_break_candidates.md").write_text(
        build_markdown(json_payload["top_representative_candidates"]),
        encoding="utf-8",
    )

    representatives = ranked[ranked["is_representative"]] if not ranked.empty else ranked
    top = representatives.sort_values("rank_score", ascending=False).head(1)
    top_year = None if top.empty else int(top.iloc[0]["target_year"])
    top_score = None if top.empty else float(top.iloc[0]["rank_score"])
    return RankingResult(
        study_path=study_path,
        all_candidates=len(ranked),
        representative_candidates=len(representatives),
        top_year=top_year,
        top_rank_score=top_score,
    )


def build_ranked_candidates(
    anomalies: pd.DataFrame,
    cross_domain_breaks: pd.DataFrame,
    *,
    parameters: RankingParameters | None = None,
) -> pd.DataFrame:
    params = parameters or RankingParameters()
    if anomalies.empty:
        return _empty_ranked_frame()

    enriched = anomalies.copy()
    enriched["domain"] = [
        metric_domain(str(row["source_id"]), str(row["metric"]))
        for row in enriched.to_dict("records")
    ]

    rows: list[dict[str, Any]] = []
    for target_year, group in enriched.groupby("target_year", dropna=False):
        target_year_int = int(target_year)
        cross_row = _cross_domain_row(cross_domain_breaks, target_year_int)
        domains = (
            list(cross_row["affected_domains"])
            if cross_row is not None and isinstance(cross_row.get("affected_domains"), list)
            else sorted(str(value) for value in group["domain"].dropna().unique())
        )
        rows.append(
            {
                "target_year": target_year_int,
                "affected_domain_count": len(domains),
                "anomaly_count": int(len(group)),
                "mean_z_score": float(group["z_score"].mean()),
                "max_z_score": float(group["z_score"].max()),
                "p95_z_score": float(group["z_score"].quantile(0.95)),
                "affected_domains": domains,
                "affected_metrics": sorted(str(value) for value in group["metric"].dropna().unique()),
                "affected_sources": sorted(str(value) for value in group["source_id"].dropna().unique()),
                "model_count": int(group["model"].nunique()),
                "persistence_score": 0.0,
                "ordinary_explanation_hint": explanation_hint(target_year_int),
                "rank_score": 0.0,
            }
        )

    ranked = pd.DataFrame(rows)
    anomalous_years = set(int(year) for year in ranked["target_year"])
    ranked["persistence_score"] = [
        persistence_score(int(year), anomalous_years, neighborhood=params.neighborhood_years)
        for year in ranked["target_year"]
    ]
    ranked["rank_score"] = rank_scores(ranked)
    ranked = mark_representatives(ranked, window_years=params.representative_window_years)
    return ranked.sort_values("rank_score", ascending=False).reset_index(drop=True)


def min_max_normalize(values: pd.Series) -> pd.Series:
    values = values.astype(float)
    minimum = values.min()
    maximum = values.max()
    if pd.isna(minimum) or pd.isna(maximum) or minimum == maximum:
        return pd.Series([0.0] * len(values), index=values.index)
    return (values - minimum) / (maximum - minimum)


def persistence_score(target_year: int, anomalous_years: set[int], *, neighborhood: int = 2) -> float:
    years = range(target_year - neighborhood, target_year + neighborhood + 1)
    return sum(1 for year in years if year in anomalous_years) / float(neighborhood * 2 + 1)


def rank_scores(candidates: pd.DataFrame) -> pd.Series:
    mean_z = min_max_normalize(candidates["mean_z_score"])
    domains = min_max_normalize(candidates["affected_domain_count"])
    anomaly_count = min_max_normalize(np.log1p(candidates["anomaly_count"].astype(float)))
    persistence = candidates["persistence_score"].astype(float)
    return 0.35 * mean_z + 0.25 * domains + 0.20 * anomaly_count + 0.20 * persistence


def explanation_hint(year: int) -> str | None:
    return EXPLANATION_HINTS.get(int(year))


def mark_representatives(candidates: pd.DataFrame, *, window_years: int = 3) -> pd.DataFrame:
    if candidates.empty:
        return candidates.assign(is_representative=pd.Series(dtype=bool), representative_year=pd.Series(dtype=int))

    ranked = candidates.sort_values("rank_score", ascending=False).copy()
    representative_for: dict[int, int] = {}
    representatives: list[int] = []
    for row in ranked.to_dict("records"):
        year = int(row["target_year"])
        if year in representative_for:
            continue
        representatives.append(year)
        for nearby_year in range(year - window_years, year + window_years + 1):
            representative_for.setdefault(nearby_year, year)

    result = candidates.copy()
    result["representative_year"] = [
        representative_for.get(int(year), int(year)) for year in result["target_year"]
    ]
    result["is_representative"] = [
        int(year) in representatives for year in result["target_year"]
    ]
    return result


def build_ranking_json(
    study_path: Path,
    ranked: pd.DataFrame,
    parameters: RankingParameters,
) -> dict[str, Any]:
    summary_path = study_path / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    representatives = ranked[ranked["is_representative"]] if not ranked.empty else ranked
    top = representatives.sort_values("rank_score", ascending=False).head(
        parameters.top_representative_limit
    )
    return {
        "study_id": summary.get("study_id", study_path.name),
        "created_at": datetime.now(UTC).isoformat(),
        "source_study_path": str(study_path),
        "ranking_parameters": parameters.to_dict(),
        "top_representative_candidates": [_json_safe(record) for record in top.to_dict("records")],
        "all_candidates_count": int(len(ranked)),
        "representative_candidates_count": int(len(representatives)),
    }


def build_markdown(top_candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# Ranked Continuity Break Candidates",
        "",
        "## Objective",
        "Reduce noisy backtest anomaly outputs into a smaller deterministic set of ranked continuity break candidates.",
        "",
        "## Ranking Method",
        "Candidates are aggregated by target year and ranked using normalized mean z-score, affected domain count, log anomaly count, and five-year persistence.",
        "",
        "## Top 20 Representative Candidates",
    ]
    for item in top_candidates[:20]:
        hint = item.get("ordinary_explanation_hint") or "none"
        lines.extend([
            f"### {item['target_year']}",
            f"- rank_score: {float(item['rank_score']):.4f}",
            f"- affected_domains: {item['affected_domains']}",
            f"- anomaly_count: {item['anomaly_count']}",
            f"- mean_z_score: {float(item['mean_z_score']):.4f}",
            f"- max_z_score: {float(item['max_z_score']):.4f}",
            f"- persistence_score: {float(item['persistence_score']):.4f}",
            f"- ordinary_explanation_hint: {hint}",
            "",
        ])
    if not top_candidates:
        lines.append("No representative candidates were produced.")
        lines.append("")

    hinted = [item for item in top_candidates[:20] if item.get("ordinary_explanation_hint")]
    lines.extend([
        "## Ordinary Explanation Hints",
        "Hints are exact-year dictionary matches only; no explanation is inferred.",
    ])
    if hinted:
        lines.extend(
            f"- {item['target_year']}: {item['ordinary_explanation_hint']}"
            for item in hinted
        )
    else:
        lines.append("- No exact-year hints matched the top candidates.")
    lines.extend([
        "",
        "## Notes and Limitations",
        "These rankings are deterministic filters over forecast-error anomalies. Source coverage, sparse historical data, and baseline-model limits can affect the ordering.",
        "",
        "## Conclusion",
        "These are statistical candidates requiring interpretation. They are not simulations, proof of rapid influx, or causal explanations.",
        "",
    ])
    return "\n".join(lines)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _cross_domain_row(df: pd.DataFrame, target_year: int) -> dict[str, Any] | None:
    if df.empty:
        return None
    matches = df[df["target_year"] == target_year]
    if matches.empty:
        return None
    return matches.iloc[0].to_dict()


def _empty_ranked_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "target_year",
            "affected_domain_count",
            "anomaly_count",
            "mean_z_score",
            "max_z_score",
            "p95_z_score",
            "affected_domains",
            "affected_metrics",
            "affected_sources",
            "model_count",
            "persistence_score",
            "ordinary_explanation_hint",
            "rank_score",
            "is_representative",
            "representative_year",
        ]
    )


def _json_safe(record: dict[str, Any]) -> dict[str, Any]:
    safe: dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, np.generic):
            safe[key] = value.item()
        elif (pd.isna(value) if not isinstance(value, list) else False):
            safe[key] = None
        else:
            safe[key] = value
    return safe
