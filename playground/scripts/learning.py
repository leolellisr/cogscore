#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DEFAULT_MAX_EPISODES = 50
DEFAULT_SMOOTH_WINDOW = 7
DEFAULT_STD_FALLBACK = 0.01

FOV_MIN_DEGREES = -30.0
FOV_MAX_DEGREES = 30.0

STRINGS_TO_REMOVE = [
    "Exp number:", "Action num: ", "Battery:", "reward: ", "num_tables:",
    "Curiosity_lv: ", "Curiosity_lv:", "Red: ", "Green: ", "Blue: ",
    "Red:", "Green:", "Blue:", "action:", "mot_value: ", "r_imp: ",
    "g_imp: ", "b_imp: ", "hug_drive: ", "cur_drive: ", " QTables:",
    "cur_a: ", "sur_a: ", "Exp:", "Nact:", "Type:", "cur_a:",
    "sur_a:", "exp_c:", "exp_s:", "dSurV:", "SurV:", "dCurV:",
    "CurV:", "QTables:", "Ri:", "Ri S:", "Ri C:", "G_Reward S:",
    "G_Reward C:", "G_Reward:", " LastAct:", "Act C:", "Act S:",
    "color1:", "Pos1:", "Pos2:", "fov:", "HeadPitch:", "NeckYaw:",
    "color2:", "fov_y:", "MaxSalValue:", "fov_p:", "Field:",
    "Memory:", ",", "]",
]


def log(level: str, message: str) -> None:
    print(f"[{level}] {message}")


def safe_name(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in value.strip())


def clean_line(line: str) -> str:
    for token in STRINGS_TO_REMOVE:
        line = line.replace(token, "")
    return line


def infer_yaw_pitch_columns(cols: list[str]) -> tuple[int, int]:
    yaw_col, pitch_col = 19, 20
    if 22 < len(cols) < 26:
        yaw_col, pitch_col = 21, 22
    elif len(cols) > 25:
        yaw_col, pitch_col = 23, 24
    return yaw_col, pitch_col


def read_nrewards(path: Path) -> dict[int, float]:
    """Return mean angular deviation for each episode in one run/seed file."""
    angles_by_episode: dict[int, list[float]] = defaultdict(list)

    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        lines = handle.readlines()[1:]

    for raw_line in lines:
        cols = clean_line(raw_line).split()
        if len(cols) < 22:
            continue
        try:
            yaw_col, pitch_col = infer_yaw_pitch_columns(cols)
            episode = int(float(cols[1]))
            yaw = float(cols[yaw_col])
            pitch = float(cols[pitch_col])
        except (ValueError, IndexError):
            continue
        angles_by_episode[episode].append(math.hypot(yaw, pitch))

    return {
        episode: float(np.mean(values))
        for episode, values in sorted(angles_by_episode.items())
        if values
    }


def seed_key(path: Path, experiment_dir: Path) -> str:
    """Identify one independent run while preferring profile over data duplicates."""
    relative = path.relative_to(experiment_dir)
    parts = relative.parts
    if len(parts) >= 3 and parts[-2] in {"profile", "data"}:
        return "/".join(parts[:-2]) or parts[-3]
    return "/".join(parts[:-1]) or path.parent.name


def select_run_files(experiment_dir: Path) -> list[Path]:
    files = sorted(experiment_dir.rglob("nrewards.txt"))

    def priority(path: Path) -> tuple[int, str]:
        if path.parent.name == "profile":
            return 0, str(path)
        if path.parent.name == "data":
            return 1, str(path)
        return 2, str(path)

    selected: dict[str, Path] = {}
    for path in sorted(files, key=priority):
        selected.setdefault(seed_key(path, experiment_dir), path)
    return sorted(selected.values())


def discover_agent_experiments(root: Path) -> dict[str, dict[str, Path]]:
    """
    Expected structure:
        ROOT/AGENT/EXPERIMENT/**/nrewards.txt

    AGENT and EXPERIMENT names are taken directly from the first two directory
    levels below ROOT. Deeper levels may contain seeds, profile, or data folders.
    """
    discovered: dict[str, dict[str, Path]] = defaultdict(dict)
    if not root.is_dir():
        return {}

    for agent_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        for experiment_dir in sorted(p for p in agent_dir.iterdir() if p.is_dir()):
            if any(experiment_dir.rglob("nrewards.txt")):
                discovered[agent_dir.name][experiment_dir.name] = experiment_dir
    return dict(discovered)


def smooth_nan(values: np.ndarray, window: int) -> np.ndarray:
    if window <= 1 or len(values) <= 2:
        return values.copy()
    window = int(window)
    if window % 2 == 0:
        window += 1
    half = window // 2
    out = np.full_like(values, np.nan, dtype=float)
    for i in range(len(values)):
        lo, hi = max(0, i - half), min(len(values), i + half + 1)
        chunk = values[lo:hi]
        if np.isfinite(chunk).any():
            out[i] = np.nanmean(chunk)
    return out


def aggregate_experiment(
    experiment_dir: Path,
    max_episodes: Optional[int],
    smooth_window: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int]:
    run_files = select_run_files(experiment_dir)
    run_series: list[dict[int, float]] = []

    for path in run_files:
        series = read_nrewards(path)
        if series:
            run_series.append(series)
        else:
            log("WARN", f"No readable angular data in {path}")

    if not run_series:
        return np.array([]), np.array([]), np.array([]), 0

    episodes = sorted(set().union(*(series.keys() for series in run_series)))
    if max_episodes is not None and max_episodes > 0:
        episodes = [ep for ep in episodes if ep <= max_episodes]

    matrix = np.full((len(run_series), len(episodes)), np.nan, dtype=float)
    episode_to_col = {episode: idx for idx, episode in enumerate(episodes)}

    for row, series in enumerate(run_series):
        for episode, value in series.items():
            col = episode_to_col.get(episode)
            if col is not None:
                matrix[row, col] = value

    with np.errstate(invalid="ignore", divide="ignore"):
        mean = np.nanmean(matrix, axis=0)

    # Sample standard deviation across independent runs.  With fewer than two
    # observations the deviation is not estimable, so use the thesis-wide
    # fallback requested by the analysis protocol.
    std = np.full(len(episodes), DEFAULT_STD_FALLBACK, dtype=float)
    finite_counts = np.sum(np.isfinite(matrix), axis=0)
    for col, count in enumerate(finite_counts):
        if count >= 2:
            candidate = float(np.nanstd(matrix[:, col], ddof=1))
            if np.isfinite(candidate) and candidate >= 0.0:
                std[col] = candidate

    mean = smooth_nan(mean, smooth_window)
    return np.asarray(episodes, dtype=float), mean, std, len(run_series)


def build_dataset(
    discovered: dict[str, dict[str, Path]],
    max_episodes: Optional[int],
    smooth_window: int,
) -> dict[str, dict[str, dict[str, object]]]:
    dataset: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    for agent, experiments in discovered.items():
        for experiment, path in experiments.items():
            x, mean, std, run_count = aggregate_experiment(path, max_episodes, smooth_window)
            if len(x) == 0:
                continue
            dataset[agent][experiment] = {
                "x": x, "mean": mean, "std": std,
                "run_count": run_count, "path": path,
            }
            log("INFO", f"{agent} / {experiment}: {run_count} run(s), {len(x)} episode(s)")
    return dict(dataset)


def draw_curve(
    ax: plt.Axes,
    series: dict[str, object],
    label: str,
) -> None:
    x = np.asarray(series["x"], dtype=float)
    mean = np.asarray(series["mean"], dtype=float)
    std = np.asarray(series["std"], dtype=float)

    valid = np.isfinite(x) & np.isfinite(mean)

    if not valid.any():
        return

    x = x[valid]
    mean = mean[valid]
    std = std[valid]

    std = np.asarray(std, dtype=float)
    invalid_std = ~np.isfinite(std) | (std < 0.0)
    std[invalid_std] = DEFAULT_STD_FALLBACK

    line, = ax.plot(
        x,
        mean,
        linewidth=2.0,
        label=label,
        zorder=3,
    )

    color = line.get_color()

    # Explicit +/- 1 SD error bars at every plotted episode.
    ax.errorbar(
        x,
        mean,
        yerr=std,
        fmt="none",
        ecolor=color,
        elinewidth=0.9,
        capsize=2.5,
        capthick=0.9,
        alpha=0.60,
        zorder=4,
        label="_nolegend_",
    )

    lower = mean - std
    upper = mean + std

    ax.fill_between(
        x,
        lower,
        upper,
        color=color,
        alpha=0.28,
        linewidth=0,
        zorder=2,
    )

def finish_plot(
    ax: plt.Axes,
    title: str,
) -> None:
    # Como o gráfico mostra magnitude do desvio,
    # o intervalo angular -30° a +30° corresponde
    # à região de erro entre 0° e 30°.
    ax.axhspan(
        0.0,
        FOV_MAX_DEGREES,
        color="gray",
        alpha=0.16,
        zorder=0,
        label="FOV [-30°, +30°]",
    )

    ax.axhline(
        FOV_MAX_DEGREES,
        color="gray",
        linestyle="--",
        linewidth=1.2,
        zorder=1,
    )

    ax.set_title(title)
    ax.set_xlabel("Episode")
    ax.set_ylabel("Mean angular deviation (degrees)")
    ax.set_ylim(bottom=0)

    ax.grid(
        True,
        alpha=0.25,
        zorder=1,
    )

    ax.legend(
        loc="best",
        fontsize=8,
    )

def save_figure(fig: plt.Figure, base_path: Path, save_pdf: bool) -> None:
    base_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    png_path = base_path.with_suffix(".png")
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    log("SAVED", str(png_path))
    if save_pdf:
        pdf_path = base_path.with_suffix(".pdf")
        fig.savefig(pdf_path, bbox_inches="tight")
        log("SAVED", str(pdf_path))
    plt.close(fig)


def plot_by_experiment(dataset: dict[str, dict[str, dict[str, object]]], out: Path, save_pdf: bool) -> None:
    experiments = sorted({exp for exps in dataset.values() for exp in exps})
    for experiment in experiments:
        fig, ax = plt.subplots(figsize=(11, 6))
        count = 0
        for agent in sorted(dataset):
            series = dataset[agent].get(experiment)
            if series is None:
                continue
            draw_curve(ax, series, f"{agent}")
            count += 1
        if count == 0:
            plt.close(fig)
            continue
        finish_plot(ax, f"Angular deviation by agent - {experiment}")
        save_figure(fig, out / "by_experiment" / f"{safe_name(experiment)}_all_agents", save_pdf)


def plot_by_agent(dataset: dict[str, dict[str, dict[str, object]]], out: Path, save_pdf: bool) -> None:
    for agent, experiments in sorted(dataset.items()):
        fig, ax = plt.subplots(figsize=(11, 6))
        count = 0
        for experiment, series in sorted(experiments.items()):
            draw_curve(ax, series, f"{experiment}")
            count += 1
        if count == 0:
            plt.close(fig)
            continue
        finish_plot(ax, f"Angular deviation by experiment - {agent}")
        save_figure(fig, out / "by_agent" / f"{safe_name(agent)}_all_experiments", save_pdf)


def write_manifest(dataset: dict[str, dict[str, dict[str, object]]], out: Path) -> None:
    path = out / "learning_plot_manifest.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write("agent,experiment,runs,episodes,source_directory\n")
        for agent, experiments in sorted(dataset.items()):
            for experiment, series in sorted(experiments.items()):
                handle.write(
                    f'"{agent}","{experiment}",{series["run_count"]},'
                    f'{len(series["x"])},"{series["path"]}"\n'
                )
    log("SAVED", str(path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Plot learning angular deviation from ROOT/AGENT/EXPERIMENT folders. "
            "Creates one plot per experiment comparing agents and one plot per "
            "agent comparing experiments. Curves show mean +/- standard deviation."
        )
    )
    parser.add_argument("--root", type=Path, required=True,
                        help="Root containing AGENT/EXPERIMENT directories.")
    parser.add_argument("--out", type=Path, required=True,
                        help="Output directory for plots.")
    parser.add_argument("--max-episodes", "--max-epochs", dest="max_episodes",
                        type=int, default=DEFAULT_MAX_EPISODES,
                        help="Maximum episode number included. Use 0 for all.")
    parser.add_argument("--smooth-window", "--window", dest="smooth_window",
                        type=int, default=DEFAULT_SMOOTH_WINDOW,
                        help="Centered smoothing window applied to mean and std. Use 1 to disable.")
    parser.add_argument("--no-smoothing", action="store_true",
                        help="Disable smoothing.")
    parser.add_argument("--png-only", action="store_true",
                        help="Save PNG only instead of PNG and PDF.")
    # Backward-compatible accepted option; no episode chunking is needed here.
    parser.add_argument("--aggregate-n", type=int, default=1,
                        help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    out = args.out.resolve()
    smooth_window = 1 if args.no_smoothing else max(1, args.smooth_window)
    max_episodes = None if args.max_episodes <= 0 else args.max_episodes

    discovered = discover_agent_experiments(root)
    if not discovered:
        log("ERROR", f"No ROOT/AGENT/EXPERIMENT/**/nrewards.txt data found under {root}")
        return 2

    log("INFO", f"Discovered {len(discovered)} agent(s)")
    dataset = build_dataset(discovered, max_episodes, smooth_window)
    if not dataset:
        log("ERROR", "No readable angular-deviation series were found")
        return 3

    plot_by_experiment(dataset, out, save_pdf=not args.png_only)
    plot_by_agent(dataset, out, save_pdf=not args.png_only)
    write_manifest(dataset, out)
    log("OK", "Learning angular plots generated successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
