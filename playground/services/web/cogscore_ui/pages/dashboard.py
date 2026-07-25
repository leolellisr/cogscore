from __future__ import annotations

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
    if actions[0].button("Upload architecture", use_container_width=True):
        navigate("Architectures", tab="upload")
    if actions[1].button("Import results", use_container_width=True):
        navigate("Imported results", tab="upload")
    if actions[2].button("Run experiment", type="primary", use_container_width=True):
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
