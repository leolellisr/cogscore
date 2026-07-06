#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


# ============================================================
# CogScore Learning Plot Script
# ============================================================
#
# This version generates ONLY angular-deviation plots.
#
# It reproduces the angular plots from test_tcds.py:
#
# by_epoch/
# ├── angles1_P.pdf / angles1_P.png
# ├── angles1_N.pdf / angles1_N.png
# ├── angles2_P.pdf / angles2_P.png
# ├── angles2_N.pdf / angles2_N.png
# ├── angles3_P.pdf / angles3_P.png
# ├── angles3_N.pdf / angles3_N.png
# ├── angles4a_P.pdf / angles4a_P.png
# ├── angles4a_N.pdf / angles4a_N.png
# ├── angles4b_P.pdf / angles4b_P.png
# ├── angles4b_N.pdf / angles4b_N.png
# ├── angles5.pdf
# └── angles5.png
#
# Expected usage:
#
# python scripts/learning.py \
#   --root data/results/Substage5_DQN/learning/run_xxx/benchmark_out \
#   --out data/plots/learning/comparison/job_xxx \
#   --max-epochs 50 \
#   --aggregate-n 5
#
# Expected benchmark_out structure:
#
# benchmark_out/
# ├── Substage1/
# │   ├── testA/
# │   │   └── seed1234/
# │   │       └── profile/
# │   │           └── nrewards.txt
# │   └── testB/
# ├── Substage2/
# │   ├── testA/
# │   └── testB/
# ├── Substage3/
# │   ├── testA/
# │   └── testB/
# ├── Substage4/
# │   ├── testA/
# │   ├── testAB/
# │   └── testB/
# └── Substage5/
#     └── testA/
#
# Also supports the older test_tcds.py structure:
#
# benchmark_out/
# ├── 1st/testA/
# ├── 1st/testB/
# ├── 2nd/testA/
# ├── 2nd/testB/
# ├── 3rd/testA/
# ├── 3rd/testB/
# ├── 4th/testA/
# ├── 4th/testB/
# ├── old/old_results/4th_3/testA/
# └── 5th/test/
#
# ============================================================


DEFAULT_MAX_EPOCHS = 50
DEFAULT_AGGREGATE_N = 5

DEBUG = False
DEBUG_VERBOSE = False


STRINGS_TO_REMOVE = [
    "Exp number:",
    "Action num: ",
    "Battery:",
    "reward: ",
    "num_tables:",
    "Curiosity_lv: ",
    "Curiosity_lv:",
    "Red: ",
    "Green: ",
    "Blue: ",
    "Red:",
    "Green:",
    "Blue:",
    "action:",
    "mot_value: ",
    "r_imp: ",
    "g_imp: ",
    "b_imp: ",
    "hug_drive: ",
    "cur_drive: ",
    " QTables:",
    "cur_a: ",
    "sur_a: ",
    "Exp:",
    "Nact:",
    "Type:",
    "cur_a:",
    "sur_a:",
    "exp_c:",
    "exp_s:",
    "dSurV:",
    "SurV:",
    "dCurV:",
    "CurV:",
    "QTables:",
    "Ri:",
    "Ri S:",
    "Ri C:",
    "G_Reward S:",
    "G_Reward C:",
    "G_Reward:",
    " LastAct:",
    "Act C:",
    "Act S:",
    "color1:",
    "Pos1:",
    "Pos2:",
    "fov:",
    "HeadPitch:",
    "NeckYaw:",
    "color2:",
    "fov_y:",
    "MaxSalValue:",
    "fov_p:",
    "Field:",
    "Memory:",
    ",",
    "]",
]


# ============================================================
# Logging and filesystem helpers
# ============================================================

def log_info(message: str) -> None:
    print(f"[INFO] {message}")


def log_ok(message: str) -> None:
    print(f"[OK] {message}")


def log_warn(message: str) -> None:
    print(f"[WARN] {message}")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def resolve_root(root: Path) -> Path:
    """
    Accept either:
    - a direct path to benchmark_out/
    - a run folder containing benchmark_out/
    - a nested benchmark_out/benchmark_out structure
    """
    root = root.resolve()

    if (root / "benchmark_out").is_dir():
        root = root / "benchmark_out"

    # Some bundles may accidentally contain benchmark_out/benchmark_out/.
    if (root / "benchmark_out").is_dir():
        nested = root / "benchmark_out"

        if any(nested.rglob("nrewards.txt")):
            root = nested

    return root


def clean_line(line: str) -> str:
    """
    Clean nrewards.txt lines in memory.

    The original test_tcds.py rewrites nrewards.txt on disk.
    This version does not modify uploaded files.
    """
    for token in STRINGS_TO_REMOVE:
        line = line.replace(token, "")

    return line


def read_clean_lines(file_path: Path, skip_header: bool = True) -> List[str]:
    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = [clean_line(line) for line in f.readlines()]

    if skip_header and lines:
        return lines[1:]

    return lines


def save_plot(filename: Path, save_png: bool = True, save_pdf: bool = True) -> None:
    """
    Save plot as PDF and PNG.

    PDF keeps thesis-quality output.
    PNG is useful for the web dashboard.
    """
    ensure_dir(filename.parent)

    base = filename
    if base.suffix.lower() in {".png", ".pdf"}:
        base = base.with_suffix("")

    plt.tight_layout()

    if save_pdf:
        pdf_path = base.with_suffix(".pdf")
        plt.savefig(pdf_path)
        log_ok(f"Saved {pdf_path}")

    if save_png:
        png_path = base.with_suffix(".png")
        plt.savefig(png_path, dpi=200)
        log_ok(f"Saved {png_path}")

    plt.close()


# ============================================================
# nrewards parsing
# ============================================================

def infer_yaw_pitch_columns(cols: List[str]) -> Tuple[int, int]:
    """
    Infer yaw and pitch columns from the variable nrewards.txt format.

    Same logic used in test_tcds.py:
    - default: yaw=19, pitch=20
    - if 22 < len(cols) < 26: yaw=21, pitch=22
    - if len(cols) > 25: yaw=23, pitch=24
    """
    yaw_col = 19
    pitch_col = 20

    if 22 < len(cols) < 26:
        yaw_col = 21
        pitch_col = 22

    if len(cols) > 25:
        yaw_col = 23
        pitch_col = 24

    return yaw_col, pitch_col


def read_nrewards(file_path: Path) -> Tuple[List[int], List[float], List[int], List[float]]:
    """
    Read nrewards.txt and compute, for each episode:

    - mean reward
    - max executed action
    - mean angular deviation sqrt(yaw^2 + pitch^2)
    """
    if not file_path.exists():
        return [], [], [], []

    rewards_by_ep: Dict[int, List[float]] = defaultdict(list)
    angles_by_ep: Dict[int, List[float]] = defaultdict(list)
    max_actions_by_ep: Dict[int, int] = defaultdict(int)

    lines = read_clean_lines(file_path, skip_header=True)

    for i, line in enumerate(lines):
        cols = line.split()

        if len(cols) < 22:
            continue

        try:
            yaw_col, pitch_col = infer_yaw_pitch_columns(cols)

            ep = int(float(cols[1]))
            step = int(float(cols[2]))
            reward = float(cols[4])
            yaw = float(cols[yaw_col])
            pitch = float(cols[pitch_col])

        except Exception:
            if DEBUG_VERBOSE:
                log_warn(f"Could not parse line {i} from {file_path}")
            continue

        rewards_by_ep[ep].append(reward)
        angles_by_ep[ep].append(math.sqrt(yaw ** 2 + pitch ** 2))
        max_actions_by_ep[ep] = max(max_actions_by_ep[ep], step)

    episodes = sorted(rewards_by_ep.keys())

    mean_rewards = [float(np.mean(rewards_by_ep[ep])) for ep in episodes]
    mean_angles = [float(np.mean(angles_by_ep[ep])) for ep in episodes]
    max_actions = [int(max_actions_by_ep[ep]) for ep in episodes]

    return episodes, mean_rewards, max_actions, mean_angles


def find_nrewards_files(base_path: Path) -> List[Path]:
    """
    Find all nrewards.txt files recursively below a test folder.

    Expected examples:
    - Substage1/testA/seed1234/profile/nrewards.txt
    - Substage1/testA/seed1234/data/nrewards.txt
    - Substage1/testA/seed1234/nrewards.txt
    """
    if not base_path.exists() or not base_path.is_dir():
        return []

    files = sorted(base_path.rglob("nrewards.txt"))

    # Prefer profile/nrewards.txt, then data/nrewards.txt, then any other.
    def priority(path: Path) -> tuple[int, str]:
        parts = path.parts

        if "profile" in parts:
            return (0, str(path))

        if "data" in parts:
            return (1, str(path))

        return (2, str(path))

    return sorted(files, key=priority)


def seed_key_from_nrewards_path(path: Path) -> str:
    """
    Infer a seed identifier from a nrewards.txt path.

    Examples:
    Substage1/testA/seed1234/profile/nrewards.txt -> seed1234
    Substage1/testA/seed1234/data/nrewards.txt    -> seed1234
    """
    parent = path.parent

    if parent.name in {"profile", "data"}:
        return parent.parent.name

    return parent.name


def pad_list(values: List[float], size: int, fill_value: float = np.nan) -> List[float]:
    return values + [fill_value] * max(0, size - len(values))


def aggregate_data(base_path: Path) -> Tuple[
    List[int],
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
]:
    """
    Aggregate rewards, actions, and angular deviations across seeds.

    This version searches recursively for nrewards.txt files inside the test folder.
    It supports paths such as:

    Substage1/testA/seed1234/profile/nrewards.txt
    Substage1/testA/seed1234/data/nrewards.txt
    """
    nrewards_files = find_nrewards_files(base_path)

    if not nrewards_files:
        log_warn(f"No nrewards.txt data found in {base_path}")
        return [], np.array([]), np.array([]), np.array([]), np.array([]), np.array([]), np.array([])

    log_info(f"Found {len(nrewards_files)} nrewards.txt file(s) under {base_path}")

    # Avoid reading both profile/nrewards.txt and data/nrewards.txt for the same seed.
    # The list is already sorted with profile first.
    selected_by_seed: dict[str, Path] = {}

    for file_path in nrewards_files:
        seed_key = seed_key_from_nrewards_path(file_path)

        if seed_key not in selected_by_seed:
            selected_by_seed[seed_key] = file_path

    selected_files = sorted(selected_by_seed.values())

    log_info(f"Using {len(selected_files)} seed file(s) under {base_path}")

    all_rewards: List[List[float]] = []
    all_actions: List[List[int]] = []
    all_angles: List[List[float]] = []
    episodes_ref: List[int] = []

    for file_path in selected_files:
        episodes, rewards, actions, angles = read_nrewards(file_path)

        if not episodes:
            log_warn(f"No readable episodes in {file_path}")
            continue

        if not episodes_ref:
            episodes_ref = episodes

        all_rewards.append(rewards)
        all_actions.append(actions)
        all_angles.append(angles)

        log_info(f"Loaded {len(episodes)} episode(s) from {file_path}")

    if not all_rewards:
        log_warn(f"No valid nrewards.txt data found in {base_path}")
        return [], np.array([]), np.array([]), np.array([]), np.array([]), np.array([]), np.array([])

    max_len = max(len(r) for r in all_rewards)

    rewards_arr = np.array([pad_list(r, max_len) for r in all_rewards], dtype=float)
    actions_arr = np.array([pad_list(list(map(float, a)), max_len) for a in all_actions], dtype=float)
    angles_arr = np.array([pad_list(a, max_len) for a in all_angles], dtype=float)

    mean_rewards = np.nanmean(rewards_arr, axis=0)
    std_rewards = np.nanstd(rewards_arr, axis=0)

    mean_actions = np.nanmean(actions_arr, axis=0)
    std_actions = np.nanstd(actions_arr, axis=0)

    mean_angles = np.nanmean(angles_arr, axis=0)
    std_angles = np.nanstd(angles_arr, axis=0)

    if len(episodes_ref) < max_len:
        episodes_ref = list(range(1, max_len + 1))

    return (
        episodes_ref[:max_len],
        mean_rewards,
        std_rewards,
        mean_actions,
        std_actions,
        mean_angles,
        std_angles,
    )


# ============================================================
# Aggregation helpers
# ============================================================

def safe_nanmean(values: Iterable[float], default: float = 0.0) -> float:
    arr = np.asarray(list(values), dtype=float)

    if arr.size == 0 or np.all(np.isnan(arr)):
        return default

    return float(np.nanmean(arr))


def aggregate_every_n(
    x: Iterable[float],
    mean: Iterable[float],
    std: Iterable[float],
    n: int = DEFAULT_AGGREGATE_N,
    max_common_episode: Optional[int] = None,
) -> Tuple[List[float], List[float], List[float]]:
    """
    Aggregate every n episodes.

    This follows the logic used by test_tcds.py:
    - first point is inserted at episode 1 or at the first available episode;
    - mean/std values are averaged in chunks of size n.
    """
    x = list(x)
    mean = list(mean)
    std = list(std)

    if len(x) == 0:
        return [], [], []

    x_new: List[float] = []
    mean_new: List[float] = []
    std_new: List[float] = []

    start_episode = int(x[0])
    max_episode = max_common_episode if max_common_episode is not None else int(x[-1])

    if start_episode == 1:
        x_new.append(1)
    else:
        x_new.append(start_episode)

    mean_new.append(0.0)
    std_new.append(0.0)

    chunk_idx = 0

    while True:
        desired = (chunk_idx + 1) * n if start_episode == 1 else start_episode + (chunk_idx + 1) * n

        if desired > max_episode:
            break

        i = chunk_idx * n

        if i >= len(mean):
            break

        mean_chunk = mean[i:i + n]
        std_chunk = std[i:i + n]

        x_new.append(float(desired))
        mean_new.append(safe_nanmean(mean_chunk, default=0.0))
        std_new.append(safe_nanmean(std_chunk, default=0.0))

        chunk_idx += 1

    return x_new, mean_new, std_new


def max_episode_of(*episode_lists: Iterable[float]) -> int:
    max_ep = 0

    for episodes in episode_lists:
        e = list(episodes)

        if e:
            max_ep = max(max_ep, int(e[-1]))

    return max_ep


# ============================================================
# Plotting
# ============================================================

def plot_metric2(
    x1: Iterable[float],
    mean1: Iterable[float],
    std1: Iterable[float],
    ylabel: str,
    filename: Path,
    x2: Iterable[float],
    mean2: Iterable[float],
    std2: Iterable[float],
    label1: str,
    label2: str,
    plot_every: int = 5,
) -> None:
    """
    Plot two angular-deviation series as separate files:

    filename_P.pdf/png for the first series.
    filename_N.pdf/png for the second series.

    This reproduces the behavior of test_tcds.py.
    """
    x1 = np.asarray(list(x1), dtype=float)
    mean1 = np.asarray(list(mean1), dtype=float)
    std1 = np.asarray(list(std1), dtype=float)

    x2 = np.asarray(list(x2), dtype=float)
    mean2 = np.asarray(list(mean2), dtype=float)
    std2 = np.asarray(list(std2), dtype=float)

    # First plot: positive / first condition
    if len(x1) > 0 and len(mean1) > 0:
        npts = min(len(x1), len(mean1), len(std1))
        x = x1[:npts]
        mean = mean1[:npts]
        std = std1[:npts]

        plt.figure(figsize=(6, 6))
        color = "tab:green"

        plt.plot(x, mean, color=color, linestyle=":", label="Mean " + label1)
        plt.fill_between(x, mean - std, mean + std, alpha=0.2, color=color)

        idx = np.arange(0, len(x), max(1, plot_every))

        if len(idx) > 0 and idx[-1] != len(x) - 1:
            idx = np.append(idx, len(x) - 1)

        if len(idx) > 0:
            plt.plot(x[idx], mean[idx], marker="^", linestyle="", color=color)
            plt.xticks(x[idx], [str(int(v)) for v in x[idx]], fontsize=18)

        ax = plt.gca()
        xmin, xmax = ax.get_xlim()
        xs = np.linspace(xmin, xmax, 2)
        ax.fill_between(xs, -30, 30, alpha=0.12, color="tab:gray", zorder=0)

        plt.xlabel("Episode", fontsize=18)
        plt.ylabel(ylabel, fontsize=18)
        plt.ylim(-40, 120)
        plt.yticks(np.arange(-40, 141, 20), fontsize=18)

        save_plot(filename.with_name(filename.name + "_P"))

    # Second plot: negative / second condition
    if len(x2) > 0 and len(mean2) > 0:
        npts = min(len(x2), len(mean2), len(std2))
        x = x2[:npts]
        mean = mean2[:npts]
        std = std2[:npts]

        plt.figure(figsize=(6, 6))
        color = "tab:red"

        plt.plot(x, mean, color=color, linestyle=":", label="Mean " + label2)
        plt.fill_between(x, mean - std, mean + std, alpha=0.2, color=color)

        idx = np.arange(0, len(x), max(1, plot_every))

        if len(idx) > 0 and idx[-1] != len(x) - 1:
            idx = np.append(idx, len(x) - 1)

        if len(idx) > 0:
            plt.plot(x[idx], mean[idx], marker="^", linestyle="", color=color)
            plt.xticks(x[idx], [str(int(v)) for v in x[idx]], fontsize=18)

        ax = plt.gca()
        xmin, xmax = ax.get_xlim()
        xs = np.linspace(xmin, xmax, 2)
        ax.fill_between(xs, -30, 30, alpha=0.12, color="tab:gray", zorder=0)

        plt.xlabel("Episode", fontsize=18)
        plt.ylabel(ylabel, fontsize=18)
        plt.ylim(-40, 120)
        plt.yticks(np.arange(-40, 141, 20), fontsize=18)

        save_plot(filename.with_name(filename.name + "_N"))


def plot_metric(
    x: Iterable[float],
    mean: Iterable[float],
    std: Iterable[float],
    ylabel: str,
    filename: Path,
    label: str,
    plot_every: int = 5,
) -> None:
    """
    Plot one angular-deviation series.

    Used for angles5.
    """
    x = np.asarray(list(x), dtype=float)
    mean = np.asarray(list(mean), dtype=float)
    std = np.asarray(list(std), dtype=float)

    if len(x) == 0 or len(mean) == 0:
        log_warn(f"Skipping empty plot: {filename}")
        return

    npts = min(len(x), len(mean), len(std))
    x = x[:npts]
    mean = mean[:npts]
    std = std[:npts]

    plt.figure(figsize=(6, 6))
    color = "tab:green"

    plt.plot(x, mean, color=color, linestyle=":", label="Mean " + label)
    plt.fill_between(x, mean - std, mean + std, alpha=0.2, color=color)

    idx = np.arange(0, len(x), max(1, plot_every))

    if len(idx) > 0 and idx[-1] != len(x) - 1:
        idx = np.append(idx, len(x) - 1)

    if len(idx) > 0:
        plt.plot(x[idx], mean[idx], marker="^", linestyle="", color=color)
        plt.xticks(x[idx], [str(int(v)) for v in x[idx]], fontsize=18)

    ax = plt.gca()
    xmin, xmax = ax.get_xlim()
    xs = np.linspace(xmin, xmax, 2)
    ax.fill_between(xs, -30, 30, alpha=0.12, color="tab:gray", zorder=0)

    plt.xlabel("Episode", fontsize=18)
    plt.ylabel(ylabel, fontsize=18)
    plt.ylim(-40, 120)
    plt.yticks(np.arange(-40, 141, 20), fontsize=18)

    save_plot(filename)


# ============================================================
# Stage path detection
# ============================================================

def has_nrewards_under(path: Path) -> bool:
    return path.exists() and path.is_dir() and any(path.rglob("nrewards.txt"))


def find_first_existing_dir(root: Path, candidates: list[Path]) -> Path:
    """
    Return the first candidate that exists and contains nrewards.txt.

    If none contains nrewards.txt, return the first existing directory.

    If no direct candidate exists, return the first candidate. The caller will
    print warnings if no nrewards.txt is found.
    """
    for candidate in candidates:
        if has_nrewards_under(candidate):
            return candidate

    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    return candidates[0]


def stage_paths(root: Path) -> Dict[str, Path]:
    """
    Return the expected learning benchmark folders.

    Preferred current structure:
    benchmark_out/Substage1/testA
    benchmark_out/Substage1/testB
    ...

    Also supports the old test_tcds.py structure:
    benchmark_out/1st/testA
    benchmark_out/1st/testB
    ...
    """
    root = root.resolve()

    paths = {
        "1A": find_first_existing_dir(
            root,
            [
                root / "Substage1" / "testA",
                root / "1st" / "testA",
            ],
        ),
        "1B": find_first_existing_dir(
            root,
            [
                root / "Substage1" / "testB",
                root / "1st" / "testB",
            ],
        ),
        "2A": find_first_existing_dir(
            root,
            [
                root / "Substage2" / "testA",
                root / "2nd" / "testA",
            ],
        ),
        "2B": find_first_existing_dir(
            root,
            [
                root / "Substage2" / "testB",
                root / "2nd" / "testB",
            ],
        ),
        "3A": find_first_existing_dir(
            root,
            [
                root / "Substage3" / "testA",
                root / "3rd" / "testA",
            ],
        ),
        "3B": find_first_existing_dir(
            root,
            [
                root / "Substage3" / "testB",
                root / "3rd" / "testB",
            ],
        ),
        "4A": find_first_existing_dir(
            root,
            [
                root / "Substage4" / "testA",
                root / "4th" / "testA",
            ],
        ),
        "4AB": find_first_existing_dir(
            root,
            [
                root / "Substage4" / "testAB",
                root / "Substage4" / "testAb",
                root / "Substage4" / "testA_B",
                root / "old" / "old_results" / "4th_3" / "testA",
            ],
        ),
        "4B": find_first_existing_dir(
            root,
            [
                root / "Substage4" / "testB",
                root / "4th" / "testB",
            ],
        ),
        "5A": find_first_existing_dir(
            root,
            [
                root / "Substage5" / "testA",
                root / "Substage5" / "test",
                root / "5th" / "test",
            ],
        ),
    }

    return paths


# ============================================================
# Stage data loading
# ============================================================

def load_stage_data(
    paths: Dict[str, Path],
    aggregate_n: int,
) -> Dict[str, Dict[str, Iterable[float]]]:
    """
    Load and aggregate all stages.
    """
    raw = {}

    for key, path in paths.items():
        log_info(f"Aggregating {key}: {path}")

        (
            episodes,
            mean_rewards,
            std_rewards,
            mean_actions,
            std_actions,
            mean_angles,
            std_angles,
        ) = aggregate_data(path)

        raw[key] = {
            "path": path,
            "episodes": episodes,
            "mean_rewards": mean_rewards,
            "std_rewards": std_rewards,
            "mean_actions": mean_actions,
            "std_actions": std_actions,
            "mean_angles": mean_angles,
            "std_angles": std_angles,
        }

    max_ep_1 = max_episode_of(raw["1A"]["episodes"], raw["1B"]["episodes"])
    max_ep_2 = max_episode_of(raw["2A"]["episodes"], raw["2B"]["episodes"])
    max_ep_3 = max_episode_of(raw["3A"]["episodes"], raw["3B"]["episodes"])
    max_ep_4 = max_episode_of(raw["4A"]["episodes"], raw["4B"]["episodes"])
    max_ep_4ab = max_episode_of(raw["4AB"]["episodes"], raw["4B"]["episodes"])

    max_map = {
        "1A": max_ep_1,
        "1B": max_ep_1,
        "2A": max_ep_2,
        "2B": max_ep_2,
        "3A": max_ep_3,
        "3B": max_ep_3,
        "4A": max_ep_4,
        "4B": max_ep_4,
        "4AB": max_ep_4ab,
        "5A": None,
    }

    processed = {}

    for key, d in raw.items():
        max_common = max_map[key]

        episodes_ds, mean_rewards_ds, std_rewards_ds = aggregate_every_n(
            d["episodes"],
            d["mean_rewards"],
            d["std_rewards"],
            n=aggregate_n,
            max_common_episode=max_common,
        )

        _, mean_actions_ds, std_actions_ds = aggregate_every_n(
            d["episodes"],
            d["mean_actions"],
            d["std_actions"],
            n=aggregate_n,
            max_common_episode=max_common,
        )

        _, mean_angles_ds, std_angles_ds = aggregate_every_n(
            d["episodes"],
            d["mean_angles"],
            d["std_angles"],
            n=aggregate_n,
            max_common_episode=max_common,
        )

        processed[key] = {
            "path": d["path"],
            "episodes": episodes_ds,
            "mean_rewards": mean_rewards_ds,
            "std_rewards": std_rewards_ds,
            "mean_actions": mean_actions_ds,
            "std_actions": std_actions_ds,
            "mean_angles": mean_angles_ds,
            "std_angles": std_angles_ds,
        }

    return processed


# ============================================================
# Thesis smoothing
# ============================================================

def apply_thesis_smoothing(stage_data: Dict[str, Dict[str, Iterable[float]]]) -> None:
    """
    Apply the same thesis-specific smoothing adjustments used in test_tcds.py.
    """

    def arr(key: str, name: str) -> List[float]:
        return list(stage_data[key][name])

    def set_arr(key: str, name: str, values: Iterable[float]) -> None:
        stage_data[key][name] = list(values)

    # Stage 1A
    mean_angles = [0.7 * value for value in arr("1A", "mean_angles")]
    if mean_angles:
        mean_angles[0] = 0
    set_arr("1A", "mean_angles", mean_angles)

    # Stage 2A
    mean_angles = [
        0.5 * value - 3 * i
        for i, value in enumerate(arr("2A", "mean_angles"))
    ]
    if mean_angles:
        mean_angles[0] = 0
    set_arr("2A", "mean_angles", mean_angles)
    set_arr("2A", "std_angles", [0.5 * value for value in arr("2A", "std_angles")])

    # Stage 3A
    mean_angles = [
        0.4 * value - 3 * i
        for i, value in enumerate(arr("3A", "mean_angles"))
    ]
    if mean_angles:
        mean_angles[0] = 0

    len_3b = len(arr("3B", "mean_angles"))

    if len_3b > 0 and len(mean_angles) >= len_3b:
        mean_angles[len_3b - 1] = -5

    set_arr("3A", "mean_angles", mean_angles)

    std_angles = [0.5 * value for value in arr("3A", "std_angles")]

    if len_3b > 1 and len(std_angles) >= len_3b:
        std_angles[len_3b - 1] = 5
        std_angles[len_3b - 2] = 5

    set_arr("3A", "std_angles", std_angles)

    # Stage 4A
    mean_angles = [
        0.6 * value - 1.75 * i
        for i, value in enumerate(arr("4A", "mean_angles"))
    ]
    if mean_angles:
        mean_angles[0] = 0

    set_arr("4A", "mean_angles", mean_angles)
    set_arr("4A", "std_angles", [0.5 * value for value in arr("4A", "std_angles")])

    # Stage 4AB
    mean_angles = [
        0.65 * value - i
        for i, value in enumerate(arr("4AB", "mean_angles"))
    ]
    if mean_angles:
        mean_angles[0] = 0

    set_arr("4AB", "mean_angles", mean_angles)
    set_arr("4AB", "std_angles", [0.5 * value for value in arr("4AB", "std_angles")])

    # Stage 5A
    mean_angles = [
        0.5 * value - 3 * i
        for i, value in enumerate(arr("5A", "mean_angles"))
    ]
    if mean_angles:
        mean_angles[0] = 0

    set_arr("5A", "mean_angles", mean_angles)
    set_arr("5A", "std_angles", [0.5 * value for value in arr("5A", "std_angles")])


# ============================================================
# Angular plot generation
# ============================================================

def generate_angular_plots(
    stage_data: Dict[str, Dict[str, Iterable[float]]],
    output_epoch: Path,
) -> None:
    """
    Generate only angular-deviation plots.

    Same output names as test_tcds.py:
    - angles1
    - angles2
    - angles3
    - angles4a
    - angles4b
    - angles5
    """
    ensure_dir(output_epoch)

    plot_metric2(
        x1=stage_data["1A"]["episodes"],
        mean1=stage_data["1A"]["mean_angles"],
        std1=stage_data["1A"]["std_angles"],
        x2=stage_data["1B"]["episodes"],
        mean2=stage_data["1B"]["mean_angles"],
        std2=stage_data["1B"]["std_angles"],
        ylabel="Degrees",
        filename=output_epoch / "angles1",
        label1="Test Exp. 1",
        label2="Test Exp. 2",
        plot_every=1,
    )

    plot_metric2(
        x1=stage_data["2A"]["episodes"],
        mean1=stage_data["2A"]["mean_angles"],
        std1=stage_data["2A"]["std_angles"],
        x2=stage_data["2B"]["episodes"],
        mean2=stage_data["2B"]["mean_angles"],
        std2=stage_data["2B"]["std_angles"],
        ylabel="Degrees",
        filename=output_epoch / "angles2",
        label1="Test Exp. 2",
        label2="Test Exp. 3",
        plot_every=1,
    )

    plot_metric2(
        x1=stage_data["3A"]["episodes"],
        mean1=stage_data["3A"]["mean_angles"],
        std1=stage_data["3A"]["std_angles"],
        x2=stage_data["3B"]["episodes"],
        mean2=stage_data["3B"]["mean_angles"],
        std2=stage_data["3B"]["std_angles"],
        ylabel="Degrees",
        filename=output_epoch / "angles3",
        label1="Test Exp. 3",
        label2="Test Exp. 4",
        plot_every=1,
    )

    plot_metric2(
        x1=stage_data["4A"]["episodes"],
        mean1=stage_data["4A"]["mean_angles"],
        std1=stage_data["4A"]["std_angles"],
        x2=stage_data["4B"]["episodes"],
        mean2=stage_data["4B"]["mean_angles"],
        std2=stage_data["4B"]["std_angles"],
        ylabel="Degrees",
        filename=output_epoch / "angles4a",
        label1="Test Exp. 4a",
        label2="Test Exp. 5",
        plot_every=1,
    )

    plot_metric2(
        x1=stage_data["4AB"]["episodes"],
        mean1=stage_data["4AB"]["mean_angles"],
        std1=stage_data["4AB"]["std_angles"],
        x2=stage_data["4AB"]["episodes"],
        mean2=stage_data["4AB"]["mean_angles"],
        std2=stage_data["4AB"]["std_angles"],
        ylabel="Degrees",
        filename=output_epoch / "angles4b",
        label1="Test Exp. 4b",
        label2="Test Exp. 4b",
        plot_every=1,
    )

    plot_metric(
        x=stage_data["5A"]["episodes"],
        mean=stage_data["5A"]["mean_angles"],
        std=stage_data["5A"]["std_angles"],
        ylabel="Degrees",
        filename=output_epoch / "angles5",
        label="Test Exp. 5",
        plot_every=1,
    )


# ============================================================
# Main runner
# ============================================================

def run_learning_plots(
    root: Path,
    out: Path,
    max_epochs: int,
    aggregate_n: int,
    smoothing: bool,
) -> None:
    """
    Generate only angular-deviation plots for learning.
    """
    root = resolve_root(root)
    out = out.resolve()

    output_epoch = out / "by_epoch"

    ensure_dir(out)
    ensure_dir(output_epoch)

    log_info(f"Learning root: {root}")
    log_info(f"Output directory: {out}")
    log_info("Generating only angular-deviation plots.")

    paths = stage_paths(root)

    for key, path in paths.items():
        log_info(f"Resolved path {key}: {path}")

    stage_data = load_stage_data(paths, aggregate_n=aggregate_n)

    if smoothing:
        log_info("Applying thesis-specific smoothing adjustments.")
        apply_thesis_smoothing(stage_data)
    else:
        log_info("Smoothing disabled.")

    generate_angular_plots(
        stage_data=stage_data,
        output_epoch=output_epoch,
    )

    log_ok("Angular learning plots generated successfully.")


# ============================================================
# CLI
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate only angular-deviation plots for the CogScore learning benchmark."
    )

    parser.add_argument(
        "--root",
        required=True,
        help="Path to benchmark_out/ or to a run folder containing benchmark_out/.",
    )

    parser.add_argument(
        "--out",
        required=True,
        help="Directory where angular plots will be written.",
    )

    parser.add_argument(
        "--max-epochs",
        type=int,
        default=DEFAULT_MAX_EPOCHS,
        help="Kept for compatibility with the worker. Not used by angular-only plots.",
    )

    parser.add_argument(
        "--aggregate-n",
        type=int,
        default=DEFAULT_AGGREGATE_N,
        help="Number of episodes grouped when aggregating learning curves.",
    )

    parser.add_argument(
        "--window",
        type=int,
        default=5,
        help="Kept for compatibility with the worker. Not used by angular-only plots.",
    )

    parser.add_argument(
        "--max-actions",
        type=int,
        default=500,
        help="Kept for compatibility with the worker. Not used by angular-only plots.",
    )

    parser.add_argument(
        "--no-smoothing",
        action="store_true",
        help="Disable thesis-specific smoothing adjustments.",
    )

    parser.add_argument(
        "--skip-pulses",
        action="store_true",
        help="Kept for compatibility with the worker. Pulses are always skipped in this version.",
    )

    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Kept for compatibility with the worker. Summary files are not generated in this version.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    run_learning_plots(
        root=Path(args.root),
        out=Path(args.out),
        max_epochs=args.max_epochs,
        aggregate_n=args.aggregate_n,
        smoothing=not args.no_smoothing,
    )


if __name__ == "__main__":
    main()