from __future__ import annotations

from typing import Any

from continuity_break_detector.sources.base import RawFetch, RawPayload
from continuity_break_detector.utils.http import HttpClient


class WorldBankConnector:
    name = "World Bank WDI"
    source_id = "world_bank_wdi"
    base_url = "https://api.worldbank.org/v2"
    documentation_url = (
        "https://datahelpdesk.worldbank.org/knowledgebase/articles/"
        "889392-about-the-indicators-api-documentation"
    )
    rate_limit_policy = "Undocumented in source connection document."
    output_format = "json"

    def __init__(
        self,
        *,
        indicators: list[str] | None = None,
        per_page: int = 1000,
        client: HttpClient | None = None,
    ) -> None:
        self.indicators = indicators or [
            "SP.POP.TOTL",
            "NY.GDP.MKTP.CD",
            "NY.GDP.PCAP.CD",
        ]
        self.per_page = per_page
        self.client = client or HttpClient()

    def fetch(self) -> RawPayload:
        return [fetch.payload for fetch in self.iter_fetches()]

    def iter_fetches(self) -> list[RawFetch]:
        fetches: list[RawFetch] = []
        for indicator in self.indicators:
            pages: list[dict[str, Any] | list[Any]] = []
            total_pages = 1
            page = 1
            while page <= total_pages:
                payload, raw_fetch = self._fetch_page(indicator, page)
                pages.append(payload)
                fetches.append(raw_fetch)
                total_pages = world_bank_total_pages(payload)
                page += 1
            fetches.append(
                RawFetch(
                    source_id=self.source_id,
                    source_name=self.name,
                    dataset_or_query=f"{indicator}_combined",
                    extension="json",
                    payload={"indicator": indicator, "pages": pages},
                    url=self._indicator_url(indicator),
                    params={"format": "json", "per_page": self.per_page, "pages": total_pages},
                    status_code=200,
                    content_type="application/json",
                    documentation_url=self.documentation_url,
                )
            )
        return fetches

    def _fetch_page(self, indicator: str, page: int) -> tuple[RawPayload, RawFetch]:
        url = self._indicator_url(indicator)
        params = {"format": "json", "per_page": self.per_page, "page": page}
        response = self.client.get(url, params=params, headers={"Accept": "application/json"})
        response.raise_for_status()
        payload = response.json()
        return payload, RawFetch(
            source_id=self.source_id,
            source_name=self.name,
            dataset_or_query=f"{indicator}_page_{page}",
            extension="json",
            payload=payload,
            url=url,
            params=params,
            status_code=response.status_code,
            content_type=response.headers.get("content-type", ""),
            documentation_url=self.documentation_url,
        )

    def _indicator_url(self, indicator: str) -> str:
        return f"{self.base_url}/country/all/indicator/{indicator}"


def world_bank_total_pages(payload: RawPayload) -> int:
    if not isinstance(payload, list) or not payload:
        return 1
    metadata = payload[0]
    if not isinstance(metadata, dict):
        return 1
    pages = metadata.get("pages", 1)
    try:
        return max(1, int(pages))
    except (TypeError, ValueError):
        return 1
