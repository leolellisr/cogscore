from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st


API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")

st.set_page_config(
    page_title="CogScore Online Runner",
    page_icon="🧠",
    layout="wide",
)


def resolve_data_path(value: str | Path) -> Path:
    """Map paths saved before the host/Docker switch to the mounted data root."""
    original = Path(str(value)).expanduser()
    if original.exists():
        return original

    data_root = Path(os.getenv("LOCAL_STORAGE_ROOT", "/data"))
    parts = original.parts
    for index in reversed(
        [position for position, part in enumerate(parts) if part == "data"]
    ):
        candidate = data_root.joinpath(*parts[index + 1:])
        if candidate.exists():
            return candidate

    return original


def api_get(path: str) -> Any:
    r = requests.get(API_URL + path, timeout=30)
    r.raise_for_status()
    return r.json()


def api_post_json(path: str, payload: dict[str, Any]) -> Any:
    r = requests.post(API_URL + path, json=payload, timeout=120)
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()

def api_upload_results(filename: str, data: bytes) -> Any:
    """Upload a result bundle and preserve the API error details."""
    try:
        response = requests.post(
            API_URL + "/uploads/results",
            files={
                "file": (
                    filename,
                    data,
                    "application/zip",
                )
            },
            timeout=300,
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Could not contact results API: {exc}") from exc

    if response.ok:
        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError(
                "The results API returned success but the response was not valid JSON.\n"
                f"HTTP status: {response.status_code}\n"
                f"Response: {response.text[:4000]}"
            ) from exc

    content_type = response.headers.get("content-type", "")
    request_id = (
        response.headers.get("x-request-id")
        or response.headers.get("x-correlation-id")
        or response.headers.get("trace-id")
    )

    detail: Any = response.text
    if "application/json" in content_type.lower():
        try:
            payload = response.json()
            detail = payload.get("detail", payload) if isinstance(payload, dict) else payload
        except ValueError:
            pass

    request_id_text = f"\nRequest ID: {request_id}" if request_id else ""
    raise RuntimeError(
        "Result upload failed.\n"
        f"Endpoint: {API_URL}/uploads/results\n"
        f"HTTP status: {response.status_code}\n"
        f"Response: {detail}"
        f"{request_id_text}"
    )

def api_upload_architecture(filename: str, data: bytes) -> Any:
    r = requests.post(
        API_URL + "/architectures/upload",
        files={"file": (filename, data, "application/zip")},
        timeout=180,
    )
    if r.status_code >= 400:
        raise RuntimeError(r.text)
    return r.json()


def architecture_declares(architecture: dict[str, Any], benchmark: str) -> bool:
    try:
        manifest = json.loads(architecture.get("manifest_json") or "{}")
    except Exception:
        return True

    benchmarks = manifest.get("benchmarks")
    if not isinstance(benchmarks, list):
        return True

    return benchmark in benchmarks


def validated_architectures_for(architectures: list[dict[str, Any]], benchmark: str) -> list[dict[str, Any]]:
    return [
        architecture
        for architecture in architectures
        if architecture.get("status") == "validated"
        and architecture_declares(architecture, benchmark)
    ]


st.sidebar.title("CogScore Online")
page = st.sidebar.radio(
    "Menu",
    [
        "Home",
        "Upload architecture",
        "Upload results",
        "Architectures",
        "Sensing experiments",
        "Attention experiments",
        "Motivation experiments",
        "Learning experiments",
        "Jobs",
        "Experiment runs",
        "Plots",
        "VNC",
    ],
)

st.sidebar.caption(f"API: `{API_URL}`")


if page == "Home":
    st.title("CogScore Online Runner")

    try:
        health = api_get("/health")
        st.success("API online")
        st.json(health)
    except Exception as exc:
        st.error("API offline")
        st.exception(exc)

    st.markdown(
        """
This server allows external research groups to upload a REST-based cognitive architecture,
validate it, and run CogScore sensing, attention, motivation, and learning experiments online using CoppeliaSim through VNC/noVNC.
"""
    )


elif page == "Upload architecture":
    st.title("Upload external architecture")

    uploaded = st.file_uploader("architecture_bundle.zip", type=["zip"])

    if uploaded is not None:
        st.info(uploaded.name)

        if st.button("Upload and create validation job"):
            try:
                result = api_upload_architecture(uploaded.name, uploaded.getvalue())
                st.success("Architecture uploaded")
                st.json(result)
            except Exception as exc:
                st.error("Upload failed")
                st.exception(exc)

    st.subheader("Expected bundle")

    st.code(
        """
architecture_bundle.zip
├── manifest.yaml
├── Dockerfile
├── requirements.txt
└── app.py
        """.strip(),
        language="text",
    )

elif page == "Upload results":
    st.title("Upload results for plotting")

    st.markdown(
        """
Upload a ZIP bundle containing the results of an experiment run.

After the upload, the server will:

1. validate the bundle;
2. import the results into `data/results`;
3. create a plot-generation job;
4. make the charts available on the **Plots** page.
"""
    )

    uploaded_result = st.file_uploader(
        "Result bundle (.zip)",
        type=["zip"],
        key="result_bundle_upload",
    )

    if uploaded_result is not None:
        st.info(
            f"Selected file: {uploaded_result.name} "
            f"({uploaded_result.size / 1024:.1f} KB)"
        )

        if st.button(
            "Upload and create plot job",
            type="primary",
            key="upload_result_button",
        ):
            try:
                with st.spinner("Uploading and validating results..."):
                    result = api_upload_results(
                        uploaded_result.name,
                        uploaded_result.getvalue(),
                    )

                st.success("Results imported successfully.")

                warnings = result.get("warnings", [])
                for warning in warnings:
                    st.warning(str(warning))

                run = result.get("run", {})
                job = result.get("job", {})

                col1, col2 = st.columns(2)

                with col1:
                    st.subheader("Imported run")
                    st.json(run)

                with col2:
                    st.subheader("Plot job")
                    st.json(job)

                if job.get("id"):
                    st.info(
                        f"Plot job `{job['id']}` was created. "
                        "Track its status in the Jobs page."
                    )

            except Exception as exc:
                st.error("Could not upload the result bundle.")
                st.exception(exc)

    st.subheader("Expected ZIP structure")

    st.code(
        """
result_bundle.zip
├── manifest.yaml
├── benchmark_out/
│   ├── AGENT_NAME/                 # required for learning
│   │   ├── EXPERIMENT_NAME/
│   │   │   └── seed.../profile/nrewards.txt
│   │   └── ...
│   ├── *_summary_episode_*.csv     # sensing/attention/motivation
│   ├── *_per_trial_episode_*.csv   # sensing/attention/motivation
│   └── other result files
└── optional/
    ├── config.json
    ├── notes.md
    └── plots/
        """.strip(),
        language="text",
    )

    st.subheader("Example manifest.yaml")

    st.code(
        """
agent_name: Substage3
architecture_name: CONAIM
benchmark: motivation
benchmark_version: motivation_v1
cogscore_version: "0.1.0"
run_name: "Substage3 motivation test"
date: "2026-07-13"

parameters:
  episodes: 50
  trials_per_experiment: 20
  seed: 777
  x_points: 50
  smooth_window: 7

source:
  type: uploaded_results
  author: Leonardo
  notes: "Results generated locally."
        """.strip(),
        language="yaml",
    )
    
elif page == "Architectures":
    st.title("Architectures")

    try:
        items = api_get("/architectures")

        if items:
            df = pd.DataFrame(items)
            st.dataframe(df, use_container_width=True)

            selected_id = st.selectbox(
                "Inspect architecture",
                [item["id"] for item in items],
            )

            selected_arch = next(item for item in items if item["id"] == selected_id)

            st.subheader("Architecture details")
            st.json(selected_arch)

            st.subheader("Manifest")

            try:
                manifest = json.loads(selected_arch.get("manifest_json") or "{}")
                st.json(manifest)

                declared = manifest.get("benchmarks", [])
                if isinstance(declared, list):
                    st.write("Declared benchmarks:")
                    st.write(", ".join(str(x) for x in declared))

                    if "learning" in declared:
                        st.success("This architecture declares support for learning.")
                    else:
                        st.warning("This architecture does not declare support for learning.")
            except Exception:
                st.warning("Could not parse manifest_json.")
        else:
            st.info("No architectures uploaded yet.")
    except Exception as exc:
        st.exception(exc)

elif page == "Sensing experiments":
    st.title("Sensing experiments")

    architectures = api_get("/architectures")
    validated = validated_architectures_for(architectures, "sensory_buffer")

    if not validated:
        st.warning("No validated architecture compatible with this benchmark is available.")
    else:
        labels = [f"{a['name']} {a['version']} ({a['id']})" for a in validated]
        selected = st.selectbox("Architecture", labels)
        arch = validated[labels.index(selected)]

        col1, col2, col3 = st.columns(3)

        with col1:
            episodes = st.number_input("Episodes", min_value=1, value=1)
            trials_per_delay = st.number_input("Trials per delay", min_value=1, value=3)

        with col2:
            resolution = st.number_input("Resolution", min_value=8, value=64)
            patch_size = st.number_input("Patch size", min_value=1, value=8)

        with col3:
            scene = st.text_input("Scene", value="sperling.ttt")
            mode = st.selectbox("Mode", ["vnc", "headless"])

        delays_text = st.text_input("Delays ms", value="0,50,100,220,500,1000")
        delays_ms = [int(x.strip()) for x in delays_text.split(",") if x.strip()]

        if st.button("Create sensing experiment job"):
            payload = {
                "architecture_id": arch["id"],
                "benchmark": "sensory_buffer",
                "scene": scene,
                "episodes": int(episodes),
                "trials_per_delay": int(trials_per_delay),
                "delays_ms": delays_ms,
                "resolution": int(resolution),
                "patch_size": int(patch_size),
                "mode": mode,
            }

            try:
                result = api_post_json("/jobs/run-experiment", payload)
                st.success("Experiment job created")
                st.json(result)
            except Exception as exc:
                st.error("Could not create job")
                st.exception(exc)

elif page == "Attention experiments":
    st.title("Attention experiments")

    try:
        architectures = api_get("/architectures")
    except Exception as exc:
        st.error("Could not load architectures")
        st.exception(exc)
        st.stop()

    validated = validated_architectures_for(architectures, "attention_posner")

    if not validated:
        st.warning("No validated architecture compatible with this benchmark is available.")
    else:
        labels = [f"{a['name']} {a['version']} ({a['id']})" for a in validated]
        selected = st.selectbox("Architecture", labels)
        arch = validated[labels.index(selected)]

        col1, col2, col3 = st.columns(3)

        with col1:
            episodes = st.number_input(
                "Episodes",
                min_value=1,
                value=1,
                key="attention_episodes",
            )

            trials_per_experiment = st.number_input(
                "Trials per experiment",
                min_value=1,
                value=20,
                key="attention_trials_per_experiment",
            )

        with col2:
            map_width = st.number_input(
                "Attention map width",
                min_value=8,
                value=32,
                key="attention_map_width",
            )

            map_height = st.number_input(
                "Attention map height",
                min_value=8,
                value=32,
                key="attention_map_height",
            )

        with col3:
            scene = st.text_input(
                "Scene",
                value="posner.ttt",
                key="attention_scene",
            )

            mode = st.selectbox(
                "Mode",
                ["vnc", "headless"],
                key="attention_mode",
            )

        col4, col5 = st.columns(2)

        with col4:
            cycles_per_trial = st.number_input(
                "Cycles per trial",
                min_value=1,
                value=30,
                key="attention_cycles_per_trial",
            )

        with col5:
            seed = st.number_input(
                "Seed",
                min_value=0,
                value=777,
                key="attention_seed",
            )

        experiments_text = st.text_input(
            "Posner experiments",
            value="1,2,3,4,5",
            help="Use 1,2,3,4,5 to run all Posner attention experiments.",
            key="attention_experiments_text",
        )

        try:
            posner_experiments = [
                int(x.strip())
                for x in experiments_text.split(",")
                if x.strip()
            ]
        except ValueError:
            st.error("Invalid Posner experiment list. Use something like: 1,2,3,4,5")
            st.stop()

        st.info(
            "This will run the attention_posner benchmark using the selected external architecture."
        )

        if st.button("Create attention experiment job"):
            payload = {
                "architecture_id": arch["id"],
                "benchmark": "attention_posner",
                "scene": scene,
                "episodes": int(episodes),
                "posner_experiments": posner_experiments,
                "trials_per_experiment": int(trials_per_experiment),
                "map_width": int(map_width),
                "map_height": int(map_height),
                "cycles_per_trial": int(cycles_per_trial),
                "seed": int(seed),
                "mode": mode,
            }

            try:
                result = api_post_json("/jobs/run-experiment", payload)
                st.success("Attention Posner experiment job created")
                st.json(result)
            except Exception as exc:
                st.error("Could not create attention experiment job")
                st.exception(exc)
                

elif page == "Motivation experiments":
    st.title("Motivation experiments")

    try:
        architectures = api_get("/architectures")
    except Exception as exc:
        st.error("Could not load architectures")
        st.exception(exc)
        st.stop()

    validated = validated_architectures_for(architectures, "motivation")

    if not validated:
        st.warning("No validated architecture compatible with this benchmark is available.")
    else:
        labels = [f"{a['name']} {a['version']} ({a['id']})" for a in validated]
        selected = st.selectbox("Architecture", labels, key="motivation_architecture")
        arch = validated[labels.index(selected)]

        col1, col2, col3 = st.columns(3)

        with col1:
            episodes = st.number_input(
                "Episodes",
                min_value=1,
                value=1,
                key="motivation_episodes",
            )

            trials_per_experiment = st.number_input(
                "Trials per experiment",
                min_value=1,
                value=20,
                key="motivation_trials_per_experiment",
            )

        with col2:
            cycles_per_motivation_trial = st.number_input(
                "Cycles per motivation trial",
                min_value=1,
                value=30,
                key="motivation_cycles_per_trial",
            )

            seed = st.number_input(
                "Seed",
                min_value=0,
                value=777,
                key="motivation_seed",
            )

        with col3:
            scene = st.text_input(
                "Scene",
                value="mot.ttt",
                key="motivation_scene",
            )

            mode = st.selectbox(
                "Mode",
                ["vnc", "headless"],
                key="motivation_mode",
            )

        experiments_text = st.text_input(
            "Motivation experiments",
            value="1,2,3,4,5",
            help="Use 1,2,3,4,5 to run all motivation experiments.",
            key="motivation_experiments_text",
        )

        try:
            motivation_experiments = [
                int(x.strip())
                for x in experiments_text.split(",")
                if x.strip()
            ]
        except ValueError:
            st.error("Invalid motivation experiment list. Use something like: 1,2,3,4,5")
            st.stop()

        if not motivation_experiments:
            st.error("Provide at least one motivation experiment id.")
            st.stop()

        st.info(
            "This will run the motivation benchmark using the selected external architecture. "
            "The worker will call /motivation/act on the architecture container."
        )

        if st.button("Create motivation experiment job"):
            payload = {
                "architecture_id": arch["id"],
                "benchmark": "motivation",
                "scene": scene,
                "episodes": int(episodes),
                "motivation_experiments": motivation_experiments,
                "trials_per_experiment": int(trials_per_experiment),
                "cycles_per_motivation_trial": int(cycles_per_motivation_trial),
                "seed": int(seed),
                "mode": mode,
            }

            try:
                result = api_post_json("/jobs/run-experiment", payload)
                st.success("Motivation experiment job created")
                st.json(result)
            except Exception as exc:
                st.error("Could not create motivation experiment job")
                st.exception(exc)

elif page == "Learning experiments":
    st.title("Learning experiments")

    try:
        architectures = api_get("/architectures")
    except Exception as exc:
        st.error("Could not load architectures")
        st.exception(exc)
        st.stop()

    validated = validated_architectures_for(architectures, "learning")

    if not validated:
        st.warning("No validated architecture compatible with this benchmark is available.")
        st.info(
            "The selected architecture bundle must declare `learning` in its manifest.yaml "
            "under the `benchmarks` field."
        )
    else:
        labels = [f"{a['name']} {a['version']} ({a['id']})" for a in validated]
        selected = st.selectbox("Architecture", labels, key="learning_architecture")
        arch = validated[labels.index(selected)]

        col1, col2, col3 = st.columns(3)

        with col1:
            episodes = st.number_input(
                "Episodes",
                min_value=1,
                value=1,
                key="learning_episodes",
            )

            steps_per_episode = st.number_input(
                "Steps per episode",
                min_value=1,
                value=100,
                key="learning_steps_per_episode",
            )

        with col2:
            seed = st.number_input(
                "Seed",
                min_value=0,
                value=777,
                key="learning_seed",
            )

            aggregate_n = st.number_input(
                "Aggregate N",
                min_value=1,
                value=5,
                key="learning_aggregate_n",
                help="Window used by learning.py when aggregating epochs for plots.",
            )

        with col3:
            scene = st.text_input(
                "Scene",
                value="learning/testing_s1A.ttt",
                key="learning_scene",
            )

            mode = st.selectbox(
                "Mode",
                ["vnc", "headless"],
                key="learning_mode",
            )

        stages_text = st.text_input(
            "Learning stages",
            value="Substage1,Substage2,Substage3,Substage4,Substage5",
            help="Use the developmental sequence Substage1..Substage5 to run the complete learning evaluation.",
            key="learning_stages_text",
        )

        tests_text = st.text_input(
            "Learning tests",
            value="testA,testB,testAB",
            help="Substage1-3 usually use testA/testB; Substage4 uses testA/testAB/testB; Substage5 uses testA.",
            key="learning_tests_text",
        )

        learning_stages = [
            x.strip()
            for x in stages_text.split(",")
            if x.strip()
        ]

        learning_tests = [
            x.strip()
            for x in tests_text.split(",")
            if x.strip()
        ]

        if not learning_stages:
            st.error("Provide at least one learning stage.")
            st.stop()

        if not learning_tests:
            st.error("Provide at least one learning test.")
            st.stop()

        st.info(
            "This will run the learning benchmark using the selected external architecture. "
            "The worker will call /learning/act on the architecture container."
        )

        st.subheader("Expected output structure")

        st.code(
            """
benchmark_out/
├── Substage1/
│   ├── testA/seed777/profile/nrewards.txt
│   └── testB/seed777/profile/nrewards.txt
├── Substage2/
│   ├── testA/seed777/profile/nrewards.txt
│   └── testB/seed777/profile/nrewards.txt
├── Substage3/
│   ├── testA/seed777/profile/nrewards.txt
│   └── testB/seed777/profile/nrewards.txt
├── Substage4/
│   ├── testA/seed777/profile/nrewards.txt
│   ├── testAB/seed777/profile/nrewards.txt
│   └── testB/seed777/profile/nrewards.txt
└── Substage5/
    └── testA/seed777/profile/nrewards.txt
            """.strip(),
            language="text",
        )

        if st.button("Create learning experiment job"):
            payload = {
                "architecture_id": arch["id"],
                "benchmark": "learning",
                "scene": scene,
                "episodes": int(episodes),
                "learning_stages": learning_stages,
                "learning_tests": learning_tests,
                "steps_per_episode": int(steps_per_episode),
                "seed": int(seed),
                "aggregate_n": int(aggregate_n),
                "mode": mode,
            }

            try:
                result = api_post_json("/jobs/run-experiment", payload)
                st.success("Learning experiment job created")
                st.json(result)
            except Exception as exc:
                st.error("Could not create learning experiment job")
                st.exception(exc)

elif page == "Jobs":
    st.title("Jobs")

    jobs = api_get("/jobs")
    if jobs:
        st.dataframe(pd.DataFrame(jobs), use_container_width=True)

        selected = st.selectbox("Inspect job", [j["id"] for j in jobs])
        job = next(j for j in jobs if j["id"] == selected)

        st.subheader("Input")
        st.json(json.loads(job["input_json"]))

        st.subheader("Output")
        if job.get("output_json"):
            st.json(json.loads(job["output_json"]))
        else:
            st.info("No output yet.")

        if job.get("error_message"):
            st.subheader("Error")
            st.error(str(job["error_message"]))

        log_path = job.get("log_path")
        if log_path:
            resolved_log_path = resolve_data_path(str(log_path))
            for log_name in ("stderr.log", "stdout.log"):
                path = resolved_log_path / log_name
                if path.exists():
                    text = path.read_text(encoding="utf-8", errors="replace")
                    st.subheader(log_name)
                    st.code(text[-12000:] or "(empty log)", language="text")
    else:
        st.info("No jobs yet.")


elif page == "Experiment runs":
    st.title("Experiment runs")

    runs = api_get("/experiment-runs")

    if runs:
        df = pd.DataFrame(runs)

        benchmarks = ["all"] + sorted(
            str(x)
            for x in df.get("benchmark", pd.Series(dtype=str)).dropna().unique()
        )

        selected_benchmark = st.selectbox(
            "Benchmark filter",
            benchmarks,
            key="experiment_runs_benchmark_filter",
        )

        if selected_benchmark != "all" and "benchmark" in df.columns:
            df = df[df["benchmark"] == selected_benchmark]

        st.dataframe(df, use_container_width=True)
    else:
        st.info("No experiment runs yet.")

elif page == "Plots":
    st.title("Plots")

    plots_dir = Path(
        os.getenv("PLOTS_DIR", "/data/plots")
    ).resolve()

    st.caption(f"Directory: `{plots_dir}`")

    def render_rebuild_controls() -> None:
        st.divider()
        st.subheader("Generate a new comparison")
        st.caption(
            "Rebuild creates a new generation of plots without deleting previous ones. "
            "The comparison includes the most recent valid result for each agent "
            "already imported, including both existing and newly added agents."
        )

        replot_options = {
            "All benchmarks with results": "all",
            "Sensing": "sensory_buffer",
            "Attention (Posner)": "attention_posner",
            "Motivation": "motivation",
            "Learning": "learning",
        }
        replot_label = st.selectbox(
            "Benchmark to rebuild",
            list(replot_options),
            key="replot_benchmark",
        )

        action_col, refresh_col = st.columns([1, 1])

        with action_col:
            if st.button("Rebuild", type="primary", use_container_width=True):
                try:
                    result = api_post_json(
                        "/plots/rebuild",
                        {"benchmark": replot_options[replot_label]},
                    )
                    st.session_state["last_replot_result"] = result
                    st.success(result.get("message", "Plot jobs created."))
                except Exception as exc:
                    st.error("Could not create the new plot jobs.")
                    st.exception(exc)

        with refresh_col:
            if st.button("Refresh plots", use_container_width=True):
                st.rerun()

        last_replot = st.session_state.get("last_replot_result")
        if last_replot:
            jobs_created = last_replot.get("jobs", [])
            if jobs_created:
                st.markdown("**Most recently created jobs**")
                st.dataframe(
                    pd.DataFrame(jobs_created),
                    use_container_width=True,
                    hide_index=True,
                )

    try:
        plot_items = api_get("/plots")
    except Exception as exc:
        st.error("Could not load plot metadata from the API.")
        st.exception(exc)
        st.stop()

    if not plot_items:
        st.info(
            "No plots were found. Use Rebuild after importing at least one result bundle."
        )
        render_rebuild_controls()
        st.stop()

    image_extensions = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
    image_items = [
        item
        for item in plot_items
        if str(item.get("extension", "")).lower() in image_extensions
    ]
    html_items = [
        item
        for item in plot_items
        if str(item.get("extension", "")).lower() == ".html"
    ]

    def item_metadata(item: dict[str, Any]) -> dict[str, Any]:
        metadata = item.get("metadata")
        return metadata if isinstance(metadata, dict) else {}

    def benchmark_id(item: dict[str, Any]) -> str:
        metadata = item_metadata(item)
        benchmark = metadata.get("benchmark", {})
        if isinstance(benchmark, dict) and benchmark.get("id"):
            return str(benchmark["id"])
        relative = str(item.get("relative_path", ""))
        return relative.split("/", 1)[0] if relative else "unknown"

    def benchmark_title(item: dict[str, Any]) -> str:
        metadata = item_metadata(item)
        benchmark = metadata.get("benchmark", {})
        if isinstance(benchmark, dict) and benchmark.get("title"):
            return str(benchmark["title"])
        return benchmark_id(item).replace("_", " ").title()

    def generation_id(item: dict[str, Any]) -> str:
        provenance = item_metadata(item).get("provenance", {})
        if isinstance(provenance, dict) and provenance.get("generation_id"):
            return str(provenance["generation_id"])
        relative = str(item.get("relative_path", ""))
        parts = relative.split("/")
        return parts[2] if len(parts) >= 3 else parts[1] if len(parts) >= 2 else "legacy"

    def generation_label(item: dict[str, Any]) -> str:
        metadata = item_metadata(item)
        provenance = metadata.get("provenance", {})
        generation = generation_id(item)
        scope = provenance.get("scope", "") if isinstance(provenance, dict) else ""
        generated_at = provenance.get("generated_at", "") if isinstance(provenance, dict) else ""
        suffix = ""
        if generated_at:
            suffix = f" — {generated_at}"
        elif item.get("modified_at"):
            try:
                suffix = " — " + pd.to_datetime(
                    item["modified_at"], unit="s"
                ).strftime("%Y-%m-%d %H:%M")
            except Exception:
                suffix = ""
        scope_text = f" ({scope})" if scope else ""
        return f"{generation}{scope_text}{suffix}"

    def experiment_key(item: dict[str, Any]) -> str:
        experiment = item_metadata(item).get("experiment", {})
        if isinstance(experiment, dict):
            return str(experiment.get("id") or experiment.get("title") or "unspecified")
        return "unspecified"

    def experiment_title(item: dict[str, Any]) -> str:
        experiment = item_metadata(item).get("experiment", {})
        if isinstance(experiment, dict) and experiment.get("title"):
            return str(experiment["title"])
        return "Multiple or unspecified experimental conditions"

    def plot_title(item: dict[str, Any]) -> str:
        plot = item_metadata(item).get("plot", {})
        if isinstance(plot, dict) and plot.get("title"):
            return str(plot["title"])
        return str(item.get("name", "Plot"))

    st.divider()
    st.subheader("Explore generated results")
    st.caption(
        "The experiment, measure, variables, processing parameters, and provenance "
        "below change with the selected result."
    )

    available_benchmark_ids = sorted(
        {benchmark_id(item) for item in [*image_items, *html_items]}
    )
    benchmark_examples = {
        value: next(
            item
            for item in [*image_items, *html_items]
            if benchmark_id(item) == value
        )
        for value in available_benchmark_ids
    }

    selected_benchmark = st.selectbox(
        "Benchmark",
        available_benchmark_ids,
        format_func=lambda value: benchmark_title(benchmark_examples[value]),
        key="plot_benchmark_filter",
    )

    benchmark_images = [
        item for item in image_items if benchmark_id(item) == selected_benchmark
    ]
    benchmark_html = [
        item for item in html_items if benchmark_id(item) == selected_benchmark
    ]

    generation_examples: dict[str, dict[str, Any]] = {}
    for item in [*benchmark_images, *benchmark_html]:
        generation_examples.setdefault(generation_id(item), item)

    generation_options = sorted(
        generation_examples,
        key=lambda value: float(generation_examples[value].get("modified_at", 0)),
        reverse=True,
    )
    selected_generation = st.selectbox(
        "Generation",
        generation_options,
        format_func=lambda value: generation_label(generation_examples[value]),
        key="plot_generation_filter",
    )

    generation_images = [
        item for item in benchmark_images if generation_id(item) == selected_generation
    ]
    generation_html = [
        item for item in benchmark_html if generation_id(item) == selected_generation
    ]

    if generation_images:
        experiment_examples: dict[str, dict[str, Any]] = {}
        for item in generation_images:
            experiment_examples.setdefault(experiment_key(item), item)

        experiment_options = sorted(
            experiment_examples,
            key=lambda value: experiment_title(experiment_examples[value]),
        )
        selected_experiment = st.selectbox(
            "Experiment",
            experiment_options,
            format_func=lambda value: experiment_title(experiment_examples[value]),
            key="plot_experiment_filter",
        )

        experiment_images = [
            item
            for item in generation_images
            if experiment_key(item) == selected_experiment
        ]
        plot_by_path = {
            str(item.get("relative_path")): item for item in experiment_images
        }
        selected_relative_path = st.selectbox(
            "Plot or measure",
            list(plot_by_path),
            format_func=lambda value: plot_title(plot_by_path[value]),
            key="selected_plot",
        )
        selected_item = plot_by_path[selected_relative_path]
        selected_metadata = item_metadata(selected_item)
        selected_plot_path = resolve_data_path(str(selected_item.get("path", "")))

        plot_column, information_column = st.columns([2, 1], gap="large")

        with plot_column:
            st.subheader(plot_title(selected_item))
            if selected_plot_path.is_file():
                st.image(
                    str(selected_plot_path),
                    caption=str(selected_item.get("relative_path", "")),
                    use_container_width=True,
                )
                with selected_plot_path.open("rb") as plot_file:
                    st.download_button(
                        "Download plot",
                        data=plot_file.read(),
                        file_name=selected_plot_path.name,
                        key=f"download-{selected_relative_path}",
                    )
            else:
                st.error(f"Plot file is not available at `{selected_plot_path}`.")

        with information_column:
            metric = selected_metadata.get("metric", {})
            plot_info = selected_metadata.get("plot", {})
            metric = metric if isinstance(metric, dict) else {}
            plot_info = plot_info if isinstance(plot_info, dict) else {}

            quick_columns = st.columns(2)
            quick_columns[0].metric("Unit", str(metric.get("unit") or "Not specified"))
            quick_columns[1].metric(
                "Preferred direction",
                str(metric.get("direction") or "Not specified"),
            )
            st.metric(
                "Success threshold",
                str(metric.get("threshold") or "Not specified"),
            )

            (
                experiment_tab,
                measure_tab,
                variables_tab,
                interpretation_tab,
                processing_tab,
                provenance_tab,
            ) = st.tabs(
                [
                    "Experiment",
                    "Measure",
                    "Variables",
                    "Interpretation",
                    "Processing",
                    "Provenance",
                ]
            )

            with experiment_tab:
                benchmark = selected_metadata.get("benchmark", {})
                experiment = selected_metadata.get("experiment", {})
                benchmark = benchmark if isinstance(benchmark, dict) else {}
                experiment = experiment if isinstance(experiment, dict) else {}

                if benchmark.get("description"):
                    st.markdown(str(benchmark["description"]))
                st.markdown(f"**{experiment.get('title', 'Experiment')}**")
                st.markdown(str(experiment.get("procedure") or "No procedure description is available."))
                st.markdown("**Expected behavior**")
                st.markdown(
                    str(
                        experiment.get("expected_behavior")
                        or "No expected-behavior description is available."
                    )
                )

            with measure_tab:
                st.markdown(f"**{metric.get('name', 'Measure')}**")
                st.markdown(
                    str(metric.get("description") or "No measure description is available.")
                )
                formula = str(metric.get("formula_latex") or "").strip()
                if formula:
                    st.latex(formula)
                if metric.get("range"):
                    st.markdown(f"**Range:** `{metric['range']}`")

            with variables_tab:
                variables = selected_metadata.get("variables", [])
                if isinstance(variables, list) and variables:
                    for variable in variables:
                        if not isinstance(variable, dict):
                            continue
                        st.markdown(
                            f"**{variable.get('label', 'Variable')}** — "
                            f"{variable.get('description', '')}"
                        )
                else:
                    st.info("No variable description is available for this plot.")

            with interpretation_tab:
                st.markdown(
                    str(
                        selected_metadata.get("interpretation")
                        or "No interpretation guidance is available for this plot."
                    )
                )

            with processing_tab:
                processing = selected_metadata.get("processing", {})
                if isinstance(processing, dict) and processing:
                    st.json(processing)
                else:
                    st.info("No processing metadata is available for this generation.")

            with provenance_tab:
                provenance = selected_metadata.get("provenance", {})
                if isinstance(provenance, dict) and provenance:
                    st.json(provenance)
                else:
                    st.info("No provenance metadata is available for this generation.")

        show_gallery = st.checkbox(
            "Show all images in this experiment",
            value=False,
            key="show_plot_gallery",
        )
        if show_gallery:
            st.subheader("Gallery")
            columns = st.columns(2)
            for index, item in enumerate(experiment_images):
                gallery_path = resolve_data_path(str(item.get("path", "")))
                if not gallery_path.is_file():
                    continue
                with columns[index % 2]:
                    st.markdown(f"**{plot_title(item)}**")
                    st.caption(str(item.get("relative_path", "")))
                    st.image(str(gallery_path), use_container_width=True)
    elif not generation_html:
        st.info("No image plots were found for the selected generation.")

    if generation_html:
        import streamlit.components.v1 as components

        st.subheader("Interactive HTML plots")
        html_by_path = {
            str(item.get("relative_path")): item for item in generation_html
        }
        selected_html_relative = st.selectbox(
            "Select an HTML plot",
            list(html_by_path),
            format_func=lambda value: plot_title(html_by_path[value]),
            key="selected_html_plot",
        )
        selected_html_item = html_by_path[selected_html_relative]
        selected_html_path = resolve_data_path(str(selected_html_item.get("path", "")))

        if selected_html_path.is_file():
            html_content = selected_html_path.read_text(
                encoding="utf-8",
                errors="replace",
            )
            components.html(
                html_content,
                height=800,
                scrolling=True,
            )
        else:
            st.error(f"HTML plot is not available at `{selected_html_path}`.")

    render_rebuild_controls()


elif page == "VNC":
    import streamlit.components.v1 as components

    st.title("CoppeliaSim VNC")

    vnc_url = os.getenv(
        "VNC_PUBLIC_URL",
        "http://localhost:6080/vnc.html"
        "?autoconnect=true"
        "&resize=scale"
        "&password=123",
    )

    st.caption(f"noVNC: `{vnc_url}`")

    components.iframe(
        vnc_url,
        height=850,
        scrolling=True,
    )

    st.markdown(
        f"[Open noVNC in a new tab]({vnc_url})"
    )