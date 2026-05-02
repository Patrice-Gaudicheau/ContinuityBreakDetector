from __future__ import annotations

import os
from typing import Any

from continuity_break_detector.sources.base import RawFetch, RawPayload
from continuity_break_detector.utils.http import HttpClient


class CrossrefConnector:
    name = "Crossref"
    source_id = "crossref"
    base_url = "https://api.crossref.org/v1"
    documentation_url = "https://www.crossref.org/documentation/retrieve-metadata/rest-api/"
    rate_limit_policy = "Public: 5 req/s with concurrency 1; polite: 10 req/s with concurrency 3 when mailto is used."
    output_format = "json"

    def __init__(
        self,
        *,
        year: int = 2020,
        rows: int = 100,
        client: HttpClient | None = None,
    ) -> None:
        self.year = year
        self.rows = rows
        self.mailto = os.getenv("CROSSREF_MAILTO")
        self.client = client or HttpClient(mailto=self.mailto, min_interval_seconds=0.25)

    def fetch(self) -> RawPayload:
        return self.iter_fetches()[0].payload

    def iter_fetches(self) -> list[RawFetch]:
        url = f"{self.base_url}/works"
        params: dict[str, Any] = {
            "rows": self.rows,
            "filter": (f"from-created-date:{self.year}-01-01,until-created-date:{self.year}-12-31"),
        }
        if self.mailto:
            params["mailto"] = self.mailto
        response = self.client.get(url, params=params, headers={"Accept": "application/json"})
        response.raise_for_status()
        return [
            RawFetch(
                source_id=self.source_id,
                source_name=self.name,
                dataset_or_query=f"works_created_{self.year}",
                extension="json",
                payload=response.json(),
                url=url,
                params=params,
                status_code=response.status_code,
                content_type=response.headers.get("content-type", ""),
                documentation_url=self.documentation_url,
            )
        ]
