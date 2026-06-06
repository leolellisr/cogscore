from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import PROJECT_NAME, STORAGE_ROOT, ensure_storage_dirs
from .database import get_job, get_run, init_db, list_jobs, list_plot_files, list_runs
from .schemas import (
    HealthResponse,
    JobResponse,
    PlotFileResponse,
    RunResponse,
    UploadResultResponse,
)
from .services.storage import import_result_bundle


app = FastAPI(
    title="CogScore Playground API",
    description="API for uploading, validating, storing, and comparing CogScore experiment results.",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    ensure_storage_dirs()
    init_db()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        project=PROJECT_NAME,
        storage_root=str(STORAGE_ROOT),
    )


@app.get("/runs", response_model=list[RunResponse])
def api_list_runs() -> list[RunResponse]:
    return [RunResponse(**run) for run in list_runs()]


@app.get("/runs/{run_id}", response_model=RunResponse)
def api_get_run(run_id: str) -> RunResponse:
    run = get_run(run_id)

    if run is None:
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")

    return RunResponse(**run)


@app.get("/jobs", response_model=list[JobResponse])
def api_list_jobs() -> list[JobResponse]:
    return [JobResponse(**job) for job in list_jobs()]


@app.get("/jobs/{job_id}", response_model=JobResponse)
def api_get_job(job_id: str) -> JobResponse:
    job = get_job(job_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")

    return JobResponse(**job)


@app.get("/plots", response_model=list[PlotFileResponse])
def api_list_plots() -> list[PlotFileResponse]:
    return [PlotFileResponse(**plot) for plot in list_plot_files()]


@app.post("/uploads/results", response_model=UploadResultResponse)
async def upload_results(file: UploadFile = File(...)) -> UploadResultResponse:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename")

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip result bundles are accepted")

    temp_dir = Path(tempfile.mkdtemp(prefix="cogscore_upload_"))
    temp_file = temp_dir / file.filename

    try:
        with temp_file.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        try:
            result = import_result_bundle(
                zip_path=temp_file,
                original_filename=file.filename,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail={
                    "ok": False,
                    "errors": [str(exc)],
                },
            ) from exc

        run = result["run"]
        job = result["job"]
        warnings = result["warnings"]

        return UploadResultResponse(
            ok=True,
            run_id=run["id"],
            job_id=job["id"],
            message="Result bundle uploaded, validated, and imported. Replot job created.",
            validation_warnings=warnings,
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
