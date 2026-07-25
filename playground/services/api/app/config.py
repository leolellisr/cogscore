from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


APP_DIR = Path(__file__).resolve().parent
API_DIR = APP_DIR.parent
SERVICES_DIR = API_DIR.parent
PROJECT_ROOT = SERVICES_DIR.parent

DEFAULT_DATABASE_PATH = (
    PROJECT_ROOT
    / "data"
    / "db"
    / "playground.sqlite"
)

DATABASE_PATH = Path(
    os.getenv(
        "DATABASE_PATH",
        str(DEFAULT_DATABASE_PATH),
    )
).resolve()
load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


PROJECT_NAME = os.getenv("PROJECT_NAME", "cogscore-online-runner")

LOCAL_STORAGE_ROOT = os.getenv("LOCAL_STORAGE_ROOT", "data")
STORAGE_ROOT = _resolve_path(LOCAL_STORAGE_ROOT)

UPLOADS_DIR = STORAGE_ROOT / "uploads"
UPLOADS_RAW_DIR = UPLOADS_DIR / "raw"
RESULTS_DIR = STORAGE_ROOT / "results"
PLOTS_DIR = STORAGE_ROOT / "plots"
JOBS_DIR = STORAGE_ROOT / "jobs"
ARCHITECTURES_DIR = STORAGE_ROOT / "architectures"
DB_DIR = STORAGE_ROOT / "db"
DATABASE_PATH = DB_DIR / "playground.sqlite"

COGSCORE_DOCKER_NETWORK = os.getenv("COGSCORE_DOCKER_NETWORK", "cogscore_online_net")

MAX_ARCH_CPU = os.getenv("MAX_ARCH_CPU", "2")
MAX_ARCH_MEMORY = os.getenv("MAX_ARCH_MEMORY", "4g")
ARCH_TIMEOUT_SECONDS = int(os.getenv("ARCH_TIMEOUT_SECONDS", "120"))
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))
SIM_VNC_INTERNAL_URL = os.getenv("SIM_VNC_INTERNAL_URL", "http://sim-vnc:6080/vnc.html")
WORKER_HEARTBEAT_PATH = STORAGE_ROOT / "worker-heartbeat.json"


def ensure_storage_dirs() -> None:
    for path in [
        STORAGE_ROOT,
        UPLOADS_DIR,
        UPLOADS_RAW_DIR,
        RESULTS_DIR,
        PLOTS_DIR,
        JOBS_DIR,
        ARCHITECTURES_DIR,
        DB_DIR,
    ]:
        path.mkdir(parents=True, exist_ok=True)
