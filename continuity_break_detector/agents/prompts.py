from __future__ import annotations

from dataclasses import dataclass


AGENT_ORDER = [
    "source_auditor",
    "statistical_reviewer",
    "domain_interpreter",
    "skeptic",
    "synthesis",
]


SAFETY_CONSTRAINTS = "\n".join([
    "Do not claim proof of simulation.",
    "Do not invent data.",
    "Use only the provided study content.",
    "Separate evidence from interpretation.",
    "Prefer ordinary explanations.",
    "Explicitly mention uncertainty.",
    "If evidence is insufficient, say so.",
    "Do not calculate new statistics.",
    "Do not modify data.",
    "Provide concise rationale only; do not expose hidden chain-of-thought.",
])


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: str
    focus: str


AGENT_SPECS: dict[str, AgentSpec] = {
    "source_auditor": AgentSpec(
        name="source_auditor",
        role="Source auditor",
        focus="Check freshness, data gaps, format consistency, and source coverage. Do not check license.",
    ),
    "statistical_reviewer": AgentSpec(
        name="statistical_reviewer",
        role="Statistical reviewer",
        focus="Review robustness of candidate breaks, model agreement, domain agreement, anomaly density, overfitting risk, and noisy ranking risk.",
    ),
    "domain_interpreter": AgentSpec(
        name="domain_interpreter",
        role="Domain interpreter",
        focus="Contextualize the audited candidates by economics, demographics, science, health, and other domains.",
    ),
    "skeptic": AgentSpec(
        name="skeptic",
        role="Skeptic",
        focus="Search for ordinary explanations before exotic hypotheses. Explicitly reject simulation claims unless evidence is extraordinary. Identify likely mundane causes.",
    ),
    "synthesis": AgentSpec(
        name="synthesis",
        role="Synthesis agent",
        focus="Produce a final cautious summary with confidence levels using the study content and previous agent reports.",
    ),
}


def build_agent_prompt(
    *,
    agent_name: str,
    study_content: str,
    previous_reports: dict[str, str] | None = None,
) -> tuple[str, str]:
    spec = AGENT_SPECS[agent_name]
    system_prompt = "\n".join([
        f"You are the {spec.role} for ContinuityBreakDetector.",
        SAFETY_CONSTRAINTS,
        "Return concise Markdown under 700 words with clear sections: Evidence, Interpretation, Uncertainty, Findings.",
    ])
    previous = ""
    if previous_reports:
        previous = "\n\nPrevious agent reports:\n" + "\n\n".join(
            f"## {name}\n{text}" for name, text in previous_reports.items()
        )
    user_prompt = "\n".join([
        f"Agent: {spec.name}",
        f"Focus: {spec.focus}",
        "",
        "Study content:",
        study_content,
        previous,
    ])
    return system_prompt, user_prompt


def build_router_prompt(study_content: str) -> tuple[str, str]:
    system_prompt = "\n".join([
        "You are a routing classifier for ContinuityBreakDetector.",
        SAFETY_CONSTRAINTS,
        "Return only a comma-separated subset of: source_auditor, statistical_reviewer, domain_interpreter, skeptic, synthesis.",
    ])
    user_prompt = "Decide which agents are needed for this study. Default to all agents when uncertain.\n\n" + study_content
    return system_prompt, user_prompt
