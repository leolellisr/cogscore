from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    project: str
    storage_root: str


class RunResponse(BaseModel):
    id: str
    agent_name: str
    architecture_name: str
    benchmark: str
    benchmark_version: str
    cogscore_version: str
    run_name: str
    run_date: str
    seed: int | None = None
    episodes: int | None = None
    trials_per_experiment: int | None = None
    status: str
    storage_path: str
    benchmark_out_path: str
    manifest_json: str
    created_at: str


class JobResponse(BaseModel):
    id: str
    job_type: str
    status: str
    input_json: str
    output_json: str | None = None
    log_path: str | None = None
    error_message: str | None = None
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None


class UploadResultResponse(BaseModel):
    ok: bool
    run_id: str
    job_id: str
    message: str
    validation_warnings: list[str]


class ValidationErrorResponse(BaseModel):
    ok: bool
    errors: list[str]
    warnings: list[str] = []


class PlotFileResponse(BaseModel):
    name: str
    path: str
    relative_path: str
    size_bytes: int

