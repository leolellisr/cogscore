#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
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


def safe_act(agent_url: str, payload: dict) -> dict:
    try:
        return post_json(agent_url.rstrip("/") + "/motivation/act", payload)
    except Exception:
        return {
            "action": "INTERACT",
            "object": payload["objects"][0]["id"],
            "confidence": 0.5,
            "debug": {"fallback": True},
        }


def action_code(action: str) -> int:
    action = action.upper()
    if action == "LOOK":
        return 1
    if action == "INTERACT":
        return 2
    if action == "STOP":
        return 3
    return 0


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-url", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--motivation-experiments", default="1,2,3,4,5")
    parser.add_argument("--trials-per-experiment", type=int, default=20)
    parser.add_argument("--cycles-per-trial", type=int, default=30)
    parser.add_argument("--seed", type=int, default=777)
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(args.seed)
    agent = "remote_motivation_agent"
    experiments = [int(x.strip()) for x in args.motivation_experiments.split(",") if x.strip()]

    get_json(args.agent_url.rstrip("/") + "/health")

    all_trials_rows = []

    for episode in range(args.episodes):
        post_json(
            args.agent_url.rstrip("/") + "/reset",
            {"benchmark": "motivation", "episode": episode},
        )

        for exp_id in experiments:
            per_trial_rows = []

            for trial in range(args.trials_per_experiment):
                trial_id = f"MOT_E{exp_id}_T{trial + 1}"

                objects = [
                    {"id": 1, "label": "blue_sphere", "role": "resource"},
                    {"id": 2, "label": "red_cube", "role": "curiosity"},
                    {"id": 3, "label": "green_cylinder", "role": "alternative"},
                    {"id": 4, "label": "neutral_object", "role": "control"},
                ]

                payload = {
                    "benchmark": "motivation",
                    "experiment_id": exp_id,
                    "episode": episode,
                    "trial_id": trial_id,
                    "phase": "trial",
                    "objects": objects,
                    "signals": {
                        "reward_available": exp_id in [2, 4],
                        "target_removed": exp_id == 1 and trial > args.trials_per_experiment // 2,
                        "outcome_devalued": exp_id == 5 and trial > args.trials_per_experiment // 2,
                        "blocked_path": exp_id == 3,
                    },
                }

                response = safe_act(args.agent_url, payload)

                chosen_object = int(response.get("object", 0) or 0)
                chosen_action = str(response.get("action", "INTERACT")).upper()

                persistence_selectivity = 1.0 if exp_id == 1 and chosen_object == 1 else 0.0
                resource_choice = 1 if chosen_object == 1 else 0
                novelty_choice = 1 if chosen_object == 2 else 0
                control_choice = 1 if chosen_object == 4 else 0
                substitution_success = 1 if exp_id == 3 and chosen_object in [2, 3] else 0
                devaluation_sensitivity = 1.0 if exp_id == 5 and chosen_object != 1 else 0.0
                response_suppression = 1.0 if chosen_action == "STOP" else 0.0

                behavioral_score = (
                    persistence_selectivity
                    + resource_choice
                    + novelty_choice
                    + substitution_success
                    + devaluation_sensitivity
                    + response_suppression
                ) / 6.0

                row = {
                    "agent": agent,
                    "motivation_experiment_id": exp_id,
                    "episode": episode,
                    "trial_id": trial_id,
                    "condition": f"experiment_{exp_id}",
                    "first_response_object": chosen_object,
                    "first_response_action": chosen_action,
                    "first_response_action_code": action_code(chosen_action),
                    "persistence_selectivity": persistence_selectivity,
                    "resource_choice": resource_choice,
                    "novelty_choice": novelty_choice,
                    "control_choice": control_choice,
                    "substitution_success": substitution_success,
                    "devaluation_sensitivity": devaluation_sensitivity,
                    "response_suppression": response_suppression,
                    "behavioral_motivation_score": behavioral_score,
                }

                per_trial_rows.append(row)
                all_trials_rows.append(row)

            per_trial_path = out_dir / f"{agent}_per_trial_episode_{episode}_exp_{exp_id}.csv"
            write_csv(
                per_trial_path,
                list(per_trial_rows[0].keys()),
                per_trial_rows,
            )

            summary = {
                "agent": agent,
                "motivation_experiment_id": exp_id,
                "episode": episode,
                "total_trials": len(per_trial_rows),
                "behavioral_motivation_score": sum(r["behavioral_motivation_score"] for r in per_trial_rows) / len(per_trial_rows),
                "mean_persistence_selectivity": sum(r["persistence_selectivity"] for r in per_trial_rows) / len(per_trial_rows),
                "mean_resource_choice": sum(r["resource_choice"] for r in per_trial_rows) / len(per_trial_rows),
                "mean_novelty_choice": sum(r["novelty_choice"] for r in per_trial_rows) / len(per_trial_rows),
                "mean_substitution_success": sum(r["substitution_success"] for r in per_trial_rows) / len(per_trial_rows),
                "mean_devaluation_sensitivity": sum(r["devaluation_sensitivity"] for r in per_trial_rows) / len(per_trial_rows),
                "mean_response_suppression": sum(r["response_suppression"] for r in per_trial_rows) / len(per_trial_rows),
            }

            write_csv(
                out_dir / f"{agent}_summary_episode_{episode}_exp_{exp_id}.csv",
                list(summary.keys()),
                [summary],
            )

    java_rows = [
        {
            "agent": row["agent"],
            "active_motivation_experiment_id": row["motivation_experiment_id"],
            "episode": row["episode"],
            "trial_id": row["trial_id"],
            "phase": "trial",
            "trace_action_count": 1,
            "first_response_action_code": row["first_response_action_code"],
        }
        for row in all_trials_rows
    ]

    write_csv(
        out_dir / f"{agent}_java_steps.csv",
        list(java_rows[0].keys()),
        java_rows,
    )

    with (out_dir / "motivation_marta_trials.txt").open("w", encoding="utf-8") as f:
        f.write("episode trial exp_id trial_id first_response_object first_response_action behavioral_motivation_score\n")
        for i, row in enumerate(all_trials_rows):
            f.write(
                f"{row['episode']} {i} {row['motivation_experiment_id']} "
                f"{row['trial_id']} {row['first_response_object']} "
                f"{row['first_response_action']} {row['behavioral_motivation_score']}\n"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())