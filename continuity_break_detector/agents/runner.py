from __future__ import annotations

import argparse
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from continuity_break_detector.agents.config import AgentConfig, load_agent_config
from continuity_break_detector.agents.lemonade import LemonadeClient, LemonadeError
from continuity_break_detector.agents.memory import (
    DEFAULT_DATABASE_PATH,
    initialize_agent_tables,
    insert_agent_report,
    insert_agent_run,
    update_agent_run_status,
)
from continuity_break_detector.agents.prompts import AGENT_ORDER, build_agent_prompt, build_router_prompt
from continuity_break_detector.backtesting.ranking import latest_study_folder
from continuity_break_detector.backtesting.study import STUDIES_DIR
from continuity_break_detector.utils.paths import ensure_directory


REQUIRED_INPUT_FILES = [
    "candidate_audit.json",
    "candidate_audit.md",
    "ranked_break_candidates.json",
    "top_break_candidates.md",
    "summary.json",
    "provenance.json",
]


@dataclass(frozen=True)
class AgentRunResult:
    study_path: Path
    run_id: str
    agents_completed: int
    output_dir: Path


def analyze_latest_study(
    *,
    studies_dir: Path = STUDIES_DIR,
    database_path: Path = DEFAULT_DATABASE_PATH,
    config: AgentConfig | None = None,
    client: LemonadeClient | None = None,
) -> AgentRunResult:
    return analyze_study(
        latest_study_folder(studies_dir),
        database_path=database_path,
        config=config,
        client=client,
    )


def analyze_study(
    study_path: Path,
    *,
    database_path: Path = DEFAULT_DATABASE_PATH,
    config: AgentConfig | None = None,
    client: LemonadeClient | None = None,
) -> AgentRunResult:
    agent_config = config or load_agent_config()
    lemonade = client or LemonadeClient(
        base_url=agent_config.lemonade_base_url,
        api_key=agent_config.lemonade_api_key,
    )
    created_at = datetime.now(UTC).isoformat()
    run_id = f"agent_run_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    output_dir = ensure_directory(study_path / "agents")
    input_payloads = load_study_content(study_path)
    study_content = format_study_content(input_payloads)

    initialize_agent_tables(database_path)
    insert_agent_run(
        database_path=database_path,
        run_id=run_id,
        created_at=created_at,
        study_path=str(study_path),
        status="running",
        router_model=agent_config.router_model,
        executor_model=agent_config.executor_model,
    )

    completed = 0
    reports: dict[str, str] = {}
    try:
        agents_to_run = route_agents(
            client=lemonade,
            model=agent_config.router_model,
            study_content=study_content,
        )
        for agent_name in agents_to_run:
            prior = reports if agent_name == "synthesis" else None
            system_prompt, user_prompt = build_agent_prompt(
                agent_name=agent_name,
                study_content=study_content,
                previous_reports=prior,
            )
            report_text = lemonade.chat(
                model=agent_config.executor_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            if not report_text.strip():
                raise LemonadeError(f"{agent_name} returned empty content")
            (output_dir / f"{agent_name}.md").write_text(report_text, encoding="utf-8")
            insert_agent_report(
                database_path=database_path,
                report_id=f"report_{uuid.uuid4().hex}",
                run_id=run_id,
                agent_name=agent_name,
                model=agent_config.executor_model,
                created_at=datetime.now(UTC).isoformat(),
                input_files=json.dumps(REQUIRED_INPUT_FILES),
                report_text=report_text,
                confidence_level=extract_confidence_level(report_text),
            )
            reports[agent_name] = report_text
            completed += 1
        write_agent_run_json(
            output_dir / "agent_run.json",
            run_id=run_id,
            created_at=created_at,
            study_path=study_path,
            status="completed",
            config=agent_config,
            agents=list(reports),
        )
        update_agent_run_status(database_path=database_path, run_id=run_id, status="completed")
    except Exception:
        update_agent_run_status(database_path=database_path, run_id=run_id, status="failed")
        write_agent_run_json(
            output_dir / "agent_run.json",
            run_id=run_id,
            created_at=created_at,
            study_path=study_path,
            status="failed",
            config=agent_config,
            agents=list(reports),
        )
        raise

    return AgentRunResult(
        study_path=study_path,
        run_id=run_id,
        agents_completed=completed,
        output_dir=output_dir,
    )


def load_study_content(study_path: Path) -> dict[str, str]:
    payloads: dict[str, str] = {}
    for filename in REQUIRED_INPUT_FILES:
        path = study_path / filename
        if not path.exists():
            raise FileNotFoundError(f"Required study file is missing: {path}")
        payloads[filename] = path.read_text(encoding="utf-8")
    return payloads


def format_study_content(payloads: dict[str, str]) -> str:
    sections: list[str] = []
    for filename in REQUIRED_INPUT_FILES:
        sections.append(f"## {filename}\n{payloads[filename]}")
    return "\n\n".join(sections)


def route_agents(*, client: LemonadeClient, model: str, study_content: str) -> list[str]:
    system_prompt, user_prompt = build_router_prompt(study_content)
    try:
        response = client.chat(model=model, system_prompt=system_prompt, user_prompt=user_prompt)
    except LemonadeError:
        return list(AGENT_ORDER)
    requested = [
        item.strip()
        for item in response.replace("\n", ",").split(",")
        if item.strip() in AGENT_ORDER
    ]
    if not requested:
        return list(AGENT_ORDER)
    if "synthesis" not in requested:
        requested.append("synthesis")
    return [agent for agent in AGENT_ORDER if agent in requested]


def extract_confidence_level(report_text: str) -> str:
    lowered = report_text.lower()
    if "high confidence" in lowered:
        return "high"
    if "low confidence" in lowered:
        return "low"
    return "medium"


def write_agent_run_json(
    path: Path,
    *,
    run_id: str,
    created_at: str,
    study_path: Path,
    status: str,
    config: AgentConfig,
    agents: list[str],
) -> None:
    payload = {
        "run_id": run_id,
        "created_at": created_at,
        "study_path": str(study_path),
        "status": status,
        "router_model": config.router_model,
        "executor_model": config.executor_model,
        "agents_completed": agents,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local Lemonade interpretation agents.")
    parser.add_argument("--studies-dir", type=Path, default=STUDIES_DIR)
    parser.add_argument("--database-path", type=Path, default=DEFAULT_DATABASE_PATH)
    args = parser.parse_args()

    try:
        result = analyze_latest_study(
            studies_dir=args.studies_dir,
            database_path=args.database_path,
        )
    except LemonadeError as exc:
        print(f"Lemonade unavailable or returned no usable content: {exc}")
        return 1
    except Exception as exc:
        print(f"Agent analysis failed: {exc}")
        return 1

    print(f"study_path,{result.study_path}")
    print(f"run_id,{result.run_id}")
    print(f"agents_completed,{result.agents_completed}")
    print(f"output_directory,{result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

