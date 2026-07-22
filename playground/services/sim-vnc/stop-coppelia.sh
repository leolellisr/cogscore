#!/usr/bin/env bash
set -euo pipefail

PID_FILE="${COPPELIASIM_PID_FILE:-/run/cogscore-coppelia.pid}"
PID=""

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" 2>/dev/null || true)"
fi

if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
  kill -TERM "$PID" 2>/dev/null || true
  for _ in $(seq 1 10); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$PID" 2>/dev/null; then
    kill -KILL "$PID" 2>/dev/null || true
  fi
fi

pkill -TERM -x coppeliaSim 2>/dev/null || true
sleep 1
pkill -KILL -x coppeliaSim 2>/dev/null || true
rm -f "$PID_FILE"
