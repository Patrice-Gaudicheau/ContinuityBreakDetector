# ContinuityBreakDetector

This repository currently implements only the raw source retrieval layer. It does
not include anomaly detection, LLM processing, interpretation, scoring,
dashboards, normalization, or analysis.

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

