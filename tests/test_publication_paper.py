from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from continuity_break_detector.publication.paper import (
    build_gpt_prompt,
    build_source_snapshot,
    build_writing_brief,
    draft_paper,
)
from continuity_break_detector.storage.parquet import write_parquet


def test_writing_brief_generation(tmp_path: Path) -> None:
    study_path = make_study_fixture(tmp_path)

    snapshot = build_source_snapshot(study_path)
    brief = build_writing_brief(snapshot)
    payload = json.loads(brief)

    assert payload["study_id"] == "fixture_study"
    assert payload["row_counts"]["forecast_error_rows"] == 2
    assert payload["core_conclusion"].startswith("The system detects known real-world shocks")


def test_no_forbidden_claims_in_prompt(tmp_path: Path) -> None:
    study_path = make_study_fixture(tmp_path)
    prompt = build_gpt_prompt(build_writing_brief(build_source_snapshot(study_path))).lower()

    forbidden = [
        "simulation proof",
        "rapid influx proof",
        "reality glitch",
        "evidence of simulation",
    ]
    assert all(claim not in prompt for claim in forbidden)
    assert "do not invent statistics" in prompt


def test_table_extraction_from_json_and_parquet_fixtures(tmp_path: Path) -> None:
    study_path = make_study_fixture(tmp_path)
    output_dir = tmp_path / "paper"

    result = draft_paper(
        study_path=study_path,
        output_dir=output_dir,
        command_runner=lambda _command, _prompt, _timeout: "# Draft\n\nCautious text.",
    )

    key_results = pd.read_csv(output_dir / "tables" / "key_results.csv")
    artifacts = pd.read_csv(output_dir / "tables" / "artifact_summary.csv")
    comparison = pd.read_csv(output_dir / "tables" / "model_comparison.csv")

    assert result.gpt_succeeded is True
    assert "forecast_error_rows" in set(key_results["measure"])
    assert list(artifacts["target_year"]) == [2020]
    assert list(comparison["model"]) == ["naive_last_value"]


def test_clean_failure_when_gpt_cli_unavailable(tmp_path: Path) -> None:
    study_path = make_study_fixture(tmp_path)
    output_dir = tmp_path / "paper"

    result = draft_paper(
        study_path=study_path,
        output_dir=output_dir,
        command_runner=lambda _command, _prompt, _timeout: (_ for _ in ()).throw(
            FileNotFoundError("missing cli")
        ),
    )

    assert result.gpt_succeeded is False
    assert (output_dir / "source_snapshot.json").exists()
    assert (output_dir / "tables" / "key_results.csv").exists()
    assert not (output_dir / "draft_v1.md").exists()


def test_metadata_creation(tmp_path: Path) -> None:
    study_path = make_study_fixture(tmp_path)
    output_dir = tmp_path / "paper"

    result = draft_paper(
        study_path=study_path,
        output_dir=output_dir,
        command_runner=lambda _command, _prompt, _timeout: "# Draft\n\nCautious text.",
    )
    metadata = json.loads((output_dir / "draft_v1_metadata.json").read_text(encoding="utf-8"))

    assert result.metadata_path == output_dir / "draft_v1_metadata.json"
    assert metadata["model"] == "gpt-5.5 medium"
    assert metadata["claims_policy"] == "cautious, no proof claims"
    assert "summary.json" in metadata["inputs_used"]


def make_study_fixture(tmp_path: Path) -> Path:
    study = tmp_path / "study"
    (study / "agents").mkdir(parents=True)
    (study / "summary.json").write_text(
        json.dumps(
            {
                "study_id": "fixture_study",
                "created_at": "2026-05-02T00:00:00+00:00",
                "models": ["naive_last_value"],
                "parameters": {"train_window_years": 20},
                "metrics_processed": 1,
                "forecast_error_rows": 2,
                "anomaly_rows": 1,
                "cross_domain_break_rows": 1,
                "forecaster_execution": {},
                "top_cross_domain_breaks": [
                    {
                        "target_year": 2020,
                        "affected_domains": ["health"],
                        "anomaly_count": 1,
                        "aggregate_score": 3.0,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (study / "provenance.json").write_text(
        json.dumps(
            {
                "git_commit": "abc",
                "python_version": "3.12",
                "package_versions": {"pandas": "x"},
            }
        ),
        encoding="utf-8",
    )
    (study / "ranked_break_candidates.json").write_text(
        json.dumps(
            {
                "all_candidates_count": 1,
                "representative_candidates_count": 1,
                "top_representative_candidates": [
                    {
                        "target_year": 2020,
                        "rank_score": 0.8,
                        "affected_domains": ["health"],
                        "anomaly_count": 1,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (study / "candidate_audit.json").write_text(
        json.dumps(
            {
                "candidate_count": 1,
                "verdict_counts": {"moderate_candidate": 1},
                "top_strong_candidates": [],
                "top_moderate_candidates": [{"target_year": 2020, "robustness_score": 0.5}],
                "top_weak_candidates": [],
            }
        ),
        encoding="utf-8",
    )
    (study / "data_artifact_audit.json").write_text(
        json.dumps(
            {
                "candidate_count": 1,
                "verdict_counts": {"low_artifact_risk": 1},
                "likely_data_artifacts": [],
                "possible_data_artifacts": [],
                "low_artifact_risk_candidates": [
                    {
                        "target_year": 2020,
                        "artifact_score": 0.1,
                        "artifact_verdict": "low_artifact_risk",
                        "ordinary_explanation_hint": "COVID-19 pandemic shock",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (study / "data_artifact_audit.md").write_text("# Data Artifact Audit\n", encoding="utf-8")
    (study / "agents" / "synthesis.md").write_text("Known shocks and artifacts.", encoding="utf-8")
    (study / "agents" / "skeptic.md").write_text("No unexplained break.", encoding="utf-8")

    write_parquet(
        pd.DataFrame(
            [
                {
                    "model": "naive_last_value",
                    "metric": "life_expectancy",
                    "mae": 1.0,
                    "rmse": 1.2,
                    "median_absolute_error": 1.0,
                    "anomaly_count": 1,
                    "extreme_anomaly_count": 0,
                }
            ]
        ),
        study / "model_comparison.parquet",
    )
    write_parquet(
        pd.DataFrame(
            [
                {
                    "source_id": "owid",
                    "metric": "life_expectancy",
                    "entity": None,
                    "model": "naive_last_value",
                    "cutoff_year": 2019,
                    "target_year": 2020,
                    "horizon": 1,
                    "actual": 70.0,
                    "predicted": 72.0,
                    "absolute_error": 2.0,
                    "relative_error": 0.03,
                    "squared_error": 4.0,
                },
                {
                    "source_id": "owid",
                    "metric": "life_expectancy",
                    "entity": None,
                    "model": "naive_last_value",
                    "cutoff_year": 2020,
                    "target_year": 2021,
                    "horizon": 1,
                    "actual": 71.0,
                    "predicted": 70.0,
                    "absolute_error": 1.0,
                    "relative_error": 0.01,
                    "squared_error": 1.0,
                },
            ]
        ),
        study / "forecast_errors.parquet",
    )
    write_parquet(
        pd.DataFrame(
            [
                {
                    "source_id": "owid",
                    "metric": "life_expectancy",
                    "entity": None,
                    "model": "naive_last_value",
                    "target_year": 2020,
                    "z_score": 3.0,
                    "absolute_error": 2.0,
                    "relative_error": 0.03,
                    "severity": "medium",
                }
            ]
        ),
        study / "anomalies.parquet",
    )
    write_parquet(
        pd.DataFrame(
            [
                {
                    "target_year": 2020,
                    "affected_domains": ["health"],
                    "affected_domain_count": 1,
                    "anomaly_count": 1,
                    "aggregate_score": 3.0,
                    "items": [],
                }
            ]
        ),
        study / "cross_domain_breaks.parquet",
    )
    return study

