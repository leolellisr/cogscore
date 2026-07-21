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

## Uploading New Results to CogScore

This section describes how to prepare, validate, upload, and process new benchmark results in the CogScore Playground.

CogScore uses a standardized **result bundle** format. A result bundle is a compressed ZIP archive containing:

1. a `manifest.yaml` file with metadata about the run;
2. a `benchmark_out/` directory containing the raw benchmark outputs;
3. optionally, an `optional/` directory containing notes, configuration files, or additional plots.

The same procedure can be used for any supported benchmark, such as `motivation`, `attention_posner`, `sensory_buffer`, `learning`, or any future benchmark added to the system.

---

### 1. Organizing the result files

Before creating the bundle, place the raw outputs of the benchmark in a directory called `benchmark_out`.

A recommended local structure is:

```text
data/uploads/real_results/{benchmark}/benchmark_out/
```

For example:

```text
data/uploads/real_results/motivation/benchmark_out/
data/uploads/real_results/attention_posner/benchmark_out/
data/uploads/real_results/sensory_buffer/benchmark_out/
data/uploads/real_results/learning/benchmark_out/
```

The internal structure of `benchmark_out/` depends on the benchmark. CogScore does not require all benchmarks to use the same internal layout. However, the structure must be compatible with the corresponding plotting script.

For example, a simple benchmark may contain CSV files directly:

```text
benchmark_out/
├── agent_summary_episode_001.csv
├── agent_per_trial_episode_001.csv
└── agent_java_steps_episode_001.csv
```

A more complex benchmark may preserve experiment folders, substages, seeds, or profile files:

```text
benchmark_out/
├── condition_A/
│   └── seed_001/
│       ├── data/
│       └── profile/
├── condition_B/
│   └── seed_001/
│       ├── data/
│       └── profile/
└── condition_C/
    └── seed_001/
        ├── data/
        └── profile/
```

For the learning benchmark, for instance, the directory may contain developmental substages:

```text
benchmark_out/
├── Substage1/
├── Substage2/
├── Substage3/
├── Substage4/
└── Substage5/
```

The key rule is that `benchmark_out/` must contain all files required by the benchmark-specific plotting script.

---

### 2. Creating the result bundle

From the root of the playground repository, run the bundle creation script.

General form:

```bash
cd cogscore/playground

python scripts/create_result_bundle.py \
  --benchmark-out data/uploads/real_results/{benchmark}/benchmark_out \
  --output data/uploads/real_results/{benchmark}/{agent_name}_{benchmark}.zip \
  --agent-name {agent_name} \
  --architecture-name {architecture_name} \
  --benchmark {benchmark} \
  --benchmark-version {benchmark_version} \
  --run-name "{run_name}" \
  --episodes {episodes} \
  --trials-per-experiment {trials_per_experiment} \
  --seed {seed} \
  --author "{author}" \
  --notes "{notes}"
```

Example:

```bash
cd cogscore/playground

python scripts/create_result_bundle.py \
  --benchmark-out data/uploads/real_results/learning/benchmark_out \
  --output data/uploads/real_results/learning/Substage5_DQN_learning.zip \
  --agent-name Substage5_DQN \
  --architecture-name CONAIM \
  --benchmark learning \
  --benchmark-version learning_v1 \
  --run-name "Learning developmental sequence - DQN" \
  --episodes 50 \
  --trials-per-experiment 20 \
  --seed 777 \
  --author "Leonardo de Lellis Rossi" \
  --notes "Benchmark results generated locally and prepared for CogScore Playground upload."
```

If the script is located in `tools/` instead of `scripts/`, use:

```bash
python tools/create_result_bundle.py \
  --benchmark-out data/uploads/real_results/{benchmark}/benchmark_out \
  --output data/uploads/real_results/{benchmark}/{agent_name}_{benchmark}.zip \
  --agent-name {agent_name} \
  --architecture-name {architecture_name} \
  --benchmark {benchmark} \
  --benchmark-version {benchmark_version} \
  --run-name "{run_name}" \
  --episodes {episodes} \
  --trials-per-experiment {trials_per_experiment} \
  --seed {seed} \
  --author "{author}" \
  --notes "{notes}"
```

The generated ZIP file should contain:

```text
{agent_name}_{benchmark}.zip
├── manifest.yaml
└── benchmark_out/
    └── ...
```

If optional files are included, the archive may contain:

```text
{agent_name}_{benchmark}.zip
├── manifest.yaml
├── benchmark_out/
│   └── ...
└── optional/
    ├── config.json
    ├── notes.md
    └── plots/
```

---

### 3. Manifest metadata

Each result bundle contains a `manifest.yaml` file. The manifest describes the experimental run and allows CogScore to register, compare, and reproduce the result.

A general manifest has the following structure:

```yaml
agent_name: {agent_name}
architecture_name: {architecture_name}
benchmark: {benchmark}
benchmark_version: {benchmark_version}
cogscore_version: "0.1.0"
run_name: "{run_name}"
date: "{YYYY-MM-DD}"

parameters:
  episodes: {episodes}
  trials_per_experiment: {trials_per_experiment}
  seed: {seed}

source:
  type: uploaded_results
  author: "{author}"
  notes: "{notes}"
```

Benchmark-specific parameters may also be included. For example:

```yaml
parameters:
  episodes: 50
  trials_per_experiment: 20
  seed: 777
  learning_algorithm: DQN
  substages:
    - Substage1
    - Substage2
    - Substage3
    - Substage4
    - Substage5
  transfer_between_substages: true
  evaluation_mode: testing
```

or:

```yaml
parameters:
  episodes: 30
  trials_per_experiment: 100
  seed: 123
  stimulus_duration_ms: 500
  delay_ms: 1000
  response_window_ms: 2000
```

The manifest should contain enough information to understand how the result was produced.

---

### 4. Validating the bundle

Before upload, validate the generated ZIP file.

If the validation script is located in `scripts/`, run:

```bash
python scripts/validate_result_bundle.py \
  data/uploads/real_results/{benchmark}/{agent_name}_{benchmark}.zip
```

If it is located in `tools/`, run:

```bash
python tools/validate_result_bundle.py \
  data/uploads/real_results/{benchmark}/{agent_name}_{benchmark}.zip
```

Example:

```bash
python scripts/validate_result_bundle.py \
  data/uploads/real_results/learning/Substage5_DQN_learning.zip
```

Expected result:

```text
[OK] Result bundle is valid.
```

If validation fails because the benchmark is not recognized, add the benchmark name to the list of allowed benchmarks.

For example:

```python
ALLOWED_BENCHMARKS = {
    "motivation",
    "attention_posner",
    "sensory_buffer",
    "learning",
}
```

If the script uses command-line choices, include the new benchmark there as well:

```python
choices=["motivation", "attention_posner", "sensory_buffer", "learning"]
```

---

### 5. Uploading the bundle through the API

After validation, upload the bundle to CogScore:

```bash
curl -F "file=@data/uploads/real_results/{benchmark}/{agent_name}_{benchmark}.zip" \
  http://localhost:8000/uploads/results
```

Example:

```bash
curl -F "file=@data/uploads/real_results/learning/Substage5_DQN_learning.zip" \
  http://localhost:8000/uploads/results
```

A successful response should contain:

```json
{
  "ok": true,
  "run_id": "...",
  "job_id": "...",
  "message": "Result bundle uploaded, validated, and imported. Replot job created.",
  "validation_warnings": []
}
```

The API performs the following operations:

1. validates the uploaded ZIP file;
2. extracts and checks `manifest.yaml`;
3. copies the result files to the internal storage directory;
4. registers the run in the database;
5. creates a replot job for the worker.

---

### 6. Internal storage after upload

After the upload, CogScore stores the result internally under:

```text
data/results/{agent_name}/{benchmark}/run_{timestamp}_{run_id}/
```

Example:

```text
data/results/Substage5_DQN/learning/run_20260706_abcdef12/
├── manifest.yaml
└── benchmark_out/
    └── ...
```

This structure allows multiple agents, architectures, benchmarks, and repeated runs to coexist in the system.

---

### 7. Running the benchmark plotting script

Each benchmark should have a corresponding plotting script.

Recommended convention:

```text
scripts/{benchmark}.py
```

Examples:

```text
scripts/motivation.py
scripts/attention_posner.py
scripts/sensory_buffer.py
scripts/learning.py
```

Each plotting script should accept at least two arguments:

```bash
--root
--out
```

where:

* `--root` points to the imported `benchmark_out/` directory;
* `--out` points to the directory where plots and derived CSV files should be saved.

General form:

```bash
python scripts/{benchmark}.py \
  --root data/results/{agent_name}/{benchmark}/run_{timestamp}_{run_id}/benchmark_out \
  --out data/plots/{benchmark}/run_{timestamp}_{run_id}
```

Example:

```bash
python scripts/learning.py \
  --root data/results/Substage5_DQN/learning/run_20260706_abcdef12/benchmark_out \
  --out data/plots/learning/run_20260706_abcdef12 \
  --max-epochs 50 \
  --window 5
```

The output should be written under:

```text
data/plots/{benchmark}/run_{timestamp}_{run_id}/
```

A benchmark may organize its plots as needed, for example:

```text
data/plots/{benchmark}/run_{timestamp}_{run_id}/
├── by_episode/
├── by_trial/
├── by_action/
├── comparison/
└── summary/
```

---

### 8. Connecting the benchmark to the worker

To process uploads automatically, the benchmark must be registered in the worker script mapping.

Example:

```python
BENCHMARK_TO_SCRIPT = {
    "motivation": SCRIPTS_DIR / "mot.py",
    "attention_posner": SCRIPTS_DIR / "posner.py",
    "sensory_buffer": SCRIPTS_DIR / "sperling.py",
    "learning": SCRIPTS_DIR / "learning.py",
}
```

For a new benchmark, add:

```python
"{benchmark}": SCRIPTS_DIR / "{benchmark}.py",
```

The worker command should pass the imported result directory and the target output directory:

```python
cmd = [
    "python",
    str(SCRIPTS_DIR / "{benchmark}.py"),
    "--root",
    str(run_path / "benchmark_out"),
    "--out",
    str(plots_dir / "{benchmark}" / run_id),
]
```

Benchmark-specific optional arguments may also be passed, such as:

```python
"--max-epochs", "50",
"--window", "5",
"--skip-pulses"
```

---

### 9. Checking the generated plots

After the replot job finishes, check the plot directory:

```bash
ls data/plots/{benchmark}
```

Example:

```bash
ls data/plots/learning
```

A typical output directory may contain:

```text
data/plots/{benchmark}/run_{timestamp}_{run_id}/
├── summary/
│   └── summary_stats.csv
├── by_episode/
│   └── ...
├── by_trial/
│   └── ...
└── comparison/
    └── ...
```

These outputs can be shown in the CogScore dashboard and compared with other uploaded runs.

---

### 10. Recommended workflow

The recommended workflow for adding any new result is:

```text
Raw benchmark outputs
   ↓
benchmark_out/
   ↓
create_result_bundle.py
   ↓
{agent_name}_{benchmark}.zip
   ↓
validate_result_bundle.py
   ↓
POST /uploads/results
   ↓
data/results/{agent_name}/{benchmark}/run_{id}/
   ↓
worker replot job
   ↓
scripts/{benchmark}.py
   ↓
data/plots/{benchmark}/run_{id}/
   ↓
CogScore dashboard
```

This workflow keeps result submission reproducible, traceable, and comparable across different cognitive architectures, agents, seeds, and benchmark versions.



# Etapa 2: API backend

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


## Docker, automatic cleanup, and comparison plots

Create the local environment file once:

```bash
cd playground
cp .env.example .env
```

Start the complete playground in the background:

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f api web worker sim-vnc
```

The Compose services use `restart: unless-stopped`. Whenever the worker starts, it
searches for dynamic architecture containers left by an earlier execution and
removes containers labeled `cogscore.managed=true` or named `cogscore-run-*` /
`cogscore-smoke-*`. Compose service containers such as `cogscore-api` and
`cogscore-web` are not removed by that startup cleanup.

For an explicit full stop and cleanup, use:

```bash
./scripts/docker_cleanup.sh
```

This removes the dynamic architecture containers first and then runs
`docker compose down --remove-orphans`.

### Rebuilding plots from the dashboard

Every uploaded result bundle automatically creates a comparison replot job. To
create another generation manually:

1. Open the Streamlit dashboard.
2. Go to **Plots**.
3. Select one benchmark or all benchmarks.
4. Click **Refazer**.

Each new job:

- keeps all previous plot generations;
- includes every distinct imported agent for the selected benchmark;
- uses the newest readable result for each agent;
- falls back to an older valid result when the newest result directory is missing
  or has no usable benchmark data;
- remaps legacy host paths such as `/home/.../playground/data/...` to the
  current Docker mount under `/data/...`;
- writes its output to `data/plots/{benchmark}/comparison/{job_id}/`;
- writes `generation.json` with the selected agents and run IDs.

The same operation is available through the API:

```bash
curl -X POST http://localhost:18000/plots/rebuild \
  -H 'Content-Type: application/json' \
  -d '{"benchmark":"all"}'
```

Valid benchmark values are `sensory_buffer`, `attention_posner`, `motivation`,
`learning`, and `all`. Job logs are available in the **Jobs** page and under
`data/jobs/{job_id}/stdout.log` and `stderr.log`.

### Checking which agents were plotted

Inspect the generation metadata:

```bash
find data/plots -name generation.json -print
cat data/plots/{benchmark}/comparison/{job_id}/generation.json
```

Or inspect the temporary normalized input created for that job:

```bash
tree data/jobs/{job_id}/plot_input -L 4
```

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

## Problem: a job was interrupted by a restart

At startup, the worker automatically marks jobs left in `running` state as
`error` and records that the previous worker execution was interrupted. The
corresponding dynamic architecture container is removed by the same startup
cleanup. Create a new experiment or click **Refazer** again to start a fresh job.


