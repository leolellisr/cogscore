#!/usr/bin/env bash
set -e

if [ -z "${VNC_PASSWORD:-}" ]; then
  export VNC_PASSWORD="change-me"
fi

echo "[sim-vnc] Starting VNC/noVNC"
echo "[sim-vnc] Open http://localhost:6080 or /vnc/ through the proxy"

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
