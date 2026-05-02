# Data Sources

This project implements API-first connectors for a small set of public sources
that are suitable for a proof-of-concept continuity-break study.

## Implemented Sources

| Source | Connector | Output |
| --- | --- | --- |
| World Bank WDI | `world_bank_wdi` | JSON |
| OpenAlex | `openalex` | JSON |
| arXiv | `arxiv` | Atom XML |
| Crossref | `crossref` | JSON |
| Our World in Data grapher | `owid` | CSV and metadata JSON |

Raw files are written under `data/raw/{source_id}/` with adjacent metadata JSON.

## Normalized Schema

All normalized outputs use:

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

## Not Implemented Yet

The detailed source plan also documents placeholders for OECD, Eurostat, IEA,
BP / Energy Institute, Maddison, GitHub public activity, Dimensions, and UN
World Population Prospects. They are intentionally excluded from the current
implementation.

## Source Detail

Endpoint-level notes, pagination, formats, and rate-limit constraints are kept
in [sources_connection_detail.md](sources_connection_detail.md).

