from __future__ import annotations

from continuity_break_detector.agents.prompts import build_agent_prompt


def test_prompt_builder_includes_safety_constraints() -> None:
    system_prompt, user_prompt = build_agent_prompt(
        agent_name="skeptic",
        study_content="study",
    )

    combined = system_prompt + "\n" + user_prompt
    assert "Do not claim proof of simulation." in combined
    assert "Do not invent data." in combined
    assert "Use only the provided study content." in combined
    assert "Prefer ordinary explanations." in combined
    assert "Explicitly mention uncertainty." in combined
