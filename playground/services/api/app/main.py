from __future__ import annotations
import json

import shutil
import tempfile
import uuid
import zipfile
import os
import urllib.request
from datetime import datetime, timezone
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
    MAX_UPLOAD_BYTES,
    SIM_VNC_INTERNAL_URL,
    WORKER_HEARTBEAT_PATH,
    ensure_storage_dirs,
)

from .database import (
    create_architecture,
    create_experiment_run,
    create_job,
    get_architecture,
    get_job,
    get_experiment_run,
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
    RetryJobResponse,
    RetryExperimentRunResponse,
    SimulatorControlRequest,
    SimulatorControlResponse,
)
from .plot_metadata import build_plot_metadata

from .services.storage import import_result_bundle
from .cogscore_matrix import compute_matrices
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



def _upload_size_guard(file: UploadFile) -> None:
    content_length = file.headers.get("content-length")
    if content_length:
        try:
            size = int(content_length)
        except ValueError:
            size = 0
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Upload exceeds the configured limit of "
                    f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
                ),
            )


def _job_type_for_benchmark(benchmark: str) -> str:
    mapping = {
        "sensory_buffer": "run_sensory_remote",
        "attention_posner": "run_attention_remote",
        "motivation": "run_motivation_remote",
        "learning": "run_learning_remote",
    }
    try:
        return mapping[benchmark]
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="Unsupported benchmark") from exc


def _create_experiment_job(
    *,
    architecture_id: str,
    benchmark: str,
    parameters: dict[str, Any],
    scene: str,
) -> tuple[str, str]:
    run_id = "run_" + uuid.uuid4().hex[:12]
    job_id = "job_" + uuid.uuid4().hex[:12]

    create_experiment_run(
        {
            "id": run_id,
            "architecture_id": architecture_id,
            "benchmark": benchmark,
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
    create_job(
        job_id=job_id,
        job_type=_job_type_for_benchmark(benchmark),
        input_data={
            "run_id": run_id,
            "architecture_id": architecture_id,
            "parameters": parameters,
        },
    )
    return run_id, job_id


def _storage_size(path: Path) -> int:
    total = 0
    try:
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    pass
    except OSError:
        return 0
    return total


def _worker_heartbeat() -> dict[str, Any]:
    if not WORKER_HEARTBEAT_PATH.is_file():
        return {"status": "unknown", "last_seen": None}
    try:
        payload = json.loads(WORKER_HEARTBEAT_PATH.read_text(encoding="utf-8"))
        timestamp = str(payload.get("timestamp") or "")
        last_seen = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - last_seen).total_seconds()
        return {
            "status": "online" if age <= 15 else "stale",
            "last_seen": timestamp,
            "age_seconds": round(age, 1),
        }
    except Exception:
        return {"status": "unknown", "last_seen": None}


def _simulator_status() -> dict[str, Any]:
    try:
        with urllib.request.urlopen(SIM_VNC_INTERNAL_URL, timeout=2) as response:
            available = 200 <= response.status < 400
    except Exception:
        available = False
    return {
        "status": "online" if available else "offline",
        "vnc_available": available,
    }


@app.post("/architectures/upload", response_model=UploadArchitectureResponse)
async def upload_architecture(file: UploadFile = File(...)) -> UploadArchitectureResponse:
    if file.filename is None:
        raise HTTPException(status_code=400, detail="Uploaded file has no filename")

    _upload_size_guard(file)

    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip architecture bundles are accepted")

    architecture_id = "arch_" + uuid.uuid4().hex[:12]
    architecture_dir = ARCHITECTURES_DIR / architecture_id
    source_dir = architecture_dir / "source"
    architecture_dir.mkdir(parents=True, exist_ok=True)
    source_dir.mkdir(parents=True, exist_ok=True)

    temp_dir = Path(tempfile.mkdtemp(prefix="cogscore_arch_upload_"))
    temp_file = temp_dir / Path(file.filename).name

    try:
        with temp_file.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        if temp_file.stat().st_size > MAX_UPLOAD_BYTES:
            shutil.rmtree(architecture_dir, ignore_errors=True)
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Upload exceeds the configured limit of "
                    f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
                ),
            )

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

    parameters = request.model_dump()
    parameters["scene"] = scene
    run_id, job_id = _create_experiment_job(
        architecture_id=request.architecture_id,
        benchmark=request.benchmark,
        parameters=parameters,
        scene=scene,
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

    _upload_size_guard(file)

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
        if temp_file.stat().st_size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Upload exceeds the configured limit of "
                    f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB"
                ),
            )

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


@app.get("/dashboard/summary")
def dashboard_summary() -> dict[str, Any]:
    jobs = list_jobs()
    architectures = list_architectures()
    experiment_runs = list_experiment_runs()
    imported_runs = list_runs()

    def counts_by_status(items: list[dict[str, Any]]) -> dict[str, int]:
        result: dict[str, int] = {}
        for item in items:
            status = str(item.get("status") or "unknown")
            result[status] = result.get(status, 0) + 1
        return result

    return {
        "api": {"status": "online"},
        "worker": _worker_heartbeat(),
        "simulator": _simulator_status(),
        "counts": {
            "architectures": len(architectures),
            "validated_architectures": sum(
                1 for item in architectures if item.get("status") == "validated"
            ),
            "jobs": len(jobs),
            "active_jobs": sum(
                1 for item in jobs if item.get("status") in {"pending", "running"}
            ),
            "failed_jobs": sum(1 for item in jobs if item.get("status") == "error"),
            "experiment_runs": len(experiment_runs),
            "imported_runs": len(imported_runs),
            "plots": sum(1 for path in PLOTS_DIR.rglob("*") if path.is_file()),
            "storage_bytes": _storage_size(STORAGE_ROOT),
        },
        "job_status": counts_by_status(jobs),
        "architecture_status": counts_by_status(architectures),
        "run_status": counts_by_status(experiment_runs),
        "recent_jobs": jobs[:8],
        "recent_runs": experiment_runs[:8],
    }




@app.get("/cogscore/matrices")
def api_cogscore_matrices() -> dict[str, Any]:
    """Compute CogScore matrices from the latest stored result of each imported agent."""
    return compute_matrices()

@app.get("/runs")
def api_list_imported_runs() -> list[dict[str, Any]]:
    return list_runs()


@app.post("/jobs/{job_id}/retry", response_model=RetryJobResponse)
def retry_job(job_id: str) -> RetryJobResponse:
    source = get_job(job_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    if source["status"] in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="The job is still active")
    if str(source["job_type"]).startswith("run_"):
        raise HTTPException(
            status_code=400,
            detail="Retry experiment jobs from the Experiment runs page",
        )

    new_job_id = "job_" + uuid.uuid4().hex[:12]
    create_job(
        job_id=new_job_id,
        job_type=str(source["job_type"]),
        input_data=json.loads(source["input_json"]),
    )
    return RetryJobResponse(
        ok=True,
        source_job_id=job_id,
        job_id=new_job_id,
        message="A new job was created with the same input.",
    )


@app.post(
    "/experiment-runs/{run_id}/retry",
    response_model=RetryExperimentRunResponse,
)
def retry_experiment_run(run_id: str) -> RetryExperimentRunResponse:
    source = get_experiment_run(run_id)
    if source is None:
        raise HTTPException(status_code=404, detail=f"Experiment run not found: {run_id}")
    if source["status"] in {"pending", "running"}:
        raise HTTPException(status_code=409, detail="The experiment run is still active")

    parameters = json.loads(source["parameters_json"])
    new_run_id, new_job_id = _create_experiment_job(
        architecture_id=str(source["architecture_id"]),
        benchmark=str(source["benchmark"]),
        parameters=parameters,
        scene=str(source["scene"]),
    )
    return RetryExperimentRunResponse(
        ok=True,
        source_run_id=run_id,
        run_id=new_run_id,
        job_id=new_job_id,
        message="A new experiment run was created with the same settings.",
    )


@app.get("/simulator/status")
def simulator_status() -> dict[str, Any]:
    return _simulator_status()


@app.post("/simulator/control", response_model=SimulatorControlResponse)
def simulator_control(request: SimulatorControlRequest) -> SimulatorControlResponse:
    default_scene = "sperling.ttt"
    job_id = "job_" + uuid.uuid4().hex[:12]
    create_job(
        job_id=job_id,
        job_type="simulator_control",
        input_data={
            "action": request.action,
            "scene": request.scene or default_scene,
        },
    )
    return SimulatorControlResponse(
        ok=True,
        job_id=job_id,
        message=f"Simulator {request.action} job created.",
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
                "metadata": build_plot_metadata(path),
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
