#!/usr/bin/env bash
set -euo pipefail

AGENT_URL=""
SCENE=""
OUT=""
EPISODES="1"
TRIALS_PER_DELAY="3"
DELAYS_MS="0,50,100,220"
RESOLUTION="64"
PATCH_SIZE="8"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent-url)
      AGENT_URL="$2"
      shift 2
      ;;
    --scene)
      SCENE="$2"
      shift 2
      ;;
    --out)
      OUT="$2"
      shift 2
      ;;
    --episodes)
      EPISODES="$2"
      shift 2
      ;;
    --trials-per-delay)
      TRIALS_PER_DELAY="$2"
      shift 2
      ;;
    --delays-ms)
      DELAYS_MS="$2"
      shift 2
      ;;
    --resolution)
      RESOLUTION="$2"
      shift 2
      ;;
    --patch-size)
      PATCH_SIZE="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

mkdir -p "$OUT"

echo "[sensory-remote] agent url: $AGENT_URL"
echo "[sensory-remote] scene: $SCENE"
echo "[sensory-remote] out: $OUT"
echo "[sensory-remote] episodes: $EPISODES"
echo "[sensory-remote] trials per delay: $TRIALS_PER_DELAY"
echo "[sensory-remote] delays ms: $DELAYS_MS"
echo "[sensory-remote] resolution: $RESOLUTION"
echo "[sensory-remote] patch size: $PATCH_SIZE"

python3 /workspace/scripts/sensory_remote_smoke_runner.py \
  --agent-url "$AGENT_URL" \
  --out "$OUT" \
  --episodes "$EPISODES" \
  --trials-per-delay "$TRIALS_PER_DELAY" \
  --delays-ms "$DELAYS_MS" \
  --resolution "$RESOLUTION" \
  --patch-size "$PATCH_SIZE"

echo "[sensory-remote] done"

# Integração real com Coppelia/Java:
#
# 1. Abrir a cena:
#    /opt/CoppeliaSim/coppeliaSim.sh "$SCENE"
#
# 2. Inicializar sua aplicação Java/CST com RGBSperlingRemoteBridge:
#    java -cp "..." your.main.Class \
#      --agent-url "$AGENT_URL" \
#      --scene "$SCENE" \
#      --out "$OUT" \
#      --episodes "$EPISODES" \
#      --trials-per-delay "$TRIALS_PER_DELAY" \
#      --delays-ms "$DELAYS_MS" \
#      --resolution "$RESOLUTION" \
#      --patch-size "$PATCH_SIZE"
