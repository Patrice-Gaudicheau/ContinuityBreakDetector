from __future__ import annotations

from typing import Any

from continuity_break_detector.sources.base import RawFetch, RawPayload
from continuity_break_detector.utils.http import HttpClient


class ArxivConnector:
    name = "arXiv"
    source_id = "arxiv"
    base_url = "http://export.arxiv.org/api"
    documentation_url = "https://info.arxiv.org/help/api/user-manual.html"
    rate_limit_policy = "One request every three seconds; single connection at a time."
    output_format = "atom+xml"

    def __init__(
        self,
        *,
        query: str = "all:machine learning",
        start: int = 0,
        max_results: int = 100,
        client: HttpClient | None = None,
    ) -> None:
        self.query = query
        self.start = start
        self.max_results = max_results
        self.client = client or HttpClient(min_interval_seconds=3.0)

    def fetch(self) -> RawPayload:
        return self.iter_fetches()[0].payload

    def iter_fetches(self) -> list[RawFetch]:
        url = f"{self.base_url}/query"
        params: dict[str, Any] = {
            "search_query": self.query,
            "start": self.start,
            "max_results": self.max_results,
            "sortBy": "submittedDate",
            "sortOrder": "ascending",
        }
        response = self.client.get(url, params=params, headers={"Accept": "application/atom+xml"})
        response.raise_for_status()
        return [
            RawFetch(
                source_id=self.source_id,
                source_name=self.name,
                dataset_or_query="machine_learning",
                extension="xml",
                payload=response.text,
                url=url,
                params=params,
                status_code=response.status_code,
                content_type=response.headers.get("content-type", ""),
                documentation_url=self.documentation_url,
            )
        ]

