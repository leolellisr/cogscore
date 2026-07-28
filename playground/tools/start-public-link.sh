#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLAYGROUND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PLAYGROUND_DIR"

[ -f .env ] || touch .env

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
    echo "Install the Docker Compose plugin or the docker-compose compatibility binary." >&2
    echo "Checks performed:" >&2
    echo "  docker compose version" >&2
    echo "  docker-compose version" >&2
    exit 1
fi

compose \
    -f docker-compose.yml \
    -f docker-compose.public.yml \
    config >/dev/null

compose \
    -f docker-compose.yml \
    -f docker-compose.public.yml \
    up -d --build api worker web sim-vnc proxy

# Quick Tunnel hostnames are temporary. Recreate only the tunnel so the
# script never reuses a hostname left in an old container log.
compose \
    -f docker-compose.yml \
    -f docker-compose.public.yml \
    rm -sf tunnel >/dev/null 2>&1 || true

compose \
    -f docker-compose.yml \
    -f docker-compose.public.yml \
    up -d --force-recreate tunnel

echo "Waiting for Cloudflare to create the public URL..."
tries=0
url=""
while [ "$tries" -lt 60 ]; do
    url=$(compose \
        -f docker-compose.yml \
        -f docker-compose.public.yml \
        logs --since=2m --no-color tunnel 2>/dev/null \
        | sed -n 's#.*\(https://[a-zA-Z0-9-]*\.trycloudflare\.com\).*#\1#p' \
        | tail -n 1)

    if [ -n "$url" ]; then
        break
    fi

    tries=$((tries + 1))
    sleep 2
done

if [ -z "$url" ]; then
    echo "The tunnel container started, but the public URL was not detected." >&2
    echo "Inspect the logs from the playground directory with:" >&2
    if docker compose version >/dev/null 2>&1; then
        echo "  docker compose -f docker-compose.yml -f docker-compose.public.yml logs tunnel" >&2
    else
        echo "  docker-compose -f docker-compose.yml -f docker-compose.public.yml logs tunnel" >&2
    fi
    exit 1
fi

printf '\nCogScore is publicly available at:\n%s\n\n' "$url"
echo "No password is configured. Anyone with this URL can access the application."
echo "Keep this computer, Docker, and the tunnel container running."
echo "The trycloudflare.com address may change when the tunnel is recreated."
