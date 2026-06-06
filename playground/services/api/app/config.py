from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[3]

load_dotenv(PROJECT_ROOT / ".env")


def _resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()

    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


PROJECT_NAME = os.getenv("PROJECT_NAME", "cogscore-playground")

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
