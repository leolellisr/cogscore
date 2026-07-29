# CogScore Playground

Online playground for evaluating, visualizing, comparing, and running cognitive architecture experiments using CogScore.

## Goals

This project provides:

1. A dashboard for visualizing and comparing CogScore experiment results.
2. Upload of new result bundles for comparison.
3. Automatic generation of plots.
4. A Docker/VNC environment for visualizing CoppeliaSim experiments.
5. Upload, validation, and execution of external cognitive architectures.

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

### 5. Uploading the bundle through the dashboard or API

#### Dashboard

1. Start the playground with `docker compose up -d --build`.
2. Open `http://localhost:8501`.
3. Select **Upload results**.
4. Choose the validated result-bundle ZIP.
5. Click **Upload and create plot job**.
6. Review the imported run and plot job returned by the page.
7. Follow the job in **Jobs** and open the generated charts in **Plots**.

#### API

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

A successful response contains the imported run, the asynchronous replot job,
and any validation warnings:

```json
{
  "ok": true,
  "message": "Result bundle imported and plot job created.",
  "run": {
    "id": "...",
    "agent_name": "Substage5_DQN",
    "benchmark": "learning",
    "status": "imported"
  },
  "job": {
    "id": "...",
    "job_type": "replot",
    "status": "pending"
  },
  "warnings": []
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


## Uploading New Cognitive Architectures

CogScore accepts external cognitive architectures as source bundles. The server
builds each bundle as a Docker image, starts it on the internal Compose network,
and communicates with it through a fixed REST interface.

The current upload mechanism does **not** accept an already-built image, a Git
URL, or a remote HTTP endpoint. Upload a ZIP archive containing everything that
Docker needs to build and start the architecture.

### 1. Runtime requirements

An uploaded architecture must satisfy all of the following requirements:

1. The ZIP root contains `manifest.yaml` and `Dockerfile`.
2. The image starts an HTTP server that listens on `0.0.0.0:9000`.
3. The server exposes `GET /health`, `POST /reset`, and the endpoint for every
   benchmark declared in the manifest.
4. All responses used by CogScore are JSON and use an HTTP 2xx status code.
5. The container does not depend on a published host port. CogScore reaches it
   by container name on the internal `cogscore_online_net` Docker network.
6. The process remains in the foreground. The container exits if its main
   server process exits.
7. Files required at runtime are copied into the image by the `Dockerfile`.
   The architecture container does not receive the playground source tree as a
   volume.

The worker currently starts uploaded containers with the limits configured by
`MAX_ARCH_CPU` and `MAX_ARCH_MEMORY`. Their defaults are `2` CPUs and `4g` of
memory. Build and validation commands use `ARCH_TIMEOUT_SECONDS`, whose default
is 120 seconds.

### 2. Architecture bundle structure

A minimal Python/FastAPI bundle can use this structure:

```text
architecture_bundle.zip
├── manifest.yaml
├── Dockerfile
├── requirements.txt
└── app.py
```

Additional source files and model assets may be included. `requirements.txt`
and `app.py` are conventions, not hard-coded requirements; the `Dockerfile` may
build an implementation in Java, C++, Python, or another language.

Files must be at the root of the ZIP. Do not wrap them in an extra directory:

```text
# Correct
architecture_bundle.zip/manifest.yaml

# Incorrect
architecture_bundle.zip/my_architecture/manifest.yaml
```

The repository includes a working reference bundle:

```text
examples/dummy_agent_learning.zip
```

### 3. Architecture manifest

The API requires these fields:

```yaml
name: MyCognitiveArchitecture
version: "1.0.0"
author: "Research Group"
interface: rest
benchmarks:
  - sensory_buffer
  - attention_posner
  - motivation
  - learning

endpoints:
  health: /health
  reset: /reset
  stimulus: /sensory/stimulus
  readout: /sensory/readout
  attention_act: /attention/act
  motivation_act: /motivation/act
  learning_act: /learning/act
  close: /close
```

`name`, `version`, `interface`, and `benchmarks` are required. `interface` must
be exactly `rest`. At least one declared entry must be one of the currently supported
benchmarks:

```text
sensory_buffer
attention_posner
motivation
learning
```

The `endpoints` mapping is useful documentation, but the current worker uses the
fixed paths shown above. Changing a path only in `manifest.yaml` does not change
which URL the worker calls.

Unsupported extra names are ignored by the worker, but they should not be
included because they cannot be selected for execution. Declare only benchmarks
that the architecture actually implements. Validation runs a smoke test for every
supported benchmark declared in the manifest.

### 4. REST contract

#### Common endpoints

`GET /health` must return any JSON object with a 2xx status. A recommended
response is:

```json
{
  "status": "ok",
  "agent": "MyCognitiveArchitecture",
  "benchmarks": ["sensory_buffer", "learning"]
}
```

`POST /reset` starts a new benchmark run or episode. The payload always contains
`benchmark` and may contain `episode`:

```json
{
  "benchmark": "sensory_buffer",
  "episode": 0
}
```

Return a JSON acknowledgement such as `{"status":"ok"}`. Reset benchmark-local
state when appropriate, but preserve learned state across calls when the
experiment design requires learning across episodes.

`POST /close` is called at the end of sensing and attention runs and may also be
called by other runners. Implement it as an idempotent cleanup endpoint:

```json
{
  "benchmark": "attention_posner"
}
```

A simple `{"status":"ok"}` response is sufficient.

#### Sensing: `sensory_buffer`

CogScore sends a complete RGB frame to `POST /sensory/stimulus`:

```json
{
  "benchmark": "sensory_buffer",
  "episode": 0,
  "trial": 0,
  "delay_ms": 100,
  "width": 64,
  "height": 64,
  "channels": 3,
  "encoding": "rgb_float_0_255",
  "frame": [0.0, 12.0, 255.0]
}
```

`frame` contains `width * height * 3` values in row-major RGB order. Store the
representation needed for delayed readout and return a JSON acknowledgement.

After the configured delay, CogScore calls `POST /sensory/readout`:

```json
{
  "benchmark": "sensory_buffer",
  "episode": 0,
  "trial": 0,
  "delay_ms": 100,
  "cue": {
    "type": "patch",
    "x0": 0,
    "y0": 0,
    "size": 8
  }
}
```

The response must contain `patch`, with `size * size * 3` RGB values in the same
encoding and order:

```json
{
  "status": "ok",
  "encoding": "rgb_float_0_255",
  "patch": [0.0, 12.0, 255.0],
  "confidence": 1.0
}
```

The runner computes MSE and visual fidelity by comparing this patch with the
original frame. `/sensory/retention_tick` appears in the example manifest, but
the current online runner does not call it.

#### Attention: `attention_posner`

CogScore calls `POST /attention/act` once per trial. Coordinates are normalized
to `[0, 1]`:

```json
{
  "benchmark": "attention_posner",
  "experiment_id": 1,
  "episode": 0,
  "trial_id": "POSNER_E1_EP0_T0",
  "trial_type": "valid",
  "cue_type": "endogenous",
  "target": {"x": 0.25, "y": 0.5},
  "cue": {"x": 0.25, "y": 0.5},
  "fixation": {"x": 0.5, "y": 0.5},
  "map_width": 32,
  "map_height": 32,
  "cycles_per_trial": 30
}
```

Return the detection result and the final peak of attention:

```json
{
  "detected": true,
  "detection_cycle": 12,
  "overt_movement_cycle": 14,
  "attention_peak": {"x": 0.25, "y": 0.5},
  "confidence": 0.95
}
```

The current runner consumes `detected`, `detection_cycle`, and
`attention_peak`. It derives reaction time, attention latency, and spatial
fidelity from these values. The validation smoke request contains a smaller
subset of fields and represents the cue as `{"side":"left","valid":true}`.
Implement sensible defaults for omitted trial fields rather than requiring every
optional key.

#### Motivation: `motivation`

CogScore calls `POST /motivation/act` with the available objects and the current
experimental signals:

```json
{
  "benchmark": "motivation",
  "experiment_id": 5,
  "episode": 0,
  "trial_id": "MOT_E5_T11",
  "phase": "trial",
  "objects": [
    {"id": 1, "label": "blue_sphere", "role": "resource"},
    {"id": 2, "label": "red_cube", "role": "curiosity"},
    {"id": 3, "label": "green_cylinder", "role": "alternative"},
    {"id": 4, "label": "neutral_object", "role": "control"}
  ],
  "signals": {
    "reward_available": false,
    "target_removed": false,
    "outcome_devalued": true,
    "blocked_path": false
  }
}
```

Return an action and an object ID from the request:

```json
{
  "action": "INTERACT",
  "object": 2,
  "confidence": 0.8
}
```

Supported action names are `LOOK`, `INTERACT`, and `STOP`. The runner uses the
selected object and action to calculate persistence, resource choice, novelty,
goal substitution, outcome devaluation, and response suppression metrics.

#### Learning: `learning`

CogScore calls `POST /learning/act` at every simulated step:

```json
{
  "benchmark": "learning",
  "stage": "Substage4",
  "test": "testAB",
  "episode": 1,
  "step": 25,
  "target": {
    "visible": false,
    "occluded": true,
    "x": 0.56,
    "y": 0.42,
    "yaw_error": 0.2,
    "pitch_error": -0.1
  },
  "objects": [
    {"id": 1, "label": "target", "visible": false},
    {"id": 2, "label": "distractor", "visible": false}
  ],
  "signals": {
    "curiosity": 0.0,
    "reward_available": true,
    "occlusion": true,
    "multiple_objects": false
  }
}
```

The response must include `action`. The current runner uses `yaw_delta` and
`pitch_delta` to update tracking error:

```json
{
  "action": "TRACK",
  "yaw_delta": -0.07,
  "pitch_delta": 0.035,
  "confidence": 0.9
}
```

The architecture process remains alive throughout the run, so in-memory models,
procedural memory, Q-tables, or neural state may be updated across steps and
episodes. `POST /reset` is called once before the learning sequence, not before
every stage.

### 5. Build and test the architecture locally

Before creating the ZIP, build and run the same image that CogScore will use:

```bash
docker build -t my-cogscore-agent .
docker run --rm --name my-cogscore-agent-test -p 9000:9000 my-cogscore-agent
```

From another terminal:

```bash
curl http://localhost:9000/health

curl -X POST http://localhost:9000/reset \
  -H 'Content-Type: application/json' \
  -d '{"benchmark":"learning"}'
```

Also test every benchmark endpoint declared in `manifest.yaml`. The example
implementation inside `examples/dummy_agent_learning.zip` can be extracted and
used as a starting point.

### 6. Create the ZIP bundle

Run the command from inside the architecture source directory so that
`manifest.yaml` and `Dockerfile` are placed at the ZIP root:

```bash
zip -r ../my_cognitive_architecture.zip . \
  -x '.git/*' '__pycache__/*' '*.pyc' '.venv/*'

unzip -l ../my_cognitive_architecture.zip
```

### 7. Upload through the dashboard

1. Start the playground with `docker compose up -d --build`.
2. Open `http://localhost:8501`.
3. Select **Upload architecture**.
4. Choose the ZIP file.
5. Click **Upload and create validation job**.
6. Save the returned `architecture_id` and `validation_job_id`.
7. Open **Jobs** to inspect build and smoke-test logs.
8. Open **Architectures** and wait for the architecture status to become
   `validated`.

The possible architecture states are:

- `uploaded`: source accepted and validation job queued;
- `validated`: Docker build and every declared benchmark smoke test succeeded;
- `error`: build, startup, health check, or a declared benchmark smoke test
  failed.

### 8. Upload through the API

```bash
curl -F "file=@../my_cognitive_architecture.zip" \
  http://localhost:18000/architectures/upload
```

Example response:

```json
{
  "ok": true,
  "architecture_id": "arch_0123456789ab",
  "validation_job_id": "job_0123456789ab",
  "message": "Architecture uploaded. Validation job created."
}
```

Monitor validation:

```bash
curl http://localhost:18000/jobs/job_0123456789ab
curl http://localhost:18000/architectures/arch_0123456789ab
curl http://localhost:18000/architectures
```

Validation performs these operations asynchronously:

```text
ZIP upload
   ↓
safe extraction to data/architectures/{architecture_id}/source/
   ↓
docker build -t cogscore-agent-{architecture_id}:latest .
   ↓
temporary container on cogscore_online_net, port 9000
   ↓
GET /health
   ↓
POST /reset and benchmark-specific smoke request for every declared benchmark
   ↓
architecture status = validated or error
```

Logs are written to:

```text
data/jobs/{validation_job_id}/stdout.log
data/jobs/{validation_job_id}/stderr.log
```

## Running Experiments with Uploaded Architectures

Only architectures whose status is `validated` can be selected for an
experiment. The requested benchmark must also appear in the architecture's
`benchmarks` list.

### 1. Current execution model

For every experiment job, the worker:

1. starts a fresh container from the validated architecture image;
2. connects it to `cogscore_online_net` with the address
   `http://cogscore-run-{run_id}:9000`;
3. opens the selected CoppeliaSim scene in the `sim-vnc` service when
   `COGSCORE_OPEN_COPPELIA=1`;
4. executes the corresponding remote Python runner;
5. stores raw output under
   `data/results/{architecture_id}/{benchmark}/{run_id}/benchmark_out/`;
6. updates the experiment run and job status;
7. removes the temporary architecture container, including on failure.

The current scripts are remote **smoke runners**. They open the configured
scene, but the benchmark observations sent to the architecture are generated by
`*_remote_smoke_runner.py`. The shell scripts contain placeholders for a future
Java/CST bridge that would drive the complete CoppeliaSim experiment. Therefore,
the procedure below documents the behavior implemented in this repository, not
a full physical or Java/CST integration.

The API accepts `mode` as `vnc` or `headless`, but the current worker does not
change its command path based on that value. Use the VNC page to observe the
`sim-vnc` desktop when CoppeliaSim is enabled.

### 2. Run from the dashboard

1. Open **Architectures** and confirm that the target architecture is
   `validated` and declares the desired benchmark.
2. Open one of **Sensing experiments**, **Attention experiments**,
   **Motivation experiments**, or **Learning experiments**.
3. Select the architecture.
4. Review the scene and benchmark parameters.
5. Click the corresponding **Create ... experiment job** button.
6. Save the returned `run_id` and `job_id`.
7. Follow progress in **Jobs** and **Experiment runs**.
8. Use **VNC** or `http://localhost:6080/vnc.html?autoconnect=true&resize=scale`
   to inspect the simulator desktop.
9. After completion, inspect `result_path` in **Experiment runs** and the files
   under `data/results`.

### 3. Run through the API

All benchmarks use:

```text
POST /jobs/run-experiment
```

The minimal common fields are:

```json
{
  "architecture_id": "arch_0123456789ab",
  "benchmark": "sensory_buffer",
  "episodes": 1,
  "seed": 777,
  "mode": "vnc"
}
```

If `scene` is omitted, the API uses these defaults:

| Benchmark | Default scene |
|---|---|
| `sensory_buffer` | `sperling.ttt` |
| `attention_posner` | `posner.ttt` |
| `motivation` | `mot.ttt` |
| `learning` | `learning/testing_s1A.ttt` |

#### Sensing request

```bash
curl -X POST http://localhost:18000/jobs/run-experiment \
  -H 'Content-Type: application/json' \
  -d '{
    "architecture_id": "arch_0123456789ab",
    "benchmark": "sensory_buffer",
    "scene": "sperling.ttt",
    "episodes": 1,
    "trials_per_delay": 3,
    "delays_ms": [0, 50, 100, 220, 500, 1000],
    "resolution": 64,
    "patch_size": 8,
    "seed": 777,
    "mode": "vnc"
  }'
```

`patch_size` must fit inside `resolution`. Each trial sends one generated RGB
frame, waits for the selected delay, requests one patch, and computes MSE and
fidelity.

#### Attention request

```bash
curl -X POST http://localhost:18000/jobs/run-experiment \
  -H 'Content-Type: application/json' \
  -d '{
    "architecture_id": "arch_0123456789ab",
    "benchmark": "attention_posner",
    "scene": "posner.ttt",
    "episodes": 1,
    "posner_experiments": [1, 2, 3, 4, 5],
    "trials_per_experiment": 20,
    "map_width": 32,
    "map_height": 32,
    "cycles_per_trial": 30,
    "seed": 777,
    "mode": "vnc"
  }'
```

Experiment IDs must be between 1 and 5. The runner produces per-trial and
summary CSV files for each selected experiment and episode.

#### Motivation request

```bash
curl -X POST http://localhost:18000/jobs/run-experiment \
  -H 'Content-Type: application/json' \
  -d '{
    "architecture_id": "arch_0123456789ab",
    "benchmark": "motivation",
    "scene": "mot.ttt",
    "episodes": 1,
    "motivation_experiments": [1, 2, 3, 4, 5],
    "trials_per_experiment": 20,
    "cycles_per_motivation_trial": 30,
    "seed": 777,
    "mode": "vnc"
  }'
```

Experiment IDs must be between 1 and 5. The current smoke runner sends one
decision request per trial; `cycles_per_motivation_trial` is accepted and
forwarded to the shell runner but is not used to make repeated REST calls.

#### Learning request

```bash
curl -X POST http://localhost:18000/jobs/run-experiment \
  -H 'Content-Type: application/json' \
  -d '{
    "architecture_id": "arch_0123456789ab",
    "benchmark": "learning",
    "scene": "learning/testing_s1A.ttt",
    "episodes": 10,
    "learning_stages": [
      "Substage1",
      "Substage2",
      "Substage3",
      "Substage4",
      "Substage5"
    ],
    "learning_tests": ["testA", "testB", "testAB"],
    "steps_per_episode": 100,
    "aggregate_n": 5,
    "seed": 777,
    "mode": "vnc"
  }'
```

The runner applies the following test selection rules:

| Stage | Executed tests from the requested list |
|---|---|
| `Substage1` to `Substage3` | `testA`, `testB` |
| `Substage4` | `testA`, `testAB`, `testB` |
| `Substage5` | `testA` |

Learning results are stored as:

```text
benchmark_out/
└── {stage}/
    └── {test}/
        └── seed{seed}/
            └── profile/
                └── nrewards.txt
```

`aggregate_n` is saved with the run parameters for plotting, but the current
learning worker does not pass it to the remote runner. Unlike sensing,
attention, and motivation, the current learning handler stores the raw result
directory as `result_path` and does not automatically create a result-bundle
ZIP.

### 4. Experiment response and monitoring

A successful submission creates the run and job but does not wait for execution:

```json
{
  "ok": true,
  "run_id": "run_0123456789ab",
  "job_id": "job_0123456789ab",
  "message": "sensory_buffer experiment job created."
}
```

Monitor the job and all experiment runs:

```bash
curl http://localhost:18000/jobs/job_0123456789ab
curl http://localhost:18000/jobs
curl http://localhost:18000/experiment-runs
```

Job and run states normally progress through:

```text
pending → running → done
                  ↘ error
```

Detailed logs are available at:

```text
data/jobs/{job_id}/stdout.log
data/jobs/{job_id}/stderr.log
```

Automatically generated result bundles for sensing, attention, and motivation
are written to:

```text
data/uploads/result_bundles/
```

Raw benchmark outputs remain under:

```text
data/results/{architecture_id}/{benchmark}/{run_id}/benchmark_out/
```

### 5. Common execution failures

- **Architecture is not selectable:** its status is not `validated`, or its
  manifest does not declare the selected benchmark.
- **Docker build fails:** inspect the validation job's `stderr.log`; reproduce
  with `docker build` inside the extracted bundle source.
- **Container starts but health fails:** confirm that the server binds to
  `0.0.0.0:9000`, not `127.0.0.1` and not another port.
- **Benchmark smoke test fails:** compare the endpoint payload and response with
  the REST contract above.
- **Scene cannot be opened:** verify that the scene exists below
  `playground/scenes/` and inspect `benchmark_out/coppelia.log`.
- **Experiment remains `running` after a restart:** the worker marks interrupted
  jobs as `error` at startup; submit a new experiment job.
- **No final ZIP for learning:** this is the current behavior; package
  `benchmark_out/` manually with `tools/create_result_bundle.py` when a portable
  bundle is required.

## API Backend

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
4. Click **Rebuild**.

Each new job:

- keeps all previous plot generations;
- includes every distinct imported agent for the selected benchmark;
- uses the newest readable result for each agent;
- falls back to an older valid result when the newest result directory is missing
  or has no usable benchmark data;
- remaps legacy host paths such as `/home/.../playground/data/...` to the
  current Docker mount under `/data/...`;
- writes its output to `data/plots/{benchmark}/comparison/{job_id}/`;
- writes `generation.json` with the selected agents, run IDs, generation time,
  and plot-processing parameters.

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

### Interpreting plots in the dashboard

The **Plots** page uses a scientific metadata catalog stored in:

```text
services/api/app/plot_catalog.yaml
```

The selected plot determines the information shown in the right-hand panel. The
panel contains the following tabs:

- **Experiment**: describes the task, experimental procedure, and expected
  behavior;
- **Measure**: defines the plotted measure, unit, preferred direction, range,
  threshold, and formula when applicable;
- **Variables**: explains axes, lines, conditions, shaded regions, bars, and
  other visual encodings;
- **Interpretation**: provides guidance for reading the result without replacing
  the scientific analysis of the researcher;
- **Processing**: reports normalization, interpolation, smoothing, aggregation,
  and other plot-generation parameters;
- **Provenance**: identifies the generation, job, agents, and run IDs used to
  produce the plot.

Plots are selected hierarchically by benchmark, generation, experiment, and
measure. The complete image gallery is disabled by default and can be enabled for
the current experiment. This avoids loading every image in benchmarks that
generate many diagnostic plots.

The API endpoint `GET /plots` returns the same metadata under the `metadata`
field of each plot item. Static scientific definitions come from
`plot_catalog.yaml`, while generation-specific provenance and processing values
come from the nearest `generation.json`. Older plot directories without a
`generation.json` remain visible; their metadata is inferred from the directory
and filename, and the provenance source is marked accordingly.

To add documentation for a new plot, add a regular-expression rule to the
corresponding benchmark under `benchmarks.<benchmark>.plots` in the catalog. A
rule may define:

```yaml
- pattern: 'example_metric'
  title: Example metric
  metric:
    name: Example measure
    unit: normalized score
    direction: Higher is better
    formula_latex: 'S=\frac{x}{n}'
    description: Description of how the measure is calculated.
  variables:
    - label: Horizontal axis
      description: Episode number.
  interpretation: Guidance for comparing the curves.
```

The first matching rule is used. More specific patterns should therefore appear
before broad fallback patterns.

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



## Dashboard UX and online operation

The dashboard is organized by researcher workflow:

- **Dashboard**: service status, operational counts, recent jobs, and quick actions;
- **Architectures**: architecture upload, ZIP preflight, validation state, manifest, and execution shortcut;
- **Imported results**: result-bundle upload, manifest preview, imported-run inventory, and plot-job tracking;
- **New experiment**: unified experiment wizard for sensing, attention, motivation, and learning;
- **Experiment runs**: filters, parameters, repeat, edit-and-run, job navigation, and plot navigation;
- **Plots**: contextual experiment and metric descriptions, processing metadata, provenance, generation comparison, and shareable query parameters;
- **Jobs**: operational filters, duration, readable errors, logs, and retry for non-experiment jobs;
- **Simulator**: noVNC view plus asynchronous start, stop, and restart controls;
- **Documentation**: bundle and execution reference.

Copy `.env.example` to `.env` before deployment. Direct development ports bind to `127.0.0.1` by default; the reverse proxy remains available on port `8080`. Set `COGSCORE_BIND_ADDRESS=0.0.0.0` only when direct exposure is intentional.

An optional dashboard password can be enabled with:

```text
COGSCORE_DASHBOARD_USERNAME=researcher
COGSCORE_DASHBOARD_PASSWORD=change-me
```

This application-level password protects the Streamlit dashboard only. A public or multi-user deployment should also use the reverse proxy authentication example in `deploy/Caddyfile.authenticated.example`, institutional identity management, per-user storage, and execution quotas. The patch does not claim to provide complete multi-tenant isolation.

### Rebuilding after the dashboard update

```bash
cd playground
docker compose up -d --build --force-recreate api worker web sim-vnc proxy
```


## Fixed public link without owning a domain

The playground can be published from the local computer through the official
ngrok Docker image. The configured ngrok development domain is stable across
container and computer restarts:

```text
https://affix-decimeter-eradicate.ngrok-free.dev
```

A ngrok account and authtoken are required. Configure a newly generated token
without displaying it or placing it in the shell history:

```bash
./tools/configure-ngrok.sh
```

The script writes the following entries to `.env` and sets its permissions to
`600`. `NGROK_DOMAIN` must not include `https://`:

```text
NGROK_AUTHTOKEN=replace-with-a-new-ngrok-authtoken
NGROK_DOMAIN=affix-decimeter-eradicate.ngrok-free.dev
```

Start the fixed public link from the `playground` directory:

```bash
./tools/start-public-link.sh
```

Anyone who has this address can access the dashboard, API, architecture upload,
result upload, plots, jobs, and the noVNC interface. Do not use this mode when
private or sensitive data is stored in the playground.

Stop only the public tunnel with:

```bash
./tools/stop-public-link.sh
```

The local services remain available after the tunnel is stopped. Restarting the
ngrok container does not change the configured development-domain address.
