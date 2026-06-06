# Result Bundle Format

A result bundle is a `.zip` file uploaded to the CogScore Playground for visualization, plotting, and comparison.

The goal is to preserve reproducibility. Every uploaded result must contain metadata describing the agent, architecture, benchmark, parameters, seed, and output files.

## General structure

```text
result_bundle.zip
├── manifest.yaml
├── benchmark_out/
│   ├── *_summary_episode_*.csv
│   ├── *_per_trial_episode_*.csv
│   ├── *_java_steps_*.csv
│   └── motivation_marta_trials.txt
└── optional/
    ├── config.json
    ├── notes.md
    └── plots/
## Example Manifest

agent_name: Substage3
architecture_name: CONAIM
benchmark: motivation
benchmark_version: motivation_v1
cogscore_version: "0.1.0"
run_name: "Substage3 motivation test"
date: "2026-06-06"

parameters:
  episodes: 50
  trials_per_experiment: 20
  seed: 777
  x_points: 50
  smooth_window: 7

source:
  type: uploaded_results
  author: Leonardo
  notes: "Run generated locally and uploaded for comparison."


Required files
Always required
manifest.yaml
benchmark_out/
Required for motivation benchmark
At least one of:
benchmark_out/*_summary_episode_*.csv
benchmark_out/*_per_trial_episode_*.csv
Recommended:
benchmark_out/*_java_steps_*.csv
benchmark_out/motivation_marta_trials.txt
Required for attention Posner benchmark
At least one of:
benchmark_out/*_summary_episode_*.csv
benchmark_out/*_per_trial_episode_*.csv
Recommended:
benchmark_out/*_java_steps_*.csv
Manifest fields
The manifest.yaml file must include:
agent_name: Substage3
architecture_name: CONAIM
benchmark: motivation
benchmark_version: motivation_v1
cogscore_version: "0.1.0"
run_name: "Substage3 motivation test"
date: "2026-06-06"

parameters:
  episodes: 50
  trials_per_experiment: 20
  seed: 777
  x_points: 50
  smooth_window: 7

source:
  type: uploaded_results
  author: Leonardo
  notes: "Run generated locally and uploaded for comparison."
Allowed benchmark names
Use one of:
motivation
attention_posner
sensory_buffer
learning
Initially, the platform will support:
motivation
attention_posner
The other benchmark names are reserved for future expansion.
Field descriptions
agent_name
Name of the evaluated agent.
Examples:
Substage1
Substage3
CONAIM
MyNewArchitecture
architecture_name
Name of the cognitive architecture or implementation family.
Examples:
CONAIM
CST
CogScoreAgent
ExternalRESTAgent
benchmark
Benchmark family.
Examples:
motivation
attention_posner
benchmark_version
Version of the experimental protocol.
Examples:
motivation_v1
posner_v1
cogscore_version
Version or commit reference of the CogScore code used to generate the result.
Examples:
0.1.0
git:a1b2c3d
run_name
Human-readable name for the run.
date
Date of execution or upload, preferably in YYYY-MM-DD format.
parameters
Execution parameters such as:
episodes: 50
trials_per_experiment: 20
seed: 777
x_points: 50
smooth_window: 7
source
Information about the origin of the result.
Example:
source:
  type: uploaded_results
  author: Leonardo
  notes: "Run generated locally and uploaded for comparison."
Recommended naming convention
When imported, result bundles should be stored internally as:
data/results/{agent_name}/{benchmark}/run_{date_or_id}/benchmark_out/
Example:
data/results/Substage3/motivation/run_2026_06_06_001/benchmark_out/
Validation rules
A valid result bundle must satisfy:
It must be a .zip file or an extracted directory.
It must contain manifest.yaml.
It must contain benchmark_out/.
manifest.yaml must contain all required fields.
benchmark must be one of the allowed benchmark names.
The benchmark output folder must contain at least one recognized CSV file.
The package should not contain absolute paths.
The package should not contain files outside the extracted directory.

Salve.

---

# 1.6 — Criar exemplo de manifesto para motivation

Crie a pasta de exemplos:

```bash
mkdir -p docs/examples
