from __future__ import annotations

from typing import Any

from fastapi import FastAPI


app = FastAPI(title="Dummy CogScore Sensory Agent")

memory: dict[str, Any] = {
    "frame": [],
    "width": 0,
    "height": 0,
    "channels": 3,
}


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "agent": "DummySensoryAgent",
        "benchmarks": ["sensory_buffer", "attention_posner", "motivation", "learning"],
    }


@app.post("/reset")
def reset(payload: dict[str, Any]) -> dict[str, Any]:
    memory["frame"] = []
    memory["width"] = 0
    memory["height"] = 0
    memory["channels"] = 3
    if payload.get("benchmark") in {None, "learning"}:
        # Function is defined later; lookup happens only when the endpoint is called.
        reset_fn = globals().get("_reset_learning")
        if reset_fn is not None:
            reset_fn()
    return {"status": "ok"}


@app.post("/sensory/stimulus")
def stimulus(payload: dict[str, Any]) -> dict[str, Any]:
    memory["frame"] = list(payload.get("frame", []))
    memory["width"] = int(payload.get("width", 0))
    memory["height"] = int(payload.get("height", 0))
    memory["channels"] = int(payload.get("channels", 3))

    return {
        "status": "ok",
        "stored_values": len(memory["frame"]),
    }


@app.post("/sensory/retention_tick")
def retention_tick(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ok"}


@app.post("/sensory/readout")
def readout(payload: dict[str, Any]) -> dict[str, Any]:
    cue = payload.get("cue", {})
    x0 = int(cue.get("x0", 0))
    y0 = int(cue.get("y0", 0))
    size = int(cue.get("size", 1))

    width = int(memory["width"])
    frame = list(memory["frame"])

    patch = []

    for y in range(y0, y0 + size):
        for x in range(x0, x0 + size):
            idx = (y * width + x) * 3
            patch.extend(frame[idx:idx + 3])

    return {
        "status": "ok",
        "encoding": "rgb_float_0_255",
        "patch": patch,
        "confidence": 1.0,
        "debug": {
            "agent": "dummy-perfect-memory",
        },
    }

@app.post("/attention/act")
def attention_act(payload: dict):
    target = payload.get("target", {"x": 0.5, "y": 0.5})
    cycles_per_trial = int(payload.get("cycles_per_trial", 30))

    return {
        "detected": True,
        "detection_cycle": max(1, cycles_per_trial // 2),
        "overt_movement_cycle": max(1, cycles_per_trial // 2 + 2),
        "attention_peak": {
            "x": float(target.get("x", 0.5)),
            "y": float(target.get("y", 0.5)),
        },
        "confidence": 1.0,
        "debug": {
            "agent": "dummy_attention_agent"
        },
    }

@app.post("/motivation/act")
def motivation_act(payload: dict):
    experiment_id = int(payload.get("experiment_id", 1))
    objects = payload.get("objects", [])

    if not objects:
        return {"action": "STOP", "object": None, "confidence": 0.0}

    if experiment_id == 1:
        chosen = objects[0]
        action = "INTERACT"
    elif experiment_id == 2:
        chosen = objects[1] if len(objects) > 1 else objects[0]
        action = "INTERACT"
    elif experiment_id == 3:
        chosen = objects[2] if len(objects) > 2 else objects[0]
        action = "INTERACT"
    elif experiment_id == 4:
        chosen = objects[1] if len(objects) > 1 else objects[0]
        action = "LOOK"
    elif experiment_id == 5:
        if payload.get("signals", {}).get("outcome_devalued"):
            chosen = objects[1] if len(objects) > 1 else objects[0]
        else:
            chosen = objects[0]
        action = "INTERACT"
    else:
        chosen = objects[0]
        action = "INTERACT"

    return {
        "action": action,
        "object": chosen["id"],
        "confidence": 0.75,
        "debug": {
            "experiment_id": experiment_id,
            "role": chosen.get("role"),
        },
    }

@app.post("/close")
def close(payload: dict[str, Any]) -> dict[str, Any]:
    return {"status": "ok"}

# ---------------------------------------------------------------------------
# Learning benchmark: online tabular Q-learning over proportional-control gains
# ---------------------------------------------------------------------------

import math
import random
from collections import defaultdict

LEARNING_GAINS = (0.15, 0.30, 0.50, 0.75, 1.00)
LEARNING_ALPHA = 0.25
LEARNING_GAMMA = 0.90
LEARNING_EPSILON_START = 0.30
LEARNING_EPSILON_MIN = 0.03
LEARNING_EPSILON_DECAY = 0.997

learning_memory: dict[str, Any] = {
    "q": defaultdict(lambda: [0.0] * len(LEARNING_GAINS)),
    "previous": None,
    "last_stream": None,
    "last_step": None,
    "last_visible_error": (0.0, 0.0),
    "last_delta": (0.0, 0.0),
    "updates": 0,
    "actions": 0,
    "rng": random.Random(777),
}


def _reset_learning() -> None:
    learning_memory["q"] = defaultdict(lambda: [0.0] * len(LEARNING_GAINS))
    learning_memory["previous"] = None
    learning_memory["last_stream"] = None
    learning_memory["last_step"] = None
    learning_memory["last_visible_error"] = (0.0, 0.0)
    learning_memory["last_delta"] = (0.0, 0.0)
    learning_memory["updates"] = 0
    learning_memory["actions"] = 0
    learning_memory["rng"] = random.Random(777)


def _error_bin(error_norm: float) -> int:
    if error_norm < 0.05:
        return 0
    if error_norm < 0.15:
        return 1
    if error_norm < 0.35:
        return 2
    if error_norm < 0.70:
        return 3
    return 4


def _learning_state(stage: str, visible: bool, error_norm: float) -> tuple[str, str, int]:
    # Knowledge is shared between testA/testB inside the same developmental stage.
    visibility = "visible" if visible else "occluded"
    return stage, visibility, _error_bin(error_norm)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _epsilon(signals: dict[str, Any]) -> float:
    actions = int(learning_memory["actions"])
    base = max(
        LEARNING_EPSILON_MIN,
        LEARNING_EPSILON_START * (LEARNING_EPSILON_DECAY ** actions),
    )
    # Curiosity produces a little more exploration in Substage2/3.
    curiosity = float(signals.get("curiosity", 0.0) or 0.0)
    return min(0.50, base + 0.15 * curiosity)


def _select_action(state: tuple[str, str, int], signals: dict[str, Any]) -> int:
    q_values = learning_memory["q"][state]
    rng: random.Random = learning_memory["rng"]
    if rng.random() < _epsilon(signals):
        return rng.randrange(len(LEARNING_GAINS))
    return max(range(len(q_values)), key=q_values.__getitem__)


def _update_previous(current_error_norm: float, next_state: tuple[str, str, int]) -> None:
    previous = learning_memory.get("previous")
    if not previous:
        return

    previous_state = previous["state"]
    previous_action = int(previous["action"])
    previous_error_norm = float(previous["error_norm"])

    # The runner does not send reward explicitly. At step t, the current error is
    # the result of the action selected at t-1, so error reduction is a reward proxy.
    improvement = previous_error_norm - current_error_norm
    proximity = max(0.0, 1.0 - current_error_norm)
    reward = improvement + 0.10 * proximity

    q_values = learning_memory["q"][previous_state]
    next_q_values = learning_memory["q"][next_state]
    td_target = reward + LEARNING_GAMMA * max(next_q_values)
    q_values[previous_action] += LEARNING_ALPHA * (
        td_target - q_values[previous_action]
    )
    learning_memory["updates"] = int(learning_memory["updates"]) + 1


@app.post("/learning/act")
def learning_act(payload: dict[str, Any]) -> dict[str, Any]:
    stage = str(payload.get("stage", "Substage1"))
    test = str(payload.get("test", "testA"))
    episode = int(payload.get("episode", 0))
    step = int(payload.get("step", 0))
    target = dict(payload.get("target") or {})
    signals = dict(payload.get("signals") or {})

    stream = (stage, test, episode)
    previous_stream = learning_memory.get("last_stream")
    previous_step = learning_memory.get("last_step")

    # Start a new temporal transition at every test/episode boundary, but retain
    # the learned Q-table so behavior can improve across episodes and tests.
    if stream != previous_stream or (
        previous_step is not None and step <= int(previous_step)
    ):
        learning_memory["previous"] = None

    visible = bool(target.get("visible", True))
    has_errors = "yaw_error" in target and "pitch_error" in target

    if has_errors:
        yaw_error = float(target.get("yaw_error", 0.0) or 0.0)
        pitch_error = float(target.get("pitch_error", 0.0) or 0.0)
    else:
        # Dead-reckoning fallback for a future runner that hides exact errors
        # while the target is occluded.
        yaw_error, pitch_error = learning_memory["last_visible_error"]
        last_yaw_delta, last_pitch_delta = learning_memory["last_delta"]
        yaw_error = float(yaw_error) + float(last_yaw_delta)
        pitch_error = float(pitch_error) + float(last_pitch_delta)

    if visible:
        learning_memory["last_visible_error"] = (yaw_error, pitch_error)

    error_norm = math.hypot(yaw_error, pitch_error)
    state = _learning_state(stage, visible, error_norm)
    _update_previous(error_norm, state)

    action_index = _select_action(state, signals)
    gain = LEARNING_GAINS[action_index]

    # The benchmark applies delta directly: new_error = old_error + delta.
    yaw_delta = _clamp(-gain * yaw_error, -1.0, 1.0)
    pitch_delta = _clamp(-gain * pitch_error, -1.0, 1.0)

    learning_memory["previous"] = {
        "state": state,
        "action": action_index,
        "error_norm": error_norm,
    }
    learning_memory["last_stream"] = stream
    learning_memory["last_step"] = step
    learning_memory["last_delta"] = (yaw_delta, pitch_delta)
    learning_memory["actions"] = int(learning_memory["actions"]) + 1

    q_values = learning_memory["q"][state]
    confidence = 0.5
    if q_values:
        ordered = sorted(q_values, reverse=True)
        margin = ordered[0] - ordered[1] if len(ordered) > 1 else ordered[0]
        confidence = _clamp(0.5 + margin, 0.0, 1.0)

    return {
        "action": "TRACK" if visible or has_errors else "PREDICT",
        "object": 1,
        "yaw_delta": yaw_delta,
        "pitch_delta": pitch_delta,
        "confidence": confidence,
        "debug": {
            "algorithm": "tabular_q_learning_gain_selection",
            "stage": stage,
            "test": test,
            "episode": episode,
            "step": step,
            "state": list(state),
            "gain": gain,
            "epsilon": _epsilon(signals),
            "error_norm": error_norm,
            "updates": learning_memory["updates"],
        },
    }


@app.get("/learning/model")
def learning_model() -> dict[str, Any]:
    q_table = {
        "|".join(map(str, state)): values
        for state, values in learning_memory["q"].items()
    }
    return {
        "algorithm": "tabular_q_learning_gain_selection",
        "gains": list(LEARNING_GAINS),
        "updates": learning_memory["updates"],
        "actions": learning_memory["actions"],
        "q_table": q_table,
    }
