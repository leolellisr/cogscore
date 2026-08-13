from __future__ import annotations

import base64
import html
import json
import mimetypes
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from .. import api_client
from ..common import (
    benchmark_title,
    format_bytes,
    format_datetime,
    navigate,
    render_exception,
    resolve_data_path,
    status_badge,
)



_DASHBOARD_PLOT_DOMAINS = [
    ("sensory_buffer", "Sensory"),
    ("attention_posner", "Attention"),
    ("motivation", "Motivation"),
    ("learning", "Learning"),
]
_DASHBOARD_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
_DASHBOARD_MAX_EXAMPLES = 8


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


def _image_data_uri(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _dashboard_plot_examples(items: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
    examples = {benchmark: [] for benchmark, _ in _DASHBOARD_PLOT_DOMAINS}
    seen: dict[str, set[str]] = {benchmark: set() for benchmark, _ in _DASHBOARD_PLOT_DOMAINS}

    # /plots is already newest-first. Keeping that order means the dashboard automatically
    # follows the newest generated comparison without requiring a separate configuration file.
    for item in items:
        benchmark = _plot_benchmark_id(item)
        if benchmark not in examples or len(examples[benchmark]) >= _DASHBOARD_MAX_EXAMPLES:
            continue
        extension = str(item.get("extension") or "").lower()
        if extension not in _DASHBOARD_IMAGE_EXTENSIONS:
            continue
        path = resolve_data_path(str(item.get("path") or ""))
        if not path.is_file():
            continue
        title = _plot_title(item)
        # Avoid filling a carousel with the same logical measure from older generations.
        if title in seen[benchmark]:
            continue
        uri = _image_data_uri(path)
        if not uri:
            continue
        seen[benchmark].add(title)
        examples[benchmark].append({"src": uri, "title": title})

    return examples


def _render_plot_examples() -> None:
    st.subheader("Benchmark plot examples")
    st.caption(
        "Examples from the four CogScore modalities. Use the arrows to browse; "
        "the gallery also advances automatically every 5 seconds."
    )

    try:
        plot_items = api_client.get("/plots")
        if not isinstance(plot_items, list):
            plot_items = []
    except Exception:
        plot_items = []

    examples = _dashboard_plot_examples(plot_items)
    payload = {
        benchmark: examples.get(benchmark, [])
        for benchmark, _ in _DASHBOARD_PLOT_DOMAINS
    }
    payload_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")

    cards = []
    for benchmark, label in _DASHBOARD_PLOT_DOMAINS:
        cards.append(
            f"""
            <article class="plot-card" data-domain="{html.escape(benchmark)}">
              <div class="plot-header">
                <span>{html.escape(label)}</span>
                <span class="plot-counter" aria-live="polite"></span>
              </div>
              <div class="plot-frame">
                <button class="plot-arrow plot-prev" type="button" aria-label="Previous {html.escape(label)} plot">&#10094;</button>
                <img class="plot-image" alt="{html.escape(label)} benchmark plot example" />
                <div class="plot-empty">No generated plot is available yet.</div>
                <button class="plot-arrow plot-next" type="button" aria-label="Next {html.escape(label)} plot">&#10095;</button>
              </div>
              <div class="plot-caption"></div>
            </article>
            """
        )

    component_html = f"""
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #252733; background: transparent; }}
        .gallery-toolbar {{ display: flex; justify-content: flex-end; margin: 0 0 8px; }}
        .gallery-pause {{ border: 1px solid rgba(37,39,51,.18); border-radius: 9px; background: #fff; color: #252733; padding: 6px 11px; font-size: 12px; font-weight: 700; cursor: pointer; box-shadow: 0 1px 4px rgba(37,39,51,.08); }}
        .gallery-pause:hover {{ background: #faf7f5; }}
        .gallery-pause[aria-pressed="true"] {{ background: #faf7f5; }}
        .plot-grid {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }}
        .plot-card {{ border: 1px solid rgba(37,39,51,.16); border-radius: 14px; overflow: hidden; background: #fff; min-width: 0; }}
        .plot-header {{ display: flex; align-items: center; justify-content: space-between; padding: 11px 14px; font-size: 14px; font-weight: 800; letter-spacing: .045em; text-transform: uppercase; background: #faf7f5; border-bottom: 1px solid rgba(37,39,51,.10); }}
        .plot-counter {{ font-size: 11px; font-weight: 700; opacity: .52; letter-spacing: 0; }}
        .plot-frame {{ position: relative; width: 100%; aspect-ratio: 16 / 9; display: flex; align-items: center; justify-content: center; background: #fff; overflow: hidden; }}
        .plot-image {{ width: 100%; height: 100%; object-fit: contain; padding: 2px; display: none; }}
        .plot-empty {{ max-width: 72%; text-align: center; font-size: 13px; line-height: 1.4; opacity: .58; }}
        .plot-arrow {{ position: absolute; z-index: 3; top: 50%; transform: translateY(-50%); width: 36px; height: 44px; border-radius: 9px; border: 1px solid rgba(37,39,51,.18); background: rgba(255,255,255,.88); color: #252733; font-size: 20px; line-height: 1; cursor: pointer; box-shadow: 0 2px 8px rgba(37,39,51,.10); }}
        .plot-arrow:hover {{ background: #fff; }}
        .plot-arrow:disabled {{ display: none; }}
        .plot-prev {{ left: 10px; }}
        .plot-next {{ right: 10px; }}
        .plot-caption {{ min-height: 42px; padding: 9px 14px 11px; border-top: 1px solid rgba(37,39,51,.08); font-size: 12px; line-height: 1.35; opacity: .72; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
        @media (max-width: 760px) {{ .plot-grid {{ grid-template-columns: 1fr; }} }}
      </style>
    </head>
    <body>
      <div class="gallery-toolbar">
        <button id="gallery-pause" class="gallery-pause" type="button" aria-pressed="false">&#10074;&#10074; Pause</button>
      </div>
      <div class="plot-grid">{''.join(cards)}</div>
      <script>
        const slides = {payload_json};
        const positions = Object.fromEntries(Object.keys(slides).map(key => [key, 0]));
        let paused = false;

        function render(domain) {{
          const card = document.querySelector(`[data-domain="${{domain}}"]`);
          const list = slides[domain] || [];
          const image = card.querySelector('.plot-image');
          const empty = card.querySelector('.plot-empty');
          const caption = card.querySelector('.plot-caption');
          const counter = card.querySelector('.plot-counter');
          const arrows = card.querySelectorAll('.plot-arrow');

          if (!list.length) {{
            image.style.display = 'none';
            empty.style.display = 'block';
            caption.textContent = 'Generate comparison plots to populate this example.';
            counter.textContent = '0 / 0';
            arrows.forEach(button => button.disabled = true);
            return;
          }}

          const index = ((positions[domain] % list.length) + list.length) % list.length;
          positions[domain] = index;
          const current = list[index];
          image.src = current.src;
          image.alt = `${{card.querySelector('.plot-header span').textContent}} — ${{current.title}}`;
          image.style.display = 'block';
          empty.style.display = 'none';
          caption.textContent = current.title;
          counter.textContent = `${{index + 1}} / ${{list.length}}`;
          arrows.forEach(button => button.disabled = list.length < 2);
        }}

        function step(domain, amount) {{
          const list = slides[domain] || [];
          if (list.length < 2) return;
          positions[domain] = (positions[domain] + amount + list.length) % list.length;
          render(domain);
        }}

        document.querySelectorAll('.plot-card').forEach(card => {{
          const domain = card.dataset.domain;
          card.querySelector('.plot-prev').addEventListener('click', () => step(domain, -1));
          card.querySelector('.plot-next').addEventListener('click', () => step(domain, 1));
          render(domain);
        }});

        const pauseButton = document.getElementById('gallery-pause');
        pauseButton.addEventListener('click', () => {{
          paused = !paused;
          pauseButton.setAttribute('aria-pressed', String(paused));
          pauseButton.innerHTML = paused ? '&#9654; Resume' : '&#10074;&#10074; Pause';
        }});

        window.setInterval(() => {{
          if (paused) return;
          Object.keys(slides).forEach(domain => step(domain, 1));
        }}, 5000);
      </script>
    </body>
    </html>
    """

    # Compact two-row 16:9 gallery plus headers/captions and the pause control.
    components.html(component_html, height=790, scrolling=False)

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
