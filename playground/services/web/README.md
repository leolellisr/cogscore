# Web service

Initial implementation.

Responsibilities:

- Upload result bundles.
- List runs.
- Show plots.
- Compare agents.
- Start jobs.

# CogScore Playground Web Dashboard

Streamlit dashboard for the CogScore Playground.

## Features

- Check API status
- Upload result bundles
- List imported runs
- List jobs
- Inspect job logs
- View generated plots

## Run locally

Terminal 1: API

```bash
cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

Terminal 2: Worker

cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/worker
python -m worker.main

Terminal 3: Web

cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/web
streamlit run app.py --server.address 0.0.0.0 --server.port 8501

Open:

http://localhost:8501
