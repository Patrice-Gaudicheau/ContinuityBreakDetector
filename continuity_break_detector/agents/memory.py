from __future__ import annotations

import sqlite3
from pathlib import Path

from continuity_break_detector.utils.paths import PROJECT_ROOT, ensure_directory

DEFAULT_DATABASE_PATH = PROJECT_ROOT / "data" / "processed" / "continuity_break_detector.sqlite"


def initialize_agent_tables(database_path: Path = DEFAULT_DATABASE_PATH) -> None:
    ensure_directory(database_path.parent)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_runs (
                run_id TEXT PRIMARY KEY,
                created_at TEXT,
                study_path TEXT,
                status TEXT,
                router_model TEXT,
                executor_model TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_reports (
                report_id TEXT PRIMARY KEY,
                run_id TEXT,
                agent_name TEXT,
                model TEXT,
                created_at TEXT,
                input_files TEXT,
                report_text TEXT,
                confidence_level TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_findings (
                finding_id TEXT PRIMARY KEY,
                run_id TEXT,
                agent_name TEXT,
                target_year INTEGER,
                finding_type TEXT,
                confidence REAL,
                summary TEXT
            )
            """
        )


def insert_agent_run(
    *,
    database_path: Path,
    run_id: str,
    created_at: str,
    study_path: str,
    status: str,
    router_model: str,
    executor_model: str,
) -> None:
    initialize_agent_tables(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO agent_runs (
                run_id, created_at, study_path, status, router_model, executor_model
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (run_id, created_at, study_path, status, router_model, executor_model),
        )


def update_agent_run_status(*, database_path: Path, run_id: str, status: str) -> None:
    initialize_agent_tables(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE agent_runs SET status = ? WHERE run_id = ?",
            (status, run_id),
        )


def insert_agent_report(
    *,
    database_path: Path,
    report_id: str,
    run_id: str,
    agent_name: str,
    model: str,
    created_at: str,
    input_files: str,
    report_text: str,
    confidence_level: str,
) -> None:
    initialize_agent_tables(database_path)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO agent_reports (
                report_id, run_id, agent_name, model, created_at,
                input_files, report_text, confidence_level
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id,
                run_id,
                agent_name,
                model,
                created_at,
                input_files,
                report_text,
                confidence_level,
            ),
        )
