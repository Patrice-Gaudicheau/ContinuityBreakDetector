from __future__ import annotations

from dataclasses import dataclass

AGENT_ORDER = [
    "source_auditor",
    "statistical_reviewer",
    "domain_interpreter",
    "skeptic",
    "synthesis",
]


SAFETY_CONSTRAINTS = "\n".join(
    [
        "Do not claim proof of simulation.",
        "Do not invent data.",
        "Use only the provided study content.",
        "Separate evidence from interpretation.",
        "Prefer ordinary explanations.",
        "Prefer artifact explanations over exotic explanations when artifact evidence exists.",
        "Explicitly mention uncertainty.",
        "If evidence is insufficient, say so.",
        "Do not calculate new statistics.",
        "Do not modify data.",
        "Provide concise rationale only; do not expose hidden chain-of-thought.",
    ]
)


@dataclass(frozen=True)
class AgentSpec:
    name: str
    role: str
    focus: str


AGENT_SPECS: dict[str, AgentSpec] = {
    "source_auditor": AgentSpec(
        name="source_auditor",
        role="Source auditor",
        focus=(
            "Check freshness, data gaps, format consistency, and source coverage. Do not check license. "
            "Include a section titled 'Data Artifact Signals' summarizing likely_data_artifact, "
            "possible_data_artifact, and low_artifact_risk counts, and highlight dominant sources such as OWID or World Bank."
        ),
    ),
    "statistical_reviewer": AgentSpec(
        name="statistical_reviewer",
        role="Statistical reviewer",
        focus=(
            "Review robustness, model agreement, domain agreement, anomaly density, overfitting risk, and noisy ranking risk. "
            "Incorporate artifact_score, downgrade extreme z-score candidates with artifact flags, and explicitly flag cases that are statistically strong but likely artifact."
        ),
    ),
    "domain_interpreter": AgentSpec(
        name="domain_interpreter",
        role="Domain interpreter",
        focus=(
            "Contextualize candidates by economics, demographics, science, health, and other domains. "
            "Ignore likely_data_artifact candidates except as data issues. Focus only on low_artifact_risk candidates and top possible_data_artifact candidates with caution."
        ),
    ),
    "skeptic": AgentSpec(
        name="skeptic",
        role="Skeptic",
        focus=(
            "Use artifact signals to reject false positives. Include a section titled 'Artifact vs Reality Analysis'. "
            "For top candidates classify them as confirmed real-world event, likely data artifact, or unresolved. "
            "Use only those three labels; do not write 'confirmed data artifact'. "
            "Strongly reject the 1848 cluster as artifact and 2012/2016 as probable revision effects. "
            "Search for ordinary explanations before exotic hypotheses and reject simulation claims unless evidence is extraordinary."
        ),
    ),
    "synthesis": AgentSpec(
        name="synthesis",
        role="Synthesis agent",
        focus=(
            "Produce a final cautious summary with confidence levels using artifact audit context and previous reports. "
            "Include sections exactly titled 'Artifact Filtering Summary', 'Surviving Candidates', 'Interpretation', and 'Conclusion'. "
            "State counts per artifact category, state that most signals are artifacts, list only low_artifact_risk candidates as surviving candidates, usually 2008 and 2020, and describe them as low-artifact-risk known shocks rather than unexplained or novel events. State that no unexplained synchronized cross-domain break is detected. "
            "The Conclusion must say: no simulation claim, no unexplained influx claim, the system currently detects known shocks plus artifacts, and further data/model refinement is required."
        ),
    ),
}


def build_agent_prompt(
    *,
    agent_name: str,
    study_content: str,
    previous_reports: dict[str, str] | None = None,
) -> tuple[str, str]:
    spec = AGENT_SPECS[agent_name]
    system_prompt = "\n".join(
        [
            f"You are the {spec.role} for ContinuityBreakDetector.",
            SAFETY_CONSTRAINTS,
            "Return concise Markdown under 500 words with complete sections. End with a short Conclusion. Do not trail off mid-sentence.",
        ]
    )
    previous = ""
    if previous_reports:
        previous = "\n\nPrevious agent reports:\n" + "\n\n".join(
            f"## {name}\n{text}" for name, text in previous_reports.items()
        )
    user_prompt = "\n".join(
        [
            f"Agent: {spec.name}",
            f"Focus: {spec.focus}",
            "",
            "Study content:",
            study_content,
            previous,
        ]
    )
    return system_prompt, user_prompt


def build_router_prompt(study_content: str) -> tuple[str, str]:
    system_prompt = "\n".join(
        [
            "You are a routing classifier for ContinuityBreakDetector.",
            SAFETY_CONSTRAINTS,
            "Return only a comma-separated subset of: source_auditor, statistical_reviewer, domain_interpreter, skeptic, synthesis.",
        ]
    )
    user_prompt = (
        "Decide which agents are needed for this study. Default to all agents when uncertain.\n\n"
        + study_content
    )
    return system_prompt, user_prompt
