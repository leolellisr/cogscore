from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from .config import DATABASE_PATH, ensure_storage_dirs


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_connection() -> sqlite3.Connection:
    ensure_storage_dirs()
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def list_runs(
    benchmark: str | None = None,
    agent_name: str | None = None,
    status: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    query = """
        SELECT *
        FROM runs
    """

    clauses: list[str] = []
    params: list[Any] = []

    if benchmark:
        clauses.append("benchmark = ?")
        params.append(benchmark)

    if agent_name:
        clauses.append("agent_name = ?")
        params.append(agent_name)

    if status:
        clauses.append("status = ?")
        params.append(status)

    if clauses:
        query += " WHERE " + " AND ".join(clauses)

    query += " ORDER BY created_at DESC"

    if limit is not None:
        query += " LIMIT ?"
        params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()

    return [dict(row) for row in rows]

def create_run(record: dict[str, Any]) -> dict[str, Any]:
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
                record["id"],
                record["agent_name"],
                record["architecture_name"],
                record["benchmark"],
                record["benchmark_version"],
                record["cogscore_version"],
                record["run_name"],
                record["run_date"],
                record.get("seed"),
                record.get("episodes"),
                record.get("trials_per_experiment"),
                record["status"],
                record["storage_path"],
                record["benchmark_out_path"],
                json.dumps(record["manifest"], ensure_ascii=False),
                record["created_at"],
            ),
        )
        conn.commit()

    return record

def init_db() -> None:
    ensure_storage_dirs()

    with get_connection() as conn:
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
            CREATE TABLE IF NOT EXISTS architectures (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                version TEXT NOT NULL,
                author TEXT,
                interface_type TEXT NOT NULL,
                status TEXT NOT NULL,
                storage_path TEXT NOT NULL,
                image_tag TEXT,
                manifest_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                validated_at TEXT,
                error_message TEXT
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS experiment_runs (
                id TEXT PRIMARY KEY,
                architecture_id TEXT NOT NULL,
                benchmark TEXT NOT NULL,
                scene TEXT NOT NULL,
                status TEXT NOT NULL,
                parameters_json TEXT NOT NULL,
                result_path TEXT,
                job_id TEXT,
                created_at TEXT NOT NULL,
                finished_at TEXT,
                error_message TEXT
            )
            """
        )
        conn.execute(
            """
            UPDATE jobs
            SET input_json = REPLACE(
                input_json,
                '"plots_refazer_button"',
                '"plots_rebuild_button"'
            )
            WHERE input_json LIKE '%plots_refazer_button%'
            """
        )

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
        conn.commit()


def create_job(
    *,
    job_id: str,
    job_type: str,
    input_data: dict[str, Any],
    status: str = "pending",
) -> dict[str, Any]:
    job = {
        "id": job_id,
        "job_type": job_type,
        "status": status,
        "input_json": json.dumps(input_data, ensure_ascii=False),
        "output_json": None,
        "log_path": None,
        "error_message": None,
        "created_at": utc_now_iso(),
        "started_at": None,
        "finished_at": None,
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (
                id, job_type, status, input_json, output_json,
                log_path, error_message, created_at, started_at, finished_at
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


def get_job(job_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()
    return row_to_dict(row)


def list_jobs() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_next_pending_job() -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            """
        ).fetchone()

    return row_to_dict(row)


def mark_job_running(*, job_id: str, log_path: str | None = None) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'running',
                started_at = ?,
                log_path = ?
            WHERE id = ?
            """,
            (utc_now_iso(), log_path, job_id),
        )
        conn.commit()


def mark_job_done(
    *,
    job_id: str,
    output_data: dict[str, Any] | None = None,
    log_path: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'done',
                finished_at = ?,
                output_json = ?,
                log_path = ?
            WHERE id = ?
            """,
            (
                utc_now_iso(),
                json.dumps(output_data or {}, ensure_ascii=False),
                log_path,
                job_id,
            ),
        )
        conn.commit()


def mark_job_error(
    *,
    job_id: str,
    error_message: str,
    output_data: dict[str, Any] | None = None,
    log_path: str | None = None,
) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'error',
                finished_at = ?,
                error_message = ?,
                output_json = ?,
                log_path = ?
            WHERE id = ?
            """,
            (
                utc_now_iso(),
                error_message,
                json.dumps(output_data or {}, ensure_ascii=False),
                log_path,
                job_id,
            ),
        )
        conn.commit()


def mark_interrupted_jobs_error(
    error_message: str = "Worker restarted before the job finished.",
) -> list[str]:
    """Close jobs left as running by a stopped or killed worker process."""
    now = utc_now_iso()

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, job_type, input_json FROM jobs WHERE status = 'running'"
        ).fetchall()

        interrupted_ids = [str(row["id"]) for row in rows]
        if not interrupted_ids:
            return []

        conn.execute(
            """
            UPDATE jobs
            SET status = 'error',
                finished_at = ?,
                error_message = ?,
                output_json = ?
            WHERE status = 'running'
            """,
            (
                now,
                error_message,
                json.dumps({"error": error_message}, ensure_ascii=False),
            ),
        )

        experiment_run_ids: set[str] = set()
        for row in rows:
            if not str(row["job_type"]).startswith("run_"):
                continue
            try:
                input_data = json.loads(str(row["input_json"]))
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            run_id = input_data.get("run_id") if isinstance(input_data, dict) else None
            if run_id:
                experiment_run_ids.add(str(run_id))

        if experiment_run_ids:
            placeholders = ",".join("?" for _ in experiment_run_ids)
            conn.execute(
                f"""
                UPDATE experiment_runs
                SET status = 'error',
                    finished_at = ?,
                    error_message = ?
                WHERE id IN ({placeholders})
                  AND status NOT IN ('done', 'error')
                """,
                (now, error_message, *sorted(experiment_run_ids)),
            )

        conn.commit()

    return interrupted_ids


def create_architecture(record: dict[str, Any]) -> dict[str, Any]:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO architectures (
                id, name, version, author, interface_type, status,
                storage_path, image_tag, manifest_json, created_at,
                validated_at, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["name"],
                record["version"],
                record.get("author"),
                record["interface_type"],
                record["status"],
                record["storage_path"],
                record.get("image_tag"),
                json.dumps(record["manifest"], ensure_ascii=False),
                record["created_at"],
                record.get("validated_at"),
                record.get("error_message"),
            ),
        )
        conn.commit()

    return record


def list_architectures() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM architectures ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def get_architecture(architecture_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM architectures WHERE id = ?",
            (architecture_id,),
        ).fetchone()
    return row_to_dict(row)


def update_architecture_status(
    *,
    architecture_id: str,
    status: str,
    image_tag: str | None = None,
    error_message: str | None = None,
) -> None:
    validated_at = utc_now_iso() if status == "validated" else None

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE architectures
            SET status = ?,
                image_tag = COALESCE(?, image_tag),
                validated_at = COALESCE(?, validated_at),
                error_message = ?
            WHERE id = ?
            """,
            (status, image_tag, validated_at, error_message, architecture_id),
        )
        conn.commit()


def create_experiment_run(record: dict[str, Any]) -> dict[str, Any]:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO experiment_runs (
                id, architecture_id, benchmark, scene, status,
                parameters_json, result_path, job_id, created_at,
                finished_at, error_message
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["id"],
                record["architecture_id"],
                record["benchmark"],
                record["scene"],
                record["status"],
                json.dumps(record["parameters"], ensure_ascii=False),
                record.get("result_path"),
                record.get("job_id"),
                record["created_at"],
                record.get("finished_at"),
                record.get("error_message"),
            ),
        )
        conn.commit()

    return record


def list_experiment_runs() -> list[dict[str, Any]]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM experiment_runs ORDER BY created_at DESC"
        ).fetchall()
    return [dict(row) for row in rows]




def get_experiment_run(run_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM experiment_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    return row_to_dict(row)


def get_run(run_id: str) -> dict[str, Any] | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM runs WHERE id = ?",
            (run_id,),
        ).fetchone()
    return row_to_dict(row)

def update_experiment_run_status(
    *,
    run_id: str,
    status: str,
    result_path: str | None = None,
    error_message: str | None = None,
) -> None:
    finished_at = utc_now_iso() if status in {"done", "error"} else None

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE experiment_runs
            SET status = ?,
                result_path = COALESCE(?, result_path),
                finished_at = COALESCE(?, finished_at),
                error_message = ?
            WHERE id = ?
            """,
            (status, result_path, finished_at, error_message, run_id),
        )
        conn.commit()
