from __future__ import annotations

import json
import os
from typing import Any

import requests


API_URL = os.getenv("API_URL", "http://localhost:8000").rstrip("/")


class ApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, detail: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _decode_error(response: requests.Response) -> Any:
    try:
        payload = response.json()
    except ValueError:
        return response.text[:8000]
    if isinstance(payload, dict) and "detail" in payload:
        return payload["detail"]
    return payload


def _request(method: str, path: str, **kwargs: Any) -> Any:
    try:
        response = requests.request(method, API_URL + path, **kwargs)
    except requests.RequestException as exc:
        raise ApiError(f"Could not contact the CogScore API: {exc}") from exc
    if not response.ok:
        detail = _decode_error(response)
        raise ApiError(
            f"The API request failed with HTTP {response.status_code}.",
            status_code=response.status_code,
            detail=detail,
        )
    if not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("The API returned a response that was not valid JSON.") from exc


def get(path: str, *, timeout: int = 30) -> Any:
    return _request("GET", path, timeout=timeout)


def post_json(path: str, payload: dict[str, Any], *, timeout: int = 120) -> Any:
    return _request("POST", path, json=payload, timeout=timeout)


def upload(path: str, filename: str, data: bytes, *, timeout: int = 300) -> Any:
    return _request(
        "POST",
        path,
        files={"file": (filename, data, "application/zip")},
        timeout=timeout,
    )


def pretty_detail(error: Exception) -> str:
    if isinstance(error, ApiError):
        detail = error.detail
        if isinstance(detail, (dict, list)):
            return json.dumps(detail, ensure_ascii=False, indent=2)
        if detail:
            return str(detail)
    return str(error)
