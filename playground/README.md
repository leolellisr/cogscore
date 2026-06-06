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

```
cogscore-playground/
├── deploy/       # Reverse proxy and deployment configuration
├── services/     # API, web dashboard, worker, VNC simulation container
├── scripts/      # Plot and analysis scripts
├── scenes/       # CoppeliaSim scenes
├── data/         # Persistent data, not tracked by Git
├── docs/         # Documentation
└── external/     # External repositories, such as cogscore
```


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


## Comparison plots with all uploaded agents
By default, each uploaded result bundle creates a replot job. The worker is configured to generate comparison plots using the latest uploaded run of each agent for the same benchmark.

For example, if the database contains:
Substage1 / motivation
Substage3 / motivation
Substage1 / attention_posner
Substage3 / attention_posner

then a comparison replot job for motivation will generate plots using both:
Substage1
Substage3

and a comparison replot job for attention_posner will also generate plots using both agents.
The generated comparison plots are stored in:
data/plots/{benchmark}/comparison/{job_id}/

Examples:
data/plots/motivation/comparison/{job_id}/
data/plots/attention_posner/comparison/{job_id}/

## Create comparison replot jobs manually
If you already uploaded several result bundles and want to regenerate comparison plots, run:
cd ~/git/cogscore-playground
source .venv/bin/activate

python tools/create_comparison_replot_jobs.py --benchmark motivation
python tools/create_comparison_replot_jobs.py --benchmark attention_posner

Or create jobs for both supported benchmarks at once:
python tools/create_comparison_replot_jobs.py

Then run the worker:
cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/worker
python -m worker.main --once
python -m worker.main --once

Each --once processes one pending job. To keep the worker running continuously:
cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/worker
python -m worker.main

## Check which agents were included in a comparison plot
After the worker runs, inspect the job output:
sqlite3 data/db/playground.sqlite "select id, job_type, status, output_json from jobs order by created_at desc limit 5;"

You can also inspect the temporary plot input folder:
tree data/jobs/*/plot_input -L 3

A correct comparison job should look like:
plot_input
├── Substage1
│   └── benchmark_out
└── Substage3
    └── benchmark_out

If only one agent appears, then only one valid run exists in the database for that benchmark.

## Check imported runs by benchmark

To see all imported runs:
sqlite3 data/db/playground.sqlite "select agent_name, benchmark, run_name, created_at from runs order by benchmark, agent_name, created_at;"

Expected example:
Substage1|attention_posner|Substage1 attentional results|...
Substage3|attention_posner|Substage3 attentional results|...
Substage1|motivation|Substage1 motivation results|...
Substage3|motivation|Substage3 motivation results|...

If an agent is missing for a benchmark, upload its result bundle again.

Check if a result was uploaded with the wrong benchmark
Run:
sqlite3 data/db/playground.sqlite "select agent_name, benchmark, benchmark_out_path from runs;"
Check whether each result was imported with the correct benchmark:
attention/Posner results -> attention_posner
motivation results       -> motivation

If a result was uploaded with the wrong benchmark in manifest.yaml, create the bundle again with the correct --benchmark value and upload it again.

Clear old one-agent plots
Old plots generated before comparison mode may still appear in the dashboard. To remove only the generated plots, run:
rm -rf data/plots/motivation
rm -rf data/plots/attention_posner

This does not delete uploaded results, runs, jobs, or the database. It only removes generated plot files.
After clearing plots, create new comparison jobs:
python tools/create_comparison_replot_jobs.py

Then run the worker:
cd services/worker
python -m worker.main

## View plots in the dashboard

Run the three services.

### Terminal 1: API
cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

### Terminal 2: Worker
cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/worker
python -m worker.main

### Terminal 3: Web dashboard
cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/web
streamlit run app.py --server.address 0.0.0.0 --server.port 8501

Open:
http://localhost:8501

Then go to:
Plots
For comparison plots, select:
Benchmark: motivation
Agent: comparison

or:
Benchmark: attention_posner
Agent: comparison

# Troubleshooting comparison plots

## Problem: only one agent appears in the plot

Check imported runs:
sqlite3 data/db/playground.sqlite "select agent_name, benchmark, run_name from runs order by benchmark, agent_name;"

You should have at least two agents for the same benchmark, for example:
Substage1|motivation|...
Substage3|motivation|...

If only one appears, upload the missing result bundle.


## Problem: the wrong script is being used
Check the benchmark stored in the database:
sqlite3 data/db/playground.sqlite "select agent_name, benchmark, benchmark_out_path from runs;"
The worker chooses the plotting script by benchmark:
motivation       -> scripts/mot.py
attention_posner -> scripts/posner.py

If the benchmark is wrong, recreate the result bundle with the correct value.
Problem: job status is error

Check the jobs table:
sqlite3 data/db/playground.sqlite "select id, job_type, status, error_message from jobs order by created_at desc limit 10;"

Then inspect logs:
tree data/jobs -L 2
cat data/jobs/{job_id}/stdout.log
cat data/jobs/{job_id}/stderr.log

Replace {job_id} with the job ID shown in the database.

## Problem: job is stuck as running
Reset running jobs to pending:
python tools/reset_jobs.py --status running --to pending
Then rerun the worker:
cd services/worker
python -m worker.main --once


