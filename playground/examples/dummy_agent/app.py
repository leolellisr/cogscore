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
        "benchmarks": ["sensory_buffer"],
    }


@app.post("/reset")
def reset(payload: dict[str, Any]) -> dict[str, Any]:
    memory["frame"] = []
    memory["width"] = 0
    memory["height"] = 0
    memory["channels"] = 3
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
