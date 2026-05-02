from __future__ import annotations

from dataclasses import dataclass

from continuity_break_detector.sources.arxiv import ArxivConnector
from continuity_break_detector.sources.base import SourceConnector
from continuity_break_detector.sources.crossref import CrossrefConnector
from continuity_break_detector.sources.openalex import OpenAlexConnector
from continuity_break_detector.sources.owid import OwidConnector
from continuity_break_detector.sources.world_bank import WorldBankConnector

IMPLEMENTED_SOURCE_IDS = (
    "world_bank_wdi",
    "openalex",
    "arxiv",
    "crossref",
    "owid",
)


NOT_IMPLEMENTED_SOURCE_IDS = {
    "oecd": "Documented in sources_connection_detail.md; connector intentionally deferred.",
    "eurostat": "Documented in sources_connection_detail.md; connector intentionally deferred.",
    "iea": "Documented in sources_connection_detail.md; connector intentionally deferred.",
    "bp_energy_institute": "Documented in sources_connection_detail.md; connector intentionally deferred.",
    "maddison": "Documented in sources_connection_detail.md; connector intentionally deferred.",
    "github": "Documented in sources_connection_detail.md; connector intentionally deferred.",
    "dimensions": "Documented in sources_connection_detail.md; connector intentionally deferred.",
    "un_wpp": "Documented in sources_connection_detail.md; connector intentionally deferred.",
    "un_population_division": "Documented in sources_connection_detail.md; connector intentionally deferred.",
}


@dataclass(frozen=True)
class SourceRegistry:
    implemented: dict[str, SourceConnector]
    not_implemented: dict[str, str]


def build_registry() -> SourceRegistry:
    connectors: list[SourceConnector] = [
        WorldBankConnector(),
        OpenAlexConnector(),
        ArxivConnector(),
        CrossrefConnector(),
        OwidConnector(),
    ]
    return SourceRegistry(
        implemented={connector.source_id: connector for connector in connectors},
        not_implemented=dict(NOT_IMPLEMENTED_SOURCE_IDS),
    )
