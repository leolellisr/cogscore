from __future__ import annotations

import copy
import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .config import APP_DIR, PLOTS_DIR


CATALOG_PATH = Path(
    os.getenv("PLOT_CATALOG_PATH", str(APP_DIR / "plot_catalog.yaml"))
).resolve()

_IMAGE_PARAMETER_RE = re.compile(r"_x(?P<x_points>\d+)_w(?P<smooth_window>\d+)", re.IGNORECASE)
_EXPERIMENT_RE = re.compile(r"(?:^|/)exp(?P<experiment_id>\d+)_", re.IGNORECASE)
_LEARNING_EXPERIMENT_RE = re.compile(
    r"(?P<experiment_id>Te(?:1|2|3|4a?|4b|5))_all_agents",
    re.IGNORECASE,
)
_LEARNING_AGENT_RE = re.compile(
    r"(?P<agent>.+)_all_experiments",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def load_plot_catalog() -> dict[str, Any]:
    """Load the static scientific descriptions used by the plots API."""
    if not CATALOG_PATH.is_file():
        return {"schema_version": 1, "benchmarks": {}}

    try:
        payload = yaml.safe_load(CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"schema_version": 1, "benchmarks": {}}

    if not isinstance(payload, dict):
        return {"schema_version": 1, "benchmarks": {}}

    benchmarks = payload.get("benchmarks")
    if not isinstance(benchmarks, dict):
        payload["benchmarks"] = {}

    return payload


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _find_generation(path: Path) -> tuple[Path | None, dict[str, Any]]:
    """Find the nearest generation.json between a plot and PLOTS_DIR."""
    plots_root = PLOTS_DIR.resolve()
    current = path.parent.resolve()

    while True:
        candidate = current / "generation.json"
        if candidate.is_file():
            return current, _read_json(candidate)

        if current == plots_root or plots_root not in current.parents:
            break
        current = current.parent

    return None, {}


def _context_from_path(path: Path, generation_dir: Path | None) -> dict[str, Any]:
    relative = path.relative_to(PLOTS_DIR)
    parts = relative.parts
    benchmark = parts[0] if parts else "unknown"

    scope = "legacy"
    generation_id = ""
    if len(parts) >= 3 and parts[1] in {"comparison", "single"}:
        scope = parts[1]
        generation_id = parts[2]
    elif len(parts) >= 2:
        generation_id = parts[1]

    if generation_dir is not None:
        try:
            plot_relative_to_generation = str(path.relative_to(generation_dir))
        except ValueError:
            plot_relative_to_generation = path.name
        generation_id = generation_dir.name
    else:
        plot_relative_to_generation = str(Path(*parts[2:])) if len(parts) > 2 else path.name

    return {
        "benchmark": benchmark,
        "scope": scope,
        "generation_id": generation_id,
        "relative_path": str(relative),
        "plot_relative_to_generation": plot_relative_to_generation,
    }


def _normalise_learning_experiment(value: str) -> str:
    lowered = value.lower()
    mapping = {
        "te1": "Te1",
        "te2": "Te2",
        "te3": "Te3",
        "te4": "Te4",
        "te4a": "Te4a",
        "te4b": "Te4b",
        "te5": "Te5",
    }
    return mapping.get(lowered, value)


def _infer_experiment_and_agent(
    benchmark: str,
    plot_relative_to_generation: str,
) -> tuple[str | None, str | None]:
    normalized = plot_relative_to_generation.replace("\\", "/")

    if benchmark in {"attention_posner", "motivation"}:
        match = _EXPERIMENT_RE.search(normalized)
        return (match.group("experiment_id"), None) if match else (None, None)

    if benchmark == "sensory_buffer":
        return "sperling", None

    if benchmark == "learning":
        experiment_match = _LEARNING_EXPERIMENT_RE.search(normalized)
        if experiment_match:
            return _normalise_learning_experiment(
                experiment_match.group("experiment_id")
            ), None

        if "/by_agent/" in f"/{normalized}":
            agent_match = _LEARNING_AGENT_RE.search(Path(normalized).stem)
            if agent_match:
                return None, agent_match.group("agent")

    return None, None


def _find_rule(benchmark_config: dict[str, Any], path_text: str) -> dict[str, Any]:
    rules = benchmark_config.get("plots", [])
    if not isinstance(rules, list):
        return {}

    for raw_rule in rules:
        if not isinstance(raw_rule, dict):
            continue
        pattern = str(raw_rule.get("pattern") or "").strip()
        if not pattern:
            continue
        try:
            if re.search(pattern, path_text, flags=re.IGNORECASE):
                return copy.deepcopy(raw_rule)
        except re.error:
            if pattern.lower() in path_text.lower():
                return copy.deepcopy(raw_rule)

    return {}


def _fallback_title(filename: str) -> str:
    title = Path(filename).stem
    title = re.sub(r"_x\d+_w\d+$", "", title)
    title = title.replace("_", " ").replace("-", " ")
    return " ".join(title.split()).capitalize()


def _processing_metadata(
    benchmark: str,
    filename: str,
    generation: dict[str, Any],
) -> dict[str, Any]:
    processing: dict[str, Any] = {}

    plot_parameters = generation.get("plot_parameters")
    if isinstance(plot_parameters, dict):
        processing.update(plot_parameters)

    filename_match = _IMAGE_PARAMETER_RE.search(filename)
    if filename_match:
        processing.setdefault("x_points", int(filename_match.group("x_points")))
        processing.setdefault(
            "smooth_window", int(filename_match.group("smooth_window"))
        )

    if benchmark in {"sensory_buffer", "attention_posner", "motivation"}:
        processing.setdefault("episode_axis", "Normalized to the configured x_points")
        processing.setdefault("missing_values", "Linear interpolation with previous-mean fallback")
        processing.setdefault("smoothing", "Centered rolling mean using smooth_window")
        processing.setdefault(
            "interpretation_note",
            "The displayed curve is a processed developmental trend and is not the unmodified raw sequence.",
        )
    elif benchmark == "learning":
        processing.setdefault("aggregation", "Mean angular deviation by episode across available runs")
        processing.setdefault("dispersion", "Standard deviation across available runs")
        processing.setdefault("smoothing", "Centered smoothing of mean and standard deviation")
        processing.setdefault(
            "field_of_view_note",
            "The plot displays angular-error magnitude, so the signed interval [-30°, +30°] is shown as the magnitude range 0° to 30°.",
        )

    return processing


def build_plot_metadata(path: Path) -> dict[str, Any]:
    """Build scientific and provenance metadata for one generated plot."""
    generation_dir, generation = _find_generation(path)
    context = _context_from_path(path, generation_dir)
    benchmark_id = context["benchmark"]
    path_text = context["plot_relative_to_generation"].replace("\\", "/")

    catalog = load_plot_catalog()
    benchmarks = catalog.get("benchmarks", {})
    benchmark_config = copy.deepcopy(benchmarks.get(benchmark_id, {}))
    if not isinstance(benchmark_config, dict):
        benchmark_config = {}

    rule = _find_rule(benchmark_config, path_text)
    experiment_id, agent_name = _infer_experiment_and_agent(benchmark_id, path_text)

    explicit_experiment = rule.get("experiment_id")
    if explicit_experiment and explicit_experiment != "developmental_profile":
        experiment_id = str(explicit_experiment)

    experiments = benchmark_config.get("experiments", {})
    experiment = {}
    if isinstance(experiments, dict) and experiment_id is not None:
        candidate = experiments.get(str(experiment_id), {})
        if isinstance(candidate, dict):
            experiment = copy.deepcopy(candidate)

    if not experiment:
        if agent_name:
            experiment = {
                "title": f"Developmental profile — {agent_name}",
                "procedure": (
                    "The plot compares the learning conditions evaluated with the "
                    "selected developmental agent."
                ),
                "expected_behavior": (
                    "Conditions supported by the available mechanisms should remain "
                    "within the field-of-view criterion."
                ),
            }
        else:
            experiment = {
                "title": "Multiple or unspecified experimental conditions",
                "procedure": benchmark_config.get("description", ""),
                "expected_behavior": benchmark_config.get("default_interpretation", ""),
            }

    plot_title = str(rule.get("title") or _fallback_title(path.name))
    if benchmark_id == "learning" and experiment_id and "by_experiment/" in path_text:
        experiment_title = str(experiment.get("title") or experiment_id)
        plot_title = f"{plot_title} — {experiment_title}"
    elif benchmark_id == "learning" and agent_name:
        plot_title = f"{plot_title} — {agent_name}"

    metric = rule.get("metric") if isinstance(rule.get("metric"), dict) else {}
    variables = rule.get("variables") if isinstance(rule.get("variables"), list) else []

    processing = _processing_metadata(benchmark_id, path.name, generation)
    selected_agents = generation.get("selected_agents", [])
    selected_run_ids = generation.get("selected_run_ids", [])

    provenance = {
        "generation_id": context["generation_id"],
        "scope": context["scope"],
        "job_id": generation.get("job_id") or context["generation_id"],
        "reference_run_id": generation.get("reference_run_id") or "",
        "selected_agents": selected_agents if isinstance(selected_agents, list) else [],
        "selected_run_ids": selected_run_ids if isinstance(selected_run_ids, list) else [],
        "generated_at": generation.get("generated_at") or "",
        "generation_metadata": (
            str((generation_dir / "generation.json").relative_to(PLOTS_DIR))
            if generation_dir is not None
            else ""
        ),
        "source": (
            "generation.json and static plot catalog"
            if generation
            else "static plot catalog and filename inference"
        ),
    }

    return {
        "catalog_schema_version": catalog.get("schema_version", 1),
        "benchmark": {
            "id": benchmark_id,
            "title": benchmark_config.get("title", benchmark_id.replace("_", " ").title()),
            "description": benchmark_config.get("description", ""),
        },
        "experiment": {
            "id": experiment_id or "",
            "title": experiment.get("title", ""),
            "procedure": experiment.get("procedure", ""),
            "expected_behavior": experiment.get("expected_behavior", ""),
        },
        "plot": {
            "title": plot_title,
            "data_type": rule.get("data_type", "Generated benchmark result"),
            "relative_path": context["relative_path"],
            "view": (
                "by_experiment"
                if "by_experiment/" in path_text
                else "by_agent"
                if "by_agent/" in path_text
                else "metric"
            ),
            "agent": agent_name or "",
        },
        "metric": metric,
        "variables": variables,
        "interpretation": rule.get(
            "interpretation", benchmark_config.get("default_interpretation", "")
        ),
        "processing": processing,
        "provenance": provenance,
    }
