from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from .. import api_client
from ..common import (
    benchmark_title,
    format_bytes,
    format_datetime,
    navigate,
    render_exception,
    status_badge,
)



_DASHBOARD_PLOT_DOMAINS = [
    ("sensory_buffer", "Sensory"),
    ("attention_posner", "Attention"),
    ("motivation", "Motivation"),
    ("learning", "Learning"),
]
_DASHBOARD_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
_DASHBOARD_PLOTS_ROOT = Path(os.getenv("PLOTS_DIR", "/data/plots")).resolve()


def _plot_benchmark_id(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        benchmark = metadata.get("benchmark")
        if isinstance(benchmark, dict) and benchmark.get("id"):
            return str(benchmark["id"])
    relative = str(item.get("relative_path", ""))
    return relative.split("/", 1)[0] if relative else ""


def _plot_title(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        plot = metadata.get("plot")
        if isinstance(plot, dict) and plot.get("title"):
            return str(plot["title"])
    return Path(str(item.get("name") or "Plot")).stem.replace("_", " ").title()


def _plot_local_path(item: dict[str, Any]) -> str | None:
    relative_path = str(item.get("relative_path") or "").strip().replace("\\", "/")
    if not relative_path or relative_path.startswith("/") or ".." in Path(relative_path).parts:
        return None
    candidate = (_DASHBOARD_PLOTS_ROOT / relative_path).resolve()
    try:
        candidate.relative_to(_DASHBOARD_PLOTS_ROOT)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    if candidate.suffix.lower() not in _DASHBOARD_IMAGE_EXTENSIONS:
        return None
    return str(candidate)


def _dashboard_plot_examples(items: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    examples = {benchmark: [] for benchmark, _ in _DASHBOARD_PLOT_DOMAINS}
    # /plots is already newest-first. Keep every generated raster image. The web
    # container mounts /data read-only, so Streamlit can serve the selected image
    # directly without relying on browser access to /api or embedding all plots.
    for item in items:
        benchmark = _plot_benchmark_id(item)
        if benchmark not in examples:
            continue
        path = _plot_local_path(item)
        if not path:
            continue
        examples[benchmark].append({"path": path, "title": _plot_title(item)})
    return examples


def _gallery_state() -> tuple[dict[str, int], bool]:
    positions_key = "dashboard_gallery_positions"
    paused_key = "dashboard_gallery_paused"
    tick_key = "dashboard_gallery_last_tick"

    if positions_key not in st.session_state:
        st.session_state[positions_key] = {benchmark: 0 for benchmark, _ in _DASHBOARD_PLOT_DOMAINS}
    if paused_key not in st.session_state:
        st.session_state[paused_key] = False
    if tick_key not in st.session_state:
        st.session_state[tick_key] = time.monotonic()

    return st.session_state[positions_key], bool(st.session_state[paused_key])


def _reset_gallery_tick() -> None:
    st.session_state["dashboard_gallery_last_tick"] = time.monotonic()


def _toggle_gallery_pause() -> None:
    st.session_state["dashboard_gallery_paused"] = not bool(
        st.session_state.get("dashboard_gallery_paused", False)
    )
    _reset_gallery_tick()


def _step_gallery(domain: str, amount: int, size: int) -> None:
    if size <= 0:
        return
    positions, _ = _gallery_state()
    positions[domain] = (int(positions.get(domain, 0)) + amount) % size
    st.session_state["dashboard_gallery_positions"] = positions
    _reset_gallery_tick()


@st.fragment(run_every="5s")
def _render_plot_examples() -> None:
    st.subheader("Benchmark plot examples")
    st.caption(
        "Plots from the four CogScore modalities. Use the arrows to browse every generated figure; "
        "the gallery advances automatically every 5 seconds unless paused."
    )

    try:
        plot_items = api_client.get("/plots")
        if not isinstance(plot_items, list):
            plot_items = []
    except Exception:
        plot_items = []

    examples = _dashboard_plot_examples(plot_items)
    positions, paused = _gallery_state()

    now = time.monotonic()
    last_tick = float(st.session_state.get("dashboard_gallery_last_tick", now))
    if not paused and now - last_tick >= 4.5:
        for benchmark, _ in _DASHBOARD_PLOT_DOMAINS:
            size = len(examples.get(benchmark, []))
            if size > 1:
                positions[benchmark] = (int(positions.get(benchmark, 0)) + 1) % size
        st.session_state["dashboard_gallery_positions"] = positions
        st.session_state["dashboard_gallery_last_tick"] = now

    toolbar = st.columns([8, 1.5])
    with toolbar[1]:
        st.button(
            "▶ Resume" if paused else "⏸ Pause",
            key="dashboard_gallery_pause",
            use_container_width=True,
            on_click=_toggle_gallery_pause,
        )

    rows = [
        _DASHBOARD_PLOT_DOMAINS[:2],
        _DASHBOARD_PLOT_DOMAINS[2:],
    ]
    for row_index, domains in enumerate(rows):
        columns = st.columns(2, gap="small")
        for column, (benchmark, label) in zip(columns, domains):
            with column:
                with st.container(border=True):
                    items = examples.get(benchmark, [])
                    count = len(items)
                    index = int(positions.get(benchmark, 0)) % count if count else 0
                    positions[benchmark] = index

                    header = st.columns([4, 1])
                    header[0].markdown(f"**{label.upper()}**")
                    header[1].caption(f"{index + 1} / {count}" if count else "0 / 0")

                    if count:
                        current = items[index]
                        st.image(current["path"], use_container_width=True)
                        controls = st.columns([1, 5, 1])
                        controls[0].button(
                            "❮",
                            key=f"dashboard_gallery_prev_{benchmark}_{row_index}",
                            help=f"Previous {label} plot",
                            disabled=count < 2,
                            use_container_width=True,
                            on_click=_step_gallery,
                            args=(benchmark, -1, count),
                        )
                        controls[1].caption(current["title"])
                        controls[2].button(
                            "❯",
                            key=f"dashboard_gallery_next_{benchmark}_{row_index}",
                            help=f"Next {label} plot",
                            disabled=count < 2,
                            use_container_width=True,
                            on_click=_step_gallery,
                            args=(benchmark, 1, count),
                        )
                    else:
                        st.info("No generated plot is available yet.")
                        st.caption("Generate comparison plots to populate this modality.")

    st.session_state["dashboard_gallery_positions"] = positions

def render() -> None:
    st.title("Dashboard")
    st.caption("Operational overview of architectures, experiments, jobs, plots, and simulator services.")

    try:
        summary = api_client.get("/dashboard/summary")
    except Exception as exc:
        render_exception("Could not load the dashboard", exc)
        return

    services = st.columns(3)
    service_items = [
        ("API", summary.get("api", {}).get("status", "unknown")),
        ("Worker", summary.get("worker", {}).get("status", "unknown")),
        ("Simulator", summary.get("simulator", {}).get("status", "unknown")),
    ]
    for column, (label, status) in zip(services, service_items):
        with column:
            st.markdown(f'<div class="cog-card"><div class="cog-eyebrow">Service</div><h4>{label}</h4>{status_badge(str(status))}</div>', unsafe_allow_html=True)

    counts = summary.get("counts", {})
    metrics = st.columns(6)
    metric_values = [
        ("Validated architectures", counts.get("validated_architectures", 0)),
        ("Active jobs", counts.get("active_jobs", 0)),
        ("Failed jobs", counts.get("failed_jobs", 0)),
        ("Experiment runs", counts.get("experiment_runs", 0)),
        ("Imported results", counts.get("imported_runs", 0)),
        ("Storage", format_bytes(counts.get("storage_bytes", 0))),
    ]
    for column, (label, value) in zip(metrics, metric_values):
        column.metric(label, value)

    st.subheader("Quick actions")
    actions = st.columns(4)
    if actions[0].button("Architectures", use_container_width=True):
        navigate("Architectures", tab="upload")
    if actions[1].button("Import results", use_container_width=True):
        navigate("Imported results", tab="upload")
    if actions[2].button("New experiment", type="primary", use_container_width=True):
        navigate("New experiment")
    if actions[3].button("View plots", use_container_width=True):
        navigate("Plots")

    failed = int(counts.get("failed_jobs", 0) or 0)
    if failed:
        st.warning(f"{failed} job(s) are currently recorded as failed. Review the Jobs page for recovery actions.")

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Recent jobs")
        jobs = summary.get("recent_jobs", [])
        if jobs:
            rows = []
            for job in jobs:
                rows.append(
                    {
                        "Status": str(job.get("status", "unknown")).title(),
                        "Type": str(job.get("job_type", "")).replace("_", " ").title(),
                        "Job": job.get("id"),
                        "Created": format_datetime(job.get("created_at")),
                    }
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            if st.button("Open Jobs", key="dashboard_open_jobs"):
                navigate("Jobs")
        else:
            st.info("No jobs have been created yet.")

    with right:
        st.subheader("Recent experiment runs")
        runs = summary.get("recent_runs", [])
        if runs:
            rows = []
            for run in runs:
                rows.append(
                    {
                        "Status": str(run.get("status", "unknown")).title(),
                        "Benchmark": benchmark_title(str(run.get("benchmark", ""))),
                        "Run": run.get("id"),
                        "Created": format_datetime(run.get("created_at")),
                    }
                )
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            if st.button("Open Experiment runs", key="dashboard_open_runs"):
                navigate("Experiment runs")
        else:
            st.info("No online experiment runs have been created yet.")

    _render_plot_examples()

    with st.expander("Technical service details"):
        st.json(
            {
                "worker": summary.get("worker", {}),
                "simulator": summary.get("simulator", {}),
                "job_status": summary.get("job_status", {}),
                "architecture_status": summary.get("architecture_status", {}),
                "run_status": summary.get("run_status", {}),
            }
        )

    st.divider()
    about_col, license_col = st.columns(2, gap="large")
    with about_col:
        st.markdown("### About CogScore")
        st.markdown(
            "CogScore is an online evaluation playground for cognitive architectures in "
            "developmental robotics. It organizes reproducible experiments and comparison "
            "plots across four benchmark domains: **Sensory, Attention, Motivation, and Learning**."
        )
    with license_col:
        st.markdown("### License")
        st.markdown(
            "CogScore is distributed under the **PolyForm Noncommercial License 1.0.0**. "
            "Noncommercial research and educational use is permitted. Commercial use and resale "
            "are not permitted. Academic or research use must attribute CogScore and cite the project "
            "as described in `CITATION.cff`. See the project `LICENSE` and `NOTICE` files for details."
        )

    st.caption("CogScore — Online Playground for Cognitive Architecture Evaluation")
