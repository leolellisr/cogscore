from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import DATABASE_PATH, ensure_storage_dirs


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    ensure_storage_dirs()

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    ensure_storage_dirs()

    with get_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY,
                agent_name TEXT NOT NULL,
                architecture_name TEXT NOT NULL,
                benchmark TEXT NOT NULL,
                benchmark_version TEXT NOT NULL,
                cogscore_version TEXT NOT NULL,
                run_name TEXT NOT NULL,
                run_date TEXT NOT NULL,
                seed INTEGER,
                episodes INTEGER,
                trials_per_experiment INTEGER,
                status TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                benchmark_out_path TEXT NOT NULL,
                manifest_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                input_json TEXT NOT NULL,
                output_json TEXT,
                log_path TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                finished_at TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS plots (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                benchmark TEXT NOT NULL,
                plot_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        conn.commit()


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None

    return dict(row)


def create_run(run: dict[str, Any]) -> dict[str, Any]:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO runs (
                id,
                agent_name,
                architecture_name,
                benchmark,
                benchmark_version,
                cogscore_version,
                run_name,
                run_date,
                seed,
                episodes,
                trials_per_experiment,
                status,
                storage_path,
                benchmark_out_path,
                manifest_json,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run["id"],
                run["agent_name"],
                run["architecture_name"],
                run["benchmark"],
                run["benchmark_version"],
                run["cogscore_version"],
                run["run_name"],
                run["run_date"],
                run.get("seed"),
                run.get("episodes"),
                run.get("trials_per_experiment"),
                run["status"],
                run["storage_path"],
                run["benchmark_out_path"],
                json.dumps(run["manifest"], ensure_ascii=False),
                run["created_at"],
            ),
        )

        conn.commit()

    return run


def list_runs() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM runs
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_run(run_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM runs
            WHERE id = ?
            """,
            (run_id,),
        ).fetchone()

    return row_to_dict(row)


def create_job(
    *,
    job_id: str,
    job_type: str,
    input_data: dict[str, Any],
    status: str = "pending",
) -> dict[str, Any]:
    created_at = utc_now_iso()

    job = {
        "id": job_id,
        "job_type": job_type,
        "status": status,
        "input_json": json.dumps(input_data, ensure_ascii=False),
        "output_json": None,
        "log_path": None,
        "error_message": None,
        "created_at": created_at,
        "started_at": None,
        "finished_at": None,
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id,
                job_type,
                status,
                input_json,
                output_json,
                log_path,
                error_message,
                created_at,
                started_at,
                finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job["id"],
                job["job_type"],
                job["status"],
                job["input_json"],
                job["output_json"],
                job["log_path"],
                job["error_message"],
                job["created_at"],
                job["started_at"],
                job["finished_at"],
            ),
        )

        conn.commit()

    return job


def list_jobs() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM jobs
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [dict(row) for row in rows]


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE id = ?
            """,
            (job_id,),
        ).fetchone()

    return row_to_dict(row)


def list_plot_files() -> list[dict[str, Any]]:
    from .config import PLOTS_DIR

    if not PLOTS_DIR.exists():
        return []

    files: list[dict[str, Any]] = []

    for path in sorted(PLOTS_DIR.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".pdf", ".svg"}:
            files.append(
                {
                    "name": path.name,
                    "path": str(path),
                    "relative_path": str(path.relative_to(PLOTS_DIR)),
                    "size_bytes": path.stat().st_size,
                }
            )

    return files
