from __future__ import annotations

from typing import Any

import streamlit as st

from .. import api_client
from ..common import (
    BENCHMARKS,
    architecture_manifest,
    architecture_supports,
    benchmark_title,
    navigate,
    render_exception,
)

ATTENTION_EXPERIMENTS = {
    1: "Experiment 1 — Central cueing",
    2: "Experiment 2 — SOA sweep",
    3: "Experiment 3 — Peripheral capture",
    4: "Experiment 4 — Visual search",
    5: "Experiment 5 — Crowding",
}
MOTIVATION_EXPERIMENTS = {
    1: "Experiment 1 — Persistence after stimulus removal",
    2: "Experiment 2 — Drive and curiosity modulation",
    3: "Experiment 3 — Goal substitution and detour",
    4: "Experiment 4 — Latent learning",
    5: "Experiment 5 — Outcome devaluation",
}
LEARNING_STAGES = ["Substage1", "Substage2", "Substage3", "Substage4", "Substage5"]
LEARNING_TESTS = ["testA", "testB", "testAB"]


def _preset_values(preset: str) -> dict[str, int]:
    if preset == "Smoke test":
        return {
            "episodes": 1,
            "trials": 3,
            "cycles": 10,
            "steps": 50,
        }
    if preset == "Standard evaluation":
        return {
            "episodes": 50,
            "trials": 20,
            "cycles": 30,
            "steps": 500,
        }
    return {
        "episodes": int(st.session_state.get("custom_episodes", 10)),
        "trials": int(st.session_state.get("custom_trials", 10)),
        "cycles": int(st.session_state.get("custom_cycles", 30)),
        "steps": int(st.session_state.get("custom_steps", 100)),
    }


def _architecture_label(item: dict[str, Any]) -> str:
    benchmarks = architecture_manifest(item).get("benchmarks", [])
    readable = ", ".join(benchmark_title(str(value)) for value in benchmarks) if isinstance(benchmarks, list) else "All"
    return f"{item['name']} {item['version']} — {readable}"


def render() -> None:
    st.title("New experiment")
    st.caption("Configure and launch an online CogScore experiment with a validated external architecture.")

    draft = st.session_state.pop("experiment_draft", None)
    try:
        architectures = api_client.get("/architectures")
    except Exception as exc:
        render_exception("Could not load architectures", exc)
        return

    validated = [item for item in architectures if item.get("status") == "validated"]
    if not validated:
        st.warning("No validated architecture is available.")
        if st.button("Upload an architecture"):
            navigate("Architectures", tab="upload")
        return

    st.markdown("### 1. Select architecture")
    architecture_ids = [item["id"] for item in validated]
    preferred_arch = st.session_state.pop("experiment_architecture_id", None)
    if isinstance(draft, dict):
        preferred_arch = draft.get("architecture_id") or preferred_arch
    default_index = architecture_ids.index(preferred_arch) if preferred_arch in architecture_ids else 0
    selected_architecture_id = st.selectbox(
        "Architecture",
        architecture_ids,
        index=default_index,
        format_func=lambda value: _architecture_label(next(item for item in validated if item["id"] == value)),
    )
    architecture = next(item for item in validated if item["id"] == selected_architecture_id)

    supported = [key for key in BENCHMARKS if architecture_supports(architecture, key)]
    st.markdown("### 2. Select benchmark")
    preferred_benchmark = draft.get("benchmark") if isinstance(draft, dict) else None
    benchmark_index = supported.index(preferred_benchmark) if preferred_benchmark in supported else 0
    benchmark = st.selectbox(
        "Benchmark",
        supported,
        index=benchmark_index,
        format_func=lambda value: f"{benchmark_title(value)} — {BENCHMARKS[value]['description']}",
    )

    st.markdown("### 3. Configure")
    preset = st.radio(
        "Preset",
        ["Smoke test", "Standard evaluation", "Custom"],
        horizontal=True,
        help="Smoke tests validate integration. Standard evaluation uses the default scientific workload. Custom exposes all values.",
    )
    defaults = _preset_values(preset)

    if isinstance(draft, dict):
        parameters = draft.get("parameters", {})
        if isinstance(parameters, dict):
            defaults["episodes"] = int(parameters.get("episodes", defaults["episodes"]))
            defaults["trials"] = int(parameters.get("trials_per_experiment", parameters.get("trials_per_delay", defaults["trials"])))
            defaults["cycles"] = int(parameters.get("cycles_per_trial", parameters.get("cycles_per_motivation_trial", defaults["cycles"])))
            defaults["steps"] = int(parameters.get("steps_per_episode", defaults["steps"]))

    cols = st.columns(2)
    with cols[0]:
        episodes = st.number_input("Episodes", min_value=1, value=int(defaults["episodes"]), key="experiment_episodes")
    with cols[1]:
        mode = st.selectbox("Execution mode", ["headless", "vnc"], help="Use VNC when you need to observe the simulator. Headless is preferable for unattended runs.")

    payload: dict[str, Any] = {
        "architecture_id": selected_architecture_id,
        "benchmark": benchmark,
        "episodes": int(episodes),
        "mode": mode,
    }

    if benchmark == "sensory_buffer":
        delay_preset = st.selectbox(
            "Delay set",
            ["Short sensory range", "Extended decay", "Custom"],
        )
        known_delays = [0, 50, 100, 220, 500, 1000, 2000, 5000, 10000]
        if delay_preset == "Short sensory range":
            delays = [0, 50, 100, 220]
        elif delay_preset == "Extended decay":
            delays = [0, 50, 100, 220, 500, 1000]
        else:
            delays = st.multiselect("Delays (ms)", known_delays, default=[0, 50, 100, 220, 500, 1000])
        payload.update(
            {
                "delays_ms": delays,
                "trials_per_delay": int(st.number_input("Trials per delay", min_value=1, value=int(defaults["trials"]))),
            }
        )
    elif benchmark == "attention_posner":
        selected_labels = st.multiselect(
            "Attention experiments",
            list(ATTENTION_EXPERIMENTS.values()),
            default=list(ATTENTION_EXPERIMENTS.values()),
        )
        payload.update(
            {
                "posner_experiments": [key for key, label in ATTENTION_EXPERIMENTS.items() if label in selected_labels],
                "trials_per_experiment": int(st.number_input("Trials per experiment", min_value=1, value=int(defaults["trials"]))),
                "cycles_per_trial": int(st.number_input("Cycles per trial", min_value=1, value=int(defaults["cycles"]))),
            }
        )
    elif benchmark == "motivation":
        selected_labels = st.multiselect(
            "Motivation experiments",
            list(MOTIVATION_EXPERIMENTS.values()),
            default=list(MOTIVATION_EXPERIMENTS.values()),
        )
        payload.update(
            {
                "motivation_experiments": [key for key, label in MOTIVATION_EXPERIMENTS.items() if label in selected_labels],
                "trials_per_experiment": int(st.number_input("Trials per experiment", min_value=1, value=int(defaults["trials"]))),
                "cycles_per_motivation_trial": int(st.number_input("Cycles per trial", min_value=1, value=int(defaults["cycles"]))),
            }
        )
    else:
        payload.update(
            {
                "learning_stages": st.multiselect("Developmental stages", LEARNING_STAGES, default=LEARNING_STAGES),
                "learning_tests": st.multiselect("Learning tests", LEARNING_TESTS, default=LEARNING_TESTS),
                "steps_per_episode": int(st.number_input("Steps per episode", min_value=1, value=int(defaults["steps"]))),
                "aggregate_n": int(st.number_input("Plot aggregation window", min_value=1, value=5)),
            }
        )

    with st.expander("Advanced parameters"):
        payload["seed"] = int(st.number_input("Seed", min_value=0, value=777))
        default_scene = BENCHMARKS[benchmark]["scene"]
        scene_mode = st.selectbox("Scene", [default_scene, "Custom path"])
        payload["scene"] = st.text_input("Custom scene path", value=default_scene) if scene_mode == "Custom path" else default_scene
        if benchmark == "sensory_buffer":
            payload["resolution"] = int(st.number_input("Image resolution", min_value=8, value=64))
            payload["patch_size"] = int(st.number_input("Patch size", min_value=1, value=8))
        elif benchmark == "attention_posner":
            map_cols = st.columns(2)
            payload["map_width"] = int(map_cols[0].number_input("Attention map width", min_value=8, value=32))
            payload["map_height"] = int(map_cols[1].number_input("Attention map height", min_value=8, value=32))

    st.markdown("### 4. Review and launch")
    summary = {
        "Architecture": f"{architecture['name']} {architecture['version']}",
        "Benchmark": benchmark_title(benchmark),
        "Episodes": payload.get("episodes"),
        "Mode": payload.get("mode"),
        "Scene": payload.get("scene"),
        "Seed": payload.get("seed"),
    }
    st.table([summary])
    with st.expander("Complete request"):
        st.json(payload)

    invalid = False
    for key in ("delays_ms", "posner_experiments", "motivation_experiments", "learning_stages", "learning_tests"):
        if key in payload and not payload[key]:
            st.error(f"Select at least one value for {key.replace('_', ' ')}.")
            invalid = True

    if st.button("Run experiment", type="primary", disabled=invalid, use_container_width=True):
        try:
            with st.spinner("Creating experiment run and worker job..."):
                result = api_client.post_json("/jobs/run-experiment", payload)
            st.success("Experiment job created.")
            cols = st.columns(2)
            cols[0].metric("Run", result.get("run_id", "—"))
            cols[1].metric("Job", result.get("job_id", "—"))
            actions = st.columns(2)
            if actions[0].button("Track run", key="track_new_run"):
                navigate("Experiment runs", run=str(result.get("run_id", "")))
            if actions[1].button("Track job", key="track_new_job"):
                navigate("Jobs", job=str(result.get("job_id", "")))
        except Exception as exc:
            render_exception("Could not create the experiment", exc)
