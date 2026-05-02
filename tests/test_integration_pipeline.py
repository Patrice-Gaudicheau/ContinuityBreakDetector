from __future__ import annotations

import json
from pathlib import Path

from continuity_break_detector import demo
from continuity_break_detector.storage.parquet import read_parquet


def test_full_demo_pipeline_end_to_end(tmp_path: Path, monkeypatch) -> None:
    study_dir = tmp_path / "demo_study"
    monkeypatch.setattr(demo, "DEMO_STUDY_DIR", study_dir)

    result = demo.run_demo_study()

    normalized_files = list((study_dir / "normalized").glob("*/*.parquet"))
    statistics_files = list((study_dir / "statistics").glob("*/*.parquet"))
    forecast_errors = read_parquet(study_dir / "forecast_errors.parquet")
    ranked = json.loads((study_dir / "ranked_break_candidates.json").read_text(encoding="utf-8"))
    artifact_audit = json.loads((study_dir / "data_artifact_audit.json").read_text(encoding="utf-8"))

    assert result.study_path == study_dir
    assert len(normalized_files) == 3
    assert len(statistics_files) == 3
    assert not forecast_errors.empty
    assert ranked["all_candidates_count"] > 0
    assert artifact_audit["candidate_count"] > 0
