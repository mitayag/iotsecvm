from __future__ import annotations

import re
from dataclasses import dataclass

PROTOCOL_VERSION = 1
MAX_REQUEST_BYTES = 16_384
MAX_RESPONSE_BYTES = 262_144
MAX_OUTPUT_CHARS = 32_000
MAX_FILENAME_LENGTH = 128

LAB_PATTERN = re.compile(r"^week(0[1-9]|1[0-8])$")
FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class RequestError(Exception):
    def __init__(self, code: str, message: str, *, details: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def as_dict(self) -> dict:
        payload = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


@dataclass(frozen=True)
class ActionSpec:
    script: str
    timeout_seconds: int
    mutating: bool
    requires_lab: bool = True
    requires_filename: bool = False


ACTION_SPECS: dict[str, ActionSpec] = {
    "start": ActionSpec("lab-start.sh", 240, True),
    "stop": ActionSpec("lab-stop.sh", 90, True),
    "reset": ActionSpec("lab-reset.sh", 300, True),
    "status": ActionSpec("lab-inspect.sh", 60, False),
    "evidence_list": ActionSpec("lab-evidence-list.sh", 60, False),
    "evidence_read": ActionSpec(
        "lab-evidence-read.sh", 60, False, requires_filename=True
    ),
}

HEALTH_ACTION = "health"


def validate_lab(lab_id: object) -> str:
    if not isinstance(lab_id, str) or not LAB_PATTERN.match(lab_id):
        raise RequestError("invalid_lab", "lab must be week01 through week18")
    return lab_id


def validate_filename(filename: object) -> str:
    if not isinstance(filename, str):
        raise RequestError("invalid_filename", "filename must be a string")
    if len(filename) > MAX_FILENAME_LENGTH or not FILENAME_PATTERN.match(filename):
        raise RequestError(
            "invalid_filename",
            "filename may only contain letters, digits, dot, dash and underscore",
        )
    if filename in (".", "..") or ".." in filename:
        raise RequestError("invalid_filename", "path traversal is forbidden")
    return filename


def validate_request(payload: object) -> dict:
    if not isinstance(payload, dict):
        raise RequestError("invalid_request", "request must be a JSON object")
    if payload.get("version") != PROTOCOL_VERSION:
        raise RequestError("unsupported_version", "protocol version must be 1")

    action = payload.get("action")
    if not isinstance(action, str):
        raise RequestError("invalid_action", "action is required")
    if action == HEALTH_ACTION:
        return {"version": PROTOCOL_VERSION, "action": HEALTH_ACTION}

    spec = ACTION_SPECS.get(action)
    if spec is None:
        raise RequestError("unknown_action", "action is not allowlisted")

    request = {"version": PROTOCOL_VERSION, "action": action}
    if spec.requires_lab:
        request["lab"] = validate_lab(payload.get("lab"))
    if spec.requires_filename:
        request["filename"] = validate_filename(payload.get("filename"))
    return request


def build_command(root: str, request: dict) -> tuple[list[str], str, int, bool]:
    action = request["action"]
    if action == HEALTH_ACTION:
        raise RequestError("invalid_action", "health has no command")
    spec = ACTION_SPECS[action]
    script = f"{root}/scripts/{spec.script}"
    command = [script, request["lab"]]
    if action == "reset":
        command.append("--yes")
    if action == "evidence_read":
        command.append(request["filename"])
    return command, spec.script, spec.timeout_seconds, spec.mutating
