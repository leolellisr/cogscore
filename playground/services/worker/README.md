# Worker service

background job processor.

Responsibilities:

- Run plotting scripts.
- Process uploaded results.
- Run experiments.
- Save logs.
- Generate downloadable artifacts.


# CogScore Playground Worker

Background worker for processing pending jobs.

Current job types:

```text
replot
The worker reads pending jobs from the SQLite database, runs the appropriate plotting script, saves logs, and updates the job status.
Run once
From the project root:
source .venv/bin/activate
cd services/worker
python -m worker.main --once
Run continuously
source .venv/bin/activate
cd services/worker
python -m worker.main
Logs
Job logs are stored in:
data/jobs/{job_id}/
Plots
Generated plots are stored in:
data/plots/{benchmark}/{agent_name}/{job_id}/

