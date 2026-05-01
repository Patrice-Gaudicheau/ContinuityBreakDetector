from __future__ import annotations

from continuity_break_detector.sources.base import RawFetch, RawPayload
from continuity_break_detector.utils.http import HttpClient


class OwidConnector:
    name = "Our World in Data Chart API"
    source_id = "owid"
    base_url = "https://ourworldindata.org"
    documentation_url = "https://docs.owid.io/projects/etl/api/chart-api/"
    rate_limit_policy = "Undocumented in source connection document."
    output_format = "csv and metadata.json"

    def __init__(
        self,
        *,
        slugs: list[str] | None = None,
        client: HttpClient | None = None,
    ) -> None:
        self.slugs = slugs or [
            "life-expectancy",
            "population",
            "gdp-per-capita-worldbank",
        ]
        self.client = client or HttpClient()

    def fetch(self) -> RawPayload:
        return [fetch.payload for fetch in self.iter_fetches()]

    def iter_fetches(self) -> list[RawFetch]:
        fetches: list[RawFetch] = []
        for slug in self.slugs:
            csv_url, metadata_url = build_owid_urls(slug)
            csv_response = self.client.get(csv_url, headers={"Accept": "text/csv"})
            csv_response.raise_for_status()
            fetches.append(
                RawFetch(
                    source_id=self.source_id,
                    source_name=self.name,
                    dataset_or_query=f"{slug}_csv",
                    extension="csv",
                    payload=csv_response.text,
                    url=csv_url,
                    params={},
                    status_code=csv_response.status_code,
                    content_type=csv_response.headers.get("content-type", ""),
                    documentation_url=self.documentation_url,
                )
            )

            metadata_response = self.client.get(
                metadata_url,
                headers={"Accept": "application/json"},
            )
            metadata_response.raise_for_status()
            fetches.append(
                RawFetch(
                    source_id=self.source_id,
                    source_name=self.name,
                    dataset_or_query=f"{slug}_source_metadata",
                    extension="json",
                    payload=metadata_response.json(),
                    url=metadata_url,
                    params={},
                    status_code=metadata_response.status_code,
                    content_type=metadata_response.headers.get("content-type", ""),
                    documentation_url=self.documentation_url,
                )
            )
        return fetches


def build_owid_urls(slug: str) -> tuple[str, str]:
    base = f"https://ourworldindata.org/grapher/{slug}"
    return f"{base}.csv", f"{base}.metadata.json"

