#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLAYGROUND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PLAYGROUND_DIR"

if docker compose version >/dev/null 2>&1; then
    compose() {
        docker compose "$@"
    }
elif command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
    compose() {
        docker-compose "$@"
    }
else
    echo "Error: Docker Compose was not found." >&2
    exit 1
fi

compose \
    -f docker-compose.yml \
    -f docker-compose.public.yml \
    stop tunnel

echo "The public tunnel has been stopped. Local CogScore services remain running."
