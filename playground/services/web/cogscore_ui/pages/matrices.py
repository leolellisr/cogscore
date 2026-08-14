from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from .. import api_client
from ..common import render_exception


def _matrix_frame(item: dict[str, Any], labels: dict[str, list[str]]) -> pd.DataFrame:
    rows = []
    matrix = item.get("matrix", {})
    for domain in ["sensing", "attention", "motivation", "learning"]:
        values = matrix.get(domain, [None] * 5)
        row = {"Domain": domain.title()}
        for i in range(5):
            row[f"M{i+1}"] = values[i] if i < len(values) else None
        rows.append(row)
    return pd.DataFrame(rows).set_index("Domain")


def render() -> None:
    st.title("CogScore matrices")
    st.caption("Matrices are computed on demand from the latest stored benchmark results for each imported agent. No example scores are hard-coded in this page.")
    try:
        payload = api_client.get("/cogscore/matrices", timeout=60)
    except Exception as exc:
        render_exception("Could not compute CogScore matrices", exc)
        return

    agents = payload.get("agents", []) if isinstance(payload, dict) else []
    labels = payload.get("coordinate_labels", {}) if isinstance(payload, dict) else {}
    if not agents:
        st.info("No imported agent results are available for matrix computation.")
        return

    names = [str(item.get("agent_name")) for item in agents]
    selected = st.selectbox("Agent", names)
    item = next(value for value in agents if str(value.get("agent_name")) == selected)

    c1, c2, c3 = st.columns(3)
    c1.metric("Observed cells", f"{int(item.get('observed_cells', 0))}/20")
    c2.metric("Coverage", f"{100.0 * float(item.get('coverage') or 0):.1f}%")
    mean = item.get("mean_observed_score")
    c3.metric("Mean observed score", "N/A" if mean is None else f"{float(mean):.3f}")

    frame = _matrix_frame(item, labels)
    st.dataframe(
        frame.style.format(lambda v: "N/A" if pd.isna(v) else f"{float(v):.3f}").background_gradient(axis=None, vmin=0.0, vmax=1.0),
        use_container_width=True,
    )
    st.caption("N/A means that no readable stored result exists for that agent/cell. It is not converted to zero.")

    st.subheader("Matrix coordinates")
    coordinate_rows = []
    for domain in ["sensing", "attention", "motivation", "learning"]:
        for i, label in enumerate(labels.get(domain, []), start=1):
            coordinate_rows.append({"Domain": domain.title(), "Coordinate": f"M{i}", "Meaning": label})
    st.dataframe(pd.DataFrame(coordinate_rows), hide_index=True, use_container_width=True)

    with st.expander("Computation provenance"):
        st.json(item.get("provenance", {}))

    if len(agents) >= 2:
        st.subheader("Compare agents")
        left_name, right_name = st.columns(2)
        a = left_name.selectbox("Agent A", names, index=0, key="matrix_agent_a")
        b = right_name.selectbox("Agent B", names, index=min(1, len(names)-1), key="matrix_agent_b")
        ia = next(value for value in agents if str(value.get("agent_name")) == a)
        ib = next(value for value in agents if str(value.get("agent_name")) == b)
        common = []
        for domain in ["sensing", "attention", "motivation", "learning"]:
            va = ia.get("matrix", {}).get(domain, [None]*5)
            vb = ib.get("matrix", {}).get(domain, [None]*5)
            for i in range(5):
                if va[i] is not None and vb[i] is not None:
                    common.append({"Domain": domain.title(), "Coordinate": f"M{i+1}", "Agent A": va[i], "Agent B": vb[i], "Difference A-B": va[i]-vb[i]})
        if common:
            st.dataframe(pd.DataFrame(common), hide_index=True, use_container_width=True)
        else:
            st.info("These agents have no observed CogScore cells in common.")
