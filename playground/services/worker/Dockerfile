ARG DOCKER_CLI_IMAGE=docker:27-cli
ARG PYTHON_IMAGE=python:3.11-slim-bookworm

FROM ${DOCKER_CLI_IMAGE} AS dockercli
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    HOME=/tmp

COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

COPY --from=dockercli \
    /usr/local/libexec/docker/cli-plugins \
    /usr/local/libexec/docker/cli-plugins

WORKDIR /worker_src

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /worker_src/requirements.txt
RUN python -m pip install --no-cache-dir -r /worker_src/requirements.txt \
    && python -I -c "import encodings, pandas, matplotlib; print(encodings.__file__)"

COPY worker /worker_src/worker

# Validate the worker source without importing runtime-only dependencies.
RUN test -f /worker_src/worker/__init__.py \
    && python -m py_compile /worker_src/worker/main.py
    
CMD ["python", "-m", "worker.main"]
