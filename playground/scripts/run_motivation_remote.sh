#!/usr/bin/env bash
set -euo pipefail

AGENT_URL=""
SCENE=""
OUT=""
EPISODES="1"
MOTIVATION_EXPERIMENTS="1,2,3,4,5"
TRIALS_PER_EXPERIMENT="20"
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
    --motivation-experiments)
      MOTIVATION_EXPERIMENTS="$2"
      shift 2
      ;;
    --trials-per-experiment)
      TRIALS_PER_EXPERIMENT="$2"
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

echo "[motivation-remote] agent url: $AGENT_URL"
echo "[motivation-remote] scene: $SCENE"
echo "[motivation-remote] out: $OUT"
echo "[motivation-remote] episodes: $EPISODES"
echo "[motivation-remote] motivation experiments: $MOTIVATION_EXPERIMENTS"
echo "[motivation-remote] trials per experiment: $TRIALS_PER_EXPERIMENT"
echo "[motivation-remote] cycles per trial: $CYCLES_PER_TRIAL"
echo "[motivation-remote] seed: $SEED"

python3 /workspace/scripts/motivation_remote_smoke_runner.py \
  --agent-url "$AGENT_URL" \
  --out "$OUT" \
  --episodes "$EPISODES" \
  --motivation-experiments "$MOTIVATION_EXPERIMENTS" \
  --trials-per-experiment "$TRIALS_PER_EXPERIMENT" \
  --cycles-per-trial "$CYCLES_PER_TRIAL" \
  --seed "$SEED"

echo "[motivation-remote] done"

# Integração real com Coppelia/Java:
#
# 1. Abrir a cena:
#    /opt/CoppeliaSim/coppeliaSim.sh "$SCENE"
#
# 2. Inicializar sua aplicação Java/CST com um MotivationRemoteBridge:
#    java -cp "..." your.main.Class \
#      --benchmark motivation \
#      --agent-url "$AGENT_URL" \
#      --scene "$SCENE" \
#      --out "$OUT" \
#      --episodes "$EPISODES" \
#      --motivation-experiments "$MOTIVATION_EXPERIMENTS" \
#      --trials-per-experiment "$TRIALS_PER_EXPERIMENT" \
#      --cycles-per-trial "$CYCLES_PER_TRIAL" \
#      --seed "$SEED"