# CogScore Playground API

FastAPI backend for the CogScore Playground.

## Current features

- Health endpoint
- Upload of result bundles
- Validation of uploaded ZIP files
- Import into `data/results`
- SQLite registry of runs
- Creation of pending replot jobs
- Listing of runs, jobs, and plot files

## Run locally

From the project root:

source .venv/bin/activate
cd services/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Open:
http://localhost:8000/docs
Test upload

From another terminal, in the project root:
curl -F "file=@data/uploads/example_motivation_bundle.zip" \
  http://localhost:8000/uploads/results

List runs:
curl http://localhost:8000/runs

List jobs:
curl http://localhost:8000/jobs
