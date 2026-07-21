
from __future__ import annotations

import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import RESULTS_DIR, UPLOADS_RAW_DIR, ensure_storage_dirs
from ..database import create_job, create_run, utc_now_iso
from .validation import validate_result_bundle


def safe_slug(value: str) -> str:
    value = str(value).strip()
    value = value.replace(" ", "_")
    value = re.sub(r"[^A-Za-z0-9_.-]+", "_", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_")

    if not value:
        return "unnamed"

    return value


def copy_uploaded_file(source_path: Path, original_filename: str) -> Path:
    ensure_storage_dirs()

    upload_id = uuid.uuid4().hex
    safe_name = safe_slug(original_filename)

    destination = UPLOADS_RAW_DIR / f"{upload_id}_{safe_name}"

    shutil.copy2(source_path, destination)

    return destination


def extract_parameters(manifest: dict[str, Any]) -> dict[str, int | None]:
    parameters = manifest.get("parameters", {})

    if not isinstance(parameters, dict):
        parameters = {}

    seed = parameters.get("seed")
    episodes = parameters.get("episodes")
    trials_per_experiment = parameters.get("trials_per_experiment")

    def to_int_or_none(value: Any) -> int | None:
        try:
            if value is None:
                return None
            return int(value)
        except Exception:
            return None

    return {
        "seed": to_int_or_none(seed),
        "episodes": to_int_or_none(episodes),
        "trials_per_experiment": to_int_or_none(trials_per_experiment),
    }


def import_result_bundle(zip_path: Path, original_filename: str) -> dict[str, Any]:
    """
    Validate and import a result bundle.

    Returns:
        {
            "run": ...,
            "job": ...,
            "warnings": [...]
        }
    """

    ensure_storage_dirs()

    validation = validate_result_bundle(zip_path)

    if not validation.valid:
        raise ValueError("; ".join(validation.errors))

    if validation.manifest is None or validation.root is None:
        raise ValueError("Validation succeeded but manifest/root is missing")

    manifest = validation.manifest

    run_id = uuid.uuid4().hex
    job_id = uuid.uuid4().hex

    agent_name = str(manifest["agent_name"])
    architecture_name = str(manifest["architecture_name"])
    benchmark = str(manifest["benchmark"])
    benchmark_version = str(manifest["benchmark_version"])
    cogscore_version = str(manifest["cogscore_version"])
    run_name = str(manifest["run_name"])
    run_date = str(manifest["date"])

    params = extract_parameters(manifest)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y%m%d_%H%M%S")

    agent_slug = safe_slug(agent_name)
    benchmark_slug = safe_slug(benchmark)

    run_folder_name = f"run_{timestamp}_{run_id[:8]}"

    destination_root = RESULTS_DIR / agent_slug / benchmark_slug / run_folder_name

    if destination_root.exists():
        raise ValueError(f"Destination already exists: {destination_root}")

    shutil.copytree(validation.root, destination_root)

    copied_zip_path = copy_uploaded_file(zip_path, original_filename)

    benchmark_out_path = destination_root / "benchmark_out"

    run = {
        "id": run_id,
        "agent_name": agent_name,
        "architecture_name": architecture_name,
        "benchmark": benchmark,
        "benchmark_version": benchmark_version,
        "cogscore_version": cogscore_version,
        "run_name": run_name,
        "run_date": run_date,
        "seed": params["seed"],
        "episodes": params["episodes"],
        "trials_per_experiment": params["trials_per_experiment"],
        "status": "imported",
        "storage_path": str(destination_root),
        "benchmark_out_path": str(benchmark_out_path),
        "manifest": manifest,
        "created_at": utc_now_iso(),
    }

    created_run = create_run(run)

    job = create_job(
        job_id=job_id,
        job_type="replot",
        status="pending",
        input_data={
            "run_id": run_id,
            "benchmark": benchmark,
            "agent_name": agent_name,
            "storage_path": str(destination_root),
            "benchmark_out_path": str(benchmark_out_path),
            "uploaded_zip_path": str(copied_zip_path),
            "mode": "comparison_all_uploaded_agents",
            "trigger": "result_upload",
        },
    )

    if validation.temp_dir is not None and validation.temp_dir.exists():
        shutil.rmtree(validation.temp_dir, ignore_errors=True)

    return {
        "run": created_run,
        "job": job,
        "warnings": validation.warnings,
    }
