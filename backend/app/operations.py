from __future__ import annotations

import json

from fastapi import HTTPException

from backend.helper.client import HelperClient, HelperError, HelperUnavailable
from backend.helper.protocol import validate_filename

from .labs import (
    availability,
    detail,
    host_evidence,
    load_lab,
    read_host_evidence,
)
from .settings import Settings

ALLOWED_ACTIONS = {"start", "stop", "reset"}
ERROR_STATUS = {
    "busy": 409,
    "lab_not_implemented": 409,
    "unknown_lab": 404,
    "timeout": 504,
    "unauthorized_peer": 403,
    "invalid_lab": 400,
    "invalid_filename": 400,
    "unknown_action": 400,
    "helper_misconfigured": 500,
    "command_failed": 500,
}


def translate_helper_error(exc: HelperError) -> HTTPException:
    if isinstance(exc, HelperUnavailable):
        return HTTPException(
            status_code=503,
            detail={
                "message": exc.message,
                "code": exc.code,
                "hint": "Check iotlab-helper.service and its Unix socket",
            },
        )
    detail_payload = {"message": exc.message, "code": exc.code}
    if exc.details:
        detail_payload["details"] = exc.details
    if exc.response is not None:
        detail_payload["result"] = exc.response.get("result")
    return HTTPException(
        status_code=ERROR_STATUS.get(exc.code, 500),
        detail=detail_payload,
    )


def require_available(settings: Settings, lab_id: str) -> dict:
    manifest = load_lab(settings, lab_id)
    if availability(settings, manifest) != "available":
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"{lab_id} is planned and has no runtime",
                "code": "lab_not_implemented",
            },
        )
    return manifest


def run_action(
    helper: HelperClient | None, settings: Settings, lab_id: str, action: str
) -> dict:
    if action not in ALLOWED_ACTIONS:
        raise HTTPException(status_code=404, detail="unknown action")
    if not settings.enable_actions:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Lab actions are disabled until the privileged helper is enabled",
                "code": "actions_disabled",
            },
        )
    require_available(settings, lab_id)
    if helper is None:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Privileged lab helper is not configured",
                "code": "helper_unavailable",
            },
        )
    try:
        response = helper.call(action, lab=lab_id)
    except HelperError as exc:
        raise translate_helper_error(exc) from exc
    result = response.get("result", {})
    return {
        "lab": lab_id,
        "action": action,
        "status": "ok",
        "duration_ms": result.get("duration_ms"),
        "stdout": result.get("stdout", ""),
        "stderr": result.get("stderr", ""),
    }


def _containers(raw: str) -> list[dict]:
    text = raw.strip()
    if not text:
        return []
    items = json.loads(text) if text.startswith("[") else [json.loads(line) for line in text.splitlines() if line.strip()]
    if not isinstance(items, list):
        raise ValueError("compose status is not a list")
    normalized = []
    for item in items:
        if not isinstance(item, dict):
            continue
        publishers = item.get("Publishers") or []
        published = [p for p in publishers if p.get("PublishedPort")]
        normalized.append(
            {
                "name": item.get("Name"),
                "service": item.get("Service"),
                "image": item.get("Image"),
                "state": item.get("State"),
                "health": item.get("Health"),
                "status": item.get("Status"),
                "exit_code": item.get("ExitCode"),
                "published_ports": published,
            }
        )
    return normalized


def get_status(
    helper: HelperClient | None, settings: Settings, lab_id: str
) -> dict:
    manifest = require_available(settings, lab_id)
    if helper is None:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Privileged lab helper is not configured",
                "code": "helper_unavailable",
            },
        )
    try:
        response = helper.call("status", lab=lab_id)
    except HelperError as exc:
        raise translate_helper_error(exc) from exc
    raw = response.get("result", {}).get("stdout", "")
    try:
        containers = _containers(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=502,
            detail={"message": "helper returned invalid container status", "code": "invalid_status"},
        ) from exc
    return {
        "lab": lab_id,
        "availability": availability(settings, manifest),
        "containers": containers,
        "expected_services": manifest.get("expected_services", []),
        "device_inventory": detail(settings, manifest)["device_inventory"],
        "networks": manifest.get("networks", {}),
        "healthy": bool(containers)
        and all(
            container.get("state") == "running"
            and container.get("health") in ("healthy", "", None)
            for container in containers
        ),
        "published_port_count": sum(
            len(container.get("published_ports") or []) for container in containers
        ),
    }


def _runtime_files(raw: str) -> list[dict]:
    files = []
    for line in raw.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        name, size, modified = parts
        try:
            files.append({"name": name, "size": int(size), "modified": int(modified)})
        except ValueError:
            continue
    return sorted(files, key=lambda item: item["name"])


def get_evidence(settings: Settings, lab_id: str) -> dict:
    load_lab(settings, lab_id)
    payload = host_evidence(settings, lab_id)
    payload["runtime_files"] = []
    payload["runtime_error"] = None
    payload["runtime_available"] = False
    if settings.helper_socket is None:
        return payload

    helper = HelperClient(settings.helper_socket, timeout=30)
    try:
        response = helper.call("evidence_list", lab=lab_id)
        payload["runtime_files"] = _runtime_files(
            response.get("result", {}).get("stdout", "")
        )
        payload["runtime_available"] = True
    except HelperError as exc:
        payload["runtime_error"] = exc.message
    return payload


def read_evidence(settings: Settings, lab_id: str, filename: str) -> dict:
    load_lab(settings, lab_id)
    try:
        safe_name = validate_filename(filename)
    except Exception as exc:  # RequestError
        raise HTTPException(
            status_code=400,
            detail={"message": str(exc), "code": "invalid_filename"},
        ) from exc

    runtime_error = None
    if settings.helper_socket is not None:
        helper = HelperClient(settings.helper_socket, timeout=30)
        try:
            response = helper.call(
                "evidence_read", lab=lab_id, filename=safe_name
            )
            return {
                "lab": lab_id,
                "name": safe_name,
                "source": "runtime",
                "content": response.get("result", {}).get("stdout", ""),
            }
        except HelperError as exc:
            runtime_error = exc.message

    host_content = read_host_evidence(settings, lab_id, safe_name)
    if host_content is not None:
        return {
            "lab": lab_id,
            "name": safe_name,
            "source": "host",
            "content": host_content,
        }

    raise HTTPException(
        status_code=404,
        detail={
            "message": "evidence file not found",
            "code": "evidence_not_found",
            "runtime_error": runtime_error,
        },
    )
