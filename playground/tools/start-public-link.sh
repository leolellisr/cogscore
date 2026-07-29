#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLAYGROUND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PLAYGROUND_DIR"

[ -f .env ] || touch .env

DEFAULT_NGROK_DOMAIN="affix-decimeter-eradicate.ngrok-free.dev"

read_env_value() {
    key=$1
    sed -n "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*//p" .env \
        | tail -n 1 \
        | tr -d '\r' \
        | sed 's/^"//; s/"$//; s/^'"'"'//; s/'"'"'$//'
}

ngrok_token=${NGROK_AUTHTOKEN:-$(read_env_value NGROK_AUTHTOKEN)}
if [ -z "$ngrok_token" ]; then
    echo "Error: NGROK_AUTHTOKEN is not configured." >&2
    echo "Add a valid token to playground/.env:" >&2
    echo "  NGROK_AUTHTOKEN=your-new-ngrok-token" >&2
    exit 1
fi

ngrok_domain=${NGROK_DOMAIN:-$(read_env_value NGROK_DOMAIN)}
if [ -z "$ngrok_domain" ]; then
    ngrok_domain=$DEFAULT_NGROK_DOMAIN
fi

case "$ngrok_domain" in
    http://*|https://*)
        echo "Error: NGROK_DOMAIN must contain only the hostname, without http:// or https://." >&2
        echo "Example: NGROK_DOMAIN=$DEFAULT_NGROK_DOMAIN" >&2
        exit 1
        ;;
esac

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

# Export the validated values so Compose receives environment overrides too.
export NGROK_AUTHTOKEN="$ngrok_token"
export NGROK_DOMAIN="$ngrok_domain"

compose \
    -f docker-compose.yml \
    -f docker-compose.public.yml \
    config >/dev/null

compose \
    -f docker-compose.yml \
    -f docker-compose.public.yml \
    up -d --build api worker web sim-vnc proxy tunnel

tries=0
running=""
while [ "$tries" -lt 15 ]; do
    running=$(docker inspect -f '{{.State.Running}}' cogscore-public-tunnel 2>/dev/null || true)
    if [ "$running" = "true" ]; then
        break
    fi
    tries=$((tries + 1))
    sleep 1
done

if [ "$running" != "true" ]; then
    echo "The ngrok container did not remain running." >&2
    echo "Inspect its logs with:" >&2
    if docker compose version >/dev/null 2>&1; then
        echo "  docker compose -f docker-compose.yml -f docker-compose.public.yml logs tunnel" >&2
    else
        echo "  docker-compose -f docker-compose.yml -f docker-compose.public.yml logs tunnel" >&2
    fi
    exit 1
fi

public_url="https://${ngrok_domain}"
printf '\nCogScore is publicly available at:\n%s\n\n' "$public_url"
echo "This address remains fixed while the ngrok dev domain is assigned to your account."
echo "No proxy password is configured. Anyone with this URL can access the application."
echo "Keep this computer, Docker, and the tunnel container running."
