#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PLAYGROUND_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
cd "$PLAYGROUND_DIR"

DEFAULT_NGROK_DOMAIN="affix-decimeter-eradicate.ngrok-free.dev"
ENV_FILE=".env"

set_env_value() {
    key=$1
    value=$2
    tmp_file=$(mktemp "${ENV_FILE}.tmp.XXXXXX")

    awk -v key="$key" '
        $0 !~ "^[[:space:]]*" key "[[:space:]]*=" { print }
    ' "$ENV_FILE" > "$tmp_file"
    printf '%s=%s\n' "$key" "$value" >> "$tmp_file"

    chmod 600 "$tmp_file"
    mv "$tmp_file" "$ENV_FILE"
}

[ -f "$ENV_FILE" ] || : > "$ENV_FILE"
chmod 600 "$ENV_FILE"

ngrok_domain=${NGROK_DOMAIN:-$DEFAULT_NGROK_DOMAIN}
case "$ngrok_domain" in
    http://*|https://*)
        echo "Error: NGROK_DOMAIN must not include http:// or https://." >&2
        exit 1
        ;;
esac

if [ -n "${NGROK_AUTHTOKEN:-}" ]; then
    ngrok_token=$NGROK_AUTHTOKEN
else
    if [ ! -t 0 ]; then
        echo "Error: run this script in a terminal or export NGROK_AUTHTOKEN first." >&2
        exit 1
    fi

    printf 'Paste the new ngrok authtoken: '
    trap 'stty echo 2>/dev/null || true' EXIT HUP INT TERM
    stty -echo
    IFS= read -r ngrok_token
    stty echo
    trap - EXIT HUP INT TERM
    printf '\n'
fi

if [ -z "$ngrok_token" ]; then
    echo "Error: the ngrok authtoken cannot be empty." >&2
    exit 1
fi

set_env_value NGROK_AUTHTOKEN "$ngrok_token"
set_env_value NGROK_DOMAIN "$ngrok_domain"

printf 'ngrok configuration saved in %s with permissions 600.\n' "$PLAYGROUND_DIR/$ENV_FILE"
printf 'Fixed public URL: https://%s\n' "$ngrok_domain"
