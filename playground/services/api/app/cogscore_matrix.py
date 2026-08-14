from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .config import STORAGE_ROOT
from .database import list_runs

DOMAINS = ["sensing", "attention", "motivation", "learning"]
BENCHMARK_TO_DOMAIN = {
    "sensory_buffer": "sensing",
    "attention_posner": "attention",
    "motivation": "motivation",
    "learning": "learning",
}
# Different benchmark bundles may use historical names for the same logical
# architecture. Canonicalize them before grouping runs so one CogScore matrix
# can combine results produced under either spelling.
AGENT_ALIASES = {
    "Substage1_DQN": "Substage1",
    "Substage3_DQN": "Substage3",
}


def _canonical_agent_name(agent_name: str) -> str:
    name = str(agent_name or "").strip()
    return AGENT_ALIASES.get(name, name)


COORDINATE_LABELS = {
    "sensing": [
        "Initial visual fidelity",
        "Short-delay retention",
        "Intermediate-delay retention",
        "Late-delay retention",
        "Temporal-decay robustness",
    ],
    "attention": [
        "Central-cue Posner task",
        "SOA sweep",
        "Peripheral-cue orienting",
        "Visual search",
        "Crowding",
    ],
    "motivation": [
        "Persistence after removal",
        "Drive/curiosity modulation",
        "Goal substitution and detour",
        "Latent learning",
        "Outcome devaluation",
    ],
    "learning": [
        "Visible-object fixation",
        "Moving-object tracking",
        "Open-space top-down tracking",
        "Object permanence",
        "Multiple-object tracking",
    ],
}


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _mean(values: Iterable[float | None]) -> float | None:
    clean = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    return sum(clean) / len(clean) if clean else None


def _resolve_result_path(raw: str) -> Path:
    path = Path(raw)
    if path.exists():
        return path
    parts = path.parts
    if "data" in parts:
        idx = parts.index("data")
        candidate = STORAGE_ROOT.joinpath(*parts[idx + 1 :])
        if candidate.exists():
            return candidate
    # Most production records use /data/... while local imported records may
    # preserve an older absolute playground/data/... prefix.
    for marker in ("results", "uploads"):
        if marker in parts:
            idx = parts.index(marker)
            candidate = STORAGE_ROOT.joinpath(*parts[idx:])
            if candidate.exists():
                return candidate
    return path


def _csv_rows(root: Path, patterns: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(root.rglob(pattern)):
            if path in seen or not path.is_file():
                continue
            seen.add(path)
            try:
                with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
                    rows.extend(dict(row) for row in csv.DictReader(fh))
            except (OSError, csv.Error):
                continue
    return rows


def _score_sensing(root: Path) -> tuple[list[float | None], dict[str, Any]]:
    rows = _csv_rows(root, ["vision_sperling_per_trial_episode_*.csv", "*sperling*summary_episode_*.csv"])
    by_delay: dict[float, list[float]] = defaultdict(list)
    for row in rows:
        delay = _finite(row.get("delay_ms"))
        fidelity = _finite(row.get("fidelity"))
        if fidelity is None:
            fidelity = _finite(row.get("mean_fidelity"))
        if delay is not None and fidelity is not None:
            by_delay[delay].append(_clip01(fidelity))
    delays = sorted(by_delay)
    if not delays:
        return [None] * 5, {"reason": "No readable fidelity-by-delay values were found."}

    # Divide the configured delay schedule into four contiguous portions. This
    # keeps the matrix stable when the benchmark is run with a denser/sparser grid.
    groups: list[list[float]] = [[] for _ in range(4)]
    for index, delay in enumerate(delays):
        bucket = min(3, (index * 4) // len(delays))
        groups[bucket].extend(by_delay[delay])
    first_four = [_mean(group) for group in groups]
    initial = _mean(by_delay[delays[0]])
    late = _mean(by_delay[delays[-1]])
    robustness = None
    if initial is not None and late is not None:
        robustness = _clip01(late / initial) if initial > 1e-12 else _clip01(late)
    scores = [(_clip01(v) if v is not None else None) for v in first_four] + [robustness]
    return scores, {"delays_ms": delays, "source_metric": "visual fidelity", "aggregation": "four contiguous delay groups + final/initial retention ratio"}


def _experiment_id(row: dict[str, str], keys: list[str]) -> int | None:
    for key in keys:
        value = _finite(row.get(key))
        if value is not None:
            ivalue = int(value)
            if 1 <= ivalue <= 5:
                return ivalue
    return None


def _score_attention(root: Path) -> tuple[list[float | None], dict[str, Any]]:
    summary = _csv_rows(root, ["*_summary_episode_*.csv"])
    per_trial = [] if summary else _csv_rows(root, ["*_per_trial_episode_*.csv"])
    values: dict[int, list[float]] = defaultdict(list)

    # Prefer bounded performance quantities already emitted by the benchmark.
    bounded_keys = [
        "mean_final_fidelity_overall", "final_fidelity", "detection_rate",
        "mean_detection_rate", "accuracy", "success_rate",
    ]
    for row in [*summary, *per_trial]:
        exp = _experiment_id(row, ["posner_experiment_id", "attention_experiment_id", "experiment_id", "exp_id"])
        if exp is None:
            continue
        row_metrics = []
        for key in bounded_keys:
            value = _finite(row.get(key))
            if value is not None and 0.0 <= value <= 1.0:
                row_metrics.append(value)
        score = _mean(row_metrics)
        if score is not None:
            values[exp].append(_clip01(score))
    scores = [_mean(values[i]) for i in range(1, 6)]
    return scores, {"source_metrics": bounded_keys, "aggregation": "mean of available bounded performance metrics per experiment"}


def _score_motivation(root: Path) -> tuple[list[float | None], dict[str, Any]]:
    rows = _csv_rows(root, ["*_summary_episode_*.csv"])
    if not rows:
        rows = _csv_rows(root, ["*_per_trial_episode_*.csv"])
    values: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        exp = _experiment_id(row, ["motivation_experiment_id", "active_motivation_experiment_id", "experiment_id", "exp_id"])
        score = _finite(row.get("behavioral_motivation_score"))
        if exp is not None and score is not None:
            values[exp].append(_clip01(score))
    return [_mean(values[i]) for i in range(1, 6)], {"source_metric": "behavioral_motivation_score", "aggregation": "mean by motivation experiment"}


def _read_nrewards(path: Path) -> dict[int, list[float]]:
    by_episode: dict[int, list[float]] = defaultdict(list)
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()[1:]
    except OSError:
        return by_episode
    remove = [
        "Exp number:", "Action num: ", "Battery:", "reward: ", "num_tables:",
        "Curiosity_lv: ", "Curiosity_lv:", "Red: ", "Green: ", "Blue: ",
        "Red:", "Green:", "Blue:", "action:", "mot_value: ", "r_imp: ",
        "g_imp: ", "b_imp: ", "hug_drive: ", "cur_drive: ", " QTables:",
        "cur_a: ", "sur_a: ", "Exp:", "Nact:", "Type:", "cur_a:", "sur_a:",
        "exp_c:", "exp_s:", "dSurV:", "SurV:", "dCurV:", "CurV:", "QTables:",
        "Ri:", "Ri S:", "Ri C:", "G_Reward S:", "G_Reward C:", "G_Reward:",
        " LastAct:", "Act C:", "Act S:", "color1:", "Pos1:", "Pos2:", "fov:",
        "HeadPitch:", "NeckYaw:", "color2:", "fov_y:", "MaxSalValue:", "fov_p:",
        "Field:", "Memory:", ",", "]",
    ]
    for raw in lines:
        line = raw
        for token in remove:
            line = line.replace(token, "")
        cols = line.split()
        if len(cols) < 22:
            continue
        try:
            episode = int(float(cols[1]))
            yaw_col, pitch_col = (19, 20)
            if 22 < len(cols) < 26:
                yaw_col, pitch_col = (21, 22)
            elif len(cols) > 25:
                yaw_col, pitch_col = (23, 24)
            deviation = math.hypot(float(cols[yaw_col]), float(cols[pitch_col]))
        except (ValueError, IndexError):
            continue
        by_episode[episode].append(deviation)
    return by_episode


def _learning_experiment_number(name: str) -> int | None:
    lower = name.lower()
    patterns = [r"(?:exp|experiment|te|test)[_-]?(\d)", r"(?:^|[_-])(\d)(?:$|[_-])"]
    for pattern in patterns:
        match = re.search(pattern, lower)
        if match:
            value = int(match.group(1))
            if 1 <= value <= 5:
                return value
    # Common test labels such as Te4a / Te4b.
    match = re.search(r"te(\d)[ab]?", lower)
    if match and 1 <= int(match.group(1)) <= 5:
        return int(match.group(1))
    return None


def _score_learning(root: Path) -> tuple[list[float | None], dict[str, Any]]:
    by_exp: dict[int, list[float]] = defaultdict(list)
    files = sorted(root.rglob("nrewards.txt"))
    for path in files:
        exp = None
        for parent in [path.parent, *path.parents]:
            if parent == root.parent:
                break
            exp = _learning_experiment_number(parent.name)
            if exp is not None:
                break
        if exp is None:
            continue
        episodes = _read_nrewards(path)
        if not episodes:
            continue
        # Final competence: average deviation over the last 20% of recorded episodes.
        episode_ids = sorted(episodes)
        tail_n = max(1, math.ceil(len(episode_ids) * 0.20))
        deviations = []
        for episode in episode_ids[-tail_n:]:
            deviations.extend(episodes[episode])
        mean_deviation = _mean(deviations)
        if mean_deviation is not None:
            by_exp[exp].append(_clip01(1.0 - mean_deviation / 30.0))
    return [_mean(by_exp[i]) for i in range(1, 6)], {"source_metric": "angular deviation", "normalization": "clip(1 - mean_deviation/30deg, 0, 1)", "aggregation": "mean over final 20% of episodes and available runs"}


SCORERS = {
    "sensory_buffer": _score_sensing,
    "attention_posner": _score_attention,
    "motivation": _score_motivation,
    "learning": _score_learning,
}


def _latest_runs_by_agent() -> dict[str, dict[str, dict[str, Any]]]:
    latest: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for run in list_runs():
        benchmark = str(run.get("benchmark") or "")
        source_agent = str(run.get("agent_name") or "").strip()
        agent = _canonical_agent_name(source_agent)
        if benchmark not in SCORERS or not agent:
            continue
        current = latest[agent].get(benchmark)
        stamp = str(run.get("created_at") or run.get("run_date") or "")
        current_stamp = str(current.get("created_at") or current.get("run_date") or "") if current else ""
        if current is None or stamp > current_stamp:
            normalized_run = dict(run)
            normalized_run["source_agent_name"] = source_agent
            normalized_run["canonical_agent_name"] = agent
            latest[agent][benchmark] = normalized_run
    return dict(latest)


def compute_matrices() -> dict[str, Any]:
    agents: list[dict[str, Any]] = []
    for agent_name, benchmark_runs in sorted(_latest_runs_by_agent().items()):
        matrix: dict[str, list[float | None]] = {domain: [None] * 5 for domain in DOMAINS}
        provenance: dict[str, Any] = {}
        for benchmark, run in benchmark_runs.items():
            domain = BENCHMARK_TO_DOMAIN[benchmark]
            root = _resolve_result_path(str(run.get("benchmark_out_path") or run.get("storage_path") or ""))
            if root.is_file() and root.suffix.lower() == ".zip":
                provenance[domain] = {
                    "run_id": run.get("id"),
                    "source_agent_name": run.get("source_agent_name") or run.get("agent_name"),
                    "canonical_agent_name": agent_name,
                    "path": str(root),
                    "warning": "ZIP-only result; extract/import it before matrix computation.",
                }
                continue
            if not root.is_dir():
                provenance[domain] = {
                    "run_id": run.get("id"),
                    "source_agent_name": run.get("source_agent_name") or run.get("agent_name"),
                    "canonical_agent_name": agent_name,
                    "path": str(root),
                    "warning": "Result directory is unavailable.",
                }
                continue
            scores, details = SCORERS[benchmark](root)
            matrix[domain] = [round(v, 6) if v is not None else None for v in scores]
            provenance[domain] = {
                "run_id": run.get("id"),
                "benchmark": benchmark,
                "source_agent_name": run.get("source_agent_name") or run.get("agent_name"),
                "canonical_agent_name": agent_name,
                "path": str(root),
                **details,
            }
        observed = [v for row in matrix.values() for v in row if v is not None]
        agents.append({
            "agent_name": agent_name,
            "matrix": matrix,
            "coverage": len(observed) / 20.0,
            "observed_cells": len(observed),
            "mean_observed_score": _mean(observed),
            "provenance": provenance,
        })
    return {"domains": DOMAINS, "coordinate_labels": COORDINATE_LABELS, "agents": agents}
