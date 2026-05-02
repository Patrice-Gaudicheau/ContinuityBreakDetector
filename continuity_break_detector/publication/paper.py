from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from continuity_break_detector.storage.parquet import read_parquet
from continuity_break_detector.utils.paths import PROJECT_ROOT, ensure_directory

PAPER_TITLE = "Detecting Cross-Domain Continuity Breaks in Long-Term Human Development Data"
MODEL_LABEL = "gpt-5.5 medium"
CLAIMS_POLICY = "cautious, no proof claims"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "publication" / "paper"

REQUIRED_INPUTS = [
    "summary.json",
    "provenance.json",
    "model_comparison.parquet",
    "forecast_errors.parquet",
    "anomalies.parquet",
    "cross_domain_breaks.parquet",
    "ranked_break_candidates.json",
    "candidate_audit.json",
    "data_artifact_audit.json",
    "data_artifact_audit.md",
    "agents/synthesis.md",
    "agents/skeptic.md",
]


@dataclass(frozen=True)
class PaperDraftResult:
    output_dir: Path
    draft_path: Path | None
    metadata_path: Path | None
    snapshot_path: Path
    gpt_succeeded: bool
    error: str | None = None


CommandRunner = Callable[[list[str], str, int], str]


def draft_paper(
    *,
    study_path: Path,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    command_runner: CommandRunner | None = None,
) -> PaperDraftResult:
    selected_study = study_path.expanduser()
    if not selected_study.is_absolute():
        selected_study = (PROJECT_ROOT / selected_study).resolve()
    validate_inputs(selected_study)

    paper_dir = ensure_directory(output_dir)
    tables_dir = ensure_directory(paper_dir / "tables")
    snapshot = build_source_snapshot(selected_study)
    write_tables(snapshot, tables_dir)
    brief = build_writing_brief(snapshot)
    snapshot_path = paper_dir / "source_snapshot.json"
    snapshot_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")

    prompt = build_gpt_prompt(brief)
    runner = command_runner or run_gpt55_medium
    command = ["injected-command-runner"] if command_runner is not None else default_gpt_command()
    try:
        draft = runner(command, prompt, 900)
    except Exception as exc:
        return PaperDraftResult(
            output_dir=paper_dir,
            draft_path=None,
            metadata_path=None,
            snapshot_path=snapshot_path,
            gpt_succeeded=False,
            error=str(exc),
        )
    if not draft.strip():
        return PaperDraftResult(
            output_dir=paper_dir,
            draft_path=None,
            metadata_path=None,
            snapshot_path=snapshot_path,
            gpt_succeeded=False,
            error="GPT-5.5 CLI returned empty draft",
        )

    draft_path = paper_dir / "draft_v1.md"
    draft_path.write_text(draft.strip() + "\n", encoding="utf-8")
    metadata = build_metadata(selected_study, paper_dir)
    metadata_path = paper_dir / "draft_v1_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
    return PaperDraftResult(
        output_dir=paper_dir,
        draft_path=draft_path,
        metadata_path=metadata_path,
        snapshot_path=snapshot_path,
        gpt_succeeded=True,
    )


def validate_inputs(study_path: Path) -> None:
    missing = [filename for filename in REQUIRED_INPUTS if not (study_path / filename).exists()]
    if missing:
        raise FileNotFoundError(
            f"Study path is missing required paper inputs: {', '.join(missing)}"
        )


def build_source_snapshot(study_path: Path) -> dict[str, Any]:
    summary = read_json(study_path / "summary.json")
    provenance = read_json(study_path / "provenance.json")
    ranked = read_json(study_path / "ranked_break_candidates.json")
    candidate_audit = read_json(study_path / "candidate_audit.json")
    artifact_audit = read_json(study_path / "data_artifact_audit.json")
    model_comparison = read_parquet(study_path / "model_comparison.parquet")
    forecast_errors = read_parquet(study_path / "forecast_errors.parquet")
    anomalies = read_parquet(study_path / "anomalies.parquet")
    cross_domain_breaks = read_parquet(study_path / "cross_domain_breaks.parquet")
    synthesis = (study_path / "agents" / "synthesis.md").read_text(encoding="utf-8")
    skeptic = (study_path / "agents" / "skeptic.md").read_text(encoding="utf-8")

    artifact_counts = artifact_audit.get("verdict_counts", {})
    low_artifact = artifact_audit.get("low_artifact_risk_candidates", [])[:10]
    likely_artifacts = artifact_audit.get("likely_data_artifacts", [])[:10]
    possible_artifacts = artifact_audit.get("possible_data_artifacts", [])[:10]
    return {
        "study_path": str(study_path),
        "study_id": summary.get("study_id"),
        "created_at": summary.get("created_at"),
        "models": summary.get("models", []),
        "parameters": summary.get("parameters", {}),
        "forecaster_execution": summary.get("forecaster_execution", {}),
        "provenance": {
            "git_commit": provenance.get("git_commit"),
            "python_version": provenance.get("python_version"),
            "package_versions": provenance.get("package_versions", {}),
        },
        "row_counts": {
            "metrics_processed": int(summary.get("metrics_processed", 0) or 0),
            "forecast_error_rows": int(len(forecast_errors)),
            "anomaly_rows": int(len(anomalies)),
            "cross_domain_break_rows": int(len(cross_domain_breaks)),
            "ranked_candidates": int(ranked.get("all_candidates_count", 0) or 0),
            "representative_candidates": int(ranked.get("representative_candidates_count", 0) or 0),
            "audited_candidates": int(candidate_audit.get("candidate_count", 0) or 0),
            "artifact_audited_candidates": int(artifact_audit.get("candidate_count", 0) or 0),
        },
        "top_cross_domain_breaks": summary.get("top_cross_domain_breaks", [])[:10],
        "top_ranked_candidates": ranked.get("top_representative_candidates", [])[:10],
        "candidate_audit": {
            "verdict_counts": candidate_audit.get("verdict_counts", {}),
            "top_strong_candidates": candidate_audit.get("top_strong_candidates", [])[:10],
            "top_moderate_candidates": candidate_audit.get("top_moderate_candidates", [])[:10],
            "top_weak_candidates": candidate_audit.get("top_weak_candidates", [])[:10],
        },
        "artifact_audit": {
            "verdict_counts": artifact_counts,
            "likely_data_artifacts": likely_artifacts,
            "possible_data_artifacts": possible_artifacts,
            "low_artifact_risk_candidates": low_artifact,
        },
        "model_comparison": dataframe_records(model_comparison),
        "key_results": build_key_results(summary, ranked, candidate_audit, artifact_audit),
        "agent_writing_aids": {
            "synthesis_excerpt": synthesis[:2500],
            "skeptic_excerpt": skeptic[:2500],
        },
        "core_conclusion": (
            "The system detects known real-world shocks and data artifacts, but does not "
            "currently identify an unexplained synchronized cross-domain continuity break."
        ),
    }


def build_key_results(
    summary: dict[str, Any],
    ranked: dict[str, Any],
    candidate_audit: dict[str, Any],
    artifact_audit: dict[str, Any],
) -> list[dict[str, Any]]:
    artifact_counts = artifact_audit.get("verdict_counts", {})
    audit_counts = candidate_audit.get("verdict_counts", {})
    return [
        {"measure": "metrics_processed", "value": summary.get("metrics_processed")},
        {"measure": "forecast_error_rows", "value": summary.get("forecast_error_rows")},
        {"measure": "anomaly_rows", "value": summary.get("anomaly_rows")},
        {"measure": "cross_domain_break_rows", "value": summary.get("cross_domain_break_rows")},
        {"measure": "all_ranked_candidates", "value": ranked.get("all_candidates_count")},
        {
            "measure": "representative_candidates",
            "value": ranked.get("representative_candidates_count"),
        },
        {"measure": "strong_candidates", "value": audit_counts.get("strong_candidate", 0)},
        {"measure": "moderate_candidates", "value": audit_counts.get("moderate_candidate", 0)},
        {"measure": "weak_candidates", "value": audit_counts.get("weak_candidate", 0)},
        {
            "measure": "likely_data_artifacts",
            "value": artifact_counts.get("likely_data_artifact", 0),
        },
        {
            "measure": "possible_data_artifacts",
            "value": artifact_counts.get("possible_data_artifact", 0),
        },
        {
            "measure": "low_artifact_risk_candidates",
            "value": artifact_counts.get("low_artifact_risk", 0),
        },
    ]


def write_tables(snapshot: dict[str, Any], tables_dir: Path) -> None:
    pd.DataFrame(snapshot["key_results"]).to_csv(tables_dir / "key_results.csv", index=False)
    artifact_rows = []
    for verdict, items in snapshot["artifact_audit"].items():
        if verdict == "verdict_counts":
            continue
        for item in items:
            artifact_rows.append(
                {
                    "category": verdict,
                    "target_year": item.get("target_year"),
                    "artifact_score": item.get("artifact_score"),
                    "artifact_verdict": item.get("artifact_verdict"),
                    "ordinary_explanation_hint": item.get("ordinary_explanation_hint"),
                }
            )
    pd.DataFrame(artifact_rows).to_csv(tables_dir / "artifact_summary.csv", index=False)
    pd.DataFrame(snapshot["model_comparison"]).to_csv(
        tables_dir / "model_comparison.csv",
        index=False,
    )


def build_writing_brief(snapshot: dict[str, Any]) -> str:
    compact = {
        key: snapshot[key]
        for key in [
            "study_id",
            "study_path",
            "models",
            "parameters",
            "forecaster_execution",
            "row_counts",
            "top_cross_domain_breaks",
            "top_ranked_candidates",
            "candidate_audit",
            "artifact_audit",
            "model_comparison",
            "key_results",
            "core_conclusion",
        ]
    }
    return json.dumps(compact, indent=2, ensure_ascii=False)


def build_gpt_prompt(writing_brief: str) -> str:
    return "\n".join(
        [
            "Write an academic-style research draft in English from the factual brief below.",
            "",
            f"Title: {PAPER_TITLE}",
            "",
            "Required sections:",
            "1. Abstract",
            "2. Introduction",
            "3. Research Question",
            "4. Data Sources",
            "5. Methodology",
            "6. Forecasting Backtest Design",
            "7. Candidate Ranking and Artifact Filtering",
            "8. Results",
            "9. Discussion",
            "10. Limitations",
            "11. Conclusion",
            "12. Future Work",
            "",
            "Use only the values in the brief. Do not invent statistics, causes, datasets, or model results.",
            "Treat any prose excerpts as internal writing aids only; do not describe them as agents or model-generated analysis.",
            "Use precise terminology: continuity break, structural break, cross-domain anomaly, forecast failure, data artifact, known real-world shock, unexplained synchronized break.",
            "Do not assert metaphysical explanations, hidden external causes, or evidential certainty beyond the deterministic outputs.",
            "The conclusion must state that the system detects known shocks and artifacts, but no unexplained synchronized cross-domain continuity break is identified.",
            "Write in a cautious, academic, readable style with no first-person narration and no marketing tone.",
            "",
            "Factual writing brief:",
            writing_brief,
        ]
    )


def default_gpt_command() -> list[str]:
    configured = os.environ.get("CBD_PAPER_GPT_COMMAND")
    if configured:
        return configured.split()
    executable = shutil.which("codex")
    if executable is None:
        raise FileNotFoundError("codex CLI was not found on PATH")
    return [
        executable,
        "exec",
        "--model",
        "gpt-5.5",
        "-c",
        'model_reasoning_effort="medium"',
        "--sandbox",
        "read-only",
        "--ephemeral",
        "--output-last-message",
    ]


def run_gpt55_medium(command: list[str], prompt: str, timeout_seconds: int) -> str:
    if command[-1] == "--output-last-message":
        with tempfile.NamedTemporaryFile(delete=False) as output_file:
            output_path = Path(output_file.name)
        full_command = [*command, str(output_path), "-"]
        try:
            completed = subprocess.run(
                full_command,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
            return output_path.read_text(encoding="utf-8")
        finally:
            output_path.unlink(missing_ok=True)
    completed = subprocess.run(
        [*command, "-"],
        input=prompt,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())
    return completed.stdout


def build_metadata(study_path: Path, paper_dir: Path) -> dict[str, Any]:
    outputs = [
        str(paper_dir / "draft_v1.md"),
        str(paper_dir / "draft_v1_metadata.json"),
        str(paper_dir / "source_snapshot.json"),
        str(paper_dir / "tables" / "key_results.csv"),
        str(paper_dir / "tables" / "artifact_summary.csv"),
        str(paper_dir / "tables" / "model_comparison.csv"),
    ]
    return {
        "created_at": datetime.now(UTC).isoformat(),
        "study_path": str(study_path),
        "model": MODEL_LABEL,
        "inputs_used": REQUIRED_INPUTS,
        "outputs": outputs,
        "claims_policy": CLAIMS_POLICY,
    }


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def dataframe_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in df.to_dict("records"):
        records.append({str(key): json_safe(value) for key, value in row.items()})
    return records


def json_safe(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value
