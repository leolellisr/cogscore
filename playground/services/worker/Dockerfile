FROM docker:27-cli AS dockercli
FROM python:3.11-slim

COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker

WORKDIR /worker_src

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /worker_src/requirements.txt
RUN pip install --no-cache-dir -r /worker_src/requirements.txt

COPY worker /worker_src/worker

CMD ["python", "-m", "worker.main"]
