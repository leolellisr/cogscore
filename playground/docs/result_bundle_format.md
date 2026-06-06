# Result Bundle Format

A result bundle is a ZIP file uploaded to the CogScore Playground for comparison and plotting.

## Expected structure

```
result_bundle.zip
├── manifest.yaml
├── benchmark_out/
│   ├── *_summary_episode_*.csv
│   ├── *_per_trial_episode_*.csv
│   ├── *_java_steps_*.csv
│   └── motivation_marta_trials.txt
└── optional/
    ├── config.json
    └── notes.md
    
```

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
