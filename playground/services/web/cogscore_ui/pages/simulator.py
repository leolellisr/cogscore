from __future__ import annotations

import os

import streamlit as st
import streamlit.components.v1 as components

from .. import api_client
from ..common import BENCHMARKS, navigate, render_exception, status_badge


def render() -> None:
    st.title("Simulator")
    st.caption("Observe and control the shared CoppeliaSim VNC service used by online experiments.")

    try:
        status = api_client.get("/simulator/status")
    except Exception as exc:
        render_exception("Could not read simulator status", exc)
        status = {"status": "unknown"}

    st.markdown(
        f'<div class="cog-card"><div class="cog-eyebrow">Simulator service</div>'
        f'<h4>CoppeliaSim through noVNC</h4>{status_badge(str(status.get("status", "unknown")))}</div>',
        unsafe_allow_html=True,
    )

    scene_options = sorted({str(item["scene"]) for item in BENCHMARKS.values()})
    selected_scene = st.selectbox("Scene for manual start or restart", scene_options)
    actions = st.columns(4)
    if actions[0].button("Start", type="primary", use_container_width=True):
        _control("start", selected_scene)
    if actions[1].button("Stop", use_container_width=True):
        _control("stop", selected_scene)
    if actions[2].button("Restart", use_container_width=True):
        _control("restart", selected_scene)
    if actions[3].button("Refresh status", use_container_width=True):
        st.rerun()

    vnc_url = os.getenv(
        "VNC_PUBLIC_URL",
        "http://localhost:6080/vnc.html?autoconnect=true&resize=scale",
    )
    st.info("VNC mode is intended for observation and manual debugging. Headless experiment runs may not be visible in this window.")
    components.iframe(vnc_url, height=820, scrolling=True)
    st.markdown(f"[Open noVNC in a new tab]({vnc_url})")
    with st.expander("Interaction notes"):
        st.markdown(
            """
- Click inside the VNC frame before using the keyboard.
- Use the noVNC side menu to send special keys or change scaling.
- The simulator is shared by queued experiments; manual control may interfere with an active run.
- Start, stop, and restart operations are asynchronous jobs and can be tracked on the Jobs page.
            """
        )


def _control(action: str, scene: str) -> None:
    try:
        result = api_client.post_json("/simulator/control", {"action": action, "scene": scene})
        st.success(result.get("message", "Simulator job created."))
        if st.button("Track simulator job", key=f"track_sim_{action}"):
            navigate("Jobs", job=str(result.get("job_id", "")))
    except Exception as exc:
        render_exception(f"Could not {action} the simulator", exc)
