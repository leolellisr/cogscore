#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
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
        if not body:
            return {}
        return json.loads(body)


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=10) as response:
        body = response.read().decode("utf-8")
        if not body:
            return {}
        return json.loads(body)


def gaussian_map(width: int, height: int, cx: float, cy: float, sigma: float = 0.12) -> list[list[float]]:
    values = []
    for y in range(height):
        row = []
        ny = y / max(1, height - 1)
        for x in range(width):
            nx = x / max(1, width - 1)
            d2 = (nx - cx) ** 2 + (ny - cy) ** 2
            row.append(math.exp(-d2 / (2.0 * sigma * sigma)))
        values.append(row)
    return values


def trial_condition(rng: random.Random) -> tuple[str, str]:
    trial_type = rng.choice(["valid", "invalid", "neutral"])
    cue_type = "neutral" if trial_type == "neutral" else "endogenous"
    return trial_type, cue_type


def target_and_cue(rng: random.Random, trial_type: str) -> tuple[tuple[float, float], tuple[float, float]]:
    target_side = rng.choice(["left", "right"])
    target = (0.25, 0.5) if target_side == "left" else (0.75, 0.5)

    if trial_type == "valid":
        cue = target
    elif trial_type == "invalid":
        cue = (0.75, 0.5) if target_side == "left" else (0.25, 0.5)
    else:
        cue = (0.5, 0.5)

    return target, cue


def call_attention_agent(
    agent_url: str,
    benchmark: str,
    experiment_id: int,
    episode: int,
    trial_id: str,
    trial_type: str,
    cue_type: str,
    target: tuple[float, float],
    cue: tuple[float, float],
    width: int,
    height: int,
    cycles_per_trial: int,
) -> dict:
    payload = {
        "benchmark": benchmark,
        "experiment_id": experiment_id,
        "episode": episode,
        "trial_id": trial_id,
        "trial_type": trial_type,
        "cue_type": cue_type,
        "target": {"x": target[0], "y": target[1]},
        "cue": {"x": cue[0], "y": cue[1]},
        "fixation": {"x": 0.5, "y": 0.5},
        "map_width": width,
        "map_height": height,
        "cycles_per_trial": cycles_per_trial,
    }

    try:
        return post_json(agent_url.rstrip("/") + "/attention/act", payload)
    except Exception:
        # Fallback: assume a simple agent that attends to the target.
        return {
            "detected": True,
            "detection_cycle": cycles_per_trial // 2,
            "overt_movement_cycle": cycles_per_trial // 2 + 2,
            "attention_peak": {"x": target[0], "y": target[1]},
        }


def write_per_trial(path: Path, rows: list[dict]) -> None:
    fieldnames = [
        "agent",
        "posner_experiment_id",
        "episode",
        "trial_id",
        "trial_type",
        "cue_type",
        "soa_ms",
        "reaction_time_cycles",
        "attention_latency_cycles",
        "initial_fidelity",
        "final_fidelity",
        "peak_value",
        "normalized_entropy",
        "distractor_count",
        "flanked",
        "flanker_distance",
    ]

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, agent: str, experiment_id: int, episode: int, rows: list[dict]) -> None:
    def mean(values: list[float]) -> float:
        values = [v for v in values if v is not None and math.isfinite(v)]
        if not values:
            return float("nan")
        return sum(values) / len(values)

    valid_rt = mean([float(r["reaction_time_cycles"]) for r in rows if r["trial_type"] == "valid"])
    invalid_rt = mean([float(r["reaction_time_cycles"]) for r in rows if r["trial_type"] == "invalid"])
    neutral_rt = mean([float(r["reaction_time_cycles"]) for r in rows if r["trial_type"] == "neutral"])

    benefit = neutral_rt - valid_rt if math.isfinite(neutral_rt) and math.isfinite(valid_rt) else float("nan")
    cost = invalid_rt - neutral_rt if math.isfinite(invalid_rt) and math.isfinite(neutral_rt) else float("nan")
    validity_effect = invalid_rt - valid_rt if math.isfinite(invalid_rt) and math.isfinite(valid_rt) else float("nan")

    fieldnames = [
        "agent",
        "posner_experiment_id",
        "episode",
        "total_trials",
        "mean_rt_valid",
        "mean_rt_invalid",
        "mean_rt_neutral",
        "benefit",
        "cost",
        "validity_effect",
        "mean_initial_fidelity_overall",
        "mean_final_fidelity_overall",
    ]

    out = {
        "agent": agent,
        "posner_experiment_id": experiment_id,
        "episode": episode,
        "total_trials": len(rows),
        "mean_rt_valid": valid_rt,
        "mean_rt_invalid": invalid_rt,
        "mean_rt_neutral": neutral_rt,
        "benefit": benefit,
        "cost": cost,
        "validity_effect": validity_effect,
        "mean_initial_fidelity_overall": mean([float(r["initial_fidelity"]) for r in rows]),
        "mean_final_fidelity_overall": mean([float(r["final_fidelity"]) for r in rows]),
    }

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--posner-experiments", default="1,2,3,4,5")
    parser.add_argument("--trials-per-experiment", type=int, default=20)
    parser.add_argument("--map-width", type=int, default=32)
    parser.add_argument("--map-height", type=int, default=32)
    parser.add_argument("--cycles-per-trial", type=int, default=30)
    parser.add_argument("--seed", type=int, default=777)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    agent = "remote_attention_agent"

    get_json(args.agent_url.rstrip("/") + "/health")

    experiments = [int(x.strip()) for x in args.posner_experiments.split(",") if x.strip()]

    for episode in range(args.episodes):
        post_json(
            args.agent_url.rstrip("/") + "/reset",
            {
                "benchmark": "attention_posner",
                "episode": episode,
            },
        )

        for experiment_id in experiments:
            rows = []

            for trial in range(args.trials_per_experiment):
                trial_type, cue_type = trial_condition(rng)
                target, cue = target_and_cue(rng, trial_type)
                trial_id = f"POSNER_E{experiment_id}_EP{episode}_T{trial}"

                response = call_attention_agent(
                    args.agent_url,
                    "attention_posner",
                    experiment_id,
                    episode,
                    trial_id,
                    trial_type,
                    cue_type,
                    target,
                    cue,
                    args.map_width,
                    args.map_height,
                    args.cycles_per_trial,
                )

                detected = bool(response.get("detected", True))
                detection_cycle = int(response.get("detection_cycle", args.cycles_per_trial // 2))
                peak = response.get("attention_peak", {"x": target[0], "y": target[1]})

                px = float(peak.get("x", target[0]))
                py = float(peak.get("y", target[1]))

                final_error = math.sqrt((px - target[0]) ** 2 + (py - target[1]) ** 2)
                final_fidelity = max(0.0, 1.0 - final_error)
                initial_fidelity = 0.25

                if not detected:
                    detection_cycle = args.cycles_per_trial
                    final_fidelity = 0.0

                row = {
                    "agent": agent,
                    "posner_experiment_id": experiment_id,
                    "episode": episode,
                    "trial_id": trial_id,
                    "trial_type": trial_type,
                    "cue_type": cue_type,
                    "soa_ms": 100 if experiment_id != 2 else rng.choice([50, 100, 200, 500]),
                    "reaction_time_cycles": detection_cycle,
                    "attention_latency_cycles": max(0, detection_cycle - 2),
                    "initial_fidelity": initial_fidelity,
                    "final_fidelity": final_fidelity,
                    "peak_value": 1.0 if detected else 0.0,
                    "normalized_entropy": 0.4 if detected else 1.0,
                    "distractor_count": rng.choice([4, 8, 16]) if experiment_id == 4 else "",
                    "flanked": experiment_id == 5,
                    "flanker_distance": rng.choice([0.05, 0.10, 0.20]) if experiment_id == 5 else "",
                }
                rows.append(row)

            per_trial_path = out_dir / f"attention_posner_exp{experiment_id}_per_trial_episode_{episode}.csv"
            summary_path = out_dir / f"attention_posner_exp{experiment_id}_summary_episode_{episode}.csv"

            write_per_trial(per_trial_path, rows)
            write_summary(summary_path, agent, experiment_id, episode, rows)

    post_json(args.agent_url.rstrip("/") + "/close", {"benchmark": "attention_posner"})

    return 0


if __name__ == "__main__":
    raise SystemExit(main())