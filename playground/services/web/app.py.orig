from __future__ import annotations

import streamlit as st

from cogscore_ui.common import (
    NAV_GROUPS,
    NAV_PAGES,
    apply_theme,
    require_optional_login,
)
from cogscore_ui.pages import assets, dashboard, experiments, help, operations, plots, simulator


st.set_page_config(
    page_title="CogScore Online",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_theme()
require_optional_login()

if "_pending_navigation_page" in st.session_state:
    st.session_state["navigation_page"] = st.session_state.pop(
        "_pending_navigation_page"
    )

if "_pending_navigation_tab" in st.session_state:
    st.session_state["navigation_tab"] = st.session_state.pop(
        "_pending_navigation_tab"
    )
    
requested_page = st.query_params.get("page", "Dashboard")
if requested_page not in NAV_PAGES:
    requested_page = "Dashboard"
if "navigation_page" not in st.session_state:
    st.session_state["navigation_page"] = requested_page

st.sidebar.title("CogScore Online")
st.sidebar.caption("Cognitive architecture evaluation playground")
page = st.sidebar.radio(
    "Navigate",
    NAV_PAGES,
    key="navigation_page",
    format_func=lambda value: f"{NAV_GROUPS[value]} · {value}",
)
st.query_params["page"] = page

if st.sidebar.button("Refresh", use_container_width=True):
    st.rerun()

st.sidebar.divider()
st.sidebar.caption("Standardized sensing, attention, motivation, and learning benchmarks.")

if page == "Dashboard":
    dashboard.render()
elif page == "Architectures":
    assets.render_architectures()
elif page == "Imported results":
    assets.render_imported_results()
elif page == "New experiment":
    experiments.render()
elif page == "Experiment runs":
    operations.render_runs()
elif page == "Plots":
    plots.render()
elif page == "Jobs":
    operations.render_jobs()
elif page == "Simulator":
    simulator.render()
elif page == "Documentation":
    help.render()
