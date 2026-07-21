from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
import logging

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
    ensure_storage_dirs,
)
from app.database import (  # noqa: E402
    get_architecture,
    get_next_pending_job,
    init_db,
    list_runs,
    mark_job_done,
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


def docker_rm_force(container_name: str) -> None:
    subprocess.run(
        ["docker", "rm", "-f", container_name],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )


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
        update_architecture_status(
            architecture_id=architecture_id,
            status="error",
            error_message="Docker build failed",
        )
        raise RuntimeError("Docker build failed")

    docker_rm_force(container_name)

    run = run_command(
        [
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
            image_tag,
        ],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout=ARCH_TIMEOUT_SECONDS,
    )

    if run.returncode != 0:
        update_architecture_status(
            architecture_id=architecture_id,
            status="error",
            error_message="Could not start architecture container",
        )
        raise RuntimeError("Could not start architecture container")

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

    docker_rm_force(container_name)

    try:
        start_agent = run_command(
            [
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
                image_tag,
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS,
        )

        if start_agent.returncode != 0:
            raise RuntimeError("Could not start architecture container")

        time.sleep(3)

        agent_url = f"http://{container_name}:9000"

        scene = str(parameters.get("scene", "sperling.ttt"))
        episodes = str(parameters.get("episodes", 1))
        trials_per_delay = str(parameters.get("trials_per_delay", 3))
        delays_ms = ",".join(str(x) for x in parameters.get("delays_ms", [0, 50, 100, 220]))
        resolution = str(parameters.get("resolution", 64))
        patch_size = str(parameters.get("patch_size", 8))

        update_experiment_run_status(run_id=run_id, status="running")

        command = [
            "docker",
            "exec",
            "cogscore-sim-vnc",
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
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message="Remote sensory experiment failed",
            )
            raise RuntimeError("Remote sensory experiment failed")

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

    docker_rm_force(container_name)

    try:
        start_agent = run_command(
            [
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
                image_tag,
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS,
        )

        if start_agent.returncode != 0:
            raise RuntimeError("Could not start architecture container")

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

        command = [
            "docker",
            "exec",
            "cogscore-sim-vnc",
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
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message="Remote attention Posner experiment failed",
            )
            raise RuntimeError("Remote attention Posner experiment failed")

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

    docker_rm_force(container_name)

    try:
        start_agent = run_command(
            [
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
                image_tag,
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS,
        )

        if start_agent.returncode != 0:
            raise RuntimeError("Could not start architecture container")

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

        command = [
            "docker",
            "exec",
            "cogscore-sim-vnc",
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
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message="Remote learning experiment failed",
            )
            raise RuntimeError("Remote learning experiment failed")

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

    docker_rm_force(container_name)

    try:
        start_agent = run_command(
            [
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
                image_tag,
            ],
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=ARCH_TIMEOUT_SECONDS,
        )

        if start_agent.returncode != 0:
            raise RuntimeError("Could not start architecture container")

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

        command = [
            "docker",
            "exec",
            "cogscore-sim-vnc",
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
            update_experiment_run_status(
                run_id=run_id,
                status="error",
                result_path=str(result_dir),
                error_message="Remote motivation experiment failed",
            )
            raise RuntimeError("Remote motivation experiment failed")

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

    # list_runs já retorna created_at DESC.
    # Mantém somente o resultado mais recente de cada agente.
    latest_by_agent: dict[str, dict[str, Any]] = {}

    for run in runs:
        agent_name = str(run.get("agent_name") or "").strip()

        if not agent_name:
            continue

        benchmark_out_value = run.get("benchmark_out_path")

        if not benchmark_out_value:
            continue

        benchmark_out = Path(str(benchmark_out_value))

        if not benchmark_out.is_dir():
            info(
                f"Ignoring missing result directory: "
                f"{benchmark_out}"
            )
            continue

        if not any(benchmark_out.rglob("nrewards.txt")):
            info(
                f"Ignoring result without nrewards.txt: "
                f"{benchmark_out}"
            )
            continue

        latest_by_agent.setdefault(agent_name, run)

    if not latest_by_agent:
        raise RuntimeError(
            f"No usable uploaded runs found for benchmark: "
            f"{benchmark}"
        )

    comparison_root = job_dir / "comparison_input"

    if comparison_root.exists():
        shutil.rmtree(comparison_root)

    comparison_root.mkdir(parents=True, exist_ok=True)

    selected_runs: list[dict[str, Any]] = []

    for agent_name, run in sorted(latest_by_agent.items()):
        source_root = Path(str(run["benchmark_out_path"]))
        destination_agent = comparison_root / agent_name

        # Estrutura comum dos bundles:
        # benchmark_out/AGENT/EXPERIMENT/...
        source_agent = source_root / agent_name

        if source_agent.is_dir():
            shutil.copytree(
                source_agent,
                destination_agent,
                dirs_exist_ok=True,
            )
        else:
            # Compatibilidade com bundles em que benchmark_out
            # já aponta diretamente para os experimentos.
            shutil.copytree(
                source_root,
                destination_agent,
                dirs_exist_ok=True,
            )

        selected_runs.append(run)

        info(
            f"Comparison input: agent={agent_name}, "
            f"source={source_root}"
        )

    discovered_files = list(
        comparison_root.rglob("nrewards.txt")
    )

    if not discovered_files:
        raise RuntimeError(
            f"No nrewards.txt files assembled under "
            f"{comparison_root}"
        )

    info(
        f"Comparison dataset assembled with "
        f"{len(selected_runs)} agent(s) and "
        f"{len(discovered_files)} nrewards.txt file(s)"
    )

    return comparison_root, selected_runs

def handle_replot(
    job: dict[str, Any],
    job_dir: Path,
) -> dict[str, Any]:
    input_data = read_json(job.get("input_json"))

    benchmark = str(
        input_data.get("benchmark", "")
    ).strip()

    run_id = str(
        input_data.get("run_id", "")
    ).strip()

    mode = str(
        input_data.get("mode", "single_run")
    ).strip()

    agent_name = str(
        input_data.get("agent_name", "agent")
    ).strip()

    selected_runs: list[dict[str, Any]] = []

    if mode == "comparison_all_uploaded_agents":
        benchmark_out_path, selected_runs = (
            prepare_comparison_root(
                benchmark=benchmark,
                job_dir=job_dir,
            )
        )

        agent_name = "all_uploaded_agents"

    else:
        benchmark_out_value = input_data.get(
            "benchmark_out_path"
        )

        if not benchmark_out_value:
            raise RuntimeError(
                "benchmark_out_path is required for "
                "single-run replot jobs"
            )

        benchmark_out_path = Path(
            str(benchmark_out_value)
        )

        if not benchmark_out_path.is_dir():
            raise RuntimeError(
                f"benchmark_out directory not found: "
                f"{benchmark_out_path}"
            )

    output_dir = (
        Path(
            os.getenv(
                "PLOTS_DIR",
                str(RESULTS_DIR.parent / "plots"),
            )
        )
        / benchmark
        / run_id
    )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    if benchmark == "learning":
        learning_script = Path(
            os.getenv(
                "PROJECT_ROOT",
                "/workspace",
            )
        ) / "scripts" / "learning.py"

        if not learning_script.exists():
            raise RuntimeError(
                f"Learning plot script not found: "
                f"{learning_script}"
            )

        nrewards_files = sorted(
            benchmark_out_path.rglob("nrewards.txt")
        )

        if not nrewards_files:
            raise RuntimeError(
                f"No nrewards.txt files found in "
                f"{benchmark_out_path}"
            )

        command = [
            "python",
            str(learning_script),
            "--root",
            str(benchmark_out_path),
            "--out",
            str(output_dir),
            "--max-episodes",
            "50",
            "--smooth-window",
            "7",
            "--png-only",
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300,
        )

        stdout_path = job_dir / "learning_plot_stdout.log"
        stderr_path = job_dir / "learning_plot_stderr.log"

        result = run_command(
            command,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
            timeout=300,
        )

        if result.returncode != 0:
            stdout_text = (
                stdout_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                if stdout_path.exists()
                else ""
            )

            stderr_text = (
                stderr_path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                if stderr_path.exists()
                else ""
            )

            raise RuntimeError(
                "Learning plot generation failed. "
                f"Exit code: {result.returncode}. "
                f"stdout={stdout_text[-4000:]!r}. "
                f"stderr={stderr_text[-4000:]!r}"
            )

        generated = sorted(
            str(path)
            for path in output_dir.rglob("*.png")
        )

        if not generated:
            raise RuntimeError(
                "Learning script completed, but no PNG "
                "plots were generated."
            )

        return {
            "run_id": run_id,
            "benchmark": benchmark,
            "mode": mode,
            "plots_dir": str(output_dir),
            "generated_plots": generated,
            "selected_agents": [
                str(run.get("agent_name"))
                for run in selected_runs
            ],
            "selected_run_ids": [
                str(run.get("id"))
                for run in selected_runs
            ],
        }

    csv_files = sorted(
        benchmark_out_path.rglob("*.csv")
    )

    if not csv_files:
        raise RuntimeError(
            f"No CSV files found in {benchmark_out_path}"
        )

    generated: list[str] = []

    for csv_path in csv_files:
        try:
            import matplotlib.pyplot as plt
            import pandas as pd

            dataframe = pd.read_csv(csv_path)

            numeric = dataframe.select_dtypes(
                include="number"
            )

            if numeric.empty:
                continue

            figure, axis = plt.subplots(
                figsize=(10, 6)
            )

            numeric.plot(ax=axis)

            axis.set_title(
                f"{agent_name} — {csv_path.stem}"
            )
            axis.set_xlabel("Row")
            axis.set_ylabel("Value")
            axis.grid(True, alpha=0.3)

            figure.tight_layout()

            output_path = (
                output_dir / f"{csv_path.stem}.png"
            )

            figure.savefig(
                output_path,
                dpi=150,
                bbox_inches="tight",
            )
            plt.close(figure)

            generated.append(str(output_path))

        except Exception as exc:
            info(
                f"Could not plot {csv_path}: {exc}"
            )

    if not generated:
        raise RuntimeError(
            "No plot could be generated from the uploaded CSV files."
        )

    return {
        "run_id": run_id,
        "benchmark": benchmark,
        "plots_dir": str(output_dir),
        "generated_plots": generated,
    }

def process_job(job: dict[str, Any]) -> None:
    job_id = str(job["id"])
    job_type = str(job["job_type"])

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
        else:
            raise RuntimeError(f"Unknown job type: {job_type}")

        mark_job_done(job_id=job_id, output_data=result, log_path=str(job_dir))

    except Exception as exc:
        mark_job_error(
            job_id=job_id,
            error_message=str(exc),
            output_data={"error": str(exc)},
            log_path=str(job_dir),
        )
        info(f"Job {job_id} failed: {exc}")


def main() -> int:
    ensure_storage_dirs()
    init_db()

    info("CogScore online worker started")

    while True:
        job = get_next_pending_job()
        if job is None:
            time.sleep(2)
            continue

        process_job(job)


if __name__ == "__main__":
    raise SystemExit(main())
