#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

printf '%s\n' '[cleanup] Removing CogScore architecture containers created outside Compose...'
{
  docker ps -aq --filter 'label=cogscore.managed=true'
  docker ps -aq --filter 'name=cogscore-run-'
  docker ps -aq --filter 'name=cogscore-smoke-'
} | sed '/^$/d' | sort -u | xargs -r docker rm -f

printf '%s\n' '[cleanup] Stopping and removing Compose services...'
docker compose down --remove-orphans --timeout "${COGSCORE_STOP_TIMEOUT:-30}"

printf '%s\n' '[cleanup] Remaining CogScore containers:'
docker ps -a --filter 'name=cogscore-' --format 'table {{.Names}}\t{{.Status}}\t{{.Image}}'
