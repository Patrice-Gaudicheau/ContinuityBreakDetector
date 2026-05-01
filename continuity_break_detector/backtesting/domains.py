from __future__ import annotations

import pandas as pd


CROSS_DOMAIN_COLUMNS = [
    "target_year",
    "affected_domains",
    "affected_domain_count",
    "anomaly_count",
    "aggregate_score",
    "items",
]


def metric_domain(source_id: str, metric: str) -> str:
    text = f"{source_id} {metric}"
    if any(token in text for token in ("gdp", "GDP", "NY.GDP")):
        return "economics"
    if any(token in text for token in ("population", "SP.POP")):
        return "demographics"
    if any(token in text for token in ("openalex", "arxiv", "crossref", "works", "publication")):
        return "science"
    if "life_expectancy" in text or "life-expectancy" in text:
        return "health"
    return "other"


def build_cross_domain_breaks(anomalies: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    if anomalies.empty:
        return pd.DataFrame(columns=CROSS_DOMAIN_COLUMNS)

    enriched = anomalies.copy()
    enriched["domain"] = [
        metric_domain(str(row["source_id"]), str(row["metric"]))
        for row in enriched.to_dict("records")
    ]
    for target_year, group in enriched.groupby("target_year", dropna=False):
        domains = sorted(str(domain) for domain in group["domain"].dropna().unique())
        items = [
            {
                "source_id": str(row["source_id"]),
                "metric": str(row["metric"]),
                "model": str(row["model"]),
            }
            for row in group[["source_id", "metric", "model"]].drop_duplicates().to_dict("records")
        ]
        rows.append(
            {
                "target_year": int(target_year),
                "affected_domains": domains,
                "affected_domain_count": len(domains),
                "anomaly_count": int(len(group)),
                "aggregate_score": float(group["z_score"].mean()),
                "items": items,
            }
        )
    return pd.DataFrame(rows, columns=CROSS_DOMAIN_COLUMNS).sort_values(
        ["aggregate_score", "anomaly_count"],
        ascending=[False, False],
    )

