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
