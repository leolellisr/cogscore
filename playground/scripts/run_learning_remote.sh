#!/usr/bin/env bash
set -euo pipefail

AGENT_URL=""
SCENE=""
OUT=""
EPISODES="1"
STAGES="Substage1,Substage2,Substage3,Substage4,Substage5"
TESTS="testA,testB,testAB"
STEPS_PER_EPISODE="100"
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
    --learning-stages)
      STAGES="$2"
      shift 2
      ;;
    --learning-tests)
      TESTS="$2"
      shift 2
      ;;
    --steps-per-episode)
      STEPS_PER_EPISODE="$2"
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

echo "[learning-remote] agent url: $AGENT_URL"
echo "[learning-remote] scene: $SCENE"
echo "[learning-remote] out: $OUT"
echo "[learning-remote] episodes: $EPISODES"
echo "[learning-remote] stages: $STAGES"
echo "[learning-remote] tests: $TESTS"
echo "[learning-remote] steps per episode: $STEPS_PER_EPISODE"
echo "[learning-remote] seed: $SEED"

python3 /workspace/scripts/learning_remote_smoke_runner.py \
  --agent-url "$AGENT_URL" \
  --out "$OUT" \
  --episodes "$EPISODES" \
  --learning-stages "$STAGES" \
  --learning-tests "$TESTS" \
  --steps-per-episode "$STEPS_PER_EPISODE" \
  --seed "$SEED"

echo "[learning-remote] done"

# Integração real com Coppelia/Java:
#
# 1. Abrir a cena correta:
#    /opt/CoppeliaSim/coppeliaSim.sh "$SCENE"
#
# 2. Inicializar sua aplicação Java/CST com um LearningRemoteBridge:
#    java -cp "..." your.main.Class \
#      --benchmark learning \
#      --agent-url "$AGENT_URL" \
#      --scene "$SCENE" \
#      --out "$OUT" \
#      --episodes "$EPISODES" \
#      --learning-stages "$STAGES" \
#      --learning-tests "$TESTS" \
#      --steps-per-episode "$STEPS_PER_EPISODE" \
#      --seed "$SEED"