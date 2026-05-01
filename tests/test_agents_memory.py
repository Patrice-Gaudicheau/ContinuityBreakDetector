from __future__ import annotations

import sqlite3

from continuity_break_detector.agents.memory import (
    initialize_agent_tables,
    insert_agent_report,
    insert_agent_run,
)


def test_sqlite_table_creation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "agents.sqlite"

    initialize_agent_tables(database_path)

    with sqlite3.connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert {"agent_runs", "agent_reports", "agent_findings"}.issubset(tables)


def test_agent_run_record_insertion(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "agents.sqlite"

    insert_agent_run(
        database_path=database_path,
        run_id="run_1",
        created_at="2026-05-01T00:00:00+00:00",
        study_path="/tmp/study",
        status="running",
        router_model="router",
        executor_model="executor",
    )

    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT run_id, status FROM agent_runs").fetchone()
    assert row == ("run_1", "running")


def test_agent_report_insertion(tmp_path) -> None:  # type: ignore[no-untyped-def]
    database_path = tmp_path / "agents.sqlite"
    insert_agent_run(
        database_path=database_path,
        run_id="run_1",
        created_at="2026-05-01T00:00:00+00:00",
        study_path="/tmp/study",
        status="running",
        router_model="router",
        executor_model="executor",
    )

    insert_agent_report(
        database_path=database_path,
        report_id="report_1",
        run_id="run_1",
        agent_name="source_auditor",
        model="executor",
        created_at="2026-05-01T00:00:00+00:00",
        input_files='["summary.json"]',
        report_text="Low confidence report",
        confidence_level="low",
    )

    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            "SELECT report_id, agent_name, confidence_level FROM agent_reports"
        ).fetchone()
    assert row == ("report_1", "source_auditor", "low")

