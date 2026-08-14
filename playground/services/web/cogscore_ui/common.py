from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import streamlit as st


BENCHMARKS: dict[str, dict[str, Any]] = {
    "sensory_buffer": {
        "title": "Sensing",
        "description": "Sensory persistence and visual-buffer fidelity.",
        "scene": "sperling.ttt",
    },
    "attention_posner": {
        "title": "Attention",
        "description": "Orienting, peripheral capture, visual search, and crowding.",
        "scene": "posner.ttt",
    },
    "motivation": {
        "title": "Motivation",
        "description": "Persistence, drive regulation, latent learning, and outcome value.",
        "scene": "mot.ttt",
    },
    "learning": {
        "title": "Learning",
        "description": "Developmental tracking, object permanence, and alternating attention.",
        "scene": "learning/testing_s1A.ttt",
    },
}

STATUS_LABELS = {
    "pending": "Queued",
    "uploaded": "Uploaded",
    "running": "Running",
    "done": "Completed",
    "validated": "Validated",
    "error": "Failed",
    "cancelled": "Cancelled",
}

STATUS_ICONS = {
    "pending": "◷",
    "uploaded": "↑",
    "running": "●",
    "done": "✓",
    "validated": "✓",
    "error": "×",
    "cancelled": "–",
    "online": "●",
    "offline": "×",
    "stale": "!",
    "unknown": "?",
}


NAVIGATION = [
    ("Dashboard", "Overview"),
    ("Architectures", "Assets"),
    ("Imported results", "Assets"),
    ("New experiment", "Experiments"),
    ("Experiment runs", "Experiments"),
    ("Plots", "Analysis"),
    ("CogScore matrices", "Analysis"),
    ("Jobs", "Operations"),
    ("Simulator", "Operations"),
    ("Documentation", "Help"),
]
NAV_PAGES = [item[0] for item in NAVIGATION]
NAV_GROUPS = {page: group for page, group in NAVIGATION}


def apply_theme() -> None:
    st.markdown(
        """
<style>
:root {
  --cog-primary: #d94b50;
  --cog-primary-dark: #252733;
  --cog-header: #f6b38f;
  --cog-header-hover: #f9c4a8;
  --cog-surface: #ffffff;
  --cog-border: rgba(37, 39, 51, 0.16);
}

/* Thin multicolor line inspired by the CogScore presentation website. */
[data-testid="stAppViewContainer"]::before {
  content: "";
  position: fixed;
  z-index: 10000;
  top: 0;
  left: 0;
  right: 0;
  height: 4px;
  background: linear-gradient(90deg, #ef5350, #ff9f43, #f6d365, #7bd389, #4dabf7, #9b5de5);
}

[data-testid="stHeader"] {
  background: transparent;
}
[data-testid="stSidebar"] {
  display: none;
}
.block-container {
  padding-top: 0.9rem;
  padding-bottom: 3rem;
  max-width: 1800px;
  padding-left: 2rem;
  padding-right: 2rem;
}

/* Top navigation */
[data-testid="stHorizontalBlock"]:has(.cog-brand) {
  background: var(--cog-header);
  border: 1px solid rgba(37, 39, 51, 0.12);
  border-radius: 0 0 12px 12px;
  padding: 0.75rem 1rem;
  min-height: 5.2rem;
  rgba(37, 39, 51, 0.08);
  position: sticky;
  top: .25rem;
  z-index: 999;
}
.cog-brand {
  color: var(--cog-primary-dark);
  font-size: 1.15rem;
  font-weight: 800;
  letter-spacing: -.02em;
  white-space: nowrap;
}
.cog-brand span {
  display: block;
  margin-top: -.15rem;
  font-size: .62rem;
  font-weight: 700;
  letter-spacing: .10em;
  text-transform: uppercase;
  opacity: .68;
}
.cog-nav-divider {
  height: 1rem;
}

/* Header buttons and popovers */
[data-testid="stHorizontalBlock"]:has(.cog-brand) button {
  width: 100% !important;
  min-width: 0 !important;
  max-width: 100% !important;
  box-sizing: border-box !important;

  min-height: 3rem;
  padding: 0.55rem 0.55rem !important;

  border: 1px solid rgba(37, 39, 51, 0.32) !important;
  border-radius: 9px !important;

  background: rgba(255, 255, 255, 0.16) !important;
  color: var(--cog-primary-dark) !important;

  font-size: 0.82rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.015em !important;
  text-transform: uppercase !important;

  line-height: 1.1 !important;
  white-space: nowrap !important;
  overflow: hidden !important;
  text-overflow: clip !important;

  box-shadow: 0 1px 2px rgba(37, 39, 51, 0.08) !important;
}
[data-testid="stHorizontalBlock"]:has(.cog-brand) button p {
  white-space: nowrap !important;
  word-break: keep-all !important;
  overflow-wrap: normal !important;
  margin: 0 !important;
}
[data-testid="stHorizontalBlock"]:has(.cog-brand) button:hover {
  background: var(--cog-header-hover) !important;
}
[data-testid="stPopoverBody"] button {
  justify-content: flex-start;
}
[data-testid="stPopover"] button {
  white-space: nowrap !important;
}

[data-testid="stPopover"] button p {
  white-space: nowrap !important;
}

.cog-eyebrow {font-size: .78rem; text-transform: uppercase; letter-spacing: .08em; opacity: .65; margin-bottom: .2rem;}
.cog-card {border: 1px solid var(--cog-border); border-radius: 12px; padding: 1rem 1.1rem; margin-bottom: .75rem; background: var(--cog-surface);}
.cog-card h4 {margin: 0 0 .25rem 0;}
.cog-muted {opacity: .7; font-size: .9rem;}
.cog-badge {display: inline-flex; align-items: center; gap: .35rem; border-radius: 999px; padding: .2rem .55rem; font-size: .78rem; font-weight: 600; border: 1px solid var(--cog-border);}
.cog-status-done,.cog-status-validated,.cog-status-online {background: rgba(25,135,84,.10); color: #198754;}
.cog-status-running {background: rgba(13,110,253,.10); color: #0d6efd;}
.cog-status-pending,.cog-status-uploaded,.cog-status-unknown {background: rgba(108,117,125,.10); color: #6c757d;}
.cog-status-error,.cog-status-offline {background: rgba(220,53,69,.10); color: #dc3545;}
.cog-status-stale {background: rgba(255,193,7,.12); color: #9a7400;}
div[data-testid="stMetric"] {border: 1px solid var(--cog-border); border-radius: 12px; padding: .7rem .85rem; background: var(--cog-surface);}
button[kind="primary"] {background-color: var(--cog-primary); border-color: var(--cog-primary);}

@media (max-width: 950px) {
  [data-testid="stHorizontalBlock"]:has(.cog-brand) {
    position: static;
  }
  .cog-brand span {display: none;}
  [data-testid="stHorizontalBlock"]:has(.cog-brand) button {
    font-size: .66rem !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
  }
}
</style>
        """,
        unsafe_allow_html=True,
    )


def status_badge(status: str) -> str:
    normalized = (status or "unknown").lower()
    label = STATUS_LABELS.get(normalized, normalized.replace("_", " ").title())
    icon = STATUS_ICONS.get(normalized, "•")
    return (
        f'<span class="cog-badge cog-status-{normalized}">'
        f"{icon} {label}</span>"
    )


def render_status(status: str) -> None:
    st.markdown(status_badge(status), unsafe_allow_html=True)


def benchmark_title(benchmark: str) -> str:
    return str(BENCHMARKS.get(benchmark, {}).get("title") or benchmark.replace("_", " ").title())


def parse_json(value: Any, default: Any = None) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return {} if default is None else default
    try:
        return json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {} if default is None else default


def architecture_manifest(architecture: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_json(architecture.get("manifest_json"), {})
    return parsed if isinstance(parsed, dict) else {}


def architecture_supports(architecture: dict[str, Any], benchmark: str) -> bool:
    benchmarks = architecture_manifest(architecture).get("benchmarks")
    return not isinstance(benchmarks, list) or benchmark in benchmarks


def resolve_data_path(value: str | Path) -> Path:
    original = Path(str(value)).expanduser()
    if original.exists():
        return original
    data_root = Path(os.getenv("LOCAL_STORAGE_ROOT", "/data"))
    parts = original.parts
    for index in reversed([i for i, part in enumerate(parts) if part == "data"]):
        candidate = data_root.joinpath(*parts[index + 1 :])
        if candidate.exists():
            return candidate
    return original


def format_datetime(value: Any) -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return str(value)


def duration_seconds(start: Any, end: Any) -> float | None:
    if not start or not end:
        return None
    try:
        start_dt = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
        return max(0.0, (end_dt - start_dt).total_seconds())
    except ValueError:
        return None


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.0f} s"
    minutes, sec = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {sec:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m"


def format_bytes(value: int | float | None) -> str:
    size = float(value or 0)
    units = ["B", "KB", "MB", "GB", "TB"]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.1f} {unit}" if unit != "B" else f"{size:.0f} B"
        size /= 1024
    return f"{size:.1f} TB"


def human_error(message: str) -> str:
    lowered = message.lower()
    if "encodings" in lowered or "init_fs_encoding" in lowered:
        return "The Python runtime inside the worker could not load its standard library. Rebuild and recreate the worker container."
    if "connection refused" in lowered or "could not contact" in lowered:
        return "A required service could not be reached. Check the API, worker, simulator, and architecture container status."
    if "timeout" in lowered:
        return "The operation exceeded its execution time limit. Review the logs and the configured runtime limits."
    if "manifest" in lowered:
        return "The uploaded bundle does not satisfy the manifest contract. Review the required files and fields."
    return message.splitlines()[0][:500]


def render_exception(title: str, error: Exception) -> None:
    from .api_client import pretty_detail

    technical = pretty_detail(error)
    st.error(f"{title}: {human_error(technical)}")
    with st.expander("Technical details"):
        st.code(technical, language="text")


def navigate(page: str, **params: str) -> None:
    if page not in NAV_PAGES:
        page = "Dashboard"

    st.query_params.clear()
    st.query_params["page"] = page

    for key, value in params.items():
        if value:
            st.query_params[key] = value


def require_optional_login() -> None:
    expected = os.getenv("COGSCORE_DASHBOARD_PASSWORD", "")
    if not expected:
        return
    if st.session_state.get("cogscore_authenticated"):
        return
    st.title("CogScore Online")
    st.caption("Authentication is required for this deployment.")
    username = st.text_input("Username", value=os.getenv("COGSCORE_DASHBOARD_USERNAME", "researcher"))
    password = st.text_input("Password", type="password")
    if st.button("Sign in", type="primary"):
        expected_user = os.getenv("COGSCORE_DASHBOARD_USERNAME", "researcher")
        user_ok = hmac.compare_digest(username, expected_user)
        password_ok = hmac.compare_digest(
            hashlib.sha256(password.encode()).digest(),
            hashlib.sha256(expected.encode()).digest(),
        )
        if user_ok and password_ok:
            st.session_state["cogscore_authenticated"] = True
            st.rerun()
        st.error("Invalid username or password.")
    st.stop()
