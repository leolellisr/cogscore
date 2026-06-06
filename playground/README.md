# CogScore Playground

Online playground for evaluating, visualizing, comparing, and running cognitive architecture experiments using CogScore.

## Goals

This project provides:

1. A dashboard for visualizing and comparing CogScore experiment results.
2. Upload of new result bundles for comparison.
3. Automatic generation of plots.
4. A Docker/VNC environment for visualizing CoppeliaSim experiments.
5. A future interface for submitting new cognitive architectures.

## Project structure

```text
cogscore-playground/
├── deploy/       # Reverse proxy and deployment configuration
├── services/     # API, web dashboard, worker, VNC simulation container
├── scripts/      # Plot and analysis scripts
├── scenes/       # CoppeliaSim scenes
├── data/         # Persistent data, not tracked by Git
├── docs/         # Documentation
└── external/     # External repositories, such as cogscore



##  Result bundle validation

A CogScore result bundle is a `.zip` file containing:

manifest.yaml
benchmark_out/

To validate a bundle:
source .venv/bin/activate

python tools/validate_result_bundle.py data/uploads/example_motivation_bundle.zip

Documentation:
docs/result_bundle_format.md


## Etapa 2: API backend

Run the API locally:

source .venv/bin/activate
cd services/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Open:
http://localhost:8000/docs

Test health:
curl http://localhost:8000/health

Upload a result bundle:
curl -F "file=@data/uploads/example_motivation_bundle.zip" \
  http://localhost:8000/uploads/results

List runs:
curl http://localhost:8000/runs

List jobs:
curl http://localhost:8000/jobs
