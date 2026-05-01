from __future__ import annotations

from continuity_break_detector.sources.registry import IMPLEMENTED_SOURCE_IDS, build_registry


def test_registry_loads_implemented_connectors() -> None:
    registry = build_registry()

    assert set(registry.implemented) == set(IMPLEMENTED_SOURCE_IDS)
    for source_id, connector in registry.implemented.items():
        assert connector.source_id == source_id
        assert connector.name
        assert connector.base_url.startswith(("http://", "https://"))
        assert connector.documentation_url.startswith("https://")

