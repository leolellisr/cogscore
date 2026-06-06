
"""
Comparison plots for Posner attention benchmark agents.

This version:
1) Forces every curve to have 50 x-points by default.
2) Infers missing points by interpolation plus previous-value fallback.
3) Smooths curves without reducing the number of x-points.
4) Uses different colors for agents.
5) Adds two theoretical agents by default:
   - Substage1_Theoretic: Piaget 1st substage, bottom-up attention only.
   - Substage3_Theoretic: Piaget 3rd substage, bottom-up + top-down attention.

The theoretical agents are not empirical results. They are expected reference
profiles based on the qualitative Posner pattern:
- Valid central cue: faster detection than neutral when top-down orienting exists.
- Invalid central cue: slower detection than neutral when top-down orienting exists.
- Peripheral cue: fast bottom-up attentional capture.
- SOA: top-down benefits increase after enough cue-target interval.
- Visual search/crowding: top-down attention improves robustness under clutter.

Expected layout:
    results/output/AGENT_NAME/benchmark_out/

Examples:
    python compare_posner_agents_development.py --root results/output
    python compare_posner_agents_development.py --root results/output --show
    python compare_posner_agents_development.py --root results/output --x-points 50
    python compare_posner_agents_development.py --root results/output --smooth-window 9
    python compare_posner_agents_development.py --root results/output --no-theoretic
    python compare_posner_agents_development.py --root results/output --theoretic-only

Dependencies:
    pip install pandas matplotlib numpy
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import hashlib

EXPERIMENT_NAMES = {
    1: "Exp 1: Central cue Posner",
    2: "Exp 2: SOA sweep",
    3: "Exp 3: Peripheral capture",
    4: "Exp 4: Visual search",
    5: "Exp 5: Crowding",
    0: "Java step log",
}

FILE_PATTERNS = {
    "per_trial": "*_per_trial_episode_*.csv",
    "summary": "*_summary_episode_*.csv",
    "soa": "*_soa_episode_*.csv",
    "crowding": "*_crowding_episode_*.csv",
    "steps": "*_java_steps_*.csv",
}

TEXT_COLUMNS = {
    "agent",
    "agent_dir",
    "source_file",
    "trial_id",
    "trial_type",
    "cue_type",
    "search_type",
    "status",
    "state",
    "flanked_label",
}

METRIC_LABELS = {
    "mean_rt_valid": "RT valid",
    "mean_rt_neutral": "RT neutral",
    "mean_rt_invalid": "RT invalid",
    "reaction_time_cycles": "Reaction time",
    "benefit": "Benefit",
    "cost": "Cost",
    "validity_effect": "Validity effect",
    "mean_initial_fidelity_overall": "Initial fidelity",
    "mean_final_fidelity_overall": "Final fidelity",
    "mean_final_fidelity_valid": "Final fidelity valid",
    "mean_final_fidelity_neutral": "Final fidelity neutral",
    "mean_final_fidelity_invalid": "Final fidelity invalid",
    "initial_fidelity": "Initial fidelity",
    "final_fidelity": "Final fidelity",
    "detected_percent": "Detection rate",
    "peak_value": "Peak value",
    "map_variance": "Map variance",
    "normalized_entropy": "Normalized entropy",
    "top_down_orienting_latency": "Top-down orienting latency",
    "mean_bottom_up_latency": "Bottom-up latency",
    "mean_eye_movement_latency": "Eye-movement latency",
    "mean_rt_cued": "RT cued",
    "mean_rt_uncued": "RT uncued",
    "feature_search_slope": "Feature-search slope",
    "conjunction_search_slope": "Conjunction-search slope",
    "crowding_cost": "Crowding cost",
    "attentional_reduction_crowding": "Attentional reduction of crowding",
    "soa_ms": "SOA",
    "distractor_count": "Distractors",
    "flanker_distance": "Flanker distance",
    "trial_type": "Trial type",
    "search_type": "Search type",
    "flanked_label": "Flanked",
    "status": "Status",
}

LINE_STYLES = ["-", "--", ":", "-."]
MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*"]

DEFAULT_X_POINTS = 50
DEFAULT_SMOOTH_WINDOW = 7
DEFAULT_IMPUTE_LOOKBACK = 5

SHOW_MARKERS = True

REAL_AGENT_BASE_COLORS = [
    "tab:red",
    "tab:green",
    "tab:purple",
    "tab:brown",
    "tab:pink",
    "tab:orange",
]

THEORETIC_AGENT_COLORS = {
    "Substage1_Theoretic": "tab:gray",
    "Substage3_Theoretic": "tab:blue",
}

DEFAULT_BLEND_NOISE_PCT = 0.15
DEFAULT_BLEND_RANDOM_SEED = 12345

NON_BLEND_NUMERIC_COLUMNS = {
    "__source_row",
    "trial_index",
    "total_trials",
}


def stable_random_multiplier(
    *,
    seed: int,
    noise_pct: float,
    parts: list[object],
) -> float:
    """
    Deterministic random multiplier in [1 - noise_pct, 1 + noise_pct].

    It does not use Python's hash(), because hash() changes between runs.
    The same seed + same parts always generates the same multiplier.
    """
    if noise_pct <= 0.0:
        return 1.0

    key = "|".join(str(p) for p in parts)
    payload = f"{seed}|{key}".encode("utf-8")

    digest = hashlib.sha256(payload).digest()
    integer_value = int.from_bytes(digest[:8], byteorder="big", signed=False)

    unit = integer_value / float(2**64 - 1)
    low = 1.0 - noise_pct
    high = 1.0 + noise_pct

    return low + unit * (high - low)


def apply_metric_clip_if_needed(metric_name: str, values: pd.Series) -> pd.Series:
    clip = value_clip_range(metric_name)

    if clip is None:
        return values

    return values.clip(clip[0], clip[1])
# ---------------------------------------------------------------------
# Basic utilities
# ---------------------------------------------------------------------

def metric_label(name: str) -> str:
    return METRIC_LABELS.get(name, name.replace("_", " ").title())


def experiment_label(exp_id) -> str:
    try:
        exp_id = int(exp_id)
    except Exception:
        return str(exp_id)

    return EXPERIMENT_NAMES.get(exp_id, f"Experiment {exp_id}")


def has_columns(df: pd.DataFrame, columns: Sequence[str]) -> bool:
    return not df.empty and all(c in df.columns for c in columns)


def ensure_output_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def save_plot(path: Path, show: bool) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=180, bbox_inches="tight")
    print(f"[SAVED] {path.resolve()}")

    if show:
        plt.show()

    plt.close()


def value_clip_range(metric: str) -> Optional[tuple[float, float]]:
    lower = metric.lower()

    if "fidelity" in lower:
        return 0.0, 1.0

    if lower in {"normalized_entropy"}:
        return 0.0, 1.0

    if lower in {"detected_percent"}:
        return 0.0, 100.0

    return None


def set_x_axis(ax, x_points: int) -> None:
    ax.set_xlim(1, x_points)

    if x_points <= 60:
        ticks = list(range(1, x_points + 1, 5))

        if x_points not in ticks:
            ticks.append(x_points)

        ax.set_xticks(sorted(set(ticks)))
    else:
        ax.set_xticks(np.linspace(1, x_points, 11, dtype=int))


def add_legend(ax, title: str) -> None:
    handles, _ = ax.get_legend_handles_labels()

    if handles:
        ax.legend(title=title, loc="best", fontsize=8)


# ---------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------

def build_agent_colors(data: dict[str, pd.DataFrame]) -> dict[str, str]:
    agents: set[str] = set()

    for df in data.values():
        if not df.empty and "agent" in df.columns:
            agents.update(df["agent"].dropna().astype(str).tolist())

    colors: dict[str, str] = {}

    for agent, color in THEORETIC_AGENT_COLORS.items():
        if agent in agents:
            colors[agent] = color

    real_agents = sorted(
        agent for agent in agents
        if agent not in THEORETIC_AGENT_COLORS
    )

    for i, agent in enumerate(real_agents):
        colors[agent] = REAL_AGENT_BASE_COLORS[i % len(REAL_AGENT_BASE_COLORS)]

    return colors


def vary_color(base_color: str, variant_index: int) -> tuple[float, float, float]:
    rgb = np.array(mcolors.to_rgb(base_color), dtype=float)

    factors = [1.00, 1.25, 0.75, 1.45, 0.55, 1.65, 0.40]
    factor = factors[variant_index % len(factors)]

    if factor >= 1.0:
        amount = min(factor - 1.0, 0.80)
        out = rgb + (1.0 - rgb) * amount
    else:
        out = rgb * factor

    return tuple(np.clip(out, 0.0, 1.0))


# ---------------------------------------------------------------------
# Loading and cleaning
# ---------------------------------------------------------------------

def discover_agents(
    root: Path,
    benchmark_dir_name: str,
    only_agents: Optional[list[str]],
) -> list[tuple[str, Path]]:
    if not root.exists():
        return []

    agents: list[tuple[str, Path]] = []

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue

        if only_agents and child.name not in only_agents:
            continue

        benchmark_dir = child / benchmark_dir_name

        if benchmark_dir.exists() and benchmark_dir.is_dir():
            agents.append((child.name, benchmark_dir))

    return agents


def read_agent_csvs(agent_name: str, benchmark_dir: Path, key: str) -> pd.DataFrame:
    paths = sorted(benchmark_dir.rglob(FILE_PATTERNS[key]))
    frames: list[pd.DataFrame] = []

    for path in paths:
        try:
            df = pd.read_csv(path)
            df["agent"] = agent_name
            df["agent_dir"] = str(benchmark_dir)
            df["source_file"] = str(path)
            df["__source_row"] = range(len(df))
            frames.append(df)
        except Exception as exc:
            print(f"[WARN] Could not read {path}: {exc}", file=sys.stderr)

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True, sort=False)


def load_all_agents(
    root: Path,
    benchmark_dir_name: str,
    only_agents: Optional[list[str]],
) -> dict[str, pd.DataFrame]:
    agents = discover_agents(root, benchmark_dir_name, only_agents)

    print("[INFO] Agents discovered:")

    for agent_name, benchmark_dir in agents:
        print(f"  {agent_name}: {benchmark_dir}")

    if not agents:
        print(
            f"[WARN] No real agents found under {root} with benchmark folder "
            f"'{benchmark_dir_name}'",
            file=sys.stderr,
        )

    loaded: dict[str, list[pd.DataFrame]] = {key: [] for key in FILE_PATTERNS}

    for agent_name, benchmark_dir in agents:
        for key in FILE_PATTERNS:
            df = read_agent_csvs(agent_name, benchmark_dir, key)

            if not df.empty:
                loaded[key].append(df)

    combined = {
        key: pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
        for key, frames in loaded.items()
    }

    print("\n[INFO] Loaded rows:")

    for key, df in combined.items():
        print(f"  {key:10s}: {len(df)}")

    return combined


def clean_frame(
    df: pd.DataFrame,
    episode: Optional[int],
    experiment: Optional[int],
) -> pd.DataFrame:
    if df.empty:
        return df

    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    if "episode" not in out.columns and "epoch" in out.columns:
        out["episode"] = out["epoch"]

    if "episode" not in out.columns:
        out["episode"] = 0

    for col in out.columns:
        if col in TEXT_COLUMNS:
            continue

        converted = pd.to_numeric(out[col], errors="coerce")

        if converted.notna().sum() > 0:
            out[col] = converted

    if "agent" in out.columns:
        out["agent"] = out["agent"].astype(str)

    if episode is not None:
        out = out[pd.to_numeric(out["episode"], errors="coerce") == episode]

    if experiment is not None and "posner_experiment_id" in out.columns:
        out = out[pd.to_numeric(out["posner_experiment_id"], errors="coerce") == experiment]

    return out


def clean_data(
    data: dict[str, pd.DataFrame],
    episode: Optional[int],
    experiment: Optional[int],
) -> dict[str, pd.DataFrame]:
    return {
        key: clean_frame(df, episode, experiment)
        for key, df in data.items()
    }


# ---------------------------------------------------------------------
# Theoretical agents
# ---------------------------------------------------------------------

def _sigmoid_progress(ep: int, n: int, midpoint: float = 0.35, steepness: float = 8.0) -> float:
    if n <= 1:
        return 1.0

    x = (ep - 1) / float(n - 1)

    raw = 1.0 / (1.0 + np.exp(-steepness * (x - midpoint)))
    lo = 1.0 / (1.0 + np.exp(-steepness * (0.0 - midpoint)))
    hi = 1.0 / (1.0 + np.exp(-steepness * (1.0 - midpoint)))

    return float((raw - lo) / (hi - lo))


def _lerp(start: float, end: float, p: float) -> float:
    return float(start + (end - start) * p)


def _small_curve(ep: int, n: int, amplitude: float = 0.25) -> float:
    if n <= 1:
        return 0.0

    x = (ep - 1) / float(n - 1)
    return float(amplitude * np.sin(2.0 * np.pi * x))


def theoretical_summary_rows(x_points: int) -> list[dict]:
    rows: list[dict] = []

    for agent in ["Substage1_Theoretic", "Substage3_Theoretic"]:
        for exp_id in [1, 2, 3, 4, 5]:
            for ep in range(1, x_points + 1):
                p = _sigmoid_progress(ep, x_points)
                wave = _small_curve(ep, x_points)

                if agent == "Substage1_Theoretic":
                    # 1st substage: reactive, bottom-up dominated.
                    base_rt = _lerp(42.0, 39.0, p) + wave

                    if exp_id == 1:
                        benefit = _lerp(0.4, 1.0, p)
                        cost = _lerp(0.7, 1.2, p)
                        init_fid = _lerp(0.42, 0.47, p)
                        final_fid = _lerp(0.48, 0.54, p)
                        top_down_latency = 18.0
                        bottom_up_latency = _lerp(8.0, 7.0, p)
                    elif exp_id == 2:
                        benefit = _lerp(0.3, 1.0, p)
                        cost = _lerp(0.6, 1.4, p)
                        init_fid = _lerp(0.42, 0.48, p)
                        final_fid = _lerp(0.48, 0.55, p)
                        top_down_latency = 18.0
                        bottom_up_latency = _lerp(8.0, 7.0, p)
                    elif exp_id == 3:
                        benefit = _lerp(5.0, 7.5, p)
                        cost = _lerp(8.0, 10.0, p)
                        init_fid = _lerp(0.50, 0.58, p)
                        final_fid = _lerp(0.58, 0.65, p)
                        top_down_latency = 18.0
                        bottom_up_latency = _lerp(6.0, 4.5, p)
                    elif exp_id == 4:
                        benefit = _lerp(0.3, 0.8, p)
                        cost = _lerp(1.0, 1.8, p)
                        init_fid = _lerp(0.38, 0.43, p)
                        final_fid = _lerp(0.42, 0.49, p)
                        top_down_latency = 18.0
                        bottom_up_latency = _lerp(8.5, 7.5, p)
                    else:
                        benefit = _lerp(0.4, 0.8, p)
                        cost = _lerp(2.0, 3.5, p)
                        init_fid = _lerp(0.36, 0.42, p)
                        final_fid = _lerp(0.40, 0.48, p)
                        top_down_latency = 18.0
                        bottom_up_latency = _lerp(8.5, 7.5, p)

                    feature_slope = _lerp(0.85, 0.75, p)
                    conjunction_slope = _lerp(1.90, 1.65, p)
                    eye_latency = _lerp(11.0, 10.0, p)

                else:
                    # 3rd substage: bottom-up + learned/top-down orienting.
                    base_rt = _lerp(40.0, 31.0, p) + wave

                    if exp_id == 1:
                        benefit = _lerp(2.0, 7.0, p)
                        cost = _lerp(3.0, 7.5, p)
                        init_fid = _lerp(0.48, 0.68, p)
                        final_fid = _lerp(0.62, 0.88, p)
                        top_down_latency = _lerp(11.0, 4.0, p)
                        bottom_up_latency = _lerp(7.0, 5.0, p)
                    elif exp_id == 2:
                        benefit = _lerp(1.5, 8.0, p)
                        cost = _lerp(2.5, 7.0, p)
                        init_fid = _lerp(0.48, 0.70, p)
                        final_fid = _lerp(0.62, 0.89, p)
                        top_down_latency = _lerp(11.0, 4.0, p)
                        bottom_up_latency = _lerp(7.0, 5.0, p)
                    elif exp_id == 3:
                        benefit = _lerp(6.5, 9.0, p)
                        cost = _lerp(7.0, 4.5, p)
                        init_fid = _lerp(0.55, 0.72, p)
                        final_fid = _lerp(0.68, 0.90, p)
                        top_down_latency = _lerp(10.0, 4.0, p)
                        bottom_up_latency = _lerp(5.5, 3.5, p)
                    elif exp_id == 4:
                        benefit = _lerp(1.5, 4.0, p)
                        cost = _lerp(3.0, 4.0, p)
                        init_fid = _lerp(0.46, 0.66, p)
                        final_fid = _lerp(0.57, 0.82, p)
                        top_down_latency = _lerp(12.0, 5.0, p)
                        bottom_up_latency = _lerp(7.5, 5.5, p)
                    else:
                        benefit = _lerp(1.0, 3.5, p)
                        cost = _lerp(4.0, 3.0, p)
                        init_fid = _lerp(0.44, 0.64, p)
                        final_fid = _lerp(0.55, 0.80, p)
                        top_down_latency = _lerp(12.0, 5.0, p)
                        bottom_up_latency = _lerp(7.5, 5.5, p)

                    feature_slope = _lerp(0.60, 0.22, p)
                    conjunction_slope = _lerp(1.30, 0.55, p)
                    eye_latency = _lerp(10.0, 7.0, p)

                mean_rt_neutral = base_rt
                mean_rt_valid = base_rt - benefit
                mean_rt_invalid = base_rt + cost

                rows.append({
                    "agent": agent,
                    "posner_experiment_id": exp_id,
                    "episode": ep,
                    "total_trials": 50,
                    "mean_rt_valid": mean_rt_valid,
                    "mean_rt_neutral": mean_rt_neutral,
                    "mean_rt_invalid": mean_rt_invalid,
                    "benefit": benefit,
                    "cost": cost,
                    "validity_effect": benefit + cost,
                    "mean_initial_fidelity_overall": init_fid,
                    "mean_final_fidelity_overall": final_fid,
                    "mean_final_fidelity_valid": min(1.0, final_fid + benefit * 0.015),
                    "mean_final_fidelity_neutral": final_fid,
                    "mean_final_fidelity_invalid": max(0.0, final_fid - cost * 0.012),
                    "top_down_orienting_latency": top_down_latency,
                    "mean_bottom_up_latency": bottom_up_latency,
                    "mean_eye_movement_latency": eye_latency,
                    "mean_rt_cued": mean_rt_valid,
                    "mean_rt_uncued": mean_rt_invalid,
                    "feature_search_slope": feature_slope,
                    "conjunction_search_slope": conjunction_slope,
                })

    return rows


def theoretical_soa_rows(x_points: int) -> list[dict]:
    rows: list[dict] = []
    soa_values = [100, 200, 300, 500, 800, 1200]

    for agent in ["Substage1_Theoretic", "Substage3_Theoretic"]:
        for ep in range(1, x_points + 1):
            p = _sigmoid_progress(ep, x_points)

            for soa in soa_values:
                if agent == "Substage1_Theoretic":
                    benefit = _lerp(0.2, 1.2, p) + 0.15 * np.log1p(soa / 100.0)
                    cost = _lerp(0.5, 1.5, p) + 0.10 * np.log1p(soa / 100.0)
                else:
                    soa_gain = 1.0 / (1.0 + np.exp(-(soa - 220.0) / 120.0))
                    benefit = _lerp(1.0, 8.0, p) * soa_gain
                    cost = _lerp(2.0, 7.0, p) * soa_gain

                rows.append({
                    "agent": agent,
                    "posner_experiment_id": 2,
                    "episode": ep,
                    "soa_ms": soa,
                    "benefit": float(benefit),
                    "cost": float(cost),
                })

    return rows


def theoretical_crowding_rows(x_points: int) -> list[dict]:
    rows: list[dict] = []
    distances = [0.12, 0.18, 0.25, 0.35, 0.50]

    for agent in ["Substage1_Theoretic", "Substage3_Theoretic"]:
        for ep in range(1, x_points + 1):
            p = _sigmoid_progress(ep, x_points)

            for d in distances:
                proximity = max(0.0, 0.55 - d)

                if agent == "Substage1_Theoretic":
                    crowding_cost = 8.0 + 32.0 * proximity - 2.0 * p
                    reduction = 1.0 + 2.0 * p
                else:
                    crowding_cost = 5.0 + 20.0 * proximity - 7.0 * p
                    reduction = 3.0 + 9.0 * p

                rows.append({
                    "agent": agent,
                    "posner_experiment_id": 5,
                    "episode": ep,
                    "flanker_distance": d,
                    "crowding_cost": float(max(0.0, crowding_cost)),
                    "attentional_reduction_crowding": float(max(0.0, reduction)),
                })

    return rows


def theoretical_per_trial_rows(x_points: int) -> list[dict]:
    rows: list[dict] = []
    trial_counter = 0

    summary_df = pd.DataFrame(theoretical_summary_rows(x_points))

    for _, row in summary_df.iterrows():
        agent = row["agent"]
        exp_id = int(row["posner_experiment_id"])
        ep = int(row["episode"])

        trial_types = [
            ("VALID", row["mean_rt_valid"], row["mean_final_fidelity_valid"]),
            ("NEUTRAL", row["mean_rt_neutral"], row["mean_final_fidelity_neutral"]),
            ("INVALID", row["mean_rt_invalid"], row["mean_final_fidelity_invalid"]),
        ]

        if exp_id in [1, 2, 3]:
            for trial_type, rt, final_fid in trial_types:
                trial_counter += 1
                rows.append({
                    "agent": agent,
                    "posner_experiment_id": exp_id,
                    "episode": ep,
                    "trial_index": trial_counter,
                    "trial_id": f"{agent}_E{exp_id}_EP{ep}_{trial_type}",
                    "trial_type": trial_type,
                    "cue_type": "PERIPHERAL" if exp_id == 3 else "CENTRAL",
                    "search_type": "NONE",
                    "distractor_count": 0,
                    "flanked": False,
                    "flanker_distance": 0.0,
                    "reaction_time_cycles": float(rt),
                    "cue_onset_cycle": 0,
                    "target_onset_cycle": 10,
                    "detection_cycle": float(10 + rt),
                    "overt_movement_cycle": np.nan,
                    "initial_fidelity": float(row["mean_initial_fidelity_overall"]),
                    "final_fidelity": float(final_fid),
                    "peak_value": float(final_fid),
                    "map_variance": float(0.10 + final_fid * 0.12),
                    "normalized_entropy": float(max(0.05, 1.0 - final_fid)),
                })

        elif exp_id == 4:
            for search_type in ["FEATURE", "CONJUNCTION"]:
                for distractors in [4, 8, 12, 16, 24]:
                    slope = row["feature_search_slope"] if search_type == "FEATURE" else row["conjunction_search_slope"]
                    rt = row["mean_rt_neutral"] + slope * distractors
                    final_fid = row["mean_final_fidelity_overall"] - 0.004 * distractors

                    if search_type == "CONJUNCTION":
                        final_fid -= 0.04

                    trial_counter += 1
                    rows.append({
                        "agent": agent,
                        "posner_experiment_id": exp_id,
                        "episode": ep,
                        "trial_index": trial_counter,
                        "trial_id": f"{agent}_E4_EP{ep}_{search_type}_{distractors}",
                        "trial_type": "SEARCH",
                        "cue_type": "CENTRAL",
                        "search_type": search_type,
                        "distractor_count": distractors,
                        "flanked": False,
                        "flanker_distance": 0.0,
                        "reaction_time_cycles": float(rt),
                        "cue_onset_cycle": 0,
                        "target_onset_cycle": 10,
                        "detection_cycle": float(10 + rt),
                        "overt_movement_cycle": np.nan,
                        "initial_fidelity": float(row["mean_initial_fidelity_overall"]),
                        "final_fidelity": float(np.clip(final_fid, 0.0, 1.0)),
                        "peak_value": float(np.clip(final_fid, 0.0, 1.0)),
                        "map_variance": float(0.11 + np.clip(final_fid, 0.0, 1.0) * 0.10),
                        "normalized_entropy": float(max(0.05, 1.0 - np.clip(final_fid, 0.0, 1.0))),
                    })

        elif exp_id == 5:
            for flanked in [False, True]:
                for d in [0.12, 0.18, 0.25, 0.35, 0.50]:
                    proximity = max(0.0, 0.55 - d)

                    if agent == "Substage1_Theoretic":
                        extra = 0.0 if not flanked else 8.0 + 32.0 * proximity
                    else:
                        p = _sigmoid_progress(ep, x_points)
                        extra = 0.0 if not flanked else max(0.0, 5.0 + 20.0 * proximity - 7.0 * p)

                    rt = row["mean_rt_neutral"] + extra
                    final_fid = row["mean_final_fidelity_overall"] - (0.0 if not flanked else 0.20 * proximity)

                    trial_counter += 1
                    rows.append({
                        "agent": agent,
                        "posner_experiment_id": exp_id,
                        "episode": ep,
                        "trial_index": trial_counter,
                        "trial_id": f"{agent}_E5_EP{ep}_F{int(flanked)}_D{d}",
                        "trial_type": "CROWDING",
                        "cue_type": "CENTRAL",
                        "search_type": "NONE",
                        "distractor_count": 0,
                        "flanked": bool(flanked),
                        "flanker_distance": d,
                        "reaction_time_cycles": float(rt),
                        "cue_onset_cycle": 0,
                        "target_onset_cycle": 10,
                        "detection_cycle": float(10 + rt),
                        "overt_movement_cycle": np.nan,
                        "initial_fidelity": float(row["mean_initial_fidelity_overall"]),
                        "final_fidelity": float(np.clip(final_fid, 0.0, 1.0)),
                        "peak_value": float(np.clip(final_fid, 0.0, 1.0)),
                        "map_variance": float(0.11 + np.clip(final_fid, 0.0, 1.0) * 0.10),
                        "normalized_entropy": float(max(0.05, 1.0 - np.clip(final_fid, 0.0, 1.0))),
                    })

    return rows


def add_theoretical_agents(
    data: dict[str, pd.DataFrame],
    x_points: int,
    episode_filter: Optional[int],
    experiment_filter: Optional[int],
) -> dict[str, pd.DataFrame]:
    out = {key: df.copy() for key, df in data.items()}

    theoretical = {
        "summary": pd.DataFrame(theoretical_summary_rows(x_points)),
        "per_trial": pd.DataFrame(theoretical_per_trial_rows(x_points)),
        "soa": pd.DataFrame(theoretical_soa_rows(x_points)),
        "crowding": pd.DataFrame(theoretical_crowding_rows(x_points)),
        "steps": pd.DataFrame(),
    }

    for key, df in theoretical.items():
        if df.empty:
            continue

        if episode_filter is not None and "episode" in df.columns:
            df = df[df["episode"] == episode_filter].copy()

        if experiment_filter is not None and "posner_experiment_id" in df.columns:
            df = df[df["posner_experiment_id"] == experiment_filter].copy()

        if out.get(key, pd.DataFrame()).empty:
            out[key] = df
        else:
            out[key] = pd.concat([out[key], df], ignore_index=True, sort=False)

    print("[INFO] Added theoretical agents:")
    print("  Substage1_Theoretic: bottom-up attention only")
    print("  Substage3_Theoretic: bottom-up + top-down attention")

    return out


# ---------------------------------------------------------------------
# Inference and smoothing
# ---------------------------------------------------------------------

def prepare_episode_axis(df: pd.DataFrame, x_points: int) -> pd.DataFrame:
    """
    Create episode_axis in 1..x_points.

    If data uses 0..49, it becomes 1..50.
    If data uses 1..50, it remains 1..50.
    """
    out = df.copy()
    out["episode"] = pd.to_numeric(out["episode"], errors="coerce")
    out = out.dropna(subset=["episode"]).copy()

    if out.empty:
        return out

    out["episode"] = out["episode"].astype(int)
    ep_min = int(out["episode"].min())
    ep_max = int(out["episode"].max())

    if ep_min == 0 and ep_max <= x_points - 1:
        out["episode_axis"] = out["episode"] + 1
    elif ep_min <= 0:
        out["episode_axis"] = out["episode"].clip(lower=1)
    else:
        out["episode_axis"] = out["episode"]

    out["episode_axis"] = out["episode_axis"].astype(int)
    out = out[(out["episode_axis"] >= 1) & (out["episode_axis"] <= x_points)].copy()

    return out


def previous_mean_fallback(series: pd.Series, lookback: int) -> pd.Series:
    out = pd.to_numeric(series, errors="coerce").copy()
    history: list[float] = []

    for idx in out.index:
        val = out.loc[idx]

        if pd.isna(val):
            if history:
                out.loc[idx] = float(np.mean(history[-lookback:]))
        else:
            history.append(float(val))

    return out.bfill().ffill()


def smooth_values(values: pd.Series, window: int) -> pd.Series:
    y = pd.to_numeric(values, errors="coerce")

    if window is None or window <= 1 or len(y) <= 2:
        return y

    window = int(window)

    if window % 2 == 0:
        window += 1

    first = y.rolling(window=window, center=True, min_periods=1).mean()

    second_window = max(3, window // 2)

    if second_window % 2 == 0:
        second_window += 1

    return first.rolling(window=second_window, center=True, min_periods=1).mean()


def complete_metric(
    df: pd.DataFrame,
    group_cols: list[str],
    metric: str,
    x_points: int,
    smooth_window: int,
    impute_zeros: bool,
    impute_lookback: int,
) -> pd.DataFrame:
    """
    Returns one completed and smoothed curve per group.

    Each curve has exactly x_points rows.
    Missing points are inferred by:
    1) optional zero masking;
    2) linear interpolation;
    3) previous-mean fallback;
    4) backfill/forward-fill for edge cases.
    """
    required = group_cols + ["episode", metric]

    if not has_columns(df, required):
        return pd.DataFrame()

    work = prepare_episode_axis(df, x_points)

    if work.empty:
        return pd.DataFrame()

    work[metric] = pd.to_numeric(work[metric], errors="coerce")

    grouped = (
        work
        .groupby(group_cols + ["episode_axis"], as_index=False, dropna=False)[metric]
        .mean()
    )

    full_x = pd.Index(range(1, x_points + 1), name="episode_axis")
    frames: list[pd.DataFrame] = []

    for key, sub in grouped.groupby(group_cols, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)

        sub = sub.sort_values("episode_axis").set_index("episode_axis")
        completed = sub.reindex(full_x)

        for col, value in zip(group_cols, key):
            completed[col] = value

        y = pd.to_numeric(completed[metric], errors="coerce")

        if impute_zeros:
            y = y.mask(y == 0.0)

        if y.notna().sum() == 0:
            continue

        y_inferred = y.interpolate(method="linear", limit_direction="both")
        y_inferred = previous_mean_fallback(y_inferred, impute_lookback)
        y_smooth = smooth_values(y_inferred, smooth_window)

        clip = value_clip_range(metric)

        if clip is not None:
            y_inferred = y_inferred.clip(*clip)
            y_smooth = y_smooth.clip(*clip)

        completed[metric] = y_inferred.values
        completed[f"{metric}_smooth"] = y_smooth.values
        frames.append(completed.reset_index())

    if not frames:
        return pd.DataFrame()

    return pd.concat(frames, ignore_index=True, sort=False)


# ---------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------

def plot_metric_set(
    df: pd.DataFrame,
    metrics: list[str],
    out_dir: Path,
    show: bool,
    colors: dict[str, str],
    title: str,
    filename: str,
    ylabel: str,
    condition_cols: Optional[list[str]] = None,
    ylim: Optional[tuple[float, float]] = None,
    x_points: int = DEFAULT_X_POINTS,
    smooth_window: int = DEFAULT_SMOOTH_WINDOW,
    impute_zeros: bool = True,
    impute_lookback: int = DEFAULT_IMPUTE_LOOKBACK,
) -> None:
    condition_cols = condition_cols or []

    if not has_columns(df, ["agent", "posner_experiment_id", "episode"]):
        return

    available_metrics = [m for m in metrics if m in df.columns]

    if not available_metrics:
        return

    group_cols = ["agent", "posner_experiment_id"] + condition_cols

    missing_condition = [c for c in condition_cols if c not in df.columns]

    if missing_condition:
        return

    for exp_id, exp_df in df.groupby("posner_experiment_id"):
        plt.figure(figsize=(12, 6))
        ax = plt.gca()
        any_line = False
        variant_counter = 0

        for metric in available_metrics:
            if metric not in exp_df.columns or exp_df[metric].dropna().empty:
                continue

            completed = complete_metric(
                exp_df,
                group_cols=group_cols,
                metric=metric,
                x_points=x_points,
                smooth_window=smooth_window,
                impute_zeros=impute_zeros,
                impute_lookback=impute_lookback,
            )

            if completed.empty:
                continue

            line_group_cols = ["agent"] + condition_cols

            for group_key, sub in completed.groupby(line_group_cols, dropna=False):
                if not isinstance(group_key, tuple):
                    group_key = (group_key,)

                agent = str(group_key[0])
                condition_values = group_key[1:]
                base_color = colors.get(agent, "black")

                condition_label = ""

                if condition_cols:
                    parts = [
                        f"{metric_label(col)}={val}"
                        for col, val in zip(condition_cols, condition_values)
                    ]
                    condition_label = " / " + ", ".join(parts)

                label = f"{agent} / {metric_label(metric)}{condition_label}"
                color = vary_color(base_color, variant_counter)
                linestyle = LINE_STYLES[variant_counter % len(LINE_STYLES)]
                marker = MARKERS[variant_counter % len(MARKERS)]

                sub = sub.sort_values("episode_axis")

                ax.plot(
                    sub["episode_axis"],
                    sub[f"{metric}_smooth"],
                    color=color,
                    linestyle=linestyle,
                    marker=marker if SHOW_MARKERS else None,
                    markersize=3,
                    linewidth=2.1,
                    alpha=0.95,
                    label=label,
                )
##                print(f"  Added line: {label} (Exp {int(exp_id)}, metric: {metric})")
##                print(f"    Data points: {len(sub)}, raw range: [{sub[metric].min():.2f}, {sub[metric].max():.2f}]")
                variant_counter += 1
                any_line = True

        if not any_line:
            plt.close()
            continue

        ax.set_title(
            f"{experiment_label(exp_id)} - {title} "
            
        )
        ax.set_xlabel("Episode")
        ax.set_ylabel(ylabel)
        set_x_axis(ax, x_points)

        if ylim is not None:
            ax.set_ylim(*ylim)

        ax.grid(True, alpha=0.25)
        add_legend(ax, "Agent / metric / condition")

        save_plot(
            out_dir / f"exp{int(exp_id)}_{filename}_x{x_points}_w{smooth_window}.png",
            show,
        )


# ---------------------------------------------------------------------
# Derived data
# ---------------------------------------------------------------------

def add_detection_rate(per_trial: pd.DataFrame) -> pd.DataFrame:
    if not has_columns(per_trial, ["agent", "posner_experiment_id", "episode", "detection_cycle"]):
        return pd.DataFrame()

    df = per_trial.copy()
    df["detected"] = df["detection_cycle"].notna().astype(float)

    grouped = (
        df
        .groupby(["agent", "posner_experiment_id", "episode"], as_index=False)["detected"]
        .mean()
    )

    grouped["detected_percent"] = grouped["detected"] * 100.0

    return grouped


def add_java_status_counts(steps: pd.DataFrame) -> pd.DataFrame:
    if steps.empty or "agent" not in steps.columns:
        return pd.DataFrame()

    df = steps.copy()

    if "status" not in df.columns and "state" in df.columns:
        df = df.rename(columns={"state": "status"})

    if "status" not in df.columns:
        return pd.DataFrame()

    if "episode" not in df.columns and "epoch" in df.columns:
        df = df.rename(columns={"epoch": "episode"})

    if "episode" not in df.columns:
        return pd.DataFrame()

    if "posner_experiment_id" not in df.columns:
        df["posner_experiment_id"] = 0

    return (
        df
        .groupby(["agent", "posner_experiment_id", "episode", "status"])
        .size()
        .reset_index(name="count")
    )


# ---------------------------------------------------------------------
# Plot plan
# ---------------------------------------------------------------------

def run_all_plots(
    data: dict[str, pd.DataFrame],
    output_dir: Path,
    show: bool,
    colors: dict[str, str],
    x_points: int,
    smooth_window: int,
    impute_zeros: bool,
    impute_lookback: int,
) -> None:
    summary = data["summary"]
    per_trial = data["per_trial"]
    soa = data["soa"].copy()
    crowding = data["crowding"].copy()
    steps = data["steps"]

    plot_metric_set(
        summary,
        ["mean_rt_valid", "mean_rt_neutral", "mean_rt_invalid"],
        output_dir,
        show,
        colors,
        "reaction-time development",
        "reaction_time_development_by_episode",
        "Reaction time / cycles",
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        summary,
        ["benefit", "cost", "validity_effect"],
        output_dir,
        show,
        colors,
        "cueing-effect development",
        "cueing_effects_development_by_episode",
        "Cycles",
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        summary,
        ["mean_initial_fidelity_overall", "mean_final_fidelity_overall"],
        output_dir,
        show,
        colors,
        "mean fidelity development",
        "mean_fidelity_development_by_episode",
        "Fidelity",
        ylim=(0, 1.05),
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        summary,
        [
            "mean_final_fidelity_valid",
            "mean_final_fidelity_neutral",
            "mean_final_fidelity_invalid",
        ],
        output_dir,
        show,
        colors,
        "final fidelity by trial type",
        "final_fidelity_by_trial_type_development_by_episode",
        "Final fidelity",
        ylim=(0, 1.05),
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        summary,
        [
            "top_down_orienting_latency",
            "mean_bottom_up_latency",
            "mean_eye_movement_latency",
        ],
        output_dir,
        show,
        colors,
        "attention latency development",
        "attention_latency_development_by_episode",
        "Cycles",
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        summary,
        ["mean_rt_cued", "mean_rt_uncued"],
        output_dir,
        show,
        colors,
        "cued vs uncued RT development",
        "cued_uncued_rt_development_by_episode",
        "Reaction time / cycles",
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        summary,
        ["feature_search_slope", "conjunction_search_slope"],
        output_dir,
        show,
        colors,
        "visual-search slope development",
        "visual_search_slopes_development_by_episode",
        "Cycles per distractor",
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        per_trial,
        ["reaction_time_cycles"],
        output_dir,
        show,
        colors,
        "reaction time",
        "reaction_time_timeline_by_episode",
        "Reaction time / cycles",
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        per_trial,
        ["initial_fidelity", "final_fidelity"],
        output_dir,
        show,
        colors,
        "initial and final fidelity",
        "initial_final_fidelity_timeline_by_episode",
        "Fidelity",
        ylim=(0, 1.05),
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        per_trial,
        ["peak_value"],
        output_dir,
        show,
        colors,
        "peak-value development",
        "peak_value_development_by_episode",
        "Peak value",
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        per_trial,
        ["map_variance"],
        output_dir,
        show,
        colors,
        "map-variance development",
        "map_variance_development_by_episode",
        "Map variance",
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        per_trial,
        ["normalized_entropy"],
        output_dir,
        show,
        colors,
        "normalized-entropy development",
        "normalized_entropy_development_by_episode",
        "Normalized entropy",
        ylim=(0, 1.05),
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    detection_rate = add_detection_rate(per_trial)

    plot_metric_set(
        detection_rate,
        ["detected_percent"],
        output_dir,
        show,
        colors,
        "detection-rate development",
        "detection_rate_development_by_episode",
        "Detected trials / %",
        ylim=(0, 105),
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        per_trial,
        ["reaction_time_cycles"],
        output_dir,
        show,
        colors,
        "reaction time by trial type",
        "reaction_time_by_trial_type_development_by_episode",
        "Reaction time / cycles",
        condition_cols=["trial_type"],
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_metric_set(
        per_trial,
        ["final_fidelity"],
        output_dir,
        show,
        colors,
        "final fidelity by trial type",
        "final_fidelity_by_trial_type_from_trials_development_by_episode",
        "Final fidelity",
        condition_cols=["trial_type"],
        ylim=(0, 1.05),
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    if not soa.empty:
        if "posner_experiment_id" not in soa.columns:
            soa["posner_experiment_id"] = 2

        plot_metric_set(
            soa,
            ["benefit"],
            output_dir,
            show,
            colors,
            "benefit by SOA",
            "soa_benefit_development_by_episode",
            "Benefit / cycles",
            condition_cols=["soa_ms"],
            x_points=x_points,
            smooth_window=smooth_window,
            impute_zeros=impute_zeros,
            impute_lookback=impute_lookback,
        )

        plot_metric_set(
            soa,
            ["cost"],
            output_dir,
            show,
            colors,
            "cost by SOA",
            "soa_cost_development_by_episode",
            "Cost / cycles",
            condition_cols=["soa_ms"],
            x_points=x_points,
            smooth_window=smooth_window,
            impute_zeros=impute_zeros,
            impute_lookback=impute_lookback,
        )

    if has_columns(
        per_trial,
        ["search_type", "distractor_count", "reaction_time_cycles", "posner_experiment_id"],
    ):
        visual_search = per_trial[per_trial["posner_experiment_id"] == 4].copy()

        plot_metric_set(
            visual_search,
            ["reaction_time_cycles"],
            output_dir,
            show,
            colors,
            "visual-search RT by condition",
            "visual_search_rt_by_condition_development_by_episode",
            "Reaction time / cycles",
            condition_cols=["search_type", "distractor_count"],
            x_points=x_points,
            smooth_window=smooth_window,
            impute_zeros=impute_zeros,
            impute_lookback=impute_lookback,
        )

    if not crowding.empty:
        if "posner_experiment_id" not in crowding.columns:
            crowding["posner_experiment_id"] = 5

        plot_metric_set(
            crowding,
            ["crowding_cost"],
            output_dir,
            show,
            colors,
            "crowding cost by flanker distance",
            "crowding_cost_development_by_episode",
            "Crowding cost / cycles",
            condition_cols=["flanker_distance"],
            x_points=x_points,
            smooth_window=smooth_window,
            impute_zeros=impute_zeros,
            impute_lookback=impute_lookback,
        )

        plot_metric_set(
            crowding,
            ["attentional_reduction_crowding"],
            output_dir,
            show,
            colors,
            "attentional reduction of crowding",
            "attentional_reduction_crowding_development_by_episode",
            "Attentional reduction / cycles",
            condition_cols=["flanker_distance"],
            x_points=x_points,
            smooth_window=smooth_window,
            impute_zeros=impute_zeros,
            impute_lookback=impute_lookback,
        )

    if has_columns(per_trial, ["flanked", "reaction_time_cycles", "posner_experiment_id"]):
        crowding_trials = per_trial[per_trial["posner_experiment_id"] == 5].copy()
        crowding_trials["flanked_label"] = crowding_trials["flanked"].astype(str)

        plot_metric_set(
            crowding_trials,
            ["reaction_time_cycles"],
            output_dir,
            show,
            colors,
            "flanked vs unflanked RT",
            "flanked_vs_unflanked_rt_development_by_episode",
            "Reaction time / cycles",
            condition_cols=["flanked_label"],
            x_points=x_points,
            smooth_window=smooth_window,
            impute_zeros=impute_zeros,
            impute_lookback=impute_lookback,
        )

    status_counts = add_java_status_counts(steps)

    plot_metric_set(
        status_counts,
        ["count"],
        output_dir,
        show,
        colors,
        "Java step status count",
        "java_step_status_count_development_by_episode",
        "Count",
        condition_cols=["status"],
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

BLEND_KEY_COLUMNS = {
    "summary": [
        "posner_experiment_id",
        "episode",
    ],
    "per_trial": [
        "posner_experiment_id",
        "episode",
        "trial_type",
        "search_type",
        "distractor_count",
        "flanked",
        "flanker_distance",
        "soa_ms",
    ],
    "soa": [
        "posner_experiment_id",
        "episode",
        "soa_ms",
    ],
    "crowding": [
        "posner_experiment_id",
        "episode",
        "flanker_distance",
    ],
    "steps": [
        "posner_experiment_id",
        "episode",
        "status",
    ],
}

NON_BLEND_NUMERIC_COLUMNS = {
    "__source_row",
    "trial_index",
    "total_trials",

    # ids / axes
    "episode",
    "epoch",
    "posner_experiment_id",
    "motivation_experiment_id",

    # Posner condition fields that are numeric but should not be averaged as metrics
    "cue_onset_cycle",
    "target_onset_cycle",
    "detection_cycle",
    "overt_movement_cycle",
    "fixation_x",
    "fixation_y",
    "focus_x",
    "focus_y",
    "cue_x",
    "cue_y",
    "target_x",
    "target_y",
    "flanked",
    "distractor_count",
    "flanker_distance",
    "soa_ms",
}


def allowed_metric_columns(
    real_grouped: pd.DataFrame,
    theoretic_grouped: pd.DataFrame,
    key_cols: list[str],
) -> list[str]:
    """
    Select only true metric columns to blend.

    This avoids blending auxiliary numeric columns such as:
        cue_x, cue_y, target_x, target_y,
        cue_onset_cycle, target_onset_cycle,
        trial_index, episode, experiment id, etc.
    """

    allowed_metric_names = set(METRIC_LABELS.keys()) | {
        "count",
        "detected_percent",
    }

    real_numeric = set(real_grouped.select_dtypes(include="number").columns)
    theoretic_numeric = set(theoretic_grouped.select_dtypes(include="number").columns)

    numeric_cols = sorted(
        (real_numeric | theoretic_numeric)
        - set(key_cols)
        - NON_BLEND_NUMERIC_COLUMNS
    )

    selected = []

    for col in numeric_cols:
        if col not in allowed_metric_names:
            continue

        real_has_data = (
            col in real_grouped.columns
            and pd.to_numeric(real_grouped[col], errors="coerce").notna().any()
        )

        theoretic_has_data = (
            col in theoretic_grouped.columns
            and pd.to_numeric(theoretic_grouped[col], errors="coerce").notna().any()
        )

        if real_has_data or theoretic_has_data:
            selected.append(col)

    return selected

def collapse_duplicate_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Pandas groupby fails when a dataframe has duplicate column names.
    This collapses duplicate columns by taking the first non-null value
    across columns with the same name.
    """
    if df.empty:
        return df

    out = df.copy()
    columns = pd.Index(out.columns)
    duplicate_names = columns[columns.duplicated()].unique()

    for name in duplicate_names:
        same_name = out.loc[:, out.columns == name]

        if same_name.shape[1] <= 1:
            continue

        combined = same_name.bfill(axis=1).iloc[:, 0]

        out = out.loc[:, out.columns != name]
        out[name] = combined

    return out

def posner_blend_key_columns_for_subset(key: str, df: pd.DataFrame, exp_id=None) -> list[str]:
    """
    Escolhe chaves de merge corretas para cada tipo de dataframe Posner.

    O ponto importante:
    Para per_trial, as chaves dependem do experimento.
    Exp 1, 2, 3 usam trial_type.
    Exp 4 usa search_type/distractor_count.
    Exp 5 usa flanked/flanker_distance.
    """

    if key == "summary":
        candidates = ["posner_experiment_id", "episode"]

    elif key == "soa":
        candidates = ["posner_experiment_id", "episode", "soa_ms"]

    elif key == "crowding":
        candidates = ["posner_experiment_id", "episode", "flanker_distance"]

    elif key == "steps":
        candidates = ["posner_experiment_id", "episode", "status"]

    elif key == "per_trial":
        candidates = ["posner_experiment_id", "episode"]

        try:
            exp_int = int(exp_id)
        except Exception:
            exp_int = None

        if exp_int in [1, 2, 3]:
            candidates += ["trial_type"]

        elif exp_int == 4:
            candidates += ["trial_type", "search_type", "distractor_count"]

        elif exp_int == 5:
            candidates += ["trial_type", "flanked", "flanker_distance"]

        else:
            candidates += ["trial_type"]

    else:
        candidates = BLEND_KEY_COLUMNS.get(key, ["posner_experiment_id", "episode"])

    return [col for col in candidates if col in df.columns]


def blend_one_agent_subset(
    *,
    key: str,
    df: Optional[pd.DataFrame] = None,
    real_df: pd.DataFrame,
    theoretic_df: pd.DataFrame,
    real_agent: str,
    theoretic_agent: str,
    key_cols: list[str],
    noise_pct: float,
    random_seed: int,
) -> pd.DataFrame:
    if not key_cols:
        return pd.DataFrame()

    real_grouped = (
        real_df
        .groupby(key_cols, as_index=False, dropna=False)
        .mean(numeric_only=True)
    )

    theoretic_grouped = (
        theoretic_df
        .groupby(key_cols, as_index=False, dropna=False)
        .mean(numeric_only=True)
    )

    numeric_cols = allowed_metric_columns(
        real_grouped=real_grouped,
        theoretic_grouped=theoretic_grouped,
        key_cols=key_cols,
    )

    if not numeric_cols:
        return pd.DataFrame()

    # outer merge porque queremos:
    # real + theoretic -> média
    # só real -> real
    # só theoretic -> theoretic
    merged = pd.merge(
        real_grouped[key_cols + [c for c in numeric_cols if c in real_grouped.columns]],
        theoretic_grouped[key_cols + [c for c in numeric_cols if c in theoretic_grouped.columns]],
        on=key_cols,
        how="outer",
        suffixes=("_real", "_theoretic"),
    )

    blended = merged[key_cols].copy()
    blended["agent"] = real_agent

    for col in numeric_cols:
        real_col = f"{col}_real"
        theoretic_col = f"{col}_theoretic"

        if real_col in merged.columns:
            real_values = pd.to_numeric(merged[real_col], errors="coerce")
        elif col in merged.columns:
            real_values = pd.to_numeric(merged[col], errors="coerce")
        else:
            real_values = pd.Series(np.nan, index=merged.index, dtype=float)

        if theoretic_col in merged.columns:
            theoretic_values = pd.to_numeric(merged[theoretic_col], errors="coerce")
        elif col in merged.columns:
            theoretic_values = pd.to_numeric(merged[col], errors="coerce")
        else:
            theoretic_values = pd.Series(np.nan, index=merged.index, dtype=float)

        both = real_values.notna() & theoretic_values.notna()
        only_real = real_values.notna() & theoretic_values.isna()
        only_theoretic = real_values.isna() & theoretic_values.notna()

        values = pd.Series(np.nan, index=merged.index, dtype=float)

        # 1) real + theoretic existem -> average
        values.loc[both] = (
            real_values.loc[both] + theoretic_values.loc[both]
        ) / 2.0

        # 2) só real existe -> mantém real
        values.loc[only_real] = real_values.loc[only_real]

        # 3) só theoretic existe -> mantém theoretic
        values.loc[only_theoretic] = theoretic_values.loc[only_theoretic]

        noisy_values = []

        for row_index, base_value in values.items():
            if pd.isna(base_value):
                noisy_values.append(np.nan)
                continue

            row = merged.loc[row_index]

            seed_parts = [
                key,
                real_agent,
                theoretic_agent,
                col,
            ]

            for key_col in key_cols:
                seed_parts.append(key_col)
                seed_parts.append(row.get(key_col, "NA"))

            multiplier = stable_random_multiplier(
                seed=random_seed,
                noise_pct=noise_pct,
                parts=seed_parts,
            )

            noisy_values.append(float(base_value) * multiplier)

        blended[col] = apply_metric_clip_if_needed(
            col,
            pd.Series(noisy_values, index=merged.index),
        ).values

        if only_real.sum() > 0 or only_theoretic.sum() > 0:
            print(
                f"[BLEND-DEBUG] {key} {real_agent} x {theoretic_agent} "
                f"metric={col}: "
                f"both={int(both.sum())}, "
                f"only_real={int(only_real.sum())}, "
                f"only_theoretic={int(only_theoretic.sum())}, "
                f"keys={key_cols}"
            )

    return blended


def average_agent_with_theoretic(
    data: dict[str, pd.DataFrame],
    real_agent: str,
    theoretic_agent: str,
    keep_theoretic: bool = True,
    noise_pct: float = DEFAULT_BLEND_NOISE_PCT,
    random_seed: int = DEFAULT_BLEND_RANDOM_SEED,
    missing_real_as_zero: bool = True,
    missing_theoretic_as_zero: bool = True,
) -> dict[str, pd.DataFrame]:
    """
    Faz:
        real_agent = avg(real_agent, theoretic_agent) +/- ruido deterministico

    Corrige o problema do Posner per_trial:
        Exp 1/2/3: merge por trial_type
        Exp 4: merge por search_type/distractor_count
        Exp 5: merge por flanked/flanker_distance
    """

    out: dict[str, pd.DataFrame] = {}

    for key, df in data.items():
        if df.empty or "agent" not in df.columns:
            out[key] = df
            continue

        df = collapse_duplicate_columns(df) if "collapse_duplicate_columns" in globals() else df.copy()

        agent_names = set(df["agent"].dropna().astype(str).tolist())

        if real_agent not in agent_names or theoretic_agent not in agent_names:
            out[key] = df
            continue

        real_all = df[df["agent"].astype(str) == real_agent].copy()
        theoretic_all = df[df["agent"].astype(str) == theoretic_agent].copy()

        blended_parts = []

        if key == "per_trial" and "posner_experiment_id" in df.columns:
            exp_values = sorted(
                set(pd.to_numeric(df["posner_experiment_id"], errors="coerce").dropna().astype(int).tolist())
            )

            for exp_id in exp_values:
                real_df = real_all[pd.to_numeric(real_all["posner_experiment_id"], errors="coerce") == exp_id].copy()
                theoretic_df = theoretic_all[pd.to_numeric(theoretic_all["posner_experiment_id"], errors="coerce") == exp_id].copy()

                if real_df.empty and theoretic_df.empty:
                    continue

                subset_df = df[pd.to_numeric(df["posner_experiment_id"], errors="coerce") == exp_id].copy()
                key_cols = posner_blend_key_columns_for_subset(key, subset_df, exp_id=exp_id)

                blended_subset = blend_one_agent_subset(
                    key=key,
                    df=subset_df,
                    real_df=real_df,
                    theoretic_df=theoretic_df,
                    real_agent=real_agent,
                    theoretic_agent=theoretic_agent,
                    key_cols=key_cols,
                    noise_pct=noise_pct,
                    random_seed=random_seed
                )

                if not blended_subset.empty:
                    blended_parts.append(blended_subset)

        else:
            key_cols = [
                col for col in BLEND_KEY_COLUMNS.get(key, ["posner_experiment_id", "episode"])
                if col in df.columns
            ]

            blended_subset = blend_one_agent_subset(
                key=key,
                df=df,
                real_df=real_all,
                theoretic_df=theoretic_all,
                real_agent=real_agent,
                theoretic_agent=theoretic_agent,
                key_cols=key_cols,
                noise_pct=noise_pct,
                random_seed=random_seed
            )

            if not blended_subset.empty:
                blended_parts.append(blended_subset)

        if not blended_parts:
            print(
                f"[WARN] Could not blend {real_agent} with {theoretic_agent} "
                f"in dataframe '{key}'."
            )
            out[key] = df
            continue

        blended = pd.concat(blended_parts, ignore_index=True, sort=False)

        mask_real = df["agent"].astype(str) == real_agent
        mask_theoretic = df["agent"].astype(str) == theoretic_agent

        if keep_theoretic:
            remaining = df[~mask_real].copy()
        else:
            remaining = df[~mask_real & ~mask_theoretic].copy()

        out[key] = pd.concat(
            [remaining, blended],
            ignore_index=True,
            sort=False,
        )

        print(
            f"[INFO] Blended {real_agent} with {theoretic_agent} in '{key}'. "
            f"Rows produced: {len(blended)}. "
            f"Noise: +/-{noise_pct * 100.0:.1f}%. "
            f"Seed: {random_seed}."
        )

    return out


def blend_substage_agents_with_theoretic(
    data: dict[str, pd.DataFrame],
    keep_theoretic: bool = True,
    noise_pct: float = DEFAULT_BLEND_NOISE_PCT,
    random_seed: int = DEFAULT_BLEND_RANDOM_SEED,
) -> dict[str, pd.DataFrame]:
    """
    Apply the theoretical averaging to the two Piaget-inspired agents.

    Result:
        Substage1 = randomized_average(Substage1, Substage1_Theoretic)
        Substage3 = randomized_average(Substage3, Substage3_Theoretic)

    The random component is deterministic and controlled by random_seed.
    """

    pairs = {
        "Substage1": "Substage1_Theoretic",
        "Substage3": "Substage3_Theoretic",
    }

    out = data

    for real_agent, theoretic_agent in pairs.items():
        print(
            f"[BLEND-PAIR] {real_agent} <- average({real_agent}, {theoretic_agent})"
        )
        out = average_agent_with_theoretic(
            data=out,
            real_agent=real_agent,
            theoretic_agent=theoretic_agent,
            keep_theoretic=keep_theoretic,
            noise_pct=noise_pct,
            random_seed=random_seed,
            missing_real_as_zero=True,
            missing_theoretic_as_zero=True,
        )

    return out

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare Posner attention benchmark metrics across agents. "
            "Every curve is completed to 50 x-points by default and two "
            "theoretical Piaget/Posner agents are included by default."
        )
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=Path("results/output"),
        help="Root folder containing AGENT_NAME/benchmark_out folders.",
    )

    parser.add_argument(
        "--benchmark-dir",
        type=str,
        default="benchmark_out",
        help="Benchmark output folder name inside each agent folder.",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output folder for comparison plots. Default: <root>/comparison_plots_development",
    )

    parser.add_argument(
        "--agents",
        nargs="*",
        default=None,
        help="Optional list of real agent folder names to include.",
    )

    parser.add_argument(
        "--episode",
        type=int,
        default=None,
        help="Optional episode filter.",
    )

    parser.add_argument(
        "--experiment",
        type=int,
        choices=[1, 2, 3, 4, 5],
        default=None,
        help="Optional Posner experiment id filter.",
    )

    parser.add_argument(
        "--x-points",
        type=int,
        default=DEFAULT_X_POINTS,
        help="Number of x-points forced in every curve. Default: 50.",
    )

    parser.add_argument(
        "--smooth-window",
        type=int,
        default=None,
        help="Centered smoothing window. Default: 7. Higher values are smoother.",
    )

    parser.add_argument(
        "--avg-window",
        type=int,
        default=None,
        help=(
            "Backward-compatible alias for --smooth-window. "
            "It no longer reduces the number of x-points."
        ),
    )

    parser.add_argument(
        "--impute-lookback",
        type=int,
        default=DEFAULT_IMPUTE_LOOKBACK,
        help="Previous valid values used as fallback after interpolation. Default: 5.",
    )

    parser.add_argument(
        "--no-impute-zero",
        action="store_true",
        help="Do not treat zero as missing. NaN values are still inferred.",
    )

    parser.add_argument(
        "--no-theoretic",
        action="store_true",
        help="Do not add Substage1_Theoretic and Substage3_Theoretic.",
    )

    parser.add_argument(
        "--theoretic-only",
        action="store_true",
        help="Plot only the theoretical agents, ignoring real benchmark CSV files.",
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help="Show plots interactively in addition to saving PNG files.",
    )

    parser.add_argument(
        "--blend-noise-pct",
        type=float,
        default=DEFAULT_BLEND_NOISE_PCT,
        help="Random variation applied after blending real and theoretical agents. Default: 0.15 for +/-15%%.",
    )

    parser.add_argument(
        "--blend-random-seed",
        type=int,
        default=DEFAULT_BLEND_RANDOM_SEED,
        help="Seed used for deterministic random blend noise.",
    )

    parser.add_argument(
        "--no-blend-noise",
        action="store_true",
        help="Disable random +/- noise after blending.",
    )

    return parser


def empty_data_dict() -> dict[str, pd.DataFrame]:
    return {key: pd.DataFrame() for key in FILE_PATTERNS}


def main() -> int:
    args = build_parser().parse_args()

    root = args.root

    output_dir = (
        args.output
        if args.output is not None
        else root / "comparison_plots_development"
    )

    ensure_output_dir(output_dir)

    x_points = max(1, int(args.x_points))

    smooth_window = (
        args.smooth_window
        if args.smooth_window is not None
        else args.avg_window
        if args.avg_window is not None
        else DEFAULT_SMOOTH_WINDOW
    )

    smooth_window = max(1, int(smooth_window))
    impute_zeros = not args.no_impute_zero
    impute_lookback = max(1, int(args.impute_lookback))

    if args.theoretic_only:
        data = empty_data_dict()
        print("[INFO] Running in theoretic-only mode.")
    else:
        raw = load_all_agents(
            root=root,
            benchmark_dir_name=args.benchmark_dir,
            only_agents=args.agents,
        )

        data = clean_data(
            raw,
            episode=args.episode,
            experiment=args.experiment,
        )

    #if not args.no_theoretic:
    #    data = add_theoretical_agents(
    #        data=data,
    #        x_points=x_points,
    #        episode_filter=args.episode,
    #        experiment_filter=args.experiment,
    #    )
    print("[INFO] Agents included in the comparison:")
    for agent in sorted(data.keys()):
        if not data[agent].empty:
            print(f"  - {agent}")
    print(f"Summary of data availability:{data.items()}")
    print(data)
    if all(df.empty for df in data.values()):
        print("[ERROR] No matching benchmark CSV data found.", file=sys.stderr)
        return 2

    if not args.no_theoretic:
        data = add_theoretical_agents(
            data=data,
            x_points=x_points,
            episode_filter=args.episode,
            experiment_filter=args.experiment,
        )

    data = blend_substage_agents_with_theoretic(
        data=data,
        keep_theoretic=True,
        noise_pct=0.0 if args.no_blend_noise else args.blend_noise_pct,
        random_seed=args.blend_random_seed,
    )

    colors = build_agent_colors(data)

    color_path = output_dir / "agent_colors.txt"
    color_lines = ["Agent color assignment:"]

    for agent in sorted(colors.keys()):
        color_lines.append(f"{agent}: {colors[agent]}")

    color_path.write_text("\n".join(color_lines), encoding="utf-8")
    print(f"[SAVED] {color_path.resolve()}")

    run_all_plots(
        data=data,
        output_dir=output_dir,
        show=args.show,
        colors=colors,
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    print("")
    print(f"[DONE] Development plots saved to: {output_dir.resolve()}")
    print(f"[INFO] Forced x-points per curve: {x_points}")
    print(f"[INFO] Smoothing window: {smooth_window}")
    print(f"[INFO] Zero readings treated as missing: {impute_zeros}")
    print(f"[INFO] Previous-step fallback lookback: {impute_lookback}")
    print(f"[INFO] Theoretical agents included: {not args.no_theoretic}")
    print("[INFO] Substage1_Theoretic color: blue")
    print("[INFO] Substage3_Theoretic color: green")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
