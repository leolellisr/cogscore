#!/usr/bin/env bash
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

section() {
  printf '\n===== %s =====\n' "$1"
}

run() {
  printf '+ %s\n' "$*"
  "$@" 2>&1 || true
}

section 'Docker CLI and daemon'
run sh -c 'command -v docker'
run sh -c 'command -v docker | xargs -r readlink -f'
run docker context show
run docker version
run docker info

section 'Possible competing installations'
run sh -c 'which -a docker'
run sh -c 'systemctl is-active docker 2>/dev/null || true'
run sh -c 'snap list docker 2>/dev/null || true'
run sh -c 'snap services docker 2>/dev/null || true'
run sh -c "ps -ef | grep -E '[d]ockerd|[c]ontainerd'"
run ls -l /var/run/docker.sock

section 'Compose services'
run docker compose ps -a
run docker compose logs --tail=120 worker

section 'CogScore network, images, and containers'
run docker network inspect cogscore_online_net
run docker image ls 'cogscore-agent-*'
run docker ps -a --filter 'name=cogscore-' --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Networks}}'

section 'Host capacity'
run docker system df
run df -h .
run sh -c 'free -h 2>/dev/null || true'

section 'Latest job stderr logs'
if [ -d data/jobs ]; then
  find data/jobs -type f -name stderr.log -printf '%T@ %p\n' 2>/dev/null \
    | sort -nr \
    | head -5 \
    | cut -d' ' -f2- \
    | while IFS= read -r log; do
        [ -n "$log" ] || continue
        printf '\n--- %s ---\n' "$log"
        tail -80 "$log" 2>/dev/null || true
      done
else
  printf '%s\n' 'data/jobs does not exist.'
fi
