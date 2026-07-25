from __future__ import annotations

import atexit
import csv
import json
import logging
import os
import signal
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import socket

DEFAULT_API_DIR = Path(__file__).resolve().parents[2] / "api"
API_DIR = Path(os.getenv("API_DIR", str(DEFAULT_API_DIR))).resolve()
sys.path.insert(0, str(API_DIR))

from app.config import (  # noqa: E402
    ARCH_TIMEOUT_SECONDS,
    ARCHITECTURES_DIR,
    UPLOADS_DIR,
    COGSCORE_DOCKER_NETWORK,
    JOBS_DIR,
    MAX_ARCH_CPU,
    MAX_ARCH_MEMORY,
    RESULTS_DIR,
    STORAGE_ROOT,
    ensure_storage_dirs,
)
from app.database import (  # noqa: E402
    get_architecture,
    get_next_pending_job,
    init_db,
    list_runs,
    mark_job_done,
    mark_interrupted_jobs_error,
    mark_job_error,
    mark_job_running,
    update_architecture_status,
    update_experiment_run_status,
)




logging.basicConfig(
    level=logging.INFO,
    format="[WORKER] %(message)s",
)

logger = logging.getLogger("cogscore-worker")

ACTIVE_ARCHITECTURE_CONTAINERS: set[str] = set()
SIMULATOR_CONTAINER_NAME = os.getenv(
    "COGSCORE_SIM_CONTAINER", "cogscore-sim-vnc"
).strip()
SIMULATOR_COMPOSE_SERVICE = os.getenv(
    "COGSCORE_SIM_SERVICE", "sim-vnc"
).strip()


def info(message: str) -> None:
    try:
        logger.info(message)
    except BrokenPipeError:
        pass


def read_json(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def run_command(
    command: list[str],
    *,
    cwd: Path | None = None,
    stdout_path: Path | None = None,
    stderr_path: Path | None = None,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    info("Running command: " + " ".join(command))

    if stdout_path is None or stderr_path is None:
        return subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            text=True,
            timeout=timeout,
        )

    with stdout_path.open("a", encoding="utf-8") as stdout_file:
        with stderr_path.open("a", encoding="utf-8") as stderr_file:
            return subprocess.run(
                command,
                cwd=str(cwd) if cwd else None,
                stdout=stdout_file,
                stderr=stderr_file,
                text=True,
                timeout=timeout,
            )


def tail_log(path: Path, *, max_chars: int = 8000) -> str:
    """Return the end of a UTF-8 log file without loading an unbounded file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""
    return text[-max_chars:].strip()


def docker_container_is_running(container_name: str) -> bool:
    if not container_name:
        return False

    completed = subprocess.run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Running}}",
            container_name,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def resolve_simulator_container() -> str:
    """Return the running Compose container that implements the sim-vnc service.

    Compose can temporarily rename an old container while recreating a service.
    Looking up the service label keeps experiments working even when the literal
    container name is no longer available.
    """
    if docker_container_is_running(SIMULATOR_CONTAINER_NAME):
        return SIMULATOR_CONTAINER_NAME

    completed = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "status=running",
            "--filter",
            f"label=com.docker.compose.service={SIMULATOR_COMPOSE_SERVICE}",
            "--format",
            "{{.ID}} {{.Names}}",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise RuntimeError(
            "Could not query the Docker Compose simulator service: " + detail
        )

    candidates = [
        line.split(maxsplit=1)
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    if not candidates:
        raise RuntimeError(
            "No running Docker container was found for Compose service "
            f"{SIMULATOR_COMPOSE_SERVICE!r}. Run 'docker compose ps' and "
            "recreate the sim-vnc service before starting an experiment."
        )

    if len(candidates) > 1:
        names = ", ".join(
            parts[1] if len(parts) > 1 else parts[0]
            for parts in candidates
        )
        raise RuntimeError(
            "More than one running simulator container was found for Compose "
            f"service {SIMULATOR_COMPOSE_SERVICE!r}: {names}. Remove stale "
            "Compose containers before starting an experiment."
        )

    container_id, *name = candidates[0]
    resolved_name = name[0] if name else container_id
    info(
        "Resolved simulator container by Compose service label: "
        f"{resolved_name} ({container_id})"
    )
    return container_id


def command_failure_message(
    description: str,
    completed: subprocess.CompletedProcess[str],
    stderr_path: Path,
) -> str:
    detail = tail_log(stderr_path, max_chars=4000)
    message = f"{description} failed with exit code {completed.returncode}"
    if detail:
        message += f": {detail}"
    return message


def docker_rm_force(container_name: str) -> None:
    completed = subprocess.run(
        ["docker", "rm", "-f", container_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    ACTIVE_ARCHITECTURE_CONTAINERS.discard(container_name)

    if completed.returncode != 0 and "No such container" not in completed.stderr:
        info(
            f"Could not remove architecture container {container_name}: "
            f"{completed.stderr.strip()}"
        )


def cleanup_stale_architecture_containers(
    *,
    attempts: int | None = None,
    retry_delay_seconds: float | None = None,
) -> list[str]:
    """Remove dynamic CogScore containers left by an earlier worker process."""
    if attempts is None:
        attempts = max(1, int(os.getenv("DOCKER_CLEANUP_ATTEMPTS", "30")))
    if retry_delay_seconds is None:
        retry_delay_seconds = max(0.1, float(os.getenv("DOCKER_CLEANUP_RETRY_SECONDS", "2")))
    filters = [
        "label=cogscore.managed=true",
        "name=cogscore-run-",
        "name=cogscore-smoke-",
    ]

    for attempt in range(1, max(1, attempts) + 1):
        container_ids: set[str] = set()
        docker_error = ""

        for filter_value in filters:
            completed = subprocess.run(
                ["docker", "ps", "-aq", "--filter", filter_value],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if completed.returncode != 0:
                docker_error = completed.stderr.strip() or completed.stdout.strip()
                break

            container_ids.update(
                line.strip()
                for line in completed.stdout.splitlines()
                if line.strip()
            )

        if docker_error:
            info(
                "Could not inspect stale architecture containers "
                f"(attempt {attempt}/{attempts}): {docker_error}"
            )
            if attempt < attempts:
                time.sleep(retry_delay_seconds)
                continue
            return []

        if not container_ids:
            info("No stale CogScore architecture containers found at worker startup")
            return []

        ordered_ids = sorted(container_ids)
        removed = subprocess.run(
            ["docker", "rm", "-f", *ordered_ids],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if removed.returncode != 0:
            detail = removed.stderr.strip() or removed.stdout.strip()
            info(f"Could not remove all stale architecture containers: {detail}")
            if attempt < attempts:
                time.sleep(retry_delay_seconds)
                continue
            return []

        removed_ids = [
            line.strip()
            for line in removed.stdout.splitlines()
            if line.strip()
        ]
        info(
            "Removed stale CogScore architecture containers at startup: "
            + ", ".join(removed_ids)
        )
        return removed_ids

    return []


def cleanup_active_architecture_containers() -> None:
    for container_name in tuple(ACTIVE_ARCHITECTURE_CONTAINERS):
        docker_rm_force(container_name)


def handle_shutdown_signal(signum: int, _frame: Any) -> None:
    info(f"Shutdown signal {signum} received; cleaning architecture containers")
    raise SystemExit(0)


def start_architecture_container(
    *,
    container_name: str,
    image_tag: str,
    stdout_path: Path,
    stderr_path: Path,
    labels: dict[str, str] | None = None,
) -> None:
    """Start an uploaded architecture and preserve Docker's real error message."""
    docker_rm_force(container_name)

    command = [
        "docker",
        "run",
        "-d",
        "--name",
        container_name,
        "--network",
        COGSCORE_DOCKER_NETWORK,
        "--cpus",
        str(MAX_ARCH_CPU),
        "--memory",
        str(MAX_ARCH_MEMORY),
        "--label",
        "cogscore.managed=true",
    ]

    for key, value in (labels or {}).items():
        command.extend(["--label", f"{key}={value}"])

    command.append(image_tag)

    completed = run_command(
        command,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout=ARCH_TIMEOUT_SECONDS,
    )

    if completed.returncode != 0:
        detail = tail_log(stderr_path)
        suffix = f": {detail}" if detail else ""
        raise RuntimeError(
            "Could not start architecture container "
            f"{container_name} with image {image_tag} "
            f"on network {COGSCORE_DOCKER_NETWORK} "
            f"(docker exit {completed.returncode}){suffix}"
        )

    ACTIVE_ARCHITECTURE_CONTAINERS.add(container_name)


atexit.register(cleanup_active_architecture_containers)


def architecture_manifest(architecture: dict[str, Any]) -> dict[str, Any]:
    raw = architecture.get("manifest_json")
    if isinstance(raw, str):
        data = read_json(raw)
        return data if isinstance(data, dict) else {}
    raw_manifest = architecture.get("manifest")
    return raw_manifest if isinstance(raw_manifest, dict) else {}


def declared_supported_benchmarks(architecture: dict[str, Any]) -> list[str]:
    manifest = architecture_manifest(architecture)
    declared = manifest.get("benchmarks", [])
    if not isinstance(declared, list):
        return ["sensory_buffer"]

    supported = [
        str(item)
        for item in declared
        if str(item) in {"sensory_buffer", "attention_posner", "motivation", "learning"}
    ]
    return supported or ["sensory_buffer"]


def smoke_test_sensory(base_url: str) -> str:
    smoke_payload = {
        "benchmark": "sensory_buffer",
        "episode": 0,
        "trial": 0,
        "delay_ms": 0,
        "width": 2,
        "height": 2,
        "channels": 3,
        "encoding": "rgb_float_0_255",
        "frame": [0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255],
    }

    return (
        "import requests, json\n"
        f"base = {base_url!r}\n"
        "r = requests.post(base + '/reset', json={'benchmark':'sensory_buffer'}, timeout=5)\n"
        "r.raise_for_status()\n"
        f"payload = {json.dumps(smoke_payload)!r}\n"
        "r = requests.post(base + '/sensory/stimulus', json=json.loads(payload), timeout=5)\n"
        "r.raise_for_status()\n"
        "r = requests.post(base + '/sensory/readout', json={'cue':{'type':'patch','x0':0,'y0':0,'size':1}}, timeout=5)\n"
        "r.raise_for_status()\n"
        "data = r.json()\n"
        "assert 'patch' in data\n"
    )


def smoke_test_attention(base_url: str) -> str:
    payload = {
        "benchmark": "attention_posner",
        "episode": 0,
        "experiment_id": 1,
        "trial_id": "SMOKE_ATTENTION",
        "cue": {"side": "left", "valid": True},
        "target": {"x": 0.25, "y": 0.5},
        "cycles_per_trial": 5,
    }

    return (
        "import requests, json\n"
        f"base = {base_url!r}\n"
        "r = requests.post(base + '/reset', json={'benchmark':'attention_posner'}, timeout=5)\n"
        "r.raise_for_status()\n"
        f"payload = {json.dumps(payload)!r}\n"
        "r = requests.post(base + '/attention/act', json=json.loads(payload), timeout=5)\n"
        "r.raise_for_status()\n"
        "data = r.json()\n"
        "assert isinstance(data, dict)\n"
    )

def smoke_test_learning(base_url: str) -> str:
    payload = {
        "benchmark": "learning",
        "stage": "Substage1",
        "test": "testA",
        "episode": 0,
        "step": 0,
        "target": {
            "visible": True,
            "occluded": False,
            "x": 0.5,
            "y": 0.5,
            "yaw_error": 0.2,
            "pitch_error": -0.1,
        },
        "objects": [
            {"id": 1, "label": "target", "visible": True}
        ],
        "signals": {
            "curiosity": 0.0,
            "reward_available": True,
            "occlusion": False,
            "multiple_objects": False,
        },
    }

    return (
        "import requests, json\n"
        f"base = {base_url!r}\n"
        "r = requests.post(base + '/reset', json={'benchmark':'learning'}, timeout=5)\n"
        "r.raise_for_status()\n"
        f"payload = {json.dumps(payload)!r}\n"
        "r = requests.post(base + '/learning/act', json=json.loads(payload), timeout=5)\n"
        "r.raise_for_status()\n"
        "data = r.json()\n"
        "assert isinstance(data, dict)\n"
        "assert 'action' in data\n"
    )

def smoke_test_motivation(base_url: str) -> str:
    payload = {
        "benchmark": "motivation",
        "episode": 0,
        "experiment_id": 1,
        "trial_id": "SMOKE_MOTIVATION",
        "phase": "trial",
        "objects": [
            {"id": 1, "label": "blue_sphere", "role": "resource"},
            {"id": 2, "label": "red_cube", "role": "curiosity"},
        ],
        "signals": {"reward_available": True},
    }

    return (
        "import requests, json\n"
        f"base = {base_url!r}\n"
        "r = requests.post(base + '/reset', json={'benchmark':'motivation'}, timeout=5)\n"
        "r.raise_for_status()\n"
        f"payload = {json.dumps(payload)!r}\n"
        "r = requests.post(base + '/motivation/act', json=json.loads(payload), timeout=5)\n"
        "r.raise_for_status()\n"
        "data = r.json()\n"
        "assert isinstance(data, dict)\n"
        "assert 'action' in data\n"
    )


def architecture_smoke_script(base_url: str, benchmarks: list[str]) -> str:
    chunks = [
        "import requests\n",
        f"base = {base_url!r}\n",
        "r = requests.get(base + '/health', timeout=5)\n",
        "r.raise_for_status()\n",
    ]

    for benchmark in benchmarks:
        if benchmark == "sensory_buffer":
            chunks.append(smoke_test_sensory(base_url))
        elif benchmark == "attention_posner":
            chunks.append(smoke_test_attention(base_url))
        elif benchmark == "motivation":
            chunks.append(smoke_test_motivation(base_url))
        elif benchmark == "learning":
            chunks.append(smoke_test_learning(base_url))    

    return "\n".join(chunks)


def handle_validate_architecture(job: dict[str, Any], job_dir: Path) -> dict[str, Any]:
    input_data = read_json(job.get("input_json"))
    architecture_id = str(input_data["architecture_id"])
    source_path = Path(str(input_data["source_path"]))

    architecture = get_architecture(architecture_id)
    if architecture is None:
        raise RuntimeError(f"Architecture not found: {architecture_id}")

    image_tag = f"cogscore-agent-{architecture_id}:latest"
    container_name = f"cogscore-smoke-{architecture_id}"

    stdout_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"

    dockerfile_path = source_path / "Dockerfile"
    if not dockerfile_path.exists():
        raise RuntimeError("Architecture bundle must contain a Dockerfile")

    build = run_command(
        ["docker", "build", "-t", image_tag, "."],
        cwd=source_path,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout=ARCH_TIMEOUT_SECONDS,
    )

    if build.returncode != 0:
        detail = tail_log(stderr_path, max_chars=4000)
        error_message = "Docker build failed"

        if detail:
            error_message = f"{error_message}: {detail}"

        update_architecture_status(
            architecture_id=architecture_id,
            status="error",
            error_message=error_message,
        )

        raise RuntimeError(error_message)

    try:
        start_architecture_container(
            container_name=container_name,
            image_tag=image_tag,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            labels={
                "cogscore.purpose": "validation",
                "cogscore.architecture_id": architecture_id,
            },
        )
    except RuntimeError as exc:
        update_architecture_status(
            architecture_id=architecture_id,
            status="error",
            error_message=str(exc),
        )
        raise

    try:
        time.sleep(3)

        base_url = f"http://{container_name}:9000"

        benchmarks = declared_supported_benchmarks(architecture)
        script = architecture_smoke_script(base_url, benchmarks)

        smoke = run_command(
            ["python", "-c", script],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS,
        )

        if smoke.returncode != 0:
            update_architecture_status(
                architecture_id=architecture_id,
                status="error",
                error_message="REST smoke test failed for declared benchmarks",
            )
            raise RuntimeError("REST smoke test failed for declared benchmarks")

        update_architecture_status(
            architecture_id=architecture_id,
            status="validated",
            image_tag=image_tag,
            error_message=None,
        )

        return {
            "architecture_id": architecture_id,
            "image_tag": image_tag,
            "status": "validated",
            "benchmarks": benchmarks,
        }

    finally:
        docker_rm_force(container_name)


def handle_run_sensory_remote(job: dict[str, Any], job_dir: Path) -> dict[str, Any]:
    input_data = read_json(job.get("input_json"))

    run_id = str(input_data["run_id"])
    architecture_id = str(input_data["architecture_id"])
    parameters = dict(input_data["parameters"])

    architecture = get_architecture(architecture_id)
    if architecture is None:
        raise RuntimeError(f"Architecture not found: {architecture_id}")

    image_tag = architecture.get("image_tag")
    if not image_tag:
        raise RuntimeError("Architecture has no validated Docker image")

    result_dir = RESULTS_DIR / architecture_id / "sensory_buffer" / run_id / "benchmark_out"
    result_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"

    container_name = f"cogscore-run-{run_id}"

    try:
        start_architecture_container(
            container_name=container_name,
            image_tag=str(image_tag),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            labels={
                "cogscore.purpose": "experiment",
                "cogscore.architecture_id": architecture_id,
                "cogscore.run_id": run_id,
            },
        )

        time.sleep(3)

        agent_url = f"http://{container_name}:9000"

        scene = str(parameters.get("scene", "sperling.ttt"))
        episodes = str(parameters.get("episodes", 1))
        trials_per_delay = str(parameters.get("trials_per_delay", 3))
        delays_ms = ",".join(str(x) for x in parameters.get("delays_ms", [0, 50, 100, 220]))
        resolution = str(parameters.get("resolution", 64))
        patch_size = str(parameters.get("patch_size", 8))

        update_experiment_run_status(run_id=run_id, status="running")

        simulator_container = resolve_simulator_container()

        command = [
            "docker",
            "exec",
            simulator_container,
            "bash",
            "/workspace/scripts/run_sensory_remote.sh",
            "--agent-url",
            agent_url,
            "--scene",
            f"/workspace/scenes/{scene}",
            "--out",
            f"/data/results/{architecture_id}/sensory_buffer/{run_id}/benchmark_out",
            "--episodes",
            episodes,
            "--trials-per-delay",
            trials_per_delay,
            "--delays-ms",
            delays_ms,
            "--resolution",
            resolution,
            "--patch-size",
            patch_size,
        ]

        completed = run_command(
            command,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS * 10,
        )

        if completed.returncode != 0:
            error_message = command_failure_message(
                "Remote sensory experiment", completed, stderr_path
            )
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message=error_message,
            )
            raise RuntimeError(error_message)

                # Automatically create a result bundle after the benchmark finishes.
        # The bundle is written under /data/uploads/result_bundles on the host:
        # playground/data/uploads/result_bundles/<architecture_id>_<run_id>_sensory_buffer.zip
        bundles_dir = UPLOADS_DIR / "result_bundles"
        bundles_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = bundles_dir / f"{architecture_id}_{run_id}_sensory_buffer.zip"

        bundle_script = Path("/workspace/tools/create_result_bundle.py")
        if not bundle_script.exists():
            raise RuntimeError(f"Result bundle script not found: {bundle_script}")

        bundle = run_command(
            [
                "python",
                str(bundle_script),
                "--benchmark-out",
                str(result_dir),
                "--output",
                str(bundle_path),
                "--agent-name",
                architecture_id,
                "--architecture-name",
                str(architecture.get("name") or "CONAIM"),
                "--benchmark",
                "sensory_buffer",
                "--benchmark-version",
                "sensory_buffer_v1",
                "--run-name",
                f"Sensory buffer run {run_id}",
                "--episodes",
                episodes,
                "--trials-per-experiment",
                trials_per_delay,
                "--seed",
                str(parameters.get("seed", 777)),
                "--author",
                str(architecture.get("author") or "CogScore playground"),
                "--notes",
                "Automatically generated after sensory_buffer experiment.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS,
        )

        if bundle.returncode != 0:
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message="Experiment finished, but result bundle generation failed",
            )
            raise RuntimeError("Result bundle generation failed")

        update_experiment_run_status(
            run_id=run_id,
            status="done",
            result_path=str(bundle_path),
            error_message=None,
        )

        return {
            "run_id": run_id,
            "architecture_id": architecture_id,
            "result_dir": str(result_dir),
            "bundle_path": str(bundle_path),
            "agent_url": agent_url,
            "parameters": parameters,
        }

    finally:
        docker_rm_force(container_name)

def handle_run_attention_remote(job: dict[str, Any], job_dir: Path) -> dict[str, Any]:
    input_data = read_json(job.get("input_json"))

    run_id = str(input_data["run_id"])
    architecture_id = str(input_data["architecture_id"])
    parameters = dict(input_data["parameters"])

    architecture = get_architecture(architecture_id)
    if architecture is None:
        raise RuntimeError(f"Architecture not found: {architecture_id}")

    image_tag = architecture.get("image_tag")
    if not image_tag:
        raise RuntimeError("Architecture has no validated Docker image")

    result_dir = RESULTS_DIR / architecture_id / "attention_posner" / run_id / "benchmark_out"
    result_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"

    container_name = f"cogscore-run-{run_id}"

    try:
        start_architecture_container(
            container_name=container_name,
            image_tag=str(image_tag),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            labels={
                "cogscore.purpose": "experiment",
                "cogscore.architecture_id": architecture_id,
                "cogscore.run_id": run_id,
            },
        )

        time.sleep(3)

        agent_url = f"http://{container_name}:9000"

        scene = str(parameters.get("scene") or "posner.ttt")
        episodes = str(parameters.get("episodes", 1))
        posner_experiments = ",".join(str(x) for x in parameters.get("posner_experiments", [1, 2, 3, 4, 5]))
        trials_per_experiment = str(parameters.get("trials_per_experiment", 20))
        map_width = str(parameters.get("map_width", 32))
        map_height = str(parameters.get("map_height", 32))
        cycles_per_trial = str(parameters.get("cycles_per_trial", 30))
        seed = str(parameters.get("seed", 777))

        update_experiment_run_status(run_id=run_id, status="running")

        simulator_container = resolve_simulator_container()

        command = [
            "docker",
            "exec",
            simulator_container,
            "bash",
            "/workspace/scripts/run_attention_remote.sh",
            "--agent-url",
            agent_url,
            "--scene",
            f"/workspace/scenes/{scene}",
            "--out",
            f"/data/results/{architecture_id}/attention_posner/{run_id}/benchmark_out",
            "--episodes",
            episodes,
            "--posner-experiments",
            posner_experiments,
            "--trials-per-experiment",
            trials_per_experiment,
            "--map-width",
            map_width,
            "--map-height",
            map_height,
            "--cycles-per-trial",
            cycles_per_trial,
            "--seed",
            seed,
        ]

        completed = run_command(
            command,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS * 10,
        )

        if completed.returncode != 0:
            error_message = command_failure_message(
                "Remote attention Posner experiment", completed, stderr_path
            )
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message=error_message,
            )
            raise RuntimeError(error_message)

        bundles_dir = UPLOADS_DIR / "result_bundles"
        bundles_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = bundles_dir / f"{architecture_id}_{run_id}_attention_posner.zip"

        bundle_script = Path("/workspace/tools/create_result_bundle.py")
        if not bundle_script.exists():
            raise RuntimeError(f"Result bundle script not found: {bundle_script}")

        bundle = run_command(
            [
                "python",
                str(bundle_script),
                "--benchmark-out",
                str(result_dir),
                "--output",
                str(bundle_path),
                "--agent-name",
                architecture_id,
                "--architecture-name",
                str(architecture.get("name") or "CONAIM"),
                "--benchmark",
                "attention_posner",
                "--benchmark-version",
                "posner_v1",
                "--run-name",
                f"Attention Posner run {run_id}",
                "--episodes",
                episodes,
                "--trials-per-experiment",
                trials_per_experiment,
                "--seed",
                seed,
                "--author",
                str(architecture.get("author") or "CogScore playground"),
                "--notes",
                "Automatically generated after attention_posner experiment.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS,
        )

        if bundle.returncode != 0:
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message="Experiment finished, but result bundle generation failed",
            )
            raise RuntimeError("Result bundle generation failed")

        update_experiment_run_status(
            run_id=run_id,
            status="done",
            result_path=str(bundle_path),
            error_message=None,
        )

        return {
            "run_id": run_id,
            "architecture_id": architecture_id,
            "result_dir": str(result_dir),
            "bundle_path": str(bundle_path),
            "agent_url": agent_url,
            "parameters": parameters,
        }

    finally:
        docker_rm_force(container_name)

def handle_run_learning_remote(job: dict[str, Any], job_dir: Path) -> dict[str, Any]:
    input_data = read_json(job.get("input_json"))

    run_id = str(input_data["run_id"])
    architecture_id = str(input_data["architecture_id"])
    parameters = dict(input_data["parameters"])

    architecture = get_architecture(architecture_id)
    if architecture is None:
        raise RuntimeError(f"Architecture not found: {architecture_id}")

    image_tag = architecture.get("image_tag")
    if not image_tag:
        raise RuntimeError("Architecture has no validated Docker image")

    result_dir = RESULTS_DIR / architecture_id / "learning" / run_id / "benchmark_out"
    result_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"

    container_name = f"cogscore-run-{run_id}"

    try:
        start_architecture_container(
            container_name=container_name,
            image_tag=str(image_tag),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            labels={
                "cogscore.purpose": "experiment",
                "cogscore.architecture_id": architecture_id,
                "cogscore.run_id": run_id,
            },
        )

        time.sleep(3)

        agent_url = f"http://{container_name}:9000"

        scene = str(parameters.get("scene") or "learning/testing_s1A.ttt")
        episodes = str(parameters.get("episodes", 1))
        learning_stages = ",".join(
            str(x) for x in parameters.get(
                "learning_stages",
                ["Substage1", "Substage2", "Substage3", "Substage4", "Substage5"],
            )
        )
        learning_tests = ",".join(
            str(x) for x in parameters.get("learning_tests", ["testA", "testB", "testAB"])
        )
        steps_per_episode = str(parameters.get("steps_per_episode", 100))
        seed = str(parameters.get("seed", 777))

        update_experiment_run_status(run_id=run_id, status="running")

        simulator_container = resolve_simulator_container()

        command = [
            "docker",
            "exec",
            simulator_container,
            "bash",
            "/workspace/scripts/run_learning_remote.sh",
            "--agent-url",
            agent_url,
            "--scene",
            f"/workspace/scenes/{scene}",
            "--out",
            f"/data/results/{architecture_id}/learning/{run_id}/benchmark_out",
            "--episodes",
            episodes,
            "--learning-stages",
            learning_stages,
            "--learning-tests",
            learning_tests,
            "--steps-per-episode",
            steps_per_episode,
            "--seed",
            seed,
        ]

        completed = run_command(
            command,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS * 10,
        )

        if completed.returncode != 0:
            error_message = command_failure_message(
                "Remote learning experiment", completed, stderr_path
            )
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message=error_message,
            )
            raise RuntimeError(error_message)

        update_experiment_run_status(
            run_id=run_id,
            status="done",
            result_path=str(result_dir),
            error_message=None,
        )

        return {
            "run_id": run_id,
            "architecture_id": architecture_id,
            "result_dir": str(result_dir),
            "agent_url": agent_url,
            "parameters": parameters,
        }

    finally:
        docker_rm_force(container_name)

def handle_run_motivation_remote(job: dict[str, Any], job_dir: Path) -> dict[str, Any]:
    input_data = read_json(job.get("input_json"))

    run_id = str(input_data["run_id"])
    architecture_id = str(input_data["architecture_id"])
    parameters = dict(input_data["parameters"])

    architecture = get_architecture(architecture_id)
    if architecture is None:
        raise RuntimeError(f"Architecture not found: {architecture_id}")

    image_tag = architecture.get("image_tag")
    if not image_tag:
        raise RuntimeError("Architecture has no validated Docker image")

    result_dir = RESULTS_DIR / architecture_id / "motivation" / run_id / "benchmark_out"
    result_dir.mkdir(parents=True, exist_ok=True)

    stdout_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"

    container_name = f"cogscore-run-{run_id}"

    try:
        start_architecture_container(
            container_name=container_name,
            image_tag=str(image_tag),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            labels={
                "cogscore.purpose": "experiment",
                "cogscore.architecture_id": architecture_id,
                "cogscore.run_id": run_id,
            },
        )

        time.sleep(3)

        agent_url = f"http://{container_name}:9000"

        scene = str(parameters.get("scene") or "mot.ttt")
        episodes = str(parameters.get("episodes", 1))
        motivation_experiments = ",".join(
            str(x) for x in parameters.get("motivation_experiments", [1, 2, 3, 4, 5])
        )
        trials_per_experiment = str(parameters.get("trials_per_experiment", 20))
        cycles_per_trial = str(parameters.get("cycles_per_motivation_trial", 30))
        seed = str(parameters.get("seed", 777))

        update_experiment_run_status(run_id=run_id, status="running")

        simulator_container = resolve_simulator_container()

        command = [
            "docker",
            "exec",
            simulator_container,
            "bash",
            "/workspace/scripts/run_motivation_remote.sh",
            "--agent-url",
            agent_url,
            "--scene",
            f"/workspace/scenes/{scene}",
            "--out",
            f"/data/results/{architecture_id}/motivation/{run_id}/benchmark_out",
            "--episodes",
            episodes,
            "--motivation-experiments",
            motivation_experiments,
            "--trials-per-experiment",
            trials_per_experiment,
            "--cycles-per-trial",
            cycles_per_trial,
            "--seed",
            seed,
        ]

        completed = run_command(
            command,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS * 10,
        )

        if completed.returncode != 0:
            error_message = command_failure_message(
                "Remote motivation experiment", completed, stderr_path
            )
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message=error_message,
            )
            raise RuntimeError(error_message)

        bundles_dir = UPLOADS_DIR / "result_bundles"
        bundles_dir.mkdir(parents=True, exist_ok=True)
        bundle_path = bundles_dir / f"{architecture_id}_{run_id}_motivation.zip"

        bundle_script = Path("/workspace/tools/create_result_bundle.py")
        if not bundle_script.exists():
            raise RuntimeError(f"Result bundle script not found: {bundle_script}")

        bundle = run_command(
            [
                "python",
                str(bundle_script),
                "--benchmark-out",
                str(result_dir),
                "--output",
                str(bundle_path),
                "--agent-name",
                architecture_id,
                "--architecture-name",
                str(architecture.get("name") or "CONAIM"),
                "--benchmark",
                "motivation",
                "--benchmark-version",
                "motivation_v1",
                "--run-name",
                f"Motivation run {run_id}",
                "--episodes",
                episodes,
                "--trials-per-experiment",
                trials_per_experiment,
                "--seed",
                seed,
                "--author",
                str(architecture.get("author") or "CogScore playground"),
                "--notes",
                "Automatically generated after motivation experiment.",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS,
        )

        if bundle.returncode != 0:
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message="Experiment finished, but result bundle generation failed",
            )
            raise RuntimeError("Result bundle generation failed")

        update_experiment_run_status(
            run_id=run_id,
            status="done",
            result_path=str(bundle_path),
            error_message=None,
        )

        return {
            "run_id": run_id,
            "architecture_id": architecture_id,
            "result_dir": str(result_dir),
            "bundle_path": str(bundle_path),
            "agent_url": agent_url,
            "parameters": parameters,
        }

    finally:
        docker_rm_force(container_name)

def resolve_stored_path(value: str | Path) -> Path:
    """Resolve paths stored before switching between host and Docker execution."""
    original = Path(str(value)).expanduser()
    if original.exists():
        return original

    parts = original.parts
    data_indexes = [
        index
        for index, part in enumerate(parts)
        if part == "data"
    ]

    for index in reversed(data_indexes):
        relative_parts = parts[index + 1:]
        if not relative_parts:
            continue
        candidate = STORAGE_ROOT.joinpath(*relative_parts)
        if candidate.exists():
            info(f"Remapped legacy storage path {original} -> {candidate}")
            return candidate

    return original


def safe_path_component(value: str) -> str:
    cleaned = "".join(
        character
        if character.isalnum() or character in {"_", "-", "."}
        else "_"
        for character in str(value).strip()
    )
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned or "unnamed"


def remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path)


def link_or_copy_directory(source: Path, destination: Path) -> str:
    """Create a lightweight plot input link, with a copy fallback."""
    remove_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        destination.symlink_to(source, target_is_directory=True)
        return "symlink"
    except OSError as exc:
        info(
            f"Could not create plot input symlink {destination} -> {source}: "
            f"{exc}. Falling back to a directory copy."
        )
        shutil.copytree(source, destination)
        return "copy"


def learning_agent_source(source_root: Path, agent_name: str) -> Path:
    """Normalize old and new learning result-bundle layouts."""
    candidates = [
        source_root / agent_name,
        source_root / safe_path_component(agent_name),
    ]

    for candidate in candidates:
        if candidate.is_dir() and any(candidate.rglob("nrewards.txt")):
            return candidate

    return source_root


def csv_has_data_rows(path: Path) -> bool:
    """Return True only for a readable CSV containing a header and data row."""
    try:
        with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as handle:
            reader = csv.reader(handle, strict=True)
            header = next(reader, None)
            if not header or not any(str(value).strip() for value in header):
                return False
            return any(
                any(str(value).strip() for value in row)
                for row in reader
            )
    except (OSError, UnicodeError, csv.Error):
        return False


def nrewards_has_data(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8", errors="strict") as handle:
            next(handle, None)
            for line in handle:
                values = line.split()
                if len(values) >= 21:
                    float(values[1])
                    float(values[19])
                    float(values[20])
                    return True
    except (OSError, UnicodeError, ValueError):
        return False
    return False


def source_has_plot_data(benchmark: str, source_root: Path, agent_name: str) -> bool:
    """Check that a result contains at least one plotter-readable data file."""
    if benchmark == "learning":
        source = learning_agent_source(source_root, agent_name)
        return any(nrewards_has_data(path) for path in source.rglob("nrewards.txt"))

    if benchmark == "sensory_buffer":
        candidates = [
            *source_root.rglob("vision_sperling_per_trial_episode_*_active.csv"),
            *source_root.rglob("vision_sperling_per_trial_episode_*_remote.csv"),
        ]
    elif benchmark in {"attention_posner", "motivation"}:
        candidates = list(source_root.rglob("*_per_trial_episode_*.csv"))
    else:
        candidates = list(source_root.rglob("*.csv"))

    return any(csv_has_data_rows(path) for path in candidates)


def add_agent_to_plot_input(
    *,
    comparison_root: Path,
    benchmark: str,
    agent_name: str,
    source_root: Path,
    destination_name: str,
) -> str:
    if benchmark == "learning":
        source = learning_agent_source(source_root, agent_name)
        destination = comparison_root / destination_name
    else:
        source = source_root
        destination = comparison_root / destination_name / "benchmark_out"

    return link_or_copy_directory(source, destination)


def unique_destination_name(agent_name: str, run_id: str, used: set[str]) -> str:
    base = safe_path_component(agent_name)
    candidate = base

    if candidate in used:
        suffix = safe_path_component(run_id)[:8] or "run"
        candidate = f"{base}_{suffix}"

    counter = 2
    while candidate in used:
        candidate = f"{base}_{counter}"
        counter += 1

    used.add(candidate)
    return candidate


def prepare_comparison_root(
    *,
    benchmark: str,
    job_dir: Path,
) -> tuple[Path, list[dict[str, Any]]]:
    runs = list_runs(benchmark=benchmark)

    if not runs:
        raise RuntimeError(
            f"No uploaded runs found for benchmark: {benchmark}"
        )

    # list_runs returns newest first. Keep the newest *usable* run for each
    # distinct agent, so old agents remain in future comparison plots.
    latest_by_agent: dict[str, dict[str, Any]] = {}

    for run in runs:
        agent_name = str(run.get("agent_name") or "").strip()
        if not agent_name or agent_name in latest_by_agent:
            continue

        benchmark_out_value = run.get("benchmark_out_path")
        if not benchmark_out_value:
            continue

        source_root = resolve_stored_path(str(benchmark_out_value))
        if not source_root.is_dir():
            info(f"Ignoring missing result directory: {source_root}")
            continue

        if not source_has_plot_data(benchmark, source_root, agent_name):
            info(
                f"Ignoring result without usable {benchmark} plot data: "
                f"{source_root}"
            )
            continue

        latest_by_agent[agent_name] = run

    if not latest_by_agent:
        raise RuntimeError(
            f"No usable uploaded runs found for benchmark: {benchmark}"
        )

    comparison_root = job_dir / "plot_input"
    remove_path(comparison_root)
    comparison_root.mkdir(parents=True, exist_ok=True)

    selected_runs: list[dict[str, Any]] = []
    used_destination_names: set[str] = set()

    for agent_name, run in sorted(latest_by_agent.items()):
        source_root = resolve_stored_path(str(run["benchmark_out_path"]))
        run_id = str(run.get("id") or "run")
        destination_name = unique_destination_name(
            agent_name,
            run_id,
            used_destination_names,
        )
        method = add_agent_to_plot_input(
            comparison_root=comparison_root,
            benchmark=benchmark,
            agent_name=agent_name,
            source_root=source_root,
            destination_name=destination_name,
        )

        selected_runs.append(run)
        info(
            f"Comparison input: agent={agent_name}, run={run_id}, "
            f"source={source_root}, destination={destination_name}, "
            f"method={method}"
        )

    info(
        f"Comparison dataset assembled for {benchmark} with "
        f"{len(selected_runs)} agent(s)"
    )

    return comparison_root, selected_runs


def prepare_single_run_root(
    *,
    benchmark: str,
    job_dir: Path,
    input_data: dict[str, Any],
) -> tuple[Path, list[dict[str, Any]]]:
    benchmark_out_value = input_data.get("benchmark_out_path")
    if not benchmark_out_value:
        raise RuntimeError(
            "benchmark_out_path is required for single-run replot jobs"
        )

    source_root = resolve_stored_path(str(benchmark_out_value))
    if not source_root.is_dir():
        raise RuntimeError(
            f"benchmark_out directory not found: {source_root}"
        )

    agent_name = str(input_data.get("agent_name") or "agent").strip() or "agent"
    if not source_has_plot_data(benchmark, source_root, agent_name):
        raise RuntimeError(
            f"No usable {benchmark} plot data found in {source_root}"
        )

    plot_root = job_dir / "plot_input"
    remove_path(plot_root)
    plot_root.mkdir(parents=True, exist_ok=True)

    destination_name = safe_path_component(agent_name)
    add_agent_to_plot_input(
        comparison_root=plot_root,
        benchmark=benchmark,
        agent_name=agent_name,
        source_root=source_root,
        destination_name=destination_name,
    )

    return plot_root, [
        {
            "id": str(input_data.get("run_id") or ""),
            "agent_name": agent_name,
            "benchmark_out_path": str(source_root),
        }
    ]


def build_plot_command(
    *,
    benchmark: str,
    input_root: Path,
    output_dir: Path,
    input_data: dict[str, Any],
) -> list[str]:
    project_root = Path(os.getenv("PROJECT_ROOT", "/workspace"))
    x_points = max(2, int(input_data.get("x_points", 50)))
    smooth_window = max(1, int(input_data.get("smooth_window", 7)))
    impute_lookback = max(1, int(input_data.get("impute_lookback", 5)))

    if benchmark == "sensory_buffer":
        script = project_root / "scripts" / "sperling.py"
        command = [
            sys.executable,
            str(script),
            "--root",
            str(input_root),
            "--out",
            str(output_dir),
            "--x-points",
            str(x_points),
            "--smooth-window",
            str(smooth_window),
            "--impute-lookback",
            str(impute_lookback),
        ]
    elif benchmark == "attention_posner":
        script = project_root / "scripts" / "posner.py"
        command = [
            sys.executable,
            str(script),
            "--root",
            str(input_root),
            "--output",
            str(output_dir),
            "--x-points",
            str(x_points),
            "--smooth-window",
            str(smooth_window),
            "--impute-lookback",
            str(impute_lookback),
        ]
    elif benchmark == "motivation":
        script = project_root / "scripts" / "mot.py"
        command = [
            sys.executable,
            str(script),
            "--root",
            str(input_root),
            "--out",
            str(output_dir),
            "--x-points",
            str(x_points),
            "--smooth-window",
            str(smooth_window),
            "--impute-lookback",
            str(impute_lookback),
        ]
    elif benchmark == "learning":
        script = project_root / "scripts" / "learning.py"
        max_episodes = max(0, int(input_data.get("max_episodes", 50)))
        command = [
            sys.executable,
            str(script),
            "--root",
            str(input_root),
            "--out",
            str(output_dir),
            "--max-episodes",
            str(max_episodes),
            "--smooth-window",
            str(smooth_window),
            "--png-only",
        ]
    else:
        raise RuntimeError(f"Unsupported plot benchmark: {benchmark}")

    if not script.is_file():
        raise RuntimeError(f"Plot script not found: {script}")

    return command


def handle_replot(
    job: dict[str, Any],
    job_dir: Path,
) -> dict[str, Any]:
    input_data = read_json(job.get("input_json"))
    benchmark = str(input_data.get("benchmark", "")).strip()
    mode = str(input_data.get("mode", "single_run")).strip()
    job_id = str(job["id"])
    run_id = str(input_data.get("run_id", "")).strip()

    supported = {
        "sensory_buffer",
        "attention_posner",
        "motivation",
        "learning",
    }
    if benchmark not in supported:
        raise RuntimeError(f"Unsupported plot benchmark: {benchmark}")

    if mode == "comparison_all_uploaded_agents":
        input_root, selected_runs = prepare_comparison_root(
            benchmark=benchmark,
            job_dir=job_dir,
        )
        output_scope = "comparison"
    else:
        input_root, selected_runs = prepare_single_run_root(
            benchmark=benchmark,
            job_dir=job_dir,
            input_data=input_data,
        )
        output_scope = "single"

    plots_root = Path(
        os.getenv("PLOTS_DIR", str(RESULTS_DIR.parent / "plots"))
    )
    output_dir = plots_root / benchmark / output_scope / job_id
    remove_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    command = build_plot_command(
        benchmark=benchmark,
        input_root=input_root,
        output_dir=output_dir,
        input_data=input_data,
    )

    stdout_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"
    timeout = max(60, int(os.getenv("PLOT_TIMEOUT_SECONDS", "1800")))

    completed = run_command(
        command,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout=timeout,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            f"{benchmark} plot generation failed with exit code "
            f"{completed.returncode}. stdout={tail_log(stdout_path, max_chars=4000)!r}; "
            f"stderr={tail_log(stderr_path, max_chars=4000)!r}"
        )

    plot_extensions = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".html", ".pdf"}
    generated = sorted(
        str(path)
        for path in output_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in plot_extensions
    )

    if not generated:
        raise RuntimeError(
            f"{benchmark} plot script completed, but no plot files were generated. "
            f"stdout={tail_log(stdout_path, max_chars=4000)!r}; "
            f"stderr={tail_log(stderr_path, max_chars=4000)!r}"
        )

    selected_agents = [
        str(run.get("agent_name") or "")
        for run in selected_runs
    ]
    selected_run_ids = [
        str(run.get("id") or "")
        for run in selected_runs
    ]

    x_points = max(2, int(input_data.get("x_points", 50)))
    smooth_window = max(1, int(input_data.get("smooth_window", 7)))
    impute_lookback = max(1, int(input_data.get("impute_lookback", 5)))
    max_episodes = max(0, int(input_data.get("max_episodes", 50)))

    plot_parameters: dict[str, Any] = {
        "smooth_window": smooth_window,
    }
    if benchmark == "learning":
        plot_parameters.update(
            {
                "max_episodes": max_episodes,
                "aggregation": "mean and standard deviation across available runs",
            }
        )
    else:
        plot_parameters.update(
            {
                "x_points": x_points,
                "impute_lookback": impute_lookback,
                "interpolation": "linear with previous-mean fallback",
            }
        )

    metadata = {
        "job_id": job_id,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "reference_run_id": run_id,
        "benchmark": benchmark,
        "mode": mode,
        "plots_dir": str(output_dir),
        "selected_agents": selected_agents,
        "selected_run_ids": selected_run_ids,
        "generated_plots": generated,
        "generated_plot_relative_paths": [
            str(Path(path).relative_to(output_dir))
            for path in generated
        ],
        "plot_parameters": plot_parameters,
    }
    (output_dir / "generation.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return metadata




def write_worker_heartbeat() -> None:
    heartbeat_path = STORAGE_ROOT / "worker-heartbeat.json"
    payload = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hostname": socket.gethostname(),
        "pid": os.getpid(),
    }
    temporary = heartbeat_path.with_suffix(".tmp")
    try:
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(heartbeat_path)
    except OSError as exc:
        info(f"Could not write worker heartbeat: {exc}")


def handle_simulator_control(job: dict[str, Any], job_dir: Path) -> dict[str, Any]:
    input_data = read_json(job.get("input_json"))
    action = str(input_data.get("action") or "").strip().lower()
    scene = str(input_data.get("scene") or "sperling.ttt").strip()
    if action not in {"start", "stop", "restart"}:
        raise ValueError(f"Unsupported simulator action: {action}")

    scene_path = Path("/workspace/scenes") / scene
    if scene_path.is_absolute() and not str(scene_path).startswith("/workspace/scenes/"):
        raise ValueError("Simulator scene must be inside /workspace/scenes")
    if ".." in Path(scene).parts:
        raise ValueError("Simulator scene cannot contain parent-directory components")

    container_name = resolve_simulator_container()
    stdout_path = job_dir / "stdout.log"
    stderr_path = job_dir / "stderr.log"

    if action in {"stop", "restart"}:
        completed = run_command(
            ["docker", "exec", container_name, "cogscore-stop-coppelia"],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=60,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                command_failure_message(
                    "Stopping CoppeliaSim",
                    completed,
                    stderr_path,
                )
            )

    if action in {"start", "restart"}:
        completed = run_command(
            [
                "docker",
                "exec",
                container_name,
                "cogscore-open-coppelia",
                str(scene_path),
                "/data/coppelia/manual-control.log",
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=90,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                command_failure_message(
                    "Starting CoppeliaSim",
                    completed,
                    stderr_path,
                )
            )

    return {
        "action": action,
        "scene": scene,
        "simulator_container": container_name,
    }


def process_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    job_type = str(job["job_type"])

    info(
        f"Processing job={job_id} "
        f"type={job_type} "
        f"hostname={socket.gethostname()} "
        f"pid={os.getpid()} "
        f"docker_host={os.getenv('DOCKER_HOST')!r}"
    )
    job_dir = JOBS_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    mark_job_running(job_id=job_id, log_path=str(job_dir))

    try:
        if job_type == "validate_architecture":
            result = handle_validate_architecture(job, job_dir)
        elif job_type == "run_sensory_remote":
            result = handle_run_sensory_remote(job, job_dir)
        elif job_type == "run_attention_remote":
            result = handle_run_attention_remote(job, job_dir)
        elif job_type == "run_motivation_remote":
            result = handle_run_motivation_remote(job, job_dir) 
        elif job_type == "run_learning_remote":
            result = handle_run_learning_remote(job, job_dir)  
        elif job_type == "replot":
            result = handle_replot(job, job_dir)
        elif job_type == "simulator_control":
            result = handle_simulator_control(job, job_dir)
        else:
            raise RuntimeError(f"Unknown job type: {job_type}")

        mark_job_done(job_id=job_id, output_data=result, log_path=str(job_dir))

    except Exception as exc:
        if job_type.startswith("run_"):
            input_data = read_json(job.get("input_json"))
            run_id = input_data.get("run_id")
            if run_id:
                update_experiment_run_status(
                    run_id=str(run_id),
                    status="error",
                    error_message=str(exc),
                )

        mark_job_error(
            job_id=job_id,
            error_message=str(exc),
            output_data={"error": str(exc)},
            log_path=str(job_dir),
        )
        info(f"Job {job_id} failed: {exc}")


def main() -> int:
    os.environ.setdefault(
        "DOCKER_HOST",
        "unix:///var/run/docker.sock",
    )

    info(
        f"Worker identity: "
        f"hostname={socket.gethostname()} "
        f"pid={os.getpid()} "
        f"docker_host={os.getenv('DOCKER_HOST')!r} "
        f"path={os.getenv('PATH')!r}"
    )
    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)

    ensure_storage_dirs()
    init_db()

    interrupted_jobs = mark_interrupted_jobs_error(
        "Worker restarted before the job finished; any dynamic architecture "
        "container from that execution was removed during startup cleanup."
    )
    if interrupted_jobs:
        info(
            "Marked interrupted jobs as error after restart: "
            + ", ".join(interrupted_jobs)
        )

    cleanup_stale_architecture_containers()

    info("CogScore online worker started")

    while True:
        write_worker_heartbeat()
        job = get_next_pending_job()
        if job is None:
            time.sleep(2)
            continue

        process_job(job)
        write_worker_heartbeat()


if __name__ == "__main__":
    raise SystemExit(main())
