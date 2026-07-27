from __future__ import annotations

import streamlit as st

from cogscore_ui.common import apply_theme, navigate, require_optional_login, NAV_PAGES
from cogscore_ui.pages import assets, dashboard, experiments, help, operations, plots, simulator


st.set_page_config(
    page_title="CogScore Online",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="collapsed",
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

def top_navigation() -> None:
    (
        brand,
        dashboard_col,
        assets_col,
        experiments_col,
        analysis_col,
        operations_col,
        help_col,
    ) = st.columns(
        [2.4, 1.3, 1.35, 1.65, 1.7, 1.55, 2.1],
        vertical_alignment="center",
        gap="medium",
    )

    with brand:
        st.markdown(
            """
            <div class="cog-brand">
                CogScore
                <span>Online Playground</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with dashboard_col:
        st.button(
            "Dashboard",
            key="nav_dashboard",
            use_container_width=True,
            on_click=navigate,
            args=("Dashboard",),
        )

    with assets_col:
        with st.popover("Assets", use_container_width=True):
            st.button(
                "Architectures",
                key="nav_architectures",
                use_container_width=True,
                on_click=navigate,
                args=("Architectures",),
            )
            st.button(
                "Imported results",
                key="nav_imported_results",
                use_container_width=True,
                on_click=navigate,
                args=("Imported results",),
            )

    with experiments_col:
        with st.popover("Experiments", use_container_width=True):
            st.button(
                "New experiment",
                key="nav_new_experiment",
                use_container_width=True,
                on_click=navigate,
                args=("New experiment",),
            )
            st.button(
                "Experiment runs",
                key="nav_experiment_runs",
                use_container_width=True,
                on_click=navigate,
                args=("Experiment runs",),
            )

    with analysis_col:
        st.button(
            "Analysis & Plots",
            key="nav_plots",
            use_container_width=True,
            on_click=navigate,
            args=("Plots",),
        )

    with operations_col:
        with st.popover("Operations", use_container_width=True):
            st.button(
                "Jobs",
                key="nav_jobs",
                use_container_width=True,
                on_click=navigate,
                args=("Jobs",),
            )
            st.button(
                "Simulator",
                key="nav_simulator",
                use_container_width=True,
                on_click=navigate,
                args=("Simulator",),
            )

    with help_col:
        st.button(
            "Help & Documentation",
            key="nav_documentation",
            use_container_width=True,
            on_click=navigate,
            args=("Documentation",),
        )

    st.markdown(
        '<div class="cog-nav-divider"></div>',
        unsafe_allow_html=True,
    )


top_navigation()

page = st.query_params.get("page", "Dashboard")

if page not in NAV_PAGES:
    page = "Dashboard"
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
