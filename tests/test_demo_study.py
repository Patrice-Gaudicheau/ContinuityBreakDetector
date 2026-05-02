from __future__ import annotations

from pathlib import Path

from continuity_break_detector import demo


def test_demo_study_runs_successfully(tmp_path: Path, monkeypatch) -> None:
    study_dir = tmp_path / "demo_study"
    monkeypatch.setattr(demo, "DEMO_STUDY_DIR", study_dir)

    result = demo.run_demo_study()

    assert result.study_path == study_dir
    assert result.normalized_files == 3
    assert result.statistics_files == 3
    assert result.forecast_error_rows > 0
    assert (study_dir / "normalized").is_dir()
    assert (study_dir / "statistics").is_dir()
    assert (study_dir / "forecast_errors.parquet").exists()
    assert (study_dir / "ranked_break_candidates.json").exists()
    assert (study_dir / "candidate_audit.json").exists()
    assert (study_dir / "data_artifact_audit.json").exists()
