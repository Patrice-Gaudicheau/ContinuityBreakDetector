from __future__ import annotations

import os
from typing import Any

from continuity_break_detector.sources.base import RawFetch, RawPayload
from continuity_break_detector.utils.http import HttpClient


class OpenAlexConnector:
    name = "OpenAlex"
    source_id = "openalex"
    base_url = "https://api.openalex.org"
    documentation_url = "https://developers.openalex.org/api-reference/introduction"
    rate_limit_policy = "100 requests/second; per_page max 100; cursor paging recommended."
    output_format = "json"

    def __init__(
        self,
        *,
        start_year: int = 2020,
        end_year: int = 2024,
        max_pages: int = 1,
        client: HttpClient | None = None,
    ) -> None:
        self.start_year = start_year
        self.end_year = end_year
        self.max_pages = max_pages
        self.client = client or HttpClient()
        self.api_key = os.getenv("OPENALEX_API_KEY")

    def fetch(self) -> RawPayload:
        return [fetch.payload for fetch in self.iter_fetches()]

    def iter_fetches(self) -> list[RawFetch]:
        fetches: list[RawFetch] = []
        url = f"{self.base_url}/works"
        for year in range(self.start_year, self.end_year + 1):
            cursor = "*"
            for page_number in range(1, self.max_pages + 1):
                params: dict[str, Any] = {
                    "filter": f"publication_year:{year}",
                    "per_page": 100,
                    "cursor": cursor,
                }
                if self.api_key:
                    params["api_key"] = self.api_key
                response = self.client.get(url, params=params, headers={"Accept": "application/json"})
                response.raise_for_status()
                payload = response.json()
                fetches.append(
                    RawFetch(
                        source_id=self.source_id,
                        source_name=self.name,
                        dataset_or_query=f"works_publication_year_{year}_page_{page_number}",
                        extension="json",
                        payload=payload,
                        url=url,
                        params=params,
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type", ""),
                        documentation_url=self.documentation_url,
                    )
                )
                cursor = payload.get("meta", {}).get("next_cursor")
                if not cursor or not payload.get("results"):
                    break
        return fetches

