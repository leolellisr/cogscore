#!/usr/bin/env bash
set -euo pipefail

SCENE="${1:-}"
LOG_PATH="${2:-/data/coppelia/coppelia.log}"
COPPELIASIM_ROOT="${COPPELIASIM_ROOT:-/opt/CoppeliaSim}"
PID_FILE="${COPPELIASIM_PID_FILE:-/run/cogscore-coppelia.pid}"
AUTO_START="${COPPELIASIM_AUTO_START:-1}"

if [[ -z "$SCENE" ]]; then
  echo "usage: cogscore-open-coppelia /absolute/path/to/scene.ttt [log-path]" >&2
  exit 2
fi

if [[ ! -f "$SCENE" ]]; then
  echo "CoppeliaSim scene not found: $SCENE" >&2
  exit 3
fi

if [[ ! -x "$COPPELIASIM_ROOT/coppeliaSim" ]]; then
  echo "CoppeliaSim executable not found: $COPPELIASIM_ROOT/coppeliaSim" >&2
  exit 4
fi

mkdir -p "$(dirname "$LOG_PATH")"

/usr/local/bin/cogscore-stop-coppelia || true

ARGS=(-vloadinfos)
if [[ "$AUTO_START" == "1" ]]; then
  ARGS+=(-s0)
fi
ARGS+=("$SCENE")

export DISPLAY="${DISPLAY:-:1}"
export LD_LIBRARY_PATH="$COPPELIASIM_ROOT${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export QT_X11_NO_MITSHM="${QT_X11_NO_MITSHM:-1}"
export LIBGL_ALWAYS_SOFTWARE="${LIBGL_ALWAYS_SOFTWARE:-1}"
export COPPELIASIM_USER_SETTINGS_FOLDER_SUFFIX="${COPPELIASIM_USER_SETTINGS_FOLDER_SUFFIX:-cogscore}"

nohup "$COPPELIASIM_ROOT/coppeliaSim" "${ARGS[@]}" >>"$LOG_PATH" 2>&1 &
PID=$!
echo "$PID" > "$PID_FILE"

for _ in $(seq 1 30); do
  if ! kill -0 "$PID" 2>/dev/null; then
    echo "CoppeliaSim exited during startup. Last log lines:" >&2
    tail -n 80 "$LOG_PATH" >&2 || true
    exit 5
  fi

  if pgrep -x coppeliaSim >/dev/null 2>&1; then
    echo "CoppeliaSim started: pid=$PID scene=$SCENE log=$LOG_PATH"
    exit 0
  fi

  sleep 1
done

echo "CoppeliaSim process exists but did not become ready within 30 seconds." >&2
tail -n 80 "$LOG_PATH" >&2 || true
exit 6
