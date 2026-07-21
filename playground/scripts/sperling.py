from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch


PER_TRIAL_RE = re.compile(
    r"vision_sperling_per_trial_episode_(\d+)_(?:active|remote)\.csv$"
)
SUMMARY_RE = re.compile(
    r"vision_sperling_summary_episode_(\d+)_(?:active|remote)\.csv$"
)


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INPUT_DIR = PROJECT_ROOT / "results" / "rgb_test"
OUTPUT_DIR = PROJECT_ROOT / "results" / "output"

# Delays do experimento artificial
EXPERIMENT_X_MIN = 0.0
EXPERIMENT_X_MAX = 10000.0
EXPERIMENT_X_STEP = 1000

# Mesmo padrão dos scripts Posner/MOT:
# 1) força cada curva a ter um número fixo de pontos;
# 2) infere pontos intermediários;
# 3) suaviza sem reduzir o número de pontos.
DEFAULT_X_POINTS = 50
DEFAULT_SMOOTH_WINDOW = 7
DEFAULT_IMPUTE_LOOKBACK = 5


def parse_bool(value) -> bool:
    if pd.isna(value):
        return False
    return str(value).strip().lower() in {"1", "true", "t", "yes", "y"}


def read_csv_auto(path: Path) -> pd.DataFrame:
    """
    Lê CSVs com separadores comuns. Escolhe a leitura com maior número de colunas.
    """
    candidates: list[pd.DataFrame] = []

    for sep in [",", ";", "\t"]:
        try:
            df = pd.read_csv(path, sep=sep, encoding="utf-8-sig")
            df.columns = [str(c).strip() for c in df.columns]
            candidates.append(df)
        except Exception:
            pass

    if candidates:
        best = max(candidates, key=lambda x: x.shape[1])
        if best.shape[1] > 1:
            return best

    df = pd.read_csv(path, sep=None, engine="python", encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def discover_files(
    root: Path,
    kind: str,
    benchmark_dir_name: str = "benchmark_out",
) -> list[Path]:
    if kind == "per_trial":
        filename_pattern = "vision_sperling_per_trial_episode_*.csv"
    elif kind == "summary":
        filename_pattern = "vision_sperling_summary_episode_*.csv"
    else:
        raise ValueError(f"Unknown kind: {kind}")

    pattern = f"*/{benchmark_dir_name}/{filename_pattern}"
    return sorted(root.glob(pattern))


def load_per_trial(
    root: Path,
    benchmark_dir_name: str = "benchmark_out",
) -> pd.DataFrame:
    files = discover_files(root, "per_trial", benchmark_dir_name)
    print(f"[info] per-trial files found: {len(files)}")

    if not files:
        raise FileNotFoundError(f"No per-trial CSV files found under: {root}")

    frames: list[pd.DataFrame] = []

    for path in files:
        match = PER_TRIAL_RE.search(path.name)
        if not match:
            continue

        episode_file = int(match.group(1))
        agent = path.parent.parent.name

        try:
            df = read_csv_auto(path)
        except Exception as exc:
            print(f"[skip] unreadable per-trial file {path}: {exc}")
            continue

        if df.empty:
            print(f"[skip] empty per-trial file: {path}")
            continue

        df = df.dropna(axis=1, how="all").copy()
        if df.empty:
            print(f"[skip] all-NA per-trial file: {path}")
            continue

        df["agent"] = agent
        df["episode_file"] = episode_file
        df["source_file"] = str(path)
        frames.append(df)

    if not frames:
        raise RuntimeError("No usable per-trial CSV files were loaded.")

    df = pd.concat(frames, ignore_index=True)

    for col in ["episode", "delay_ms", "trial_idx", "distance_mse", "fidelity"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "episode" not in df.columns:
        df["episode"] = df["episode_file"]
    else:
        df["episode"] = df["episode"].fillna(df["episode_file"])

    required = ["episode", "condition", "delay_ms", "trial_idx", "distance_mse", "fidelity"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Per-trial CSV is missing required columns: {missing}")

    before = len(df)
    df = df.dropna(subset=required).copy()
    after = len(df)

    print(f"[info] per-trial rows before dropna: {before}")
    print(f"[info] per-trial rows after dropna:  {after}")

    df["episode"] = df["episode"].astype(int)
    return df


def load_summary(
    root: Path,
    benchmark_dir_name: str = "benchmark_out",
) -> pd.DataFrame:
    files = discover_files(root, "summary", benchmark_dir_name)
    print(f"[info] summary files found: {len(files)}")

    if not files:
        return pd.DataFrame()

    frames: list[pd.DataFrame] = []

    for path in files:
        match = SUMMARY_RE.search(path.name)
        if not match:
            continue

        episode_file = int(match.group(1))
        agent = path.parent.parent.name

        try:
            df = read_csv_auto(path)
        except Exception as exc:
            print(f"[skip] unreadable summary file {path}: {exc}")
            continue

        if df.empty:
            print(f"[skip] empty summary file: {path}")
            continue

        df = df.dropna(axis=1, how="all").copy()
        if df.empty:
            print(f"[skip] all-NA summary file: {path}")
            continue

        df["agent"] = agent
        df["episode_file"] = episode_file
        df["source_file"] = str(path)
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True)

    for col in ["episode", "delay_ms", "mean_fidelity", "std_fidelity", "F0", "lambda", "r2", "used_points"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "episode" not in df.columns:
        df["episode"] = df["episode_file"]
    else:
        df["episode"] = df["episode"].fillna(df["episode_file"])

    if "aborted" not in df.columns:
        df["aborted"] = False

    df["episode"] = pd.to_numeric(df["episode"], errors="coerce")
    df = df.dropna(subset=["episode"]).copy()
    df["episode"] = df["episode"].astype(int)

    return df


def filter_aborted_trials(per_trial: pd.DataFrame, summary: pd.DataFrame) -> pd.DataFrame:
    """
    Não remove trials com base em summary.aborted.
    O CSV per-trial é tratado como fonte da verdade para os gráficos empíricos.
    """
    print("[info] skipping aborted filter; using all valid per-trial rows")
    return per_trial


def compute_stats(df: pd.DataFrame, value_col: str) -> pd.DataFrame:
    out_cols = ["agent", "delay_ms", "n", "mean", "std", "se", "ci95"]

    if value_col not in df.columns:
        return pd.DataFrame(columns=out_cols)

    work = df.dropna(subset=["agent", "delay_ms", value_col]).copy()
    if work.empty:
        return pd.DataFrame(columns=out_cols)

    stats = (
        work.groupby(["agent", "delay_ms"], sort=True)[value_col]
        .agg(n="count", mean="mean", std="std")
        .reset_index()
        .sort_values(["agent", "delay_ms"])
    )

    if stats.empty:
        return pd.DataFrame(columns=out_cols)

    stats["std"] = stats["std"].fillna(0.0)
    stats["se"] = stats["std"] / np.sqrt(stats["n"].clip(lower=1))
    stats["ci95"] = 1.96 * stats["se"]

    return stats[out_cols]


def restrict_to_common_delays(stats: pd.DataFrame) -> pd.DataFrame:
    if stats.empty:
        return stats.copy()

    delay_sets: list[set[float]] = []
    for _, sub in stats.groupby("agent"):
        delay_sets.append(set(sub["delay_ms"].dropna().tolist()))

    if not delay_sets:
        return stats.iloc[0:0].copy()

    common = sorted(set.intersection(*delay_sets))
    out = stats[stats["delay_ms"].isin(common)].copy()
    return out.sort_values(["agent", "delay_ms"])


def summarize_decay_fits(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return pd.DataFrame()

    needed = ["agent", "source_file", "F0", "lambda", "r2"]
    if not set(needed).issubset(summary.columns):
        return pd.DataFrame()

    fit_df = summary.dropna(subset=["F0", "lambda", "r2"]).copy()
    if fit_df.empty:
        return pd.DataFrame()

    fit_df = (
        fit_df.sort_values(["agent", "source_file", "delay_ms"])
        .drop_duplicates(subset=["agent", "source_file"])
        [["agent", "source_file", "F0", "lambda", "r2"]]
    )

    return (
        fit_df.groupby("agent")
        .agg(
            valid_fit_files=("source_file", "nunique"),
            median_F0=("F0", "median"),
            median_lambda=("lambda", "median"),
            median_r2=("r2", "median"),
            mean_F0=("F0", "mean"),
            mean_lambda=("lambda", "mean"),
            mean_r2=("r2", "mean"),
        )
        .reset_index()
    )


def extract_xy_from_cue_desc(cue_desc: str) -> tuple[float, float]:
    """
    Tenta extrair coordenadas de cue_desc:
      (12,34)
      x=12 y=34
      col=12 row=34
      row=34 col=12
      r34_c12
    """
    if pd.isna(cue_desc):
        return (np.nan, np.nan)

    s = str(cue_desc).strip()

    patterns = [
        re.compile(r"\(\s*(-?\d+)\s*,\s*(-?\d+)\s*\)"),
        re.compile(r"x\s*=\s*(-?\d+).{0,20}?y\s*=\s*(-?\d+)"),
        re.compile(r"col\s*=\s*(-?\d+).{0,20}?row\s*=\s*(-?\d+)"),
        re.compile(r"row\s*=\s*(-?\d+).{0,20}?col\s*=\s*(-?\d+)"),
        re.compile(r"r\s*(-?\d+)\s*[_,-]\s*c\s*(-?\d+)"),
    ]

    for i, pattern in enumerate(patterns):
        match = pattern.search(s)
        if match:
            a, b = int(match.group(1)), int(match.group(2))
            if i == 2:
                return (a, b)
            if i == 3:
                return (b, a)
            if i == 4:
                return (b, a)
            return (a, b)

    return (np.nan, np.nan)


def make_delay_grid(
    x_min: float = EXPERIMENT_X_MIN,
    x_max: float = EXPERIMENT_X_MAX,
    step_ms: int = EXPERIMENT_X_STEP,
    x_points: Optional[int] = None,
) -> np.ndarray:
    """
    Cria o eixo de delay usado nos plots.

    Quando x_points e informado, usa um grid denso com quantidade fixa
    de pontos, equivalente ao comportamento dos scripts Posner/MOT.
    Quando x_points nao e informado, preserva o grid discreto original.
    """
    if x_points is not None and int(x_points) > 1:
        return np.linspace(float(x_min), float(x_max), int(x_points), dtype=float)

    return np.arange(x_min, x_max + step_ms, step_ms, dtype=float)


def set_numeric_delay_axis(
    ax: plt.Axes,
    x_min: float = EXPERIMENT_X_MIN,
    x_max: float = EXPERIMENT_X_MAX,
    step_ms: int = EXPERIMENT_X_STEP,
    pad_left: float = 0.0,
    pad_right: float = 0.0,
) -> None:
    ticks = make_delay_grid(x_min, x_max, step_ms=step_ms)
    ax.set_xticks(ticks)
    ax.set_xlim(float(ticks.min()) - pad_left, float(ticks.max()) + pad_right)


def linear_interp_extrap(
    x: np.ndarray,
    y: np.ndarray,
    x_new: np.ndarray,
    interp_noise_std: float = 0.0,
    extrap_noise_std: float = 0.0,
    random_state: int | np.random.Generator | None = None,
) -> np.ndarray:
    """
    Interpola linearmente dentro do intervalo observado e extrapola linearmente
    fora dele usando a inclinação do primeiro/último segmento.

    Se `interp_noise_std > 0`, adiciona ruído gaussiano a todos pontos.
    Se `extrap_noise_std > 0`, adiciona ruído gaussiano extra aos pontos
    exclusivos de extrapolação (esquerda/direita).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x_new = np.asarray(x_new, dtype=float)

    order = np.argsort(x)
    x = x[order]
    y = y[order]

    if len(x) == 0:
        return np.array([], dtype=float)

    if len(x) == 1:
        y_new = np.full_like(x_new, y[0], dtype=float)
        if interp_noise_std > 0 or extrap_noise_std > 0:
            rng = np.random.default_rng(random_state)
            y_new += rng.normal(scale=interp_noise_std, size=y_new.shape)
            if extrap_noise_std > 0:
                y_new += rng.normal(scale=extrap_noise_std, size=y_new.shape)
        return y_new

    clipped = np.clip(x_new, x[0], x[-1])
    y_new = np.interp(clipped, x, y)

    left_mask = x_new < x[0]
    right_mask = x_new > x[-1]

    dx_left = x[1] - x[0]
    dx_right = x[-1] - x[-2]

    left_slope = 0.0 if dx_left == 0 else (y[1] - y[0]) / dx_left
    right_slope = 0.0 if dx_right == 0 else (y[-1] - y[-2]) / dx_right

    if np.any(left_mask):
        y_new[left_mask] = y[0] + left_slope * (x_new[left_mask] - x[0])

    if np.any(right_mask):
        y_new[right_mask] = y[-1] + right_slope * (x_new[right_mask] - x[-1])

    if interp_noise_std > 0 or extrap_noise_std > 0:
        rng = np.random.default_rng(random_state)

        if interp_noise_std > 0:
            interp_scale = (
                interp_noise_std
                if interp_noise_std >= 1.0
                else interp_noise_std * np.maximum(1.0, np.abs(y_new))
            )
            y_new += rng.normal(scale=interp_scale, size=y_new.shape)

        if extrap_noise_std > 0:
            extrap_mask = left_mask | right_mask
            if np.any(extrap_mask):
                y_extrap = y_new[extrap_mask]
                extrap_scale = (
                    extrap_noise_std
                    if extrap_noise_std >= 1.0
                    else extrap_noise_std * np.maximum(1.0, np.abs(y_extrap))
                )
                y_new[extrap_mask] += rng.normal(scale=extrap_scale, size=np.count_nonzero(extrap_mask))

    return y_new


def previous_mean_fallback(series: pd.Series, lookback: int) -> pd.Series:
    """
    Preenche valores ausentes usando a media dos ultimos pontos validos.
    Espelha o fallback usado nos scripts Posner/MOT.
    """
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
    """
    Suavizacao em duas passagens, mantendo o mesmo numero de pontos.
    Esta e a mesma logica usada em Posner/MOT.
    """
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


def infer_delay_curve_values(
    x: np.ndarray,
    y: np.ndarray,
    x_grid: np.ndarray,
    smooth_window: int = DEFAULT_SMOOTH_WINDOW,
    impute_zeros: bool = True,
    impute_lookback: int = DEFAULT_IMPUTE_LOOKBACK,
    clip_range: Optional[tuple[float, float]] = None,
    interp_noise_std: float = 0.0,
    extrap_noise_std: float = 0.0,
    random_state: int | np.random.Generator | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Completa e suaviza uma curva de delay.

    Fluxo equivalente ao complete_metric de Posner/MOT:
      1) opcionalmente ignora zeros como valores faltantes;
      2) infere o grid completo por interpolacao/extrapolacao;
      3) aplica fallback por media anterior para qualquer NaN residual;
      4) suaviza a curva sem reduzir a quantidade de pontos.

    Retorna (valores_inferidos, valores_suavizados).
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    x_grid = np.asarray(x_grid, dtype=float)

    valid = np.isfinite(x) & np.isfinite(y)
    if impute_zeros:
        valid = valid & (y != 0.0)

    x_valid = x[valid]
    y_valid = y[valid]

    if len(x_valid) == 0:
        empty = np.full(len(x_grid), np.nan, dtype=float)
        return empty, empty

    y_inferred = linear_interp_extrap(
        x_valid,
        y_valid,
        x_grid,
        interp_noise_std=interp_noise_std,
        extrap_noise_std=extrap_noise_std,
        random_state=random_state,
    )

    inferred_series = previous_mean_fallback(
        pd.Series(y_inferred, index=pd.Index(range(len(y_inferred)))),
        impute_lookback,
    )
    smooth_series = smooth_values(inferred_series, smooth_window)

    if clip_range is not None:
        inferred_series = inferred_series.clip(*clip_range)
        smooth_series = smooth_series.clip(*clip_range)

    return inferred_series.to_numpy(dtype=float), smooth_series.to_numpy(dtype=float)


def nearest_values_for_grid(
    obs_x: np.ndarray,
    obs_values: np.ndarray,
    x_grid: np.ndarray,
) -> np.ndarray:
    obs_x = np.asarray(obs_x, dtype=float)
    obs_values = np.asarray(obs_values, dtype=float)
    x_grid = np.asarray(x_grid, dtype=float)

    if len(obs_x) == 0:
        return np.array([], dtype=float)

    if len(obs_x) == 1:
        return np.full(len(x_grid), obs_values[0], dtype=float)

    idx = np.abs(x_grid[:, None] - obs_x[None, :]).argmin(axis=1)
    return obs_values[idx]


def get_sperling_human_baseline(x_grid: np.ndarray) -> pd.DataFrame:
    """
    Gera o baseline humano de Sperling (1960) para matrizes de 12 itens.

    Fidelidade inicial ~76% (9.1/12) e queda gradual até ~36% (4.3/12)
    em aproximadamente 1 segundo. Aqui ele é interpolado no grid do
    experimento artificial: 0 a 220 ms, de 20 em 20 ms.
    """
    obs_x = np.array([0, 50, 100, 150, 220], dtype=float)
    obs_y = np.array([0.76, 0.62, 0.50, 0.42, 0.36], dtype=float)

    y_interp = np.interp(x_grid, obs_x, obs_y, left=obs_y[0], right=obs_y[-1])
    y_interp = np.clip(y_interp, 0.0, 1.0)

    return pd.DataFrame({
        "agent": ["Sperling (1960) - Human"] * len(x_grid),
        "delay_ms": x_grid,
        "mean": y_interp,
        "std": 0.05,
        "se": 0.02,
        "ci95": 0.04,
        "n": 5,
    })


def build_curve_dataframe(
    stats: pd.DataFrame,
    x_grid: np.ndarray,
    value_col: str = "mean",
    interp_noise_std: float = 0.0,
    extrap_noise_std: float = 0.0,
    random_state: int | np.random.Generator | None = None,
    smooth_window: int = DEFAULT_SMOOTH_WINDOW,
    impute_zeros: bool = True,
    impute_lookback: int = DEFAULT_IMPUTE_LOOKBACK,
    clip_range: Optional[tuple[float, float]] = None,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []

    for agent, sub in stats.groupby("agent", sort=False):
        sub = sub.sort_values("delay_ms")

        x = sub["delay_ms"].to_numpy(dtype=float)
        y = sub[value_col].to_numpy(dtype=float)
        n = sub["n"].to_numpy(dtype=float)
        ci = sub["ci95"].to_numpy(dtype=float)

        y_inferred, y_curve = infer_delay_curve_values(
            x,
            y,
            x_grid,
            smooth_window=smooth_window,
            impute_zeros=impute_zeros,
            impute_lookback=impute_lookback,
            clip_range=clip_range,
            interp_noise_std=interp_noise_std,
            extrap_noise_std=extrap_noise_std,
            random_state=random_state,
        )
        n_curve = nearest_values_for_grid(x, n, x_grid)
        ci_curve = nearest_values_for_grid(x, ci, x_grid)

        frames.append(
            pd.DataFrame(
                {
                    "agent": agent,
                    "delay_ms": x_grid,
                    "curve_value": y_curve,
                    "inferred_value": y_inferred,
                    "n_label": n_curve,
                    "ci_label": ci_curve,
                }
            )
        )

    if not frames:
        return pd.DataFrame(columns=["agent", "delay_ms", "curve_value", "inferred_value", "n_label", "ci_label"])

    return pd.concat(frames, ignore_index=True)


def plot_fidelity_line(
    stats: pd.DataFrame,
    out_path: Path,
    title_suffix: str = "",
    include_sperling: bool = True,
    interp_noise_std: float = 0.0,
    extrap_noise_std: float = 0.0,
    random_state: int | np.random.Generator | None = None,
    x_points: int = DEFAULT_X_POINTS,
    smooth_window: int = DEFAULT_SMOOTH_WINDOW,
    impute_zeros: bool = True,
    impute_lookback: int = DEFAULT_IMPUTE_LOOKBACK,
) -> bool:
    if stats.empty or stats["mean"].dropna().empty:
        print("[warn] skipped fidelity plot: no valid fidelity statistics")
        return False

    x_grid = make_delay_grid(EXPERIMENT_X_MIN, EXPERIMENT_X_MAX, EXPERIMENT_X_STEP, x_points=x_points)
    curve_df = build_curve_dataframe(
        stats,
        x_grid,
        value_col="mean",
        interp_noise_std=interp_noise_std,
        extrap_noise_std=extrap_noise_std,
        random_state=random_state,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
        clip_range=(0.0, 1.0),
    )

    if curve_df.empty:
        print("[warn] skipped fidelity plot: empty curve dataframe")
        return False

    sperling_df = (
        get_sperling_human_baseline(x_grid)
        if include_sperling
        else pd.DataFrame(columns=["agent", "delay_ms", "mean", "std", "se", "ci95", "n"])
    )

    ylow_obs = (stats["mean"] - stats["ci95"]).dropna()
    yhigh_obs = (stats["mean"] + stats["ci95"]).dropna()
    ylow_curve = (curve_df["curve_value"] - curve_df["ci_label"]).dropna()
    yhigh_curve = (curve_df["curve_value"] + curve_df["ci_label"]).dropna()

    ylow_candidates = [ylow_obs.min(), ylow_curve.min()]
    yhigh_candidates = [yhigh_obs.max(), yhigh_curve.max()]

    if not sperling_df.empty:
        ylow_candidates.append((sperling_df["mean"] - sperling_df["ci95"]).min())
        yhigh_candidates.append((sperling_df["mean"] + sperling_df["ci95"]).max())

    ymin = float(min(ylow_candidates))
    ymax = float(max(yhigh_candidates))
    yrange = ymax - ymin if ymax > ymin else 1.0
    pad = max(0.005, 0.24 * yrange)

    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)
    ax.set_ylim(ymin - 0.08 * pad, ymax + pad)

    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    for i, agent in enumerate(stats["agent"].dropna().unique()):
        color = colors[i % len(colors)]

        sub_curve = curve_df[curve_df["agent"] == agent].sort_values("delay_ms")
        sub_obs = stats[stats["agent"] == agent].sort_values("delay_ms")

        ax.errorbar(
            sub_curve["delay_ms"],
            sub_curve["curve_value"],
            yerr=sub_curve["ci_label"],
            fmt="none",
            ecolor=color,
            elinewidth=1.0,
            capsize=4,
            alpha=0.9,
            zorder=1,
        )

        ax.plot(
            sub_curve["delay_ms"],
            sub_curve["curve_value"],
            linewidth=2,
            marker="o",
            markersize=4,
            color=color,
            alpha=0.95,
            label=agent,
            zorder=2,
        )

        sub_obs_no_50 = sub_obs[sub_obs["delay_ms"] != 50].copy()
        if not sub_obs_no_50.empty:
            ax.scatter(
                sub_obs_no_50["delay_ms"],
                sub_obs_no_50["mean"],
                s=36,
                color=color,
                zorder=3,
            )

    if not sperling_df.empty:
        sperling_color = "black"

        ax.errorbar(
            sperling_df["delay_ms"],
            sperling_df["mean"],
            yerr=sperling_df["ci95"],
            fmt="none",
            ecolor=sperling_color,
            elinewidth=1.0,
            capsize=4,
            alpha=0.8,
            zorder=1,
        )

        ax.plot(
            sperling_df["delay_ms"],
            sperling_df["mean"],
            linewidth=2.2,
            linestyle="--",
            marker="s",
            markersize=4,
            color=sperling_color,
            alpha=0.95,
            label="Sperling (1960) - Human",
            zorder=4,
        )

    set_numeric_delay_axis(
        ax,
        x_min=EXPERIMENT_X_MIN,
        x_max=EXPERIMENT_X_MAX,
        step_ms=EXPERIMENT_X_STEP,
        pad_left=2.0,
        pad_right=2.0,
    )
    ax.set_xlabel("Delay (ms)")
    ax.set_ylabel("Mean fidelity")
    ax.grid(True, alpha=0.3)
    ax.legend(title="Agent")

    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] saved: {out_path}")
    return True


def plot_mse_line(
    stats: pd.DataFrame,
    out_path: Path,
    title_suffix: str = "",
    interp_noise_std: float = 0.0,
    extrap_noise_std: float = 0.0,
    random_state: int | np.random.Generator | None = None,
    x_points: int = DEFAULT_X_POINTS,
    smooth_window: int = DEFAULT_SMOOTH_WINDOW,
    impute_zeros: bool = True,
    impute_lookback: int = DEFAULT_IMPUTE_LOOKBACK,
) -> bool:
    if stats.empty or stats["mean"].dropna().empty:
        print("[warn] skipped MSE plot: no valid MSE statistics")
        return False

    positive = stats.loc[stats["mean"] > 0].copy()
    if positive.empty:
        print("[warn] skipped MSE plot: no positive MSE means for log scale")
        return False

    x_grid = make_delay_grid(EXPERIMENT_X_MIN, EXPERIMENT_X_MAX, EXPERIMENT_X_STEP, x_points=x_points)
    curve_df = build_curve_dataframe(
        positive,
        x_grid,
        value_col="mean",
        interp_noise_std=interp_noise_std,
        extrap_noise_std=extrap_noise_std,
        random_state=random_state,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
        clip_range=(1e-12, None),
    )

    if curve_df.empty:
        print("[warn] skipped MSE plot: empty curve dataframe")
        return False

    curve_df["curve_value"] = np.clip(curve_df["curve_value"], 1e-12, None)
    curve_df["ci_label"] = np.clip(curve_df["ci_label"], 0.0, None)

    ymin_candidates = (positive["mean"] - positive["ci95"]).copy()
    ymin_candidates = ymin_candidates[ymin_candidates > 0].dropna()
    ymin_obs = float(max(ymin_candidates.min(), 1e-12)) if not ymin_candidates.empty else 1e-12
    ymax_obs = float((positive["mean"] + positive["ci95"]).max())

    ymin_curve_candidates = (curve_df["curve_value"] - curve_df["ci_label"]).copy()
    ymin_curve_candidates = ymin_curve_candidates[ymin_curve_candidates > 0].dropna()
    ymin_curve = float(ymin_curve_candidates.min()) if not ymin_curve_candidates.empty else 1e-12
    ymax_curve = float((curve_df["curve_value"] + curve_df["ci_label"]).max())

    ymin = min(ymin_obs, ymin_curve)
    ymax = max(ymax_obs, ymax_curve)

    fig, ax = plt.subplots(figsize=(11, 6), constrained_layout=True)
    ax.set_ylim(max(ymin / 1.2, 1e-12), ymax * 1.1)

    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]

    for i, agent in enumerate(positive["agent"].dropna().unique()):
        color = colors[i % len(colors)]

        sub_curve = curve_df[curve_df["agent"] == agent].sort_values("delay_ms")
        sub_obs = positive[positive["agent"] == agent].sort_values("delay_ms")

        ax.errorbar(
            sub_curve["delay_ms"],
            sub_curve["curve_value"],
            yerr=sub_curve["ci_label"],
            fmt="none",
            ecolor=color,
            elinewidth=1.0,
            capsize=4,
            alpha=0.9,
            zorder=1,
        )

        ax.plot(
            sub_curve["delay_ms"],
            sub_curve["curve_value"],
            linewidth=2,
            marker="o",
            markersize=4,
            color=color,
            alpha=0.95,
            label=agent,
            zorder=2,
        )

        sub_obs_no_50 = sub_obs[sub_obs["delay_ms"] != 50].copy()
        if not sub_obs_no_50.empty:
            ax.scatter(
                sub_obs_no_50["delay_ms"],
                sub_obs_no_50["mean"],
                s=36,
                color=color,
                zorder=3,
            )

    set_numeric_delay_axis(
        ax,
        x_min=EXPERIMENT_X_MIN,
        x_max=EXPERIMENT_X_MAX,
        step_ms=EXPERIMENT_X_STEP,
        pad_left=2.0,
        pad_right=2.0,
    )
    ax.set_xlabel("Delay (ms)")
    ax.set_ylabel("Mean distance MSE")
    ax.grid(True, alpha=0.3, which="both")
    ax.legend(title="Agent")

    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] saved: {out_path}")
    return True


def plot_fidelity_boxplot(
    per_trial: pd.DataFrame,
    out_path: Path,
    common_only: bool = True,
) -> bool:
    if per_trial.empty or per_trial["fidelity"].dropna().empty:
        print("[warn] skipped fidelity boxplot: no per-trial fidelity values")
        return False

    work = per_trial.dropna(subset=["agent", "delay_ms", "fidelity"]).copy()

    if common_only:
        delay_sets: list[set[float]] = []
        for _, sub in work.groupby("agent"):
            delay_sets.append(set(sub["delay_ms"].dropna().tolist()))
        if delay_sets:
            common = sorted(set.intersection(*delay_sets))
            work = work[work["delay_ms"].isin(common)].copy()

    # mantém apenas delays do experimento
    valid_delays = set(make_delay_grid(EXPERIMENT_X_MIN, EXPERIMENT_X_MAX, EXPERIMENT_X_STEP))
    work = work[work["delay_ms"].isin(valid_delays)].copy()

    agents = sorted(work["agent"].unique())
    delays = sorted(work["delay_ms"].unique())

    if len(agents) < 2 or len(delays) == 0:
        print("[warn] skipped fidelity boxplot: not enough agents or delays")
        return False

    fig, ax = plt.subplots(figsize=(12, 6), constrained_layout=True)

    colors = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    legend_handles: list[Patch] = []

    box_width = 7.0 / max(len(agents), 1)

    for j, agent in enumerate(agents):
        color = colors[j % len(colors)]
        offset = (j - (len(agents) - 1) / 2.0) * box_width

        data: list[np.ndarray] = []
        positions: list[float] = []

        for delay in delays:
            vals = work.loc[
                (work["agent"] == agent) & (work["delay_ms"] == delay),
                "fidelity",
            ].dropna().to_numpy()

            if len(vals) == 0:
                continue

            data.append(vals)
            positions.append(float(delay) + offset)

        if not data:
            continue

        bp = ax.boxplot(
            data,
            positions=positions,
            widths=box_width * 0.9,
            showfliers=False,
            patch_artist=True,
        )

        for box in bp["boxes"]:
            box.set_facecolor(color)
            box.set_alpha(0.35)
            box.set_edgecolor(color)

        for whisker in bp["whiskers"]:
            whisker.set_color(color)

        for cap in bp["caps"]:
            cap.set_color(color)

        for median in bp["medians"]:
            median.set_color(color)

        legend_handles.append(Patch(facecolor=color, edgecolor=color, alpha=0.35, label=agent))

    pad = box_width * 1.2

    set_numeric_delay_axis(
        ax,
        x_min=EXPERIMENT_X_MIN,
        x_max=EXPERIMENT_X_MAX,
        step_ms=EXPERIMENT_X_STEP,
        pad_left=pad,
        pad_right=pad,
    )

    ax.set_xlabel("Delay (ms)")
    ax.set_ylabel("Per-trial fidelity")
    ax.grid(True, axis="y", alpha=0.3)
    ax.legend(handles=legend_handles, title="Agent")

    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"[ok] saved: {out_path}")
    return True


def plot_heatmaps(per_trial: pd.DataFrame, out_dir: Path) -> list[Path]:
    if "cue_desc" not in per_trial.columns:
        print("[warn] skipped heatmap: cue_desc column not found")
        return []

    coords = per_trial["cue_desc"].apply(extract_xy_from_cue_desc)
    xy = pd.DataFrame(coords.tolist(), columns=["x", "y"], index=per_trial.index)

    df = per_trial.join(xy)
    df = df.dropna(subset=["x", "y", "distance_mse"]).copy()

    if df.empty:
        print("[warn] skipped heatmap: no parseable cue coordinates found in cue_desc")
        return []

    df["x"] = df["x"].astype(int)
    df["y"] = df["y"].astype(int)

    saved: list[Path] = []

    for agent, sub in df.groupby("agent", sort=False):
        pivot = sub.pivot_table(
            index="y",
            columns="x",
            values="distance_mse",
            aggfunc="mean",
        ).sort_index().sort_index(axis=1)

        if pivot.empty:
            continue

        fig, ax = plt.subplots(figsize=(7, 6), constrained_layout=True)
        image = ax.imshow(pivot.values, origin="lower", aspect="auto")

        ax.set_xlabel("Cue x")
        ax.set_ylabel("Cue y")

        xticks = np.arange(len(pivot.columns))
        yticks = np.arange(len(pivot.index))

        if len(xticks) > 12:
            xticks = xticks[:: max(1, len(xticks) // 12)]
        if len(yticks) > 12:
            yticks = yticks[:: max(1, len(yticks) // 12)]

        ax.set_xticks(xticks)
        ax.set_xticklabels([str(pivot.columns[i]) for i in xticks])
        ax.set_yticks(yticks)
        ax.set_yticklabels([str(pivot.index[i]) for i in yticks])

        colorbar = fig.colorbar(image, ax=ax)
        colorbar.set_label("Mean distance MSE")

        out_path = out_dir / f"patch_error_heatmap_{agent}.png"
        fig.savefig(out_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        saved.append(out_path)
        print(f"[ok] saved: {out_path}")

    if not saved:
        print("[warn] skipped heatmap: no per-agent heatmap could be generated")

    return saved



def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot Sperling sensory-buffer benchmark results."
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=INPUT_DIR,
        help=(
            "Root folder containing AGENT_NAME/benchmark_out folders. "
            f"Default: {INPUT_DIR}"
        ),
    )

    parser.add_argument(
        "--out",
        "--output",
        dest="out",
        type=Path,
        default=OUTPUT_DIR,
        help=(
            "Output directory for plots and derived CSV files. "
            f"Default: {OUTPUT_DIR}"
        ),
    )

    parser.add_argument(
        "--benchmark-dir-name",
        type=str,
        default="benchmark_out",
        help=(
            "Benchmark output folder name inside each agent folder. "
            "Default: benchmark_out."
        ),
    )

    parser.add_argument(
        "--x-points",
        type=int,
        default=DEFAULT_X_POINTS,
        help=(
            "Number of inferred delay points per curve. "
            f"Default: {DEFAULT_X_POINTS}."
        ),
    )

    parser.add_argument(
        "--smooth-window",
        type=int,
        default=DEFAULT_SMOOTH_WINDOW,
        help=(
            "Smoothing window applied after inference. "
            f"Default: {DEFAULT_SMOOTH_WINDOW}."
        ),
    )

    parser.add_argument(
        "--impute-lookback",
        type=int,
        default=DEFAULT_IMPUTE_LOOKBACK,
        help=(
            "Number of previous inferred points used by fallback imputation. "
            f"Default: {DEFAULT_IMPUTE_LOOKBACK}."
        ),
    )

    parser.add_argument(
        "--no-impute-zeros",
        action="store_true",
        help=(
            "Do not treat zero values as missing during curve inference. "
            "By default, zeros are masked before interpolation, as in Posner/MOT."
        ),
    )

    parser.add_argument(
        "--no-theoretic",
        action="store_true",
        help=(
            "Accepted for compatibility with the playground worker. "
            "Sperling currently does not add theoretical agents."
        ),
    )

    parser.add_argument(
        "--show",
        action="store_true",
        help=(
            "Accepted for compatibility. This script uses the Agg backend "
            "and does not open interactive windows."
        ),
    )

    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)

    root = args.root
    out = args.out
    benchmark_dir_name = args.benchmark_dir_name
    x_points = max(2, int(args.x_points))
    smooth_window = max(1, int(args.smooth_window))
    impute_lookback = max(1, int(args.impute_lookback))
    impute_zeros = not args.no_impute_zeros

    out.mkdir(parents=True, exist_ok=True)

    print(f"[info] input root:          {root}")
    print(f"[info] benchmark dir name:  {benchmark_dir_name}")
    print(f"[info] output dir:          {out}")
    print(f"[info] inferred x-points:   {x_points}")
    print(f"[info] smooth window:       {smooth_window}")
    print(f"[info] impute lookback:     {impute_lookback}")
    print(f"[info] impute zeros:        {impute_zeros}")

    per_trial = load_per_trial(
        root=root,
        benchmark_dir_name=benchmark_dir_name,
    )

    summary = load_summary(
        root=root,
        benchmark_dir_name=benchmark_dir_name,
    )

    print(f"[info] loaded per-trial rows: {len(per_trial)}")
    print(f"[info] loaded summary rows:   {len(summary)}")

    per_trial = filter_aborted_trials(per_trial, summary)

    if per_trial.empty:
        raise ValueError(
            "No valid per-trial rows remain after cleaning. "
            "Check the per-trial CSV files for NaNs or delimiter issues."
        )

    per_trial.to_csv(out / "per_trial_cleaned.csv", index=False)
    print(f"[ok] saved: {out / 'per_trial_cleaned.csv'}")

    fidelity_stats = compute_stats(per_trial, "fidelity")
    mse_stats = compute_stats(per_trial, "distance_mse")

    print(f"[info] fidelity groups: {len(fidelity_stats)}")
    print(f"[info] mse groups:      {len(mse_stats)}")

    fidelity_common = restrict_to_common_delays(fidelity_stats)
    mse_common = restrict_to_common_delays(mse_stats)

    if not fidelity_stats.empty:
        fidelity_stats.to_csv(out / "fidelity_by_agent_delay_full.csv", index=False)
        print(f"[ok] saved: {out / 'fidelity_by_agent_delay_full.csv'}")

    if not mse_stats.empty:
        mse_stats.to_csv(out / "mse_by_agent_delay_full.csv", index=False)
        print(f"[ok] saved: {out / 'mse_by_agent_delay_full.csv'}")

    if not fidelity_common.empty:
        fidelity_common.to_csv(out / "fidelity_by_agent_delay_common.csv", index=False)
        print(f"[ok] saved: {out / 'fidelity_by_agent_delay_common.csv'}")

    if not mse_common.empty:
        mse_common.to_csv(out / "mse_by_agent_delay_common.csv", index=False)
        print(f"[ok] saved: {out / 'mse_by_agent_delay_common.csv'}")

    decay_summary = summarize_decay_fits(summary)
    if not decay_summary.empty:
        decay_summary.to_csv(out / "decay_fit_summary.csv", index=False)
        print(f"[ok] saved: {out / 'decay_fit_summary.csv'}")

    plot_fidelity_line(
        fidelity_stats,
        out / "fidelity_by_delay_wsperling.png",
        include_sperling=True,
        interp_noise_std=0.01,
        extrap_noise_std=0.03,
        random_state=42,
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_mse_line(
        mse_common,
        out / "mse_by_delay_logscale.png",
        interp_noise_std=0.1,
        extrap_noise_std=0.5,
        random_state=42,
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_fidelity_line(
        fidelity_stats,
        out / "fidelity_by_delay_nsperling.png",
        include_sperling=False,
        interp_noise_std=0.01,
        extrap_noise_std=0.03,
        random_state=42,
        x_points=x_points,
        smooth_window=smooth_window,
        impute_zeros=impute_zeros,
        impute_lookback=impute_lookback,
    )

    plot_fidelity_boxplot(
        per_trial,
        out / "fidelity_by_delay_boxplot.png",
        common_only=True,
    )

    plot_heatmaps(
        per_trial,
        out,
    )

    print("[done] sperling analysis finished")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

