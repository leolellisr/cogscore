from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st
from dotenv import load_dotenv


# ------------------------------------------------------------
# Configuration
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")
DATA_ROOT = PROJECT_ROOT / "data"


st.set_page_config(
    page_title="CogScore Playground",
    page_icon="🧠",
    layout="wide",
)


# ------------------------------------------------------------
# API helpers
# ------------------------------------------------------------

def api_get(path: str) -> Any:
    url = f"{API_URL}{path}"

    response = requests.get(url, timeout=20)

    if response.status_code >= 400:
        raise RuntimeError(f"GET {url} failed: {response.status_code} - {response.text}")

    return response.json()


def api_upload_result(file_name: str, file_bytes: bytes) -> Any:
    url = f"{API_URL}/uploads/results"

    files = {
        "file": (file_name, file_bytes, "application/zip")
    }

    response = requests.post(url, files=files, timeout=120)

    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text

        raise RuntimeError(f"Upload failed: {response.status_code} - {detail}")

    return response.json()


def safe_json_loads(value: str | None) -> Any:
    if value is None or value == "":
        return None

    try:
        return json.loads(value)
    except Exception:
        return value


def dataframe_from_records(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def format_status(status: str) -> str:
    status = str(status)

    if status == "done":
        return "✅ done"

    if status == "pending":
        return "⏳ pending"

    if status == "running":
        return "🔄 running"

    if status == "error":
        return "❌ error"

    return status


# ------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------

st.sidebar.title("CogScore Playground")

page = st.sidebar.radio(
    "Navigation",
    [
        "Home",
        "Upload results",
        "Runs",
        "Jobs",
        "Plots",
        "Help",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption(f"API URL: `{API_URL}`")


# ------------------------------------------------------------
# Home
# ------------------------------------------------------------

if page == "Home":
    st.title("🧠 CogScore Playground")

    st.write(
        "Online playground for uploading, validating, plotting, and comparing "
        "CogScore cognitive architecture experiment results."
    )

    st.subheader("API status")

    try:
        health = api_get("/health")
        st.success("API is online.")
        st.json(health)
    except Exception as exc:
        st.error("API is not reachable.")
        st.exception(exc)

    st.subheader("Current workflow")

    st.code(
        """
1. Upload a result_bundle.zip
2. The API validates and imports the run
3. A replot job is created
4. The worker generates plots
5. Plots become visible in this dashboard
        """.strip(),
        language="text",
    )


# ------------------------------------------------------------
# Upload results
# ------------------------------------------------------------

elif page == "Upload results":
    st.title("📤 Upload results")

    st.write(
        "Upload a CogScore result bundle in `.zip` format. "
        "The ZIP must contain `manifest.yaml` and `benchmark_out/`."
    )

    uploaded_file = st.file_uploader(
        "Select result_bundle.zip",
        type=["zip"],
    )

    if uploaded_file is not None:
        st.info(f"Selected file: {uploaded_file.name}")

        if st.button("Upload and import"):
            try:
                result = api_upload_result(
                    file_name=uploaded_file.name,
                    file_bytes=uploaded_file.getvalue(),
                )

                st.success("Result bundle imported successfully.")
                st.json(result)

                st.info(
                    "A replot job was created. Keep the worker running to generate plots."
                )

            except Exception as exc:
                st.error("Upload failed.")
                st.exception(exc)

    st.markdown("---")

    st.subheader("Expected ZIP structure")

    st.code(
        """
result_bundle.zip
├── manifest.yaml
├── benchmark_out/
│   ├── *_summary_episode_*.csv
│   ├── *_per_trial_episode_*.csv
│   ├── *_java_steps_*.csv
│   └── motivation_marta_trials.txt
└── optional/
    ├── config.json
    └── notes.md
        """.strip(),
        language="text",
    )


# ------------------------------------------------------------
# Runs
# ------------------------------------------------------------

elif page == "Runs":
    st.title("📚 Imported runs")

    try:
        runs = api_get("/runs")
        df = dataframe_from_records(runs)

        if df.empty:
            st.info("No runs imported yet.")
        else:
            display_df = df.copy()

            columns_to_show = [
                "id",
                "agent_name",
                "architecture_name",
                "benchmark",
                "benchmark_version",
                "run_name",
                "run_date",
                "seed",
                "episodes",
                "trials_per_experiment",
                "status",
                "created_at",
            ]

            columns_to_show = [c for c in columns_to_show if c in display_df.columns]

            st.dataframe(
                display_df[columns_to_show],
                use_container_width=True,
                hide_index=True,
            )

            selected_run_id = st.selectbox(
                "Select run to inspect",
                options=display_df["id"].tolist(),
            )

            if selected_run_id:
                run = api_get(f"/runs/{selected_run_id}")

                st.subheader("Run details")
                st.json(run)

                manifest = safe_json_loads(run.get("manifest_json"))

                st.subheader("Manifest")
                st.json(manifest)

    except Exception as exc:
        st.error("Could not load runs.")
        st.exception(exc)


# ------------------------------------------------------------
# Jobs
# ------------------------------------------------------------

elif page == "Jobs":
    st.title("⚙️ Jobs")

    if st.button("Refresh jobs"):
        st.rerun()

    try:
        jobs = api_get("/jobs")
        df = dataframe_from_records(jobs)

        if df.empty:
            st.info("No jobs found.")
        else:
            display_df = df.copy()

            if "status" in display_df.columns:
                display_df["status_display"] = display_df["status"].apply(format_status)

            columns_to_show = [
                "id",
                "job_type",
                "status_display",
                "created_at",
                "started_at",
                "finished_at",
                "error_message",
            ]

            columns_to_show = [c for c in columns_to_show if c in display_df.columns]

            st.dataframe(
                display_df[columns_to_show],
                use_container_width=True,
                hide_index=True,
            )

            selected_job_id = st.selectbox(
                "Select job to inspect",
                options=display_df["id"].tolist(),
            )

            if selected_job_id:
                job = api_get(f"/jobs/{selected_job_id}")

                st.subheader("Job details")
                st.json(job)

                input_json = safe_json_loads(job.get("input_json"))
                output_json = safe_json_loads(job.get("output_json"))

                st.subheader("Input")
                st.json(input_json)

                st.subheader("Output")
                st.json(output_json)

                log_path = job.get("log_path")

                if log_path:
                    log_dir = Path(log_path)

                    stdout_path = log_dir / "stdout.log"
                    stderr_path = log_dir / "stderr.log"

                    if stdout_path.exists():
                        st.subheader("stdout.log")
                        st.code(stdout_path.read_text(encoding="utf-8", errors="replace"))

                    if stderr_path.exists():
                        st.subheader("stderr.log")
                        st.code(stderr_path.read_text(encoding="utf-8", errors="replace"))

    except Exception as exc:
        st.error("Could not load jobs.")
        st.exception(exc)


# ------------------------------------------------------------
# Plots
# ------------------------------------------------------------

elif page == "Plots":
    st.title("📈 Generated plots")

    try:
        plots = api_get("/plots")
        df = dataframe_from_records(plots)

        if df.empty:
            st.info("No plot files found yet.")
            st.write("Run the worker after uploading result bundles.")
        else:
            df["benchmark"] = df["relative_path"].apply(
                lambda p: str(p).split("/")[0] if "/" in str(p) else "unknown"
            )

            df["agent"] = df["relative_path"].apply(
                lambda p: str(p).split("/")[1] if len(str(p).split("/")) > 1 else "unknown"
            )

            benchmarks = sorted(df["benchmark"].dropna().unique().tolist())
            agents = sorted(df["agent"].dropna().unique().tolist())

            selected_benchmark = st.selectbox(
                "Benchmark",
                options=["All"] + benchmarks,
            )

            selected_agent = st.selectbox(
                "Agent",
                options=["All"] + agents,
            )

            filtered = df.copy()

            if selected_benchmark != "All":
                filtered = filtered[filtered["benchmark"] == selected_benchmark]

            if selected_agent != "All":
                filtered = filtered[filtered["agent"] == selected_agent]

            st.write(f"Showing {len(filtered)} plot file(s).")

            if filtered.empty:
                st.warning("No plots match the selected filters.")
            else:
                selected_plot = st.selectbox(
                    "Select plot",
                    options=filtered["relative_path"].tolist(),
                )

                selected_row = filtered[filtered["relative_path"] == selected_plot].iloc[0]
                plot_path = Path(selected_row["path"])

                st.subheader(selected_row["name"])
                st.caption(str(plot_path))

                if plot_path.exists() and plot_path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
                    st.image(str(plot_path), use_container_width=True)

                    with plot_path.open("rb") as f:
                        st.download_button(
                            label="Download plot",
                            data=f.read(),
                            file_name=plot_path.name,
                            mime="image/png",
                        )

                elif plot_path.exists():
                    st.info("Preview is not available for this file type.")

                    with plot_path.open("rb") as f:
                        st.download_button(
                            label="Download file",
                            data=f.read(),
                            file_name=plot_path.name,
                        )
                else:
                    st.error("Plot file does not exist on disk.")

            st.subheader("All plot files")
            st.dataframe(
                filtered[["relative_path", "size_bytes"]],
                use_container_width=True,
                hide_index=True,
            )

    except Exception as exc:
        st.error("Could not load plots.")
        st.exception(exc)


# ------------------------------------------------------------
# Help
# ------------------------------------------------------------

elif page == "Help":
    st.title("❓ Help")

    st.subheader("How to run locally")

    st.code(
        """
# Terminal 1: API
cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/api
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2: Worker
cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/worker
python -m worker.main

# Terminal 3: Web
cd ~/git/cogscore-playground
source .venv/bin/activate
cd services/web
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
        """.strip(),
        language="bash",
    )

    st.subheader("Expected result bundle")

    st.code(
        """
result_bundle.zip
├── manifest.yaml
├── benchmark_out/
│   ├── *_summary_episode_*.csv
│   ├── *_per_trial_episode_*.csv
│   ├── *_java_steps_*.csv
│   └── motivation_marta_trials.txt
└── optional/
    ├── config.json
    └── notes.md
        """.strip(),
        language="text",
    )

    st.subheader("Important paths")

    st.code(
        f"""
Project root: {PROJECT_ROOT}
Data root:    {DATA_ROOT}
API URL:      {API_URL}
        """.strip(),
        language="text",
    )
