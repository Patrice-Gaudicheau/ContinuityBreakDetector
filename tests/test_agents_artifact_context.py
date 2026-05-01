from __future__ import annotations

from continuity_break_detector.agents.artifact_context import (
    classify_artifact_vs_reality,
    low_artifact_risk_candidates,
)
from continuity_break_detector.agents.prompts import build_agent_prompt
from continuity_break_detector.agents.runner import REQUIRED_INPUT_FILES, format_study_content


def test_artifact_context_inclusion() -> None:
    payloads = {filename: "{}" for filename in REQUIRED_INPUT_FILES}
    payloads["data_artifact_audit.md"] = "# Data Artifact Audit"

    context = format_study_content(payloads)

    assert "## data_artifact_audit.json" in context
    assert "## data_artifact_audit.md" in context
    assert "top_break_candidates.md" not in REQUIRED_INPUT_FILES


def test_synthesis_prompt_includes_artifact_filtering_summary() -> None:
    system_prompt, user_prompt = build_agent_prompt(
        agent_name="synthesis",
        study_content="study",
        previous_reports={"skeptic": "report"},
    )

    combined = system_prompt + "\n" + user_prompt
    assert "Artifact Filtering Summary" in combined
    assert "Surviving Candidates" in combined
    assert "no unexplained synchronized cross-domain break is detected" in combined


def test_skeptic_prompt_classifies_artifact_vs_reality() -> None:
    _system_prompt, user_prompt = build_agent_prompt(
        agent_name="skeptic",
        study_content="study",
    )

    assert "Artifact vs Reality Analysis" in user_prompt
    assert "Strongly reject the 1848 cluster as artifact" in user_prompt
    assert "2012/2016 as probable revision effects" in user_prompt


def test_low_artifact_risk_filtering() -> None:
    payload = {
        "low_artifact_risk_candidates": [
            {"target_year": 2008},
            "bad row",
            {"target_year": 2020},
        ]
    }

    assert [row["target_year"] for row in low_artifact_risk_candidates(payload)] == [2008, 2020]


def test_artifact_vs_reality_classification() -> None:
    assert classify_artifact_vs_reality(
        {"target_year": 1848, "artifact_verdict": "likely_data_artifact"}
    ) == "likely data artifact"
    assert classify_artifact_vs_reality(
        {
            "target_year": 2016,
            "artifact_verdict": "possible_data_artifact",
            "revision_artifact_hint": "possible global data revision or methodology artifact",
        }
    ) == "likely data artifact"
    assert classify_artifact_vs_reality(
        {
            "target_year": 2008,
            "artifact_verdict": "low_artifact_risk",
            "known_real_world_event": True,
        }
    ) == "confirmed real-world event"

