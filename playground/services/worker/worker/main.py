from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# ------------------------------------------------------------
# Locate project paths
# ------------------------------------------------------------

WORKER_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = WORKER_DIR.parents[1]
API_DIR = PROJECT_ROOT / "services" / "api"

# Allow importing the API database/config modules.
sys.path.insert(0, str(API_DIR))

from app.config import JOBS_DIR, PLOTS_DIR, ensure_storage_dirs  # noqa: E402
from app.database import (  # noqa: E402
    get_next_pending_job,
    get_run,
    init_db,
    mark_job_done,
    mark_job_error,
    mark_job_running,
)


SCRIPTS_DIR = PROJECT_ROOT / "scripts"

BENCHMARK_TO_SCRIPT = {
    "motivation": SCRIPTS_DIR / "mot.py",
    "attention_posner": SCRIPTS_DIR / "posner.py",
}


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------

def info(message: str) -> None:
    print(f"[WORKER] {message}", flush=True)


def safe_slug(value: str) -> str:
    cleaned = "".join(
        ch if ch.isalnum() or ch in {"_", "-", "."} else "_"
        for ch in str(value).strip()
    )
    cleaned = "_".join(part for part in cleaned.split("_") if part)

    if not cleaned:
        return "unnamed"

    return cleaned


def read_json_field(value: str | None) -> dict[str, Any]:
    if value is None or value == "":
        return {}

    try:
        data = json.loads(value)
    except Exception:
        return {}

    if isinstance(data, dict):
        return data

    return {}


def remove_dir_if_exists(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def symlink_or_copytree(source: Path, destination: Path) -> None:
    """
    Prefer symlink because it is fast.
    If symlink is unavailable, copy the folder.
    """

    if destination.exists():
        if destination.is_symlink():
            destination.unlink()
        elif destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()

    try:
        destination.symlink_to(source, target_is_directory=True)
    except Exception:
        shutil.copytree(source, destination)


def list_generated_plot_files(out_dir: Path) -> list[str]:
    if not out_dir.exists():
        return []

    allowed_suffixes = {".png", ".jpg", ".jpeg", ".pdf", ".svg"}

    files = []

    for path in sorted(out_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in allowed_suffixes:
            files.append(str(path))

    return files


def build_plot_input_root(
    *,
    job_id: str,
    agent_name: str,
    benchmark_out_path: Path,
) -> Path:
    """
    The plot scripts expect a structure like:

        root/
        └── AGENT_NAME/
            └── benchmark_out/
                ├── csv files

    But imported runs are stored as:

        data/results/AGENT/benchmark/run_xxx/benchmark_out/

    So for each job we create a temporary plotting input folder:

        data/jobs/JOB_ID/plot_input/AGENT_NAME/benchmark_out -> symlink to real benchmark_out
    """

    job_dir = JOBS_DIR / job_id
    plot_input_root = job_dir / "plot_input"

    remove_dir_if_exists(plot_input_root)

    agent_slug = safe_slug(agent_name)

    agent_dir = plot_input_root / agent_slug
    agent_dir.mkdir(parents=True, exist_ok=True)

    link_path = agent_dir / "benchmark_out"

    symlink_or_copytree(benchmark_out_path, link_path)

    return plot_input_root


def run_plot_script(
    *,
    job_id: str,
    benchmark: str,
    agent_name: str,
    benchmark_out_path: Path,
) -> dict[str, Any]:
    if benchmark not in BENCHMARK_TO_SCRIPT:
        raise ValueError(f"Unsupported benchmark for plotting: {benchmark}")

    script_path = BENCHMARK_TO_SCRIPT[benchmark]

    if not script_path.exists():
        raise FileNotFoundError(f"Plot script not found: {script_path}")

    if not benchmark_out_path.exists():
        raise FileNotFoundError(f"benchmark_out path not found: {benchmark_out_path}")

    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"

    plot_input_root = build_plot_input_root(
        job_id=job_id,
        agent_name=agent_name,
        benchmark_out_path=benchmark_out_path,
    )

    out_dir = PLOTS_DIR / benchmark / safe_slug(agent_name) / job_id
    remove_dir_if_exists(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    command = [
        sys.executable,
        str(script_path),
        "--root",
        str(plot_input_root),
        "--out",
        str(out_dir),
    ]

    env = os.environ.copy()
    env["MPLBACKEND"] = "Agg"

    info("Running plot command:")
    info(" ".join(command))

    with stdout_path.open("w", encoding="utf-8") as stdout_file, stderr_path.open("w", encoding="utf-8") as stderr_file:
        completed = subprocess.run(
            command,
            cwd=str(PROJECT_ROOT),
            stdout=stdout_file,
            stderr=stderr_file,
            env=env,
            text=True,
        )

    generated_files = list_generated_plot_files(out_dir)

    return {
        "command": command,
        "return_code": completed.returncode,
        "stdout_log": str(stdout_path),
        "stderr_log": str(stderr_path),
        "plot_input_root": str(plot_input_root),
        "output_dir": str(out_dir),
        "generated_files": generated_files,
        "generated_file_count": len(generated_files),
    }


# ------------------------------------------------------------
# Job handlers
# ------------------------------------------------------------

def handle_replot_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    input_data = read_json_field(job.get("input_json"))

    run_id = input_data.get("run_id")

    if not run_id:
        raise ValueError("Replot job is missing run_id")

    run = get_run(str(run_id))

    if run is None:
        raise ValueError(f"Run not found: {run_id}")

    benchmark = str(run["benchmark"])
    agent_name = str(run["agent_name"])
    benchmark_out_path = Path(str(run["benchmark_out_path"]))

    result = run_plot_script(
        job_id=job_id,
        benchmark=benchmark,
        agent_name=agent_name,
        benchmark_out_path=benchmark_out_path,
    )

    if result["return_code"] != 0:
        raise RuntimeError(
            "Plot script failed with return code "
            + str(result["return_code"])
            + ". See logs: "
            + result["stdout_log"]
            + " and "
            + result["stderr_log"]
        )

    mark_job_done(
        job_id=job_id,
        output_data=result,
        log_path=str(JOBS_DIR / job_id),
    )

    info(
        f"Job {job_id} done. "
        f"Generated {result['generated_file_count']} plot files."
    )


def process_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    job_type = str(job["job_type"])

    job_log_dir = JOBS_DIR / job_id
    job_log_dir.mkdir(parents=True, exist_ok=True)

    info(f"Processing job {job_id} of type {job_type}")

    mark_job_running(
        job_id=job_id,
        log_path=str(job_log_dir),
    )

    try:
        if job_type == "replot":
            handle_replot_job(job)
        else:
            raise ValueError(f"Unknown job type: {job_type}")

    except Exception as exc:
        error_message = str(exc)

        mark_job_error(
            job_id=job_id,
            error_message=error_message,
            output_data={
                "error": error_message,
            },
            log_path=str(job_log_dir),
        )

        info(f"Job {job_id} failed: {error_message}")


def process_next_job() -> bool:
    job = get_next_pending_job()

    if job is None:
        return False

    process_job(job)
    return True


def run_loop(*, once: bool, sleep_seconds: float) -> int:
    ensure_storage_dirs()
    init_db()

    info("Worker started")

    if once:
        processed = process_next_job()

        if not processed:
            info("No pending jobs found")

        return 0

    while True:
        processed = process_next_job()

        if not processed:
            time.sleep(sleep_seconds)


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CogScore Playground worker."
    )

    parser.add_argument(
        "--once",
        action="store_true",
        help="Process at most one pending job and exit.",
    )

    parser.add_argument(
        "--sleep",
        type=float,
        default=2.0,
        help="Sleep interval between polling attempts in daemon mode.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    return run_loop(
        once=args.once,
        sleep_seconds=args.sleep,
    )


if __name__ == "__main__":
    raise SystemExit(main())
