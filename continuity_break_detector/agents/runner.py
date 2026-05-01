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
            reports[agent_name] = summarize_report_for_synthesis(report_text)
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
    sections: list[str] = [
        "The following are deterministic excerpts from the required study files. "
        "Use only this provided content; do not infer unseen values."
    ]
    for filename in REQUIRED_INPUT_FILES:
        sections.append(f"## {filename}\n{compact_file_content(filename, payloads[filename])}")
    return "\n\n".join(sections)


def compact_file_content(filename: str, content: str) -> str:
    if filename.endswith(".md"):
        return content[:3000]
    if filename == "summary.json":
        return _compact_summary_json(content)
    if filename == "ranked_break_candidates.json":
        return _compact_ranked_json(content)
    if filename == "candidate_audit.json":
        return _compact_audit_json(content)
    if filename == "provenance.json":
        return _compact_json(content, keep_top_items=5)
    return content[:12000]


def _compact_summary_json(content: str) -> str:
    payload = _load_json_object(content)
    if payload is None:
        return content[:8000]
    compacted = {
        key: payload.get(key)
        for key in [
            "study_id",
            "created_at",
            "input_path",
            "models",
            "parameters",
            "metrics_processed",
            "forecast_error_rows",
            "anomaly_rows",
            "cross_domain_break_rows",
        ]
    }
    compacted["top_cross_domain_breaks"] = [
        _select_fields(
            item,
            [
                "target_year",
                "affected_domains",
                "affected_domain_count",
                "anomaly_count",
                "aggregate_score",
            ],
        )
        for item in payload.get("top_cross_domain_breaks", [])[:5]
        if isinstance(item, dict)
    ]
    return json.dumps(compacted, indent=2, ensure_ascii=False)


def _compact_ranked_json(content: str) -> str:
    payload = _load_json_object(content)
    if payload is None:
        return content[:8000]
    compacted = {
        key: payload.get(key)
        for key in [
            "study_id",
            "created_at",
            "source_study_path",
            "ranking_parameters",
            "all_candidates_count",
            "representative_candidates_count",
        ]
    }
    compacted["top_representative_candidates"] = [
        _select_fields(
            item,
            [
                "target_year",
                "rank_score",
                "affected_domain_count",
                "anomaly_count",
                "mean_z_score",
                "max_z_score",
                "p95_z_score",
                "affected_domains",
                "affected_metrics",
                "affected_sources",
                "model_count",
                "persistence_score",
                "ordinary_explanation_hint",
            ],
        )
        for item in payload.get("top_representative_candidates", [])[:8]
        if isinstance(item, dict)
    ]
    return json.dumps(compacted, indent=2, ensure_ascii=False)


def _compact_audit_json(content: str) -> str:
    payload = _load_json_object(content)
    if payload is None:
        return content[:8000]
    compacted = {
        key: payload.get(key)
        for key in [
            "study_id",
            "created_at",
            "source_study_path",
            "audit_parameters",
            "candidate_count",
            "verdict_counts",
        ]
    }
    for list_name in [
        "top_strong_candidates",
        "top_moderate_candidates",
        "top_weak_candidates",
    ]:
        compacted[list_name] = [
            _select_fields(
                item,
                [
                    "target_year",
                    "rank_score",
                    "robustness_score",
                    "audit_verdict",
                    "affected_domains",
                    "source_count",
                    "metric_count",
                    "domain_count",
                    "model_count",
                    "anomaly_count",
                    "model_agreement_score",
                    "domain_agreement_score",
                    "persistence_score",
                    "sparsity_risk",
                    "historical_data_risk",
                    "known_explanation_risk",
                    "ordinary_explanation_hint",
                    "audit_notes",
                ],
            )
            for item in payload.get(list_name, [])[:5]
            if isinstance(item, dict)
        ]
    return json.dumps(compacted, indent=2, ensure_ascii=False)


def _load_json_object(content: str) -> dict[str, object] | None:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _select_fields(item: dict[str, object], fields: list[str]) -> dict[str, object]:
    return {field: item.get(field) for field in fields}


def _compact_json(content: str, *, keep_top_items: int) -> str:
    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return content[:12000]
    if isinstance(payload, dict):
        compacted: dict[str, object] = {}
        for key, value in payload.items():
            if isinstance(value, list):
                compacted[key] = value[:keep_top_items]
            else:
                compacted[key] = value
        return json.dumps(compacted, indent=2, ensure_ascii=False)
    return json.dumps(payload, indent=2, ensure_ascii=False)[:12000]


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


def summarize_report_for_synthesis(report_text: str, *, max_chars: int = 1200) -> str:
    return report_text.strip()[:max_chars]


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
