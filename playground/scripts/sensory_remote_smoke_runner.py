from __future__ import annotations

import argparse
import csv
import math
import random
import time
from pathlib import Path

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--trials-per-delay", type=int, default=3)
    parser.add_argument("--delays-ms", default="0,50,100,220")
    parser.add_argument("--resolution", type=int, default=64)
    parser.add_argument("--patch-size", type=int, default=8)
    return parser.parse_args()


def make_frame(width: int, height: int, seed: int) -> list[float]:
    rnd = random.Random(seed)
    return [float(rnd.randint(0, 255)) for _ in range(width * height * 3)]


def extract_patch(frame: list[float], width: int, x0: int, y0: int, size: int) -> list[float]:
    patch = []
    for y in range(y0, y0 + size):
        for x in range(x0, x0 + size):
            idx = (y * width + x) * 3
            patch.extend(frame[idx:idx + 3])
    return patch


def mse(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 255.0 * 255.0
    return sum((float(a[i]) - float(b[i])) ** 2 for i in range(n)) / n


def main() -> int:
    args = parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    delays = [int(x.strip()) for x in args.delays_ms.split(",") if x.strip()]
    width = args.resolution
    height = args.resolution
    patch_size = args.patch_size

    base = args.agent_url.rstrip("/")

    requests.get(base + "/health", timeout=10).raise_for_status()

    for episode in range(args.episodes):
        requests.post(base + "/reset", json={"benchmark": "sensory_buffer", "episode": episode}, timeout=10).raise_for_status()

        per_trial_path = out_dir / f"vision_sperling_per_trial_episode_{episode}_remote.csv"
        summary_path = out_dir / f"vision_sperling_summary_episode_{episode}_remote.csv"

        sums = {d: 0.0 for d in delays}
        sums2 = {d: 0.0 for d in delays}
        counts = {d: 0 for d in delays}

        with per_trial_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["episode", "condition", "delay_ms", "trial_idx", "cue_desc", "distance_mse", "fidelity"])

            for delay_ms in delays:
                for trial_idx in range(args.trials_per_delay):
                    frame = make_frame(width, height, seed=episode * 100000 + delay_ms * 100 + trial_idx)

                    stimulus = {
                        "benchmark": "sensory_buffer",
                        "episode": episode,
                        "trial": trial_idx,
                        "delay_ms": delay_ms,
                        "width": width,
                        "height": height,
                        "channels": 3,
                        "encoding": "rgb_float_0_255",
                        "frame": frame,
                    }

                    requests.post(base + "/sensory/stimulus", json=stimulus, timeout=30).raise_for_status()

                    if delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)

                    x0 = (trial_idx * 7) % (width - patch_size + 1)
                    y0 = (trial_idx * 11) % (height - patch_size + 1)

                    cue = {
                        "benchmark": "sensory_buffer",
                        "episode": episode,
                        "trial": trial_idx,
                        "delay_ms": delay_ms,
                        "cue": {
                            "type": "patch",
                            "x0": x0,
                            "y0": y0,
                            "size": patch_size,
                        },
                    }

                    r = requests.post(base + "/sensory/readout", json=cue, timeout=30)
                    r.raise_for_status()
                    data = r.json()

                    truth_patch = extract_patch(frame, width, x0, y0, patch_size)
                    stored_patch = data.get("patch", [])

                    distance = mse(stored_patch, truth_patch)
                    fidelity = 1.0 - distance / (255.0 * 255.0)
                    fidelity = max(0.0, min(1.0, fidelity))

                    cue_desc = f"VisionPatchList[x0={x0},y0={y0},s={patch_size}]"

                    writer.writerow([episode, "remote", delay_ms, trial_idx, cue_desc, distance, fidelity])

                    sums[delay_ms] += fidelity
                    sums2[delay_ms] += fidelity * fidelity
                    counts[delay_ms] += 1

        with summary_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["episode", "condition", "aborted", "delay_ms", "mean_fidelity", "std_fidelity", "F0", "lambda", "r2", "used_points"])

            for delay_ms in delays:
                count = counts[delay_ms]
                mean = sums[delay_ms] / count if count else float("nan")
                var = sums2[delay_ms] / count - mean * mean if count else float("nan")
                std = math.sqrt(max(0.0, var)) if count else float("nan")

                writer.writerow([episode, "remote", "false", delay_ms, mean, std, "", "", "", count])

    requests.post(base + "/close", json={}, timeout=10)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
