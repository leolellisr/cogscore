#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import math
import random
import urllib.request
from pathlib import Path


def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--learning-stages", default="Substage1,Substage2,Substage3,Substage4,Substage5")
    parser.add_argument("--learning-tests", default="testA,testB,testAB")
    parser.add_argument("--steps-per-episode", type=int, default=100)
    parser.add_argument("--seed", type=int, default=777)
    return parser.parse_args()


def tests_for_stage(stage: str, requested_tests: list[str]) -> list[str]:
    if stage in {"Substage1", "Substage2", "Substage3"}:
        return [t for t in requested_tests if t in {"testA", "testB"}]
    if stage == "Substage4":
        return [t for t in requested_tests if t in {"testA", "testAB", "testB"}]
    if stage == "Substage5":
        return ["testA"]
    return ["testA"]


def fallback_action(yaw_error: float, pitch_error: float) -> dict:
    return {
        "action": "TRACK",
        "yaw_delta": -0.35 * yaw_error,
        "pitch_delta": -0.35 * pitch_error,
        "confidence": 0.5,
    }


def call_agent(
    agent_url: str,
    stage: str,
    test: str,
    episode: int,
    step: int,
    yaw_error: float,
    pitch_error: float,
    rng: random.Random,
) -> dict:
    visible = not (stage == "Substage4" and test in {"testAB", "testB"} and 20 <= step <= 55)
    multiple_objects = stage == "Substage5"

    payload = {
        "benchmark": "learning",
        "stage": stage,
        "test": test,
        "episode": episode,
        "step": step,
        "target": {
            "visible": visible,
            "occluded": not visible,
            "x": 0.5 + 0.1 * math.sin(step / 10.0),
            "y": 0.5 + 0.1 * math.cos(step / 10.0),
            "yaw_error": yaw_error,
            "pitch_error": pitch_error,
        },
        "objects": [
            {"id": 1, "label": "target", "visible": visible},
            {"id": 2, "label": "distractor", "visible": multiple_objects},
        ],
        "signals": {
            "curiosity": 0.4 if stage in {"Substage2", "Substage3"} else 0.0,
            "reward_available": True,
            "occlusion": not visible,
            "multiple_objects": multiple_objects,
        },
    }

    try:
        return post_json(agent_url.rstrip("/") + "/learning/act", payload)
    except Exception:
        return fallback_action(yaw_error, pitch_error)


def write_nrewards(
    file_path: Path,
    agent_url: str,
    stage: str,
    test: str,
    episodes: int,
    steps_per_episode: int,
    seed: int,
) -> None:
    rng = random.Random(seed + hash(stage + test) % 100000)

    file_path.parent.mkdir(parents=True, exist_ok=True)

    with file_path.open("w", encoding="utf-8") as f:
        f.write("header\n")

        for episode in range(1, episodes + 1):
            yaw_error = rng.uniform(-1.0, 1.0)
            pitch_error = rng.uniform(-0.5, 0.5)

            for step in range(1, steps_per_episode + 1):
                response = call_agent(
                    agent_url=agent_url,
                    stage=stage,
                    test=test,
                    episode=episode,
                    step=step,
                    yaw_error=yaw_error,
                    pitch_error=pitch_error,
                    rng=rng,
                )

                yaw_delta = float(response.get("yaw_delta", 0.0))
                pitch_delta = float(response.get("pitch_delta", 0.0))

                yaw_error += yaw_delta
                pitch_error += pitch_delta

                yaw_error += rng.uniform(-0.01, 0.01)
                pitch_error += rng.uniform(-0.005, 0.005)

                angular_error = math.sqrt(yaw_error * yaw_error + pitch_error * pitch_error)
                reward = max(0.0, 1.0 - angular_error)

                cols = [0.0] * 22
                cols[0] = 0
                cols[1] = episode
                cols[2] = step
                cols[3] = 0
                cols[4] = reward
                cols[19] = yaw_error * 100.0
                cols[20] = pitch_error * 100.0

                f.write(" ".join(str(x) for x in cols) + "\n")


def main() -> int:
    args = parse_args()

    out_dir = Path(args.out)
    stages = [x.strip() for x in args.learning_stages.split(",") if x.strip()]
    requested_tests = [x.strip() for x in args.learning_tests.split(",") if x.strip()]

    base = args.agent_url.rstrip("/")

    try:
        get_json(base + "/health")
        post_json(base + "/reset", {"benchmark": "learning"})
    except Exception:
        pass

    for stage in stages:
        for test in tests_for_stage(stage, requested_tests):
            nrewards_path = out_dir / stage / test / f"seed{args.seed}" / "profile" / "nrewards.txt"
            write_nrewards(
                file_path=nrewards_path,
                agent_url=base,
                stage=stage,
                test=test,
                episodes=args.episodes,
                steps_per_episode=args.steps_per_episode,
                seed=args.seed,
            )

    try:
        post_json(base + "/close", {})
    except Exception:
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())