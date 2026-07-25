from __future__ import annotations

import io
import json
import os
import zipfile
from typing import Any

import pandas as pd
import streamlit as st
import yaml

from .. import api_client
from ..common import (
    BENCHMARKS,
    architecture_manifest,
    benchmark_title,
    format_datetime,
    navigate,
    parse_json,
    render_exception,
    status_badge,
)


MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))


def _zip_preflight(data: bytes, *, architecture: bool) -> tuple[list[tuple[str, bool, str]], dict[str, Any]]:
    checks: list[tuple[str, bool, str]] = []
    manifest: dict[str, Any] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as bundle:
            names = {name.lstrip("./") for name in bundle.namelist() if not name.endswith("/")}
            checks.append(("Valid ZIP archive", True, f"{len(names)} file(s) detected"))
            checks.append(("manifest.yaml at bundle root", "manifest.yaml" in names, "Required metadata file"))
            if architecture:
                checks.append(("Dockerfile at bundle root", "Dockerfile" in names, "Required container definition"))
            else:
                checks.append(("benchmark_out directory", any(name.startswith("benchmark_out/") for name in names), "Required result directory"))
            if "manifest.yaml" in names:
                raw = bundle.read("manifest.yaml").decode("utf-8", errors="replace")
                loaded = yaml.safe_load(raw)
                if isinstance(loaded, dict):
                    manifest = loaded
                    checks.append(("Manifest is a YAML mapping", True, "Parsed successfully"))
                else:
                    checks.append(("Manifest is a YAML mapping", False, "The root value must be a mapping"))
    except zipfile.BadZipFile:
        checks.append(("Valid ZIP archive", False, "The selected file is not a valid ZIP archive"))
    return checks, manifest


def _render_checks(checks: list[tuple[str, bool, str]]) -> bool:
    all_valid = True
    for label, valid, detail in checks:
        all_valid = all_valid and valid
        icon = "✓" if valid else "×"
        st.markdown(f"**{icon} {label}**  \n{detail}")
    return all_valid


def render_architectures() -> None:
    st.title("Architectures")
    st.caption("Upload, validate, inspect, and execute external REST-based cognitive architectures.")

    requested_tab = st.query_params.get("tab", "browse")
    browse_tab, upload_tab = st.tabs(["Browse architectures", "Upload architecture"])

    with upload_tab:
        st.subheader("Upload architecture bundle")
        st.markdown("The ZIP root must contain `manifest.yaml` and `Dockerfile`. Validation builds the image and runs interface smoke tests.")
        uploaded = st.file_uploader("Architecture ZIP", type=["zip"], key="architecture_upload")
        if uploaded is not None:
            data = uploaded.getvalue()
            st.caption(f"{uploaded.name} · {len(data) / (1024 * 1024):.2f} MB")
            if len(data) > MAX_UPLOAD_BYTES:
                st.error("The selected file exceeds the configured upload limit.")
            else:
                checks, manifest = _zip_preflight(data, architecture=True)
                st.markdown("#### Preflight validation")
                valid = _render_checks(checks)
                if manifest:
                    with st.expander("Detected manifest"):
                        st.json(manifest)
                if st.button("Upload and validate", type="primary", disabled=not valid, key="submit_architecture_upload"):
                    try:
                        with st.spinner("Uploading the bundle and creating the validation job..."):
                            result = api_client.upload("/architectures/upload", uploaded.name, data)
                        st.success("Architecture uploaded. Validation has been queued.")
                        cols = st.columns(2)
                        cols[0].metric("Architecture", result.get("architecture_id", "—"))
                        cols[1].metric("Validation job", result.get("validation_job_id", "—"))
                        if st.button("Track validation job", key="track_arch_validation"):
                            navigate("Jobs", job=result.get("validation_job_id", ""))
                    except Exception as exc:
                        render_exception("Architecture upload failed", exc)

        with st.expander("Expected bundle structure"):
            st.code(
                """architecture_bundle.zip
├── manifest.yaml
├── Dockerfile
├── requirements.txt
└── app.py""",
                language="text",
            )

    with browse_tab:
        try:
            architectures = api_client.get("/architectures")
        except Exception as exc:
            render_exception("Could not load architectures", exc)
            return

        if not architectures:
            st.info("No architectures have been uploaded.")
            return

        status_filter = st.multiselect(
            "Status",
            sorted({str(item.get("status", "unknown")) for item in architectures}),
            default=sorted({str(item.get("status", "unknown")) for item in architectures}),
            format_func=lambda value: value.replace("_", " ").title(),
        )
        filtered = [item for item in architectures if item.get("status") in status_filter]

        labels: dict[str, str] = {}
        for item in filtered:
            labels[item["id"]] = f"{item['name']} {item['version']} — {item.get('status', 'unknown').title()}"
        selected_id = st.selectbox("Architecture", list(labels), format_func=lambda value: labels[value])
        selected = next(item for item in filtered if item["id"] == selected_id)
        manifest = architecture_manifest(selected)
        benchmarks = manifest.get("benchmarks", []) if isinstance(manifest.get("benchmarks"), list) else []

        st.markdown(
            f'<div class="cog-card"><div class="cog-eyebrow">Architecture</div>'
            f'<h4>{selected.get("name")} {selected.get("version")}</h4>'
            f'{status_badge(str(selected.get("status", "unknown")))}'
            f'<p class="cog-muted">{selected.get("author") or "Author not specified"} · REST interface · {selected.get("id")}</p></div>',
            unsafe_allow_html=True,
        )
        overview_tab, validation_tab, manifest_tab, raw_tab = st.tabs(["Overview", "Validation", "Manifest", "Raw record"])
        with overview_tab:
            cols = st.columns(3)
            cols[0].metric("Interface", selected.get("interface_type", "—"))
            cols[1].metric("Created", format_datetime(selected.get("created_at")))
            cols[2].metric("Validated", format_datetime(selected.get("validated_at")))
            st.markdown("**Supported benchmarks**")
            if benchmarks:
                st.write(" · ".join(benchmark_title(str(value)) for value in benchmarks))
            else:
                st.write("Not declared")
            if selected.get("status") == "validated" and st.button("Run an experiment with this architecture", type="primary"):
                st.session_state["experiment_architecture_id"] = selected["id"]
                navigate("New experiment")
        with validation_tab:
            if selected.get("status") == "error":
                st.error("Validation failed. Review the message below and upload a corrected bundle as a new architecture version.")
                st.code(str(selected.get("error_message") or "No validation message was recorded."), language="text")
            elif selected.get("status") == "validated":
                st.success("The architecture image was built and the declared REST interface passed validation.")
                if selected.get("image_tag"):
                    st.code(str(selected["image_tag"]), language="text")
            else:
                st.info("Validation is pending or still in progress. Track the associated job on the Jobs page.")
        with manifest_tab:
            st.json(manifest)
        with raw_tab:
            st.json(selected)


def render_imported_results() -> None:
    st.title("Imported results")
    st.caption("Import result bundles generated outside the online runner and create comparison plots.")

    browse_tab, upload_tab = st.tabs(["Browse imported runs", "Upload results"])
    with upload_tab:
        uploaded = st.file_uploader("Result bundle ZIP", type=["zip"], key="results_upload")
        if uploaded is not None:
            data = uploaded.getvalue()
            st.caption(f"{uploaded.name} · {len(data) / (1024 * 1024):.2f} MB")
            checks, manifest = _zip_preflight(data, architecture=False)
            valid = _render_checks(checks)
            if manifest:
                st.markdown("#### Detected run")
                cols = st.columns(4)
                cols[0].metric("Agent", manifest.get("agent_name", "—"))
                cols[1].metric("Architecture", manifest.get("architecture_name", "—"))
                cols[2].metric("Benchmark", benchmark_title(str(manifest.get("benchmark", ""))))
                params = manifest.get("parameters", {}) if isinstance(manifest.get("parameters"), dict) else {}
                cols[3].metric("Episodes", params.get("episodes", "—"))
                with st.expander("Manifest"):
                    st.json(manifest)
            if st.button("Import results and generate plots", type="primary", disabled=not valid, key="submit_results_upload"):
                try:
                    with st.spinner("Uploading, validating, importing, and creating the plot job..."):
                        result = api_client.upload("/uploads/results", uploaded.name, data)
                    st.success("Results imported successfully.")
                    for warning in result.get("warnings", []):
                        st.warning(str(warning))
                    run = result.get("run", {})
                    job = result.get("job", {})
                    cols = st.columns(2)
                    cols[0].metric("Imported run", run.get("id", "—"))
                    cols[1].metric("Plot job", job.get("id", "—"))
                    actions = st.columns(2)
                    if actions[0].button("Track plot job", key="track_import_plot_job"):
                        navigate("Jobs", job=str(job.get("id", "")))
                    if actions[1].button("Open plots", key="open_import_plots"):
                        navigate("Plots", benchmark=str(run.get("benchmark", "")))
                except Exception as exc:
                    render_exception("Result import failed", exc)

        with st.expander("Expected bundle structure"):
            st.code(
                """result_bundle.zip
├── manifest.yaml
└── benchmark_out/
    ├── AGENT/EXPERIMENT/...        # learning
    └── *_summary_episode_*.csv     # other benchmarks""",
                language="text",
            )

    with browse_tab:
        try:
            runs = api_client.get("/runs")
        except Exception as exc:
            render_exception("Could not load imported results", exc)
            return
        if not runs:
            st.info("No result bundles have been imported.")
            return
        benchmark_options = sorted({str(item.get("benchmark", "")) for item in runs})
        selected_benchmarks = st.multiselect(
            "Benchmark",
            benchmark_options,
            default=benchmark_options,
            format_func=benchmark_title,
        )
        filtered = [item for item in runs if item.get("benchmark") in selected_benchmarks]
        rows = []
        for item in filtered:
            rows.append(
                {
                    "Agent": item.get("agent_name"),
                    "Architecture": item.get("architecture_name"),
                    "Benchmark": benchmark_title(str(item.get("benchmark", ""))),
                    "Run": item.get("id"),
                    "Episodes": item.get("episodes"),
                    "Created": format_datetime(item.get("created_at")),
                }
            )
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
