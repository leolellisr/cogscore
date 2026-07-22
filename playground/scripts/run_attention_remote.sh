#!/usr/bin/env bash
set -euo pipefail

AGENT_URL=""
SCENE=""
OUT=""
EPISODES="1"
POSNER_EXPERIMENTS="1,2,3,4,5"
TRIALS_PER_EXPERIMENT="20"
MAP_WIDTH="32"
MAP_HEIGHT="32"
CYCLES_PER_TRIAL="30"
SEED="777"

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
    --posner-experiments)
      POSNER_EXPERIMENTS="$2"
      shift 2
      ;;
    --trials-per-experiment)
      TRIALS_PER_EXPERIMENT="$2"
      shift 2
      ;;
    --map-width)
      MAP_WIDTH="$2"
      shift 2
      ;;
    --map-height)
      MAP_HEIGHT="$2"
      shift 2
      ;;
    --cycles-per-trial)
      CYCLES_PER_TRIAL="$2"
      shift 2
      ;;
    --seed)
      SEED="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

mkdir -p "$OUT"

if [[ "${COGSCORE_OPEN_COPPELIA:-1}" == "1" ]]; then
  /usr/local/bin/cogscore-open-coppelia \
    "$SCENE" \
    "$OUT/coppelia.log"
fi

echo "[attention-remote] agent url: $AGENT_URL"
echo "[attention-remote] scene: $SCENE"
echo "[attention-remote] out: $OUT"
echo "[attention-remote] episodes: $EPISODES"
echo "[attention-remote] posner experiments: $POSNER_EXPERIMENTS"
echo "[attention-remote] trials per experiment: $TRIALS_PER_EXPERIMENT"
echo "[attention-remote] map size: ${MAP_WIDTH}x${MAP_HEIGHT}"
echo "[attention-remote] cycles per trial: $CYCLES_PER_TRIAL"
echo "[attention-remote] seed: $SEED"

python3 /workspace/scripts/attention_remote_smoke_runner.py \
  --agent-url "$AGENT_URL" \
  --out "$OUT" \
  --episodes "$EPISODES" \
  --posner-experiments "$POSNER_EXPERIMENTS" \
  --trials-per-experiment "$TRIALS_PER_EXPERIMENT" \
  --map-width "$MAP_WIDTH" \
  --map-height "$MAP_HEIGHT" \
  --cycles-per-trial "$CYCLES_PER_TRIAL" \
  --seed "$SEED"

echo "[attention-remote] done"

# Integração real com Coppelia/Java:
#
# 1. Abrir a cena:
#    /opt/CoppeliaSim/coppeliaSim.sh "$SCENE"
#
# 2. Inicializar sua aplicação Java/CST com um PosnerRemoteBridge:
#    java -cp "..." your.main.Class \
#      --benchmark attention_posner \
#      --agent-url "$AGENT_URL" \
#      --scene "$SCENE" \
#      --out "$OUT" \
#      --episodes "$EPISODES" \
#      --posner-experiments "$POSNER_EXPERIMENTS" \
#      --trials-per-experiment "$TRIALS_PER_EXPERIMENT" \
#      --map-width "$MAP_WIDTH" \
#      --map-height "$MAP_HEIGHT" \
#      --cycles-per-trial "$CYCLES_PER_TRIAL" \
#      --seed "$SEED"