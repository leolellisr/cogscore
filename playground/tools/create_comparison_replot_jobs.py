#!/usr/bin/env python3

from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
API_DIR = PROJECT_ROOT / "services" / "api"

sys.path.insert(0, str(API_DIR))

from app.config import ensure_storage_dirs  # noqa: E402
from app.database import create_job, init_db, list_runs  # noqa: E402


def latest_run_for_benchmark(benchmark: str) -> dict | None:
    runs = list_runs()

    for run in runs:
        if str(run.get("benchmark")) == benchmark:
            return run

    return None


def create_replot_job_for_benchmark(benchmark: str) -> str | None:
    run = latest_run_for_benchmark(benchmark)

    if run is None:
        print(f"[WARN] No run found for benchmark: {benchmark}")
        return None

    job_id = uuid.uuid4().hex

    create_job(
        job_id=job_id,
        job_type="replot",
        status="pending",
        input_data={
            "run_id": run["id"],
            "benchmark": benchmark,
            "mode": "comparison_all_uploaded_agents",
            "note": (
                "This job uses one run_id only to identify the benchmark. "
                "The worker will include all latest uploaded runs for this benchmark."
            ),
        },
    )

    print(
        f"[OK] Created comparison replot job for benchmark={benchmark}: {job_id}"
    )

    return job_id


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create comparison replot jobs for existing uploaded runs."
    )

    parser.add_argument(
        "--benchmark",
        action="append",
        choices=["motivation", "attention_posner", "sensory_buffer", "learning"],
        help=(
            "Benchmark to replot. Can be passed multiple times. "
            "If omitted, all benchmarks are used."
        ),
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    ensure_storage_dirs()
    init_db()

    benchmarks = args.benchmark or ["motivation", "attention_posner", "sensory_buffer", "learning"]

    created = []

    for benchmark in benchmarks:
        job_id = create_replot_job_for_benchmark(benchmark)
        print("Created replot for:")
        print(benchmark)
        if job_id is not None:
            created.append(job_id)

    if not created:
        print("[WARN] No jobs created.")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
