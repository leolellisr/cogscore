# CogScore Playground Worker

The worker continuously processes pending SQLite jobs. It validates uploaded
architectures, starts experiment containers, imports results, and generates plots.

## Docker startup cleanup

At every worker startup, stale dynamic containers are removed when they match one
of these selectors:

- label `cogscore.managed=true`;
- name `cogscore-run-*`;
- name `cogscore-smoke-*`.

The retry behavior is controlled by `DOCKER_CLEANUP_ATTEMPTS` and
`DOCKER_CLEANUP_RETRY_SECONDS`. Active architecture containers are also removed
on normal `SIGTERM` / `SIGINT` shutdown.

## Running

With Compose:

```bash
cd playground
docker compose up -d --build
docker compose logs -f worker
```

Without Compose:

```bash
source .venv/bin/activate
cd playground/services/worker
python -m worker.main
```

Job logs are stored in `data/jobs/{job_id}/`. Comparison plots are stored in
`data/plots/{benchmark}/comparison/{job_id}/`.
