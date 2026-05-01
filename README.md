# ContinuityBreakDetector

This repository currently implements raw source retrieval plus deterministic
normalization and statistics. It does not include anomaly detection, LLM
processing, interpretation, scoring, dashboards, or agent workflows.

## Implemented sources

- `world_bank_wdi`: World Bank WDI JSON API
- `openalex`: OpenAlex works API
- `arxiv`: arXiv Atom API
- `crossref`: Crossref works API
- `owid`: Our World in Data Grapher Chart API

Raw outputs are written under `data/raw/{source_id}/` with a sibling
`.metadata.json` audit file containing URL, params, status, content type, source
documentation URL, and raw file path.

Run ingestion:

```bash
python -m continuity_break_detector.ingestion.runner
python main.py ingest
```

## Phase 2 deterministic processing

Normalization reads raw Phase 1 files from `data/raw/` and writes yearly time
series with this schema:

```json
{
  "source_id": "string",
  "metric": "string",
  "year": 2020,
  "value": 1.0,
  "unit": null,
  "entity": null
}
```

Run normalization and statistics:

```bash
python main.py normalize
python main.py compute_statistics
```

Normalized outputs are written to
`data/processed/normalized/{source_id}/{metric}.parquet`.

Statistics outputs are written to
`data/processed/statistics/{source_id}/{metric}_statistics.parquet`.

The statistics layer is deterministic only. It computes growth rate, log growth,
acceleration, rolling z-score, rolling mean deviation, and conservative rolling
mean structural-break candidate scores. It does not perform interpretation,
scoring, dashboarding, LLM calls, or anomaly detection.

Optional environment variables:

- `OPENALEX_API_KEY`: passed as OpenAlex `api_key` query parameter.
- `CROSSREF_MAILTO`: passed as Crossref `mailto` query parameter and included in
  the User-Agent.

## Not implemented yet

The following sources are documented in `docs/sources_connection_detail.md` but
are intentionally placeholders for later work:

- OECD
- Eurostat
- IEA
- BP / Energy Institute
- Maddison Project Database
- GitHub
- Dimensions
- UN Population Division API
- UN World Population Prospects bulk files

Crossref cursor pagination is also intentionally deferred for the POC; the
current connector fetches the first filtered page only.
