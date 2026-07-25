from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd
import streamlit as st

from .. import api_client
from ..common import (
    benchmark_title,
    duration_seconds,
    format_datetime,
    format_duration,
    human_error,
    navigate,
    parse_json,
    render_exception,
    resolve_data_path,
    status_badge,
)


def _benchmark_from_job(job: dict[str, Any]) -> str:
    data = parse_json(job.get("input_json"), {})
    if not isinstance(data, dict):
        return ""
    if data.get("benchmark"):
        return str(data["benchmark"])
    parameters = data.get("parameters")
    if isinstance(parameters, dict):
        return str(parameters.get("benchmark") or "")
    return ""


def _job_label(job: dict[str, Any]) -> str:
    return (
        f"{str(job.get('status', 'unknown')).title()} · "
        f"{str(job.get('job_type', '')).replace('_', ' ').title()} · "
        f"{job.get('id')}"
    )


def render_jobs() -> None:
    st.title("Jobs")
    st.caption("Inspect asynchronous validation, experiment, plot, and simulator operations.")
    try:
        jobs = api_client.get("/jobs")
    except Exception as exc:
        render_exception("Could not load jobs", exc)
        return
    if not jobs:
        st.info("No jobs have been created.")
        return

    filter_cols = st.columns(4)
    statuses = sorted({str(job.get("status", "unknown")) for job in jobs})
    types = sorted({str(job.get("job_type", "unknown")) for job in jobs})
    benchmarks = sorted({_benchmark_from_job(job) for job in jobs if _benchmark_from_job(job)})
    selected_statuses = filter_cols[0].multiselect("Status", statuses, default=statuses, format_func=lambda value: value.title())
    selected_types = filter_cols[1].multiselect("Job type", types, default=types, format_func=lambda value: value.replace("_", " ").title())
    selected_benchmarks = filter_cols[2].multiselect("Benchmark", benchmarks, default=benchmarks, format_func=benchmark_title)
    period = filter_cols[3].selectbox("Period", ["All time", "Last 7 days", "Last 30 days"])

    cutoff: datetime | None = None
    if period == "Last 7 days":
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    elif period == "Last 30 days":
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    filtered = []
    for job in jobs:
        if job.get("status") not in selected_statuses or job.get("job_type") not in selected_types:
            continue
        benchmark = _benchmark_from_job(job)
        if benchmarks and benchmark and benchmark not in selected_benchmarks:
            continue
        if cutoff:
            try:
                created = datetime.fromisoformat(str(job.get("created_at")).replace("Z", "+00:00"))
            except ValueError:
                created = cutoff
            if created < cutoff:
                continue
        filtered.append(job)

    rows = []
    for job in filtered:
        rows.append(
            {
                "Status": str(job.get("status", "unknown")).title(),
                "Type": str(job.get("job_type", "")).replace("_", " ").title(),
                "Benchmark": benchmark_title(_benchmark_from_job(job)) if _benchmark_from_job(job) else "—",
                "Job": job.get("id"),
                "Created": format_datetime(job.get("created_at")),
                "Duration": format_duration(duration_seconds(job.get("started_at"), job.get("finished_at"))),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if not filtered:
        st.info("No jobs match the selected filters.")
        return

    requested = st.query_params.get("job", "")
    ids = [job["id"] for job in filtered]
    index = ids.index(requested) if requested in ids else 0
    selected_id = st.selectbox("Inspect job", ids, index=index, format_func=lambda value: _job_label(next(job for job in filtered if job["id"] == value)))
    job = next(job for job in filtered if job["id"] == selected_id)

    st.markdown(f'<div class="cog-card"><div class="cog-eyebrow">Job</div><h4>{job.get("id")}</h4>{status_badge(str(job.get("status", "unknown")))}<p class="cog-muted">{str(job.get("job_type", "")).replace("_", " ").title()}</p></div>', unsafe_allow_html=True)
    summary_cols = st.columns(4)
    summary_cols[0].metric("Created", format_datetime(job.get("created_at")))
    summary_cols[1].metric("Started", format_datetime(job.get("started_at")))
    summary_cols[2].metric("Finished", format_datetime(job.get("finished_at")))
    summary_cols[3].metric("Duration", format_duration(duration_seconds(job.get("started_at"), job.get("finished_at"))))

    if job.get("error_message"):
        message = str(job["error_message"])
        st.error(human_error(message))
        with st.expander("Complete error message"):
            st.code(message, language="text")

    input_tab, output_tab, logs_tab = st.tabs(["Input", "Output", "Logs"])
    with input_tab:
        st.json(parse_json(job.get("input_json"), {}))
    with output_tab:
        if job.get("output_json"):
            st.json(parse_json(job.get("output_json"), {}))
        else:
            st.info("No output has been recorded.")
    with logs_tab:
        log_path = job.get("log_path")
        if not log_path:
            st.info("No log directory has been recorded.")
        else:
            resolved = resolve_data_path(str(log_path))
            for name in ("stderr.log", "stdout.log"):
                path = resolved / name
                st.markdown(f"**{name}**")
                if path.is_file():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    st.code(text[-20000:] or "(empty log)", language="text")
                else:
                    st.caption("Not available")

    if job.get("status") not in {"pending", "running"} and not str(job.get("job_type", "")).startswith("run_"):
        if st.button("Retry as a new job", type="primary"):
            try:
                result = api_client.post_json(f"/jobs/{selected_id}/retry", {})
                st.success(f"New job created: {result.get('job_id')}")
                navigate("Jobs", job=str(result.get("job_id", "")))
            except Exception as exc:
                render_exception("Could not retry the job", exc)


def render_runs() -> None:
    st.title("Experiment runs")
    st.caption("Review online experiment executions, inspect parameters, and repeat previous configurations.")
    try:
        runs = api_client.get("/experiment-runs")
        architectures = api_client.get("/architectures")
    except Exception as exc:
        render_exception("Could not load experiment runs", exc)
        return
    if not runs:
        st.info("No online experiment runs have been created.")
        if st.button("Create an experiment"):
            navigate("New experiment")
        return

    arch_names = {item["id"]: f"{item['name']} {item['version']}" for item in architectures}
    filter_cols = st.columns(3)
    benchmark_options = sorted({str(run.get("benchmark", "")) for run in runs})
    status_options = sorted({str(run.get("status", "unknown")) for run in runs})
    architecture_options = sorted({str(run.get("architecture_id", "")) for run in runs})
    selected_benchmarks = filter_cols[0].multiselect("Benchmark", benchmark_options, default=benchmark_options, format_func=benchmark_title)
    selected_statuses = filter_cols[1].multiselect("Status", status_options, default=status_options, format_func=lambda value: value.title())
    selected_architectures = filter_cols[2].multiselect("Architecture", architecture_options, default=architecture_options, format_func=lambda value: arch_names.get(value, value))

    filtered = [run for run in runs if run.get("benchmark") in selected_benchmarks and run.get("status") in selected_statuses and run.get("architecture_id") in selected_architectures]
    rows = []
    for run in filtered:
        rows.append(
            {
                "Status": str(run.get("status", "unknown")).title(),
                "Benchmark": benchmark_title(str(run.get("benchmark", ""))),
                "Architecture": arch_names.get(str(run.get("architecture_id")), str(run.get("architecture_id"))),
                "Run": run.get("id"),
                "Created": format_datetime(run.get("created_at")),
                "Duration": format_duration(duration_seconds(run.get("created_at"), run.get("finished_at"))),
            }
        )
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    if not filtered:
        st.info("No experiment runs match the selected filters.")
        return

    requested = st.query_params.get("run", "")
    ids = [run["id"] for run in filtered]
    index = ids.index(requested) if requested in ids else 0
    selected_id = st.selectbox("Inspect run", ids, index=index)
    run = next(run for run in filtered if run["id"] == selected_id)
    parameters = parse_json(run.get("parameters_json"), {})

    st.markdown(f'<div class="cog-card"><div class="cog-eyebrow">Experiment run</div><h4>{benchmark_title(str(run.get("benchmark", "")))}</h4>{status_badge(str(run.get("status", "unknown")))}<p class="cog-muted">{arch_names.get(str(run.get("architecture_id")), run.get("architecture_id"))} · {run.get("id")}</p></div>', unsafe_allow_html=True)
    cols = st.columns(4)
    cols[0].metric("Scene", run.get("scene", "—"))
    cols[1].metric("Created", format_datetime(run.get("created_at")))
    cols[2].metric("Finished", format_datetime(run.get("finished_at")))
    cols[3].metric("Job", run.get("job_id", "—"))

    if run.get("error_message"):
        st.error(human_error(str(run["error_message"])))
        with st.expander("Complete error message"):
            st.code(str(run["error_message"]), language="text")
    with st.expander("Parameters", expanded=True):
        st.json(parameters)

    actions = st.columns(4)
    if actions[0].button("Open job", use_container_width=True, disabled=not bool(run.get("job_id"))):
        navigate("Jobs", job=str(run.get("job_id", "")))
    if actions[1].button("Open plots", use_container_width=True):
        navigate("Plots", benchmark=str(run.get("benchmark", "")))
    if actions[2].button("Repeat run", use_container_width=True, disabled=run.get("status") in {"pending", "running"}):
        try:
            result = api_client.post_json(f"/experiment-runs/{selected_id}/retry", {})
            st.success(f"New run created: {result.get('run_id')}")
            navigate("Experiment runs", run=str(result.get("run_id", "")))
        except Exception as exc:
            render_exception("Could not repeat the experiment", exc)
    if actions[3].button("Edit and run", type="primary", use_container_width=True):
        st.session_state["experiment_draft"] = {
            "architecture_id": run.get("architecture_id"),
            "benchmark": run.get("benchmark"),
            "parameters": parameters,
        }
        navigate("New experiment")
