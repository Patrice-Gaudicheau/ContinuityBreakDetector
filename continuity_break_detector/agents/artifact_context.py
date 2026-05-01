from __future__ import annotations

from typing import Any


def low_artifact_risk_candidates(artifact_payload: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = artifact_payload.get("low_artifact_risk_candidates", [])
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def classify_artifact_vs_reality(candidate: dict[str, Any]) -> str:
    verdict = str(candidate.get("artifact_verdict", ""))
    known_event = bool(candidate.get("known_real_world_event"))
    year = int(candidate.get("target_year", 0))
    if verdict == "likely_data_artifact":
        return "likely data artifact"
    if year in {2012, 2016} and candidate.get("revision_artifact_hint"):
        return "likely data artifact"
    if known_event and verdict == "low_artifact_risk":
        return "confirmed real-world event"
    return "unresolved"

