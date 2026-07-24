from __future__ import annotations
import json

import shutil
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Any

import yaml
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import (
    ARCHITECTURES_DIR,
    PLOTS_DIR,
    PROJECT_NAME,
    STORAGE_ROOT,
    ensure_storage_dirs,
)

from .database import (
    create_architecture,
    create_experiment_run,
    create_job,
    get_architecture,
    get_job,
    init_db,
    list_architectures,
    list_experiment_runs,
    list_jobs,
    list_runs,
    utc_now_iso,
)
from .schemas import (
    ArchitectureResponse,
    ExperimentRunResponse,
    HealthResponse,
    JobResponse,
    ReplotRequest,
    ReplotResponse,
    RunExperimentRequest,
    RunExperimentResponse,
    UploadArchitectureResponse,
)

from .services.storage import import_result_bundle
app = FastAPI(
    title="CogScore Online Runner API",
    description="API for validating external architectures and running CogScore experiments online.",
    version="0.2.0",
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


@app.get("/jobs", response_model=list[JobResponse])
def api_list_jobs() -> list[JobResponse]:
    return [JobResponse(**job) for job in list_jobs()]


@app.get("/jobs/{job_id}", response_model=JobResponse)
def api_get_job(job_id: str) -> JobResponse:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    return JobResponse(**job)


@app.get("/architectures", response_model=list[ArchitectureResponse])
def api_list_architectures() -> list[ArchitectureResponse]:
    return [ArchitectureResponse(**item) for item in list_architectures()]


@app.get("/architectures/{architecture_id}", response_model=ArchitectureResponse)
def api_get_architecture(architecture_id: str) -> ArchitectureResponse:
    item = get_architecture(architecture_id)
    if item is None:
        raise HTTPException(status_code=404, detail=f"Architecture not found: {architecture_id}")
    return ArchitectureResponse(**item)


def _safe_extract_zip(zip_path: Path, destination: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            member_path = destination / member.filename
            resolved = member_path.resolve()
            if not str(resolved).startswith(str(destination.resolve())):
                raise ValueError(f"Unsafe ZIP path: {member.filename}")
        zf.extractall(destination)


def _read_manifest(bundle_dir: Path) -> dict[str, Any]:
    manifest_path = bundle_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise ValueError("Architecture bundle must contain manifest.yaml at its root")

    with manifest_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError("manifest.yaml must be a YAML mapping")

    required = ["name", "version", "interface", "benchmarks"]
    missing = [field for field in required if field not in data]
    if missing:
        raise ValueError("manifest.yaml missing fields: " + ", ".join(missing))

    if data["interface"] != "rest":
        raise ValueError("Only interface: rest is supported in this online runner")

    declared_benchmarks = data.get("benchmarks", [])

    allowed = {"sensory_buffer", "attention_posner", "motivation", "learning"}

    if not any(item in allowed for item in declared_benchmarks):
        raise ValueError(
            "Architecture must declare at least one supported benchmark: "
            + ", ".join(sorted(allowed))
        )
    return data


@app.post("/architectures/upload", response_model=UploadArchitectureResponse)
async def upload_architecture(file: UploadFile = File(...)) -> UploadArchitectureResponse:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename")

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip architecture bundles are accepted")

    architecture_id = "arch_" + uuid.uuid4().hex[:12]
    architecture_dir = ARCHITECTURES_DIR / architecture_id
    source_dir = architecture_dir / "source"
    architecture_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(tempfile.mkdtemp(prefix="cogscore_arch_upload_"))
    temp_file = temp_dir / file.filename

    try:
        with temp_file.open("wb") as f:
            shutil.copyfileobj(file.file, f)

        try:
            _safe_extract_zip(temp_file, source_dir)
            manifest = _read_manifest(source_dir)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        record = {
            "id": architecture_id,
            "name": str(manifest["name"]),
            "version": str(manifest["version"]),
            "author": manifest.get("author"),
            "interface_type": "rest",
            "status": "uploaded",
            "storage_path": str(architecture_dir),
            "image_tag": None,
            "manifest": manifest,
            "created_at": utc_now_iso(),
            "validated_at": None,
            "error_message": None,
        }

        create_architecture(record)

        validation_job_id = "job_" + uuid.uuid4().hex[:12]
        create_job(
            job_id=validation_job_id,
            job_type="validate_architecture",
            input_data={
                "architecture_id": architecture_id,
                "architecture_path": str(architecture_dir),
                "source_path": str(source_dir),
            },
        )

        return UploadArchitectureResponse(
            ok=True,
            architecture_id=architecture_id,
            validation_job_id=validation_job_id,
            message="Architecture uploaded. Validation job created.",
        )

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.post("/jobs/run-experiment", response_model=RunExperimentResponse)
def run_experiment(request: RunExperimentRequest) -> RunExperimentResponse:
    architecture = get_architecture(request.architecture_id)
    if architecture is None:
        raise HTTPException(status_code=404, detail=f"Architecture not found: {request.architecture_id}")

    if architecture["status"] != "validated":
        raise HTTPException(
            status_code=400,
            detail="Architecture must be validated before running experiments",
        )

    supported_benchmarks = {"sensory_buffer", "attention_posner", "motivation", "learning"}

    if request.benchmark not in supported_benchmarks:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported benchmark: {request.benchmark}. Supported: {sorted(supported_benchmarks)}",
        )

    manifest = json.loads(architecture.get("manifest_json") or "{}")
    declared_benchmarks = manifest.get("benchmarks", [])
    if isinstance(declared_benchmarks, list) and request.benchmark not in declared_benchmarks:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Architecture {request.architecture_id} does not declare "
                f"benchmark {request.benchmark}. Declared: {declared_benchmarks}"
            ),
        )

    default_scenes = {
        "sensory_buffer": "sperling.ttt",
        "attention_posner": "posner.ttt",
        "motivation": "mot.ttt",
        "learning": "learning/testing_s1A.ttt",
    }
    scene = request.scene or default_scenes[request.benchmark]

    run_id = "run_" + uuid.uuid4().hex[:12]
    job_id = "job_" + uuid.uuid4().hex[:12]

    parameters = request.model_dump()
    parameters["scene"] = scene

    create_experiment_run(
        {
            "id": run_id,
            "architecture_id": request.architecture_id,
            "benchmark": request.benchmark,
            "scene": scene,
            "status": "pending",
            "parameters": parameters,
            "result_path": None,
            "job_id": job_id,
            "created_at": utc_now_iso(),
            "finished_at": None,
            "error_message": None,
        }
    )
    if request.benchmark == "sensory_buffer":
        job_type = "run_sensory_remote"
    elif request.benchmark == "attention_posner":
        job_type = "run_attention_remote"
    elif request.benchmark == "motivation":
        job_type = "run_motivation_remote"    
    elif request.benchmark == "learning":
        job_type = "run_learning_remote"    
    else:
        raise HTTPException(status_code=400, detail="Unsupported benchmark")

    create_job(
        job_id=job_id,
        job_type=job_type,
        input_data={
            "run_id": run_id,
            "architecture_id": request.architecture_id,
            "parameters": parameters,
        },
    )

    return RunExperimentResponse(
        ok=True,
        run_id=run_id,
        job_id=job_id,
        message=f"{request.benchmark} experiment job created.",
    )

@app.post("/uploads/results")
async def upload_results(file: UploadFile = File(...)) -> dict[str, Any]:
    if file.filename is None:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file has no filename",
        )

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(
            status_code=400,
            detail="Only .zip result bundles are accepted",
        )

    temp_dir = Path(
        tempfile.mkdtemp(prefix="cogscore_result_upload_")
    )
    temp_file = temp_dir / Path(file.filename).name

    try:
        with temp_file.open("wb") as destination:
            shutil.copyfileobj(file.file, destination)

        try:
            imported = import_result_bundle(
                temp_file,
                file.filename,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        return {
            "ok": True,
            "message": (
                "Result bundle imported and plot job created."
            ),
            **imported,
        }

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)



@app.post("/plots/rebuild", response_model=ReplotResponse)
def rebuild_comparison_plots(request: ReplotRequest) -> ReplotResponse:
    """Create fresh comparison plots using every previously uploaded agent."""
    supported = [
        "sensory_buffer",
        "attention_posner",
        "motivation",
        "learning",
    ]

    available = {
        str(run.get("benchmark"))
        for run in list_runs()
        if str(run.get("benchmark")) in supported
    }

    if request.benchmark == "all":
        benchmarks = [item for item in supported if item in available]
    else:
        benchmarks = [request.benchmark] if request.benchmark in available else []

    if not benchmarks:
        selected = "any benchmark" if request.benchmark == "all" else request.benchmark
        raise HTTPException(
            status_code=404,
            detail=f"No imported results were found for {selected}.",
        )

    created: list[dict[str, str]] = []

    for benchmark in benchmarks:
        benchmark_runs = list_runs(benchmark=benchmark, limit=1)
        reference_run_id = (
            str(benchmark_runs[0]["id"])
            if benchmark_runs
            else ""
        )
        job_id = "job_" + uuid.uuid4().hex[:12]

        create_job(
            job_id=job_id,
            job_type="replot",
            input_data={
                "run_id": reference_run_id,
                "benchmark": benchmark,
                "mode": "comparison_all_uploaded_agents",
                "trigger": "plots_rebuild_button",
            },
        )

        created.append({
            "benchmark": benchmark,
            "job_id": job_id,
        })

    return ReplotResponse(
        ok=True,
        message=(
            "New comparison jobs were created. "
            "Each job creates a new plot directory without deleting previous ones."
        ),
        jobs=created,
    )

@app.get("/plots")
def list_plots() -> list[dict[str, Any]]:
    ensure_storage_dirs()

    supported_extensions = {
        ".png",
        ".jpg",
        ".jpeg",
        ".webp",
        ".svg",
        ".html",
        ".pdf",
    }

    items: list[dict[str, Any]] = []

    for path in PLOTS_DIR.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in supported_extensions:
            continue

        stat = path.stat()

        items.append(
            {
                "name": path.name,
                "relative_path": str(
                    path.relative_to(PLOTS_DIR)
                ),
                "path": str(path),
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )

    return sorted(
        items,
        key=lambda item: item["modified_at"],
        reverse=True,
    )

@app.get("/experiment-runs", response_model=list[ExperimentRunResponse])
def api_list_experiment_runs() -> list[ExperimentRunResponse]:
    return [ExperimentRunResponse(**item) for item in list_experiment_runs()]
